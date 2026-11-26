"""Remplacement des données personnelles par des pseudonymes.

Deux modes, au sens du RGPD :

* **pseudonymisation** : chaque donnée reçoit une étiquette stable
  (``[PERSONNE_1]``) et une *table de correspondance* permet de revenir aux
  données d'origine. Cette table est une donnée sensible : elle doit être
  conservée à part, sous accès restreint ;
* **anonymisation** : étiquettes génériques (``[PERSONNE]``), aucune table.
  Le texte produit ne permet plus de retrouver les personnes.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field

from .entites import Entite


@dataclass
class Resultat:
    texte: str
    #: Étiquette → formes d'origine rencontrées (vide en mode anonymisation).
    table: dict[str, list[str]] = field(default_factory=dict)
    entites: list[Entite] = field(default_factory=list)

    @property
    def compteurs(self) -> Counter[str]:
        return Counter(e.type for e in self.entites)


def cle_identite(entite: Entite) -> str:
    """Clé qui décide si deux mentions sont « la même donnée »."""
    if entite.cle:
        return entite.cle
    texte = " ".join(entite.texte.split()).casefold()
    if entite.type in {"NIR", "IBAN", "TELEPHONE"}:
        texte = re.sub(r"[\s.-]", "", texte)
    return f"{entite.type}:{texte}"


def remplacer(texte: str, entites: list[Entite], anonymiser: bool = False) -> Resultat:
    """Remplace chaque entité (supposées sans chevauchement) par son étiquette."""
    etiquettes: dict[str, str] = {}
    numeros: Counter[str] = Counter()
    table: dict[str, list[str]] = defaultdict(list)
    morceaux: list[str] = []
    position = 0
    for entite in sorted(entites, key=lambda e: e.debut):
        if anonymiser:
            etiquette = f"[{entite.type}]"
        else:
            cle = cle_identite(entite)
            if cle not in etiquettes:
                numeros[entite.type] += 1
                etiquettes[cle] = f"[{entite.type}_{numeros[entite.type]}]"
            etiquette = etiquettes[cle]
            if entite.texte not in table[etiquette]:
                table[etiquette].append(entite.texte)
        morceaux += [texte[position : entite.debut], etiquette]
        position = entite.fin
    morceaux.append(texte[position:])
    return Resultat("".join(morceaux), {} if anonymiser else dict(table), list(entites))
