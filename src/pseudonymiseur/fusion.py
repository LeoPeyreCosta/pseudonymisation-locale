"""Arbitrage des détections qui se chevauchent."""

from __future__ import annotations

from .entites import Entite

#: Les règles sont prioritaires : elles sont vérifiables et ne se trompent pas
#: de frontière (une adresse « rue Jean Moulin » reste une adresse).
_PRIORITE = {"regle": 0, "llm": 1}


def resoudre_chevauchements(entites: list[Entite]) -> list[Entite]:
    """Garde un ensemble d'entités sans chevauchement, trié par position.

    Ordre de préférence : source (règle avant LLM), puis entité la plus longue."""
    candidats = sorted(
        entites, key=lambda e: (_PRIORITE.get(e.source, 9), -e.longueur, e.debut)
    )
    retenues: list[Entite] = []
    for entite in candidats:
        if not any(entite.chevauche(r) for r in retenues):
            retenues.append(entite)
    return sorted(retenues, key=lambda e: e.debut)
