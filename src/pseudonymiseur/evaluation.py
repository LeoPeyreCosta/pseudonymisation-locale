"""Mesure de la qualité sur un corpus annoté.

Chaque document ``nom.txt`` est accompagné de ``nom.annotations.json`` : la
liste des données personnelles qu'il contient (``{"texte", "type"}``). Toutes
leurs occurrences doivent être masquées.

Indicateurs :

* **rappel** (le plus important en protection des données) : part des
  occurrences effectivement masquées ; ce qui n'est pas masqué *fuit* ;
* **précision** : part des masquages *justes*, c'est-à-dire qui portent sur
  une donnée personnelle sans déborder sur le texte voisin (une civilité
  masquée avec le nom est tolérée). Le reste est du sur-masquage : gênant
  pour la lecture, sans risque pour les personnes.

Le rappel ne tient pas compte du type : une ville masquée comme
``[ORGANISATION]`` ne fuit pas. Les tableaux par type indiquent le type
annoté, pas le type prédit.
"""

from __future__ import annotations

import json
import re
import time
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from .entites import CIVILITES, TYPES, Entite
from .llm import ClientLLM, occurrences
from .pipeline import detecter


@dataclass
class Fuite:
    document: str
    texte: str
    type: str


@dataclass
class RapportEvaluation:
    occurrences: Counter[str] = field(default_factory=Counter)
    masquees: Counter[str] = field(default_factory=Counter)
    masquages: int = 0
    masquages_justes: int = 0
    fuites: list[Fuite] = field(default_factory=list)
    #: Masquages sans aucune donnée personnelle : (document, texte, type).
    faux_positifs: list[tuple[str, str, str]] = field(default_factory=list)
    #: Masquages qui débordent d'une donnée sur le texte voisin.
    debordements: list[tuple[str, str, str]] = field(default_factory=list)
    documents: int = 0
    duree_s: float = 0.0

    @property
    def rappel(self) -> float:
        total = sum(self.occurrences.values())
        return sum(self.masquees.values()) / total if total else 1.0

    @property
    def precision(self) -> float:
        return self.masquages_justes / self.masquages if self.masquages else 1.0

    def en_markdown(self) -> str:
        lignes = [
            "| Type | Occurrences | Masquées | Rappel |",
            "|---|---:|---:|---:|",
        ]
        for type_ in TYPES:
            n = self.occurrences[type_]
            if n:
                m = self.masquees[type_]
                lignes.append(f"| {type_} | {n} | {m} | {m / n:.0%} |")
        total = sum(self.occurrences.values())
        lignes.append(
            f"| **Total** | **{total}** | **{sum(self.masquees.values())}** "
            f"| **{self.rappel:.1%}** |"
        )
        lignes += [
            "",
            f"Précision : {self.precision:.1%} "
            f"({self.masquages_justes} masquages justes sur {self.masquages} ; "
            f"{len(self.faux_positifs)} sans donnée personnelle, "
            f"{len(self.debordements)} qui débordent).",
            f"{self.documents} documents, {self.duree_s:.0f} s au total.",
        ]
        return "\n".join(lignes)


def occurrences_reference(texte: str, annotations: list[dict[str, str]]) -> list[tuple[int, int, str, str]]:
    """Positions de toutes les données annotées. Une occurrence incluse dans
    une occurrence plus longue (« Ferrand » dans « Josiane Ferrand ») n'est
    comptée qu'une fois, via la plus longue."""
    toutes: list[tuple[int, int, str, str]] = []
    for annotation in annotations:
        positions = list(occurrences(texte, annotation["texte"]))
        if not positions:
            raise ValueError(f"Annotation introuvable dans le texte : {annotation['texte']!r}")
        toutes += [(d, f, annotation["type"], annotation["texte"]) for d, f in positions]
    return [
        occ
        for occ in toutes
        if not any(
            autre is not occ and autre[0] <= occ[0] and occ[1] <= autre[1]
            and (autre[1] - autre[0]) > (occ[1] - occ[0])
            for autre in toutes
        )
    ]


def _est_couverte(masque: list[bool], texte: str, debut: int, fin: int) -> bool:
    """Une donnée est masquée si tous ses caractères alphanumériques le sont
    (la ponctuation entre deux morceaux d'adresse ne compte pas)."""
    return all(masque[i] for i in range(debut, fin) if texte[i].isalnum())


def _deborde(texte: str, reference_masque: list[bool], entite: Entite) -> bool:
    """Vrai si le masquage couvre des mots hors de toute donnée annotée
    (« 34000 Montpellier » suivi du « Tél » de la ligne d'après), civilités
    exceptées (« Mme » dans « Mme Ferrand »)."""
    hors = "".join(
        " " if reference_masque[i] else texte[i] for i in range(entite.debut, entite.fin)
    )
    return any(mot.casefold() not in CIVILITES for mot in re.findall(r"\w+", hors))


def evaluer_document(
    nom: str, texte: str, annotations: list[dict[str, str]], entites: list[Entite],
    rapport: RapportEvaluation,
) -> None:
    masque = [False] * len(texte)
    for entite in entites:
        masque[entite.debut : entite.fin] = [True] * entite.longueur
    reference = occurrences_reference(texte, annotations)
    for debut, fin, type_, valeur in reference:
        rapport.occurrences[type_] += 1
        if _est_couverte(masque, texte, debut, fin):
            rapport.masquees[type_] += 1
        else:
            rapport.fuites.append(Fuite(nom, valeur, type_))
    reference_masque = [False] * len(texte)
    for debut, fin, _, _ in reference:
        reference_masque[debut:fin] = [True] * (fin - debut)
    for entite in entites:
        rapport.masquages += 1
        if not any(reference_masque[entite.debut : entite.fin]):
            rapport.faux_positifs.append((nom, entite.texte, entite.type))
        elif _deborde(texte, reference_masque, entite):
            rapport.debordements.append((nom, entite.texte, entite.type))
        else:
            rapport.masquages_justes += 1


def evaluer_corpus(
    dossier: str | Path,
    client: ClientLLM | None = None,
    types: tuple[str, ...] = TYPES,
    regles: bool = True,
) -> RapportEvaluation:
    rapport = RapportEvaluation()
    depart = time.perf_counter()
    for chemin in sorted(Path(dossier).glob("*.txt")):
        annotations = json.loads(
            chemin.with_suffix(".annotations.json").read_text(encoding="utf-8")
        )
        annotations = [a for a in annotations if a["type"] in types]
        texte = chemin.read_text(encoding="utf-8")
        entites, _ = detecter(texte, client, types, regles)
        evaluer_document(chemin.name, texte, annotations, entites, rapport)
        rapport.documents += 1
    rapport.duree_s = time.perf_counter() - depart
    return rapport
