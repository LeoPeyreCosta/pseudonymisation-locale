"""Détection par règles des données personnelles à format connu.

Ces détecteurs sont déterministes, rapides et vérifiables : on les préfère au
modèle de langue dès qu'une donnée a une structure (numéro de sécurité
sociale, IBAN, téléphone, date, adresse…). Les numéros dotés d'une clé de
contrôle (NIR, IBAN) sont validés, ce qui écarte la plupart des faux positifs.
"""

from __future__ import annotations

import re
from collections.abc import Iterator

from .entites import Entite

# --------------------------------------------------------------------- NIR
# Numéro de sécurité sociale : sexe, année, mois, département (2A/2B pour la
# Corse), commune, rang, puis une clé de deux chiffres (souvent espacés).
_NIR = re.compile(
    r"(?<!\w)"
    r"(?P<corps>[1-478][ .]?\d{2}[ .]?(?:0[1-9]|1[0-2]|[2-9]\d)[ .]?(?:\d{2}|2[AaBb])"
    r"[ .]?\d{3}[ .]?\d{3})"
    r"(?:[ .]?(?P<cle>\d{2}))?"
    r"(?!\w)"
)
_CONTEXTE_NIR = re.compile(
    r"s[ée]curit[ée]\s+sociale|\bNIR\b|\bINSEE\b|\bn°\s*SS\b|\bs[ée]cu\b", re.IGNORECASE
)


def cle_nir_valide(corps: str, cle: str) -> bool:
    """Vérifie la clé d'un NIR : ``97 - (corps mod 97)`` (2A → 19, 2B → 18)."""
    corps = re.sub(r"[ .]", "", corps).upper()
    departement = corps[5:7]
    if departement == "2A":
        corps = corps[:5] + "19" + corps[7:]
    elif departement == "2B":
        corps = corps[:5] + "18" + corps[7:]
    if len(corps) != 13 or not corps.isdigit() or not cle.isdigit():
        return False
    return 97 - int(corps) % 97 == int(cle)


def _detecter_nir(texte: str) -> Iterator[Entite]:
    for m in _NIR.finditer(texte):
        cle = m.group("cle")
        contexte = _CONTEXTE_NIR.search(texte, max(0, m.start() - 80), m.start())
        # Clé valide = quasi-certitude. Sans clé valide, on n'accepte le motif
        # que si le contexte annonce un numéro de sécurité sociale.
        if (cle and cle_nir_valide(m.group("corps"), cle)) or contexte:
            yield Entite(m.start(), m.end(), "NIR", m.group())


# -------------------------------------------------------------------- IBAN
_IBAN = re.compile(
    r"(?<!\w)[A-Z]{2}\d{2}(?: ?[A-Z0-9]{4}){2,7}(?: ?[A-Z0-9]{1,3})?(?!\w)"
)


def iban_valide(iban: str) -> bool:
    """Contrôle ISO 13616 : le nombre obtenu en déplaçant les 4 premiers
    caractères à la fin (lettres → 10..35) doit valoir 1 modulo 97."""
    iban = iban.replace(" ", "").upper()
    if not 15 <= len(iban) <= 34 or not iban.isalnum():
        return False
    chiffres = "".join(str(int(c, 36)) for c in iban[4:] + iban[:4])
    return int(chiffres) % 97 == 1


def _detecter_iban(texte: str) -> Iterator[Entite]:
    for m in _IBAN.finditer(texte):
        if iban_valide(m.group()):
            yield Entite(m.start(), m.end(), "IBAN", m.group())


# ---------------------------------------------------- courriel, téléphone
_EMAIL = re.compile(r"(?<![\w.+-])[\w.+-]+@[\w-]+(?:\.[\w-]+)+(?![\w-])")
_TELEPHONE = re.compile(
    r"(?<![\w+])(?:\+33[\s.]?|0033[\s.]?|0)[1-9](?:[\s.-]?\d{2}){4}(?!\w)"
)

# ------------------------------------------------------------------- dates
_MOIS = (
    "janvier|février|fevrier|mars|avril|mai|juin|juillet|août|aout|"
    "septembre|octobre|novembre|décembre|decembre"
)
_DATE_CHIFFRES = re.compile(
    r"(?<![\w/.-])(?:0?[1-9]|[12]\d|3[01])(?P<sep>[/.-])(?:0?[1-9]|1[0-2])(?P=sep)"
    r"(?:(?:19|20)\d{2}|\d{2})(?![\w/.-])"
)
_DATE_LETTRES = re.compile(
    rf"(?<!\w)(?:1er|0?[1-9]|[12]\d|3[01])\s+(?:{_MOIS})\s+(?:19|20)\d{{2}}(?!\w)",
    re.IGNORECASE,
)

# ---------------------------------------------------------------- adresses
# Une adresse peut tenir sur deux lignes (voie, puis code postal et ville),
# mais un nom de voie ou de ville ne déborde jamais sur la ligne suivante :
# les espaces internes (_ESP) excluent le retour à la ligne.
_ESP = r"[^\S\r\n]"
_VOIES = (
    r"(?i:rue|avenue|av\.|boulevard|bd|chemin|impasse|all[ée]e|place|route|quai|cours|"
    r"square|r[ée]sidence|lotissement|lieu-dit|faubourg|passage|sentier|chauss[ée]e|"
    r"esplanade|promenade|voie|cit[ée])"
)
_LIAISON = r"(?:de|du|des|la|le|les|l['’]|d['’]|et|sur|en|aux|au)"
_MOT_PROPRE = r"[A-ZÀ-ÖØ-Þ][\w'’-]*"
_NOM_VOIE = (
    rf"(?:{_LIAISON}{_ESP}*)*{_MOT_PROPRE}"
    rf"(?:{_ESP}+(?:{_LIAISON}{_ESP}*)*{_MOT_PROPRE})*"
)
_ADRESSE_VOIE = re.compile(
    rf"(?<!\w)\d{{1,4}}(?:{_ESP}?(?i:bis|ter|quater))?,?{_ESP}+{_VOIES}{_ESP}+{_NOM_VOIE}"
)
_SEP_VILLE = rf"(?:{_ESP}|-)"
_VILLE = (
    rf"[A-ZÀ-ÖØ-Þ][\w'’]*(?:{_SEP_VILLE}(?:(?:sur|sous|en|lès|les|le|la|de|du|des|aux|au)"
    rf"{_SEP_VILLE}|d['’]|l['’])*[A-ZÀ-ÖØ-Þ][\w'’]*)*"
)
# Code postal : cinq chiffres isolés, pas la fin d'un matricule (« RH-58213 »).
_CODE_POSTAL_VILLE = re.compile(rf"(?<![\w-])\d{{5}}{_ESP}+{_VILLE}")
# Compléments d'adresse : résidence, immeuble, bâtiment, escalier, appartement.
_COMPLEMENT = re.compile(
    rf"(?<!\w)(?:"
    rf"(?i:b[âa]timent|b[âa]t\.|escalier|esc\.|appartement|appt\.?){_ESP}*(?:n°{_ESP}*)?"
    rf"[A-Z0-9]{{1,4}}(?!\w)"
    rf"|(?i:r[ée]sidence|immeuble|hameau){_ESP}+{_NOM_VOIE}"
    rf")"
)
_ENTRE_ADRESSES = re.compile(r"[\s,]{0,3}")

# ------------------------------------------------------------ identifiants
_IDENTIFIANT = re.compile(
    r"(?i:\b(?:IPP|NIP|RPPS|ADELI|matricule"
    r"|(?:n°|num[ée]ro)\s*(?:de\s+|d['’])?(?:dossier|patient|allocataire|adh[ée]rent|client"
    r"|contrat|s[ée]jour|agent|candidat)"
    r"|(?:dossier|allocataire|s[ée]jour)\s+n°))"
    # Organisme éventuel entre le libellé et la valeur : « N° allocataire CAF : ».
    r"(?:\s+(?:CAF|MSA|CPAM|URSSAF))?"
    r"\s*[:.]?\s*(?P<valeur>[A-Z0-9][A-Z0-9/-]{3,})"
)


def _simple(motif: re.Pattern[str], type_: str):
    def detecter(texte: str) -> Iterator[Entite]:
        for m in motif.finditer(texte):
            yield Entite(m.start(), m.end(), type_, m.group())

    return detecter


def _detecter_identifiants(texte: str) -> Iterator[Entite]:
    for m in _IDENTIFIANT.finditer(texte):
        yield Entite(m.start("valeur"), m.end("valeur"), "IDENTIFIANT", m.group("valeur"))


def _detecter_adresses(texte: str) -> list[Entite]:
    """Repère voies, compléments et « code postal + ville », puis fusionne les
    morceaux contigus (« bâtiment C, 12 rue des Lilas, 34170 Castelnau-le-Lez »)
    en une seule adresse."""
    morceaux = sorted(
        m.span()
        for motif in (_ADRESSE_VOIE, _COMPLEMENT, _CODE_POSTAL_VILLE)
        for m in motif.finditer(texte)
    )
    fusionnes: list[list[int]] = []
    for debut, fin in morceaux:
        if fusionnes and (
            debut <= fusionnes[-1][1]
            or _ENTRE_ADRESSES.fullmatch(texte[fusionnes[-1][1] : debut])
        ):
            fusionnes[-1][1] = max(fusionnes[-1][1], fin)
        else:
            fusionnes.append([debut, fin])
    return [Entite(d, f, "ADRESSE", texte[d:f]) for d, f in fusionnes]


_DETECTEURS = (
    _detecter_nir,
    _detecter_iban,
    _simple(_EMAIL, "EMAIL"),
    _simple(_TELEPHONE, "TELEPHONE"),
    _simple(_DATE_CHIFFRES, "DATE"),
    _simple(_DATE_LETTRES, "DATE"),
    _detecter_identifiants,
    _detecter_adresses,
)


def detecter_par_regles(texte: str) -> list[Entite]:
    """Applique tous les détecteurs par règles. Les chevauchements éventuels
    sont arbitrés plus tard (voir :mod:`pseudonymiseur.fusion`)."""
    entites: list[Entite] = []
    for detecteur in _DETECTEURS:
        entites.extend(detecteur(texte))
    return entites
