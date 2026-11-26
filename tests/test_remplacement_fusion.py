from pseudonymiseur.entites import Entite
from pseudonymiseur.fusion import resoudre_chevauchements
from pseudonymiseur.remplacement import remplacer


def test_regle_prioritaire_sur_llm():
    regle = Entite(0, 25, "ADRESSE", "12 rue Jean Moulin, Paris", "regle")
    llm = Entite(7, 18, "PERSONNE", "Jean Moulin", "llm")
    assert resoudre_chevauchements([llm, regle]) == [regle]


def test_la_plus_longue_gagne_a_source_egale():
    courte = Entite(4, 11, "PERSONNE", "Ferrand", "llm")
    longue = Entite(0, 11, "PERSONNE", "Mme Ferrand", "llm")
    assert resoudre_chevauchements([courte, longue]) == [longue]


def test_pseudonymes_stables_et_table():
    texte = "Tél 06 39 98 12 34 ou 0639981234, courriel a@b.example."
    entites = [
        Entite(4, 18, "TELEPHONE", "06 39 98 12 34"),
        Entite(22, 32, "TELEPHONE", "0639981234"),
        Entite(43, 54, "EMAIL", "a@b.example"),
    ]
    resultat = remplacer(texte, entites)
    assert resultat.texte == "Tél [TELEPHONE_1] ou [TELEPHONE_1], courriel [EMAIL_1]."
    assert resultat.table["[TELEPHONE_1]"] == ["06 39 98 12 34", "0639981234"]


def _entite(texte, mot, type_, debut_recherche=0, **autres):
    debut = texte.index(mot, debut_recherche)
    return Entite(debut, debut + len(mot), type_, mot, **autres)


def test_mode_anonymisation_sans_table():
    texte = "Paul salue Lise."
    entites = [_entite(texte, "Paul", "PERSONNE"), _entite(texte, "Lise", "PERSONNE")]
    resultat = remplacer(texte, entites, anonymiser=True)
    assert resultat.texte == "[PERSONNE] salue [PERSONNE]."
    assert resultat.table == {}


def test_cle_relie_des_formes_differentes():
    texte = "Josiane Ferrand puis Ferrand."
    cle = "PERSONNE:josiane ferrand"
    entites = [
        _entite(texte, "Josiane Ferrand", "PERSONNE", source="llm", cle=cle),
        _entite(texte, "Ferrand", "PERSONNE", debut_recherche=16, source="llm", cle=cle),
    ]
    resultat = remplacer(texte, entites)
    assert resultat.texte == "[PERSONNE_1] puis [PERSONNE_1]."
