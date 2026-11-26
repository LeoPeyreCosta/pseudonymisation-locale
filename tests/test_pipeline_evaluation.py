import json

import pytest

from pseudonymiseur.__main__ import main
from pseudonymiseur.entites import Entite
from pseudonymiseur.evaluation import RapportEvaluation, evaluer_document, occurrences_reference
from pseudonymiseur.pipeline import traiter

TEXTE = (
    "Mme Josiane Ferrand, née le 03/02/1951, demeurant 12 rue des Tisserands, "
    "34170 Castelnau-le-Lez. NIR : 2 51 02 34 172 045 40. Mme Ferrand est joignable "
    "au 06 39 98 12 34."
)
MENTIONS = [{"texte": "Josiane Ferrand", "type": "PERSONNE"}]


def test_bout_en_bout_aucune_fuite(client_factice):
    traitement = traiter(TEXTE, client_factice(MENTIONS))
    sortie = traitement.resultat.texte
    for donnee in ("Josiane", "Ferrand", "03/02/1951", "Tisserands", "Castelnau", "172 045", "98 12"):
        assert donnee not in sortie, donnee
    assert sortie.startswith("Mme [PERSONNE_1], née le [DATE_1]")
    assert "Mme [PERSONNE_1] est joignable" in sortie


def test_sans_llm_les_regles_suffisent_pour_les_numeros():
    sortie = traiter(TEXTE).resultat.texte
    assert "06 39 98 12 34" not in sortie and "2 51 02" not in sortie
    assert "Josiane Ferrand" in sortie  # les noms exigent le modèle


def test_reference_sans_double_compte():
    texte = "Josiane Ferrand et Mme Ferrand."
    reference = occurrences_reference(
        texte, [{"texte": "Josiane Ferrand", "type": "PERSONNE"}, {"texte": "Ferrand", "type": "PERSONNE"}]
    )
    assert [r[3] for r in reference] == ["Josiane Ferrand", "Ferrand"]


def test_annotation_introuvable_signalee():
    with pytest.raises(ValueError):
        occurrences_reference("Texte.", [{"texte": "Absent", "type": "PERSONNE"}])


def test_rappel_et_fuites(client_factice):
    rapport = RapportEvaluation()
    annotations = [
        {"texte": "Josiane Ferrand", "type": "PERSONNE"},
        {"texte": "Ferrand", "type": "PERSONNE"},
        {"texte": "03/02/1951", "type": "DATE"},
    ]
    entites = traiter(TEXTE).resultat.entites  # sans LLM : les noms fuient
    evaluer_document("test.txt", TEXTE, annotations, entites, rapport)
    assert rapport.masquees["DATE"] == 1
    assert rapport.masquees["PERSONNE"] == 0
    assert {f.texte for f in rapport.fuites} == {"Josiane Ferrand", "Ferrand"}


def test_precision_compte_les_debordements():
    texte = "Mme Josiane Ferrand\n34000 Montpellier\nTél. : 04 65 71 90 33"
    annotations = [
        {"texte": "Josiane Ferrand", "type": "PERSONNE"},
        {"texte": "34000 Montpellier", "type": "ADRESSE"},
    ]
    entites = [
        Entite(0, 19, "PERSONNE", "Mme Josiane Ferrand", "llm"),  # civilité tolérée
        Entite(20, 41, "ADRESSE", "34000 Montpellier\nTél"),  # déborde
        Entite(45, 59, "TELEPHONE", "04 65 71 90 33"),  # non annoté ici
    ]
    rapport = RapportEvaluation()
    evaluer_document("test.txt", texte, annotations, entites, rapport)
    assert rapport.masquages_justes == 1
    assert [d[1] for d in rapport.debordements] == ["34000 Montpellier\nTél"]
    assert [f[1] for f in rapport.faux_positifs] == ["04 65 71 90 33"]
    assert rapport.rappel == 1.0


def test_ligne_de_commande_sans_llm(tmp_path):
    document = tmp_path / "courrier.txt"
    document.write_text(TEXTE, encoding="utf-8")
    main(["traiter", str(document), "--sans-llm"])
    sortie = (tmp_path / "courrier.pseudonymise.txt").read_text(encoding="utf-8")
    table = json.loads((tmp_path / "courrier.table.json").read_text(encoding="utf-8"))
    assert "[NIR_1]" in sortie
    assert table["[NIR_1]"] == ["2 51 02 34 172 045 40"]
