"""Enchaînement complet : détection (règles + LLM), arbitrage, remplacement."""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from .entites import TYPES, Entite
from .fusion import resoudre_chevauchements
from .llm import ClientLLM, detecter_par_llm
from .regles import detecter_par_regles
from .remplacement import Resultat, remplacer


@dataclass
class Traitement:
    resultat: Resultat
    #: Mentions proposées par le LLM mais introuvables dans le texte.
    rejetees: list[str] = field(default_factory=list)
    duree_s: float = 0.0


def detecter(
    texte: str,
    client: ClientLLM | None = None,
    types: tuple[str, ...] = TYPES,
    regles: bool = True,
) -> tuple[list[Entite], list[str]]:
    """Détecte les données personnelles. Sans client LLM, seules les règles
    s'appliquent (noms de personnes non détectés). ``regles=False`` laisse le
    modèle seul : utile pour mesurer ce que les règles apportent."""
    entites = detecter_par_regles(texte) if regles else []
    rejetees: list[str] = []
    if client is not None:
        resultat_llm = detecter_par_llm(texte, client)
        entites += resultat_llm.entites
        rejetees = resultat_llm.rejetees
    entites = [e for e in entites if e.type in types]
    return resoudre_chevauchements(entites), rejetees


def traiter(
    texte: str,
    client: ClientLLM | None = None,
    anonymiser: bool = False,
    types: tuple[str, ...] = TYPES,
) -> Traitement:
    """Pseudonymise (ou anonymise) un texte."""
    depart = time.perf_counter()
    entites, rejetees = detecter(texte, client, types)
    resultat = remplacer(texte, entites, anonymiser=anonymiser)
    return Traitement(resultat, rejetees, time.perf_counter() - depart)
