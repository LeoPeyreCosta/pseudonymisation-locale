"""Le contrat avec Ollama : ce qui est envoyé et ce qui est relu (sans réseau)."""

import json

import requests

from pseudonymiseur import llm
from pseudonymiseur.llm import SCHEMA, ClientOllama


class Reponse:
    def __init__(self, contenu):
        self.contenu = contenu

    def raise_for_status(self):
        pass

    def json(self):
        return {"message": {"content": self.contenu}}


def test_requete_envoyee_et_reponse_lue(monkeypatch):
    envois = []

    def post(url, json, timeout):
        envois.append((url, json))
        return Reponse('{"entites": [{"texte": "Lucie Bernard", "type": "PERSONNE"}]}')

    monkeypatch.setattr(llm.requests, "post", post)
    mentions = ClientOllama(modele="mistral", url="http://127.0.0.1:11434").extraire("Mme Lucie Bernard.")
    assert mentions == [{"texte": "Lucie Bernard", "type": "PERSONNE"}]
    url, corps = envois[0]
    assert url == "http://127.0.0.1:11434/api/chat"
    assert corps["format"] == SCHEMA and corps["stream"] is False
    assert corps["options"] == {"temperature": 0}
    assert corps["messages"][1] == {"role": "user", "content": "Mme Lucie Bernard."}
    json.dumps(corps)  # la requête est bien sérialisable


def test_serveur_injoignable(monkeypatch):
    def get(*args, **kwargs):
        raise requests.ConnectionError("refusé")

    monkeypatch.setattr(llm.requests, "get", get)
    assert ClientOllama().disponible() is False
