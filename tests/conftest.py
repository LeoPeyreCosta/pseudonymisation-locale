"""Outils communs aux tests : un faux client LLM, sans réseau ni GPU."""

from __future__ import annotations

import pytest


class ClientFactice:
    """Renvoie des mentions prédéfinies, comme le ferait le modèle.

    Une mention n'est renvoyée que si elle figure dans le bloc demandé, sauf
    si ``toujours=True`` (pour simuler une hallucination)."""

    def __init__(self, mentions: list[dict], toujours: bool = False):
        self.mentions = mentions
        self.toujours = toujours
        self.appels = 0

    def extraire(self, texte: str) -> list[dict[str, str]]:
        self.appels += 1
        return [
            {"texte": m["texte"], "type": m["type"]}
            for m in self.mentions
            if self.toujours or m["texte"] in texte
        ]


@pytest.fixture
def client_factice():
    return ClientFactice
