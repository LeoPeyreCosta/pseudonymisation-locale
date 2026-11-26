from pseudonymiseur.regles import cle_nir_valide, detecter_par_regles, iban_valide


def types_et_textes(texte):
    return {(e.type, e.texte) for e in detecter_par_regles(texte)}


# ------------------------------------------------------------------ NIR
def test_nir_avec_cle_valide_espace_ou_non():
    assert ("NIR", "2 51 02 34 172 045 40") in types_et_textes("NIR : 2 51 02 34 172 045 40.")
    assert ("NIR", "251023417204540") in types_et_textes("Numéro 251023417204540 noté.")


def test_cle_nir_corse():
    assert cle_nir_valide("1 92 05 2A 004 012", "18")
    assert not cle_nir_valide("1 92 05 2A 004 012", "19")


def test_nir_cle_invalide_sans_contexte_ignore():
    # Motif plausible mais clé fausse et aucun indice : probablement un autre numéro.
    assert not any(e.type == "NIR" for e in detecter_par_regles("Réf. 2 51 02 34 172 045 41"))


def test_nir_sans_cle_accepte_si_contexte():
    texte = "N° de sécurité sociale : 1 78 11 30 189 112"
    assert any(e.type == "NIR" for e in detecter_par_regles(texte))


# ----------------------------------------------------------------- IBAN
def test_iban_valide_detecte():
    iban = "FR93 9999 9000 1200 0457 1836 042"
    assert iban_valide(iban)
    assert ("IBAN", iban) in types_et_textes(f"Virement sur {iban} merci.")


def test_iban_clef_fausse_ignore():
    assert not iban_valide("FR94 9999 9000 1200 0457 1836 042")
    assert not any(e.type == "IBAN" for e in detecter_par_regles("FR94 9999 9000 1200 0457 1836 042"))


# ------------------------------------------------- courriel, téléphone
def test_courriel():
    assert ("EMAIL", "h.varenne@ch-troisfontaines.example") in types_et_textes(
        "Écrire à h.varenne@ch-troisfontaines.example."
    )


def test_telephones_formats_courants():
    for numero in ("06 39 98 12 34", "06.39.98.12.34", "0639981234", "+33 6 39 98 12 34"):
        assert ("TELEPHONE", numero) in types_et_textes(f"Tél : {numero}"), numero


# ---------------------------------------------------------------- dates
def test_dates_chiffres_et_lettres():
    t = types_et_textes("Née le 03/02/1951, vue le 9 octobre 2026 et le 1er mars 2025.")
    assert {("DATE", "03/02/1951"), ("DATE", "9 octobre 2026"), ("DATE", "1er mars 2025")} <= t


def test_pas_de_date_impossible():
    assert not any(e.type == "DATE" for e in detecter_par_regles("Lot 12/13/2024"))


# ------------------------------------------------------------- adresses
def test_adresse_voie_et_ville_fusionnees():
    texte = "Domicile : 12 rue des Tisserands, 34170 Castelnau-le-Lez. Merci."
    adresses = [e.texte for e in detecter_par_regles(texte) if e.type == "ADRESSE"]
    assert adresses == ["12 rue des Tisserands, 34170 Castelnau-le-Lez"]


def test_adresse_avec_complement_et_nom_compose():
    texte = "Au 3 bis avenue du Général de Gaulle à Lunel."
    adresses = [e.texte for e in detecter_par_regles(texte) if e.type == "ADRESSE"]
    assert adresses == ["3 bis avenue du Général de Gaulle"]


# --------------------------------------------------------- identifiants
def test_identifiant_seule_la_valeur_est_masquee():
    entites = [e for e in detecter_par_regles("IPP : 20481739 ; RPPS 10101234567") if e.type == "IDENTIFIANT"]
    assert [e.texte for e in entites] == ["20481739", "10101234567"]
