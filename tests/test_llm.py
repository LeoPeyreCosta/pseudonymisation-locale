from pseudonymiseur.llm import analyser_reponse, decouper, detecter_par_llm, relier_personnes


# ------------------------------------------------- lecture de la réponse
def test_reponse_json_valide():
    contenu = '{"entites": [{"texte": "Lucie Bernard", "type": "PERSONNE"}]}'
    assert analyser_reponse(contenu) == [{"texte": "Lucie Bernard", "type": "PERSONNE"}]


def test_reponse_avec_texte_parasite():
    contenu = 'Voici : {"entites": [{"texte": "Nîmes", "type": "LIEU"}]} Fin.'
    assert analyser_reponse(contenu) == [{"texte": "Nîmes", "type": "LIEU"}]


def test_reponse_illisible_ou_mal_typee():
    assert analyser_reponse("pas de JSON") == []
    contenu = '{"entites": [{"texte": "X", "type": "PERSONNE"}, {"texte": "Paris", "type": "PLANETE"}, 3]}'
    assert analyser_reponse(contenu) == []


# ---------------------------------------------------------- découpage
def test_decoupage_respecte_les_paragraphes():
    texte = "\n\n".join(f"Paragraphe {i} " + "x" * 400 for i in range(10))
    blocs = decouper(texte, taille=1000)
    assert len(blocs) > 1
    assert "\n\n".join(blocs) == texte


# ------------------------------------------------ garde-fous et liaison
def test_hallucination_ecartee(client_factice):
    client = client_factice([{"texte": "Paul Inventé", "type": "PERSONNE"}], toujours=True)
    resultat = detecter_par_llm("Aucun nom ici.", client)
    assert resultat.entites == []
    assert resultat.rejetees == ["Paul Inventé"]


def test_nom_trouve_au_debut_masque_partout(client_factice):
    debut = "Patiente : Josiane Ferrand."
    texte = debut + "\n\n" + "Suivi. " * 300 + "\n\nJosiane Ferrand reviendra."
    client = client_factice([{"texte": "Josiane Ferrand", "type": "PERSONNE"}])
    resultat = detecter_par_llm(texte, client, taille_bloc=500)
    assert len([e for e in resultat.entites if e.texte == "Josiane Ferrand"]) == 2


def test_mentions_d_une_meme_personne_reliees(client_factice):
    texte = "Mme Josiane Ferrand est venue. Mme Ferrand va bien. Josiane rentre. Thierry Ferrand l'accompagne."
    client = client_factice([
        {"texte": "Josiane Ferrand", "type": "PERSONNE"},
        {"texte": "Thierry Ferrand", "type": "PERSONNE"},
    ])
    entites = detecter_par_llm(texte, client).entites
    cles = {e.texte: e.cle for e in entites}
    assert cles["Josiane"] == cles["Josiane Ferrand"]
    assert cles["Thierry Ferrand"] != cles["Josiane Ferrand"]
    assert "Ferrand" in cles  # le nom employé seul est masqué aussi


def test_nom_commun_homonyme_non_masque(client_factice):
    texte = "M. Paul Petit est arrivé. Un petit malaise. M. Petit se repose."
    client = client_factice([{"texte": "Paul Petit", "type": "PERSONNE"}])
    textes = [e.texte for e in detecter_par_llm(texte, client).entites]
    assert "petit" not in textes
    assert textes.count("Petit") == 1


def test_relier_personnes():
    canon = relier_personnes(["Mme Ferrand", "Josiane Ferrand", "Thierry Ferrand"])
    assert canon["Mme Ferrand"] == "Josiane Ferrand"
    assert canon["Thierry Ferrand"] == "Thierry Ferrand"
