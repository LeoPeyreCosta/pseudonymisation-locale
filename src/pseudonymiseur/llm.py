"""Détection des personnes, lieux et organisations par un LLM local (Ollama).

Le modèle ne fait que *proposer* des mentions ; le code garde la main :

* la sortie est contrainte par un schéma JSON (pas de réponse mal formée) ;
* une mention n'est retenue que si elle figure réellement dans le texte
  (filtre anti-hallucination) ;
* les mentions d'une même personne (« Josiane Ferrand », « Mme Ferrand »,
  « Josiane ») sont reliées pour recevoir le même pseudonyme.
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Protocol

import requests

from .entites import CIVILITES, TYPES_LLM, Entite

journal = logging.getLogger(__name__)

SCHEMA: dict = {
    "type": "object",
    "properties": {
        "entites": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "texte": {"type": "string"},
                    "type": {"type": "string", "enum": list(TYPES_LLM)},
                },
                "required": ["texte", "type"],
            },
        }
    },
    "required": ["entites"],
}

CONSIGNE = """Tu repères les données personnelles dans un document administratif ou médical français.
Liste chaque mention de :
- PERSONNE : nom et/ou prénom d'une personne (patient, médecin, agent, proche…), avec ou sans civilité ;
- LIEU : ville, commune, quartier ou lieu-dit ;
- ORGANISATION : établissement, entreprise, administration ou association désignée par son nom propre.
Règles :
- recopie chaque mention EXACTEMENT comme dans le texte (mêmes majuscules, mêmes accents) ;
- n'invente rien, ne reformule rien ;
- ignore les fonctions seules (« le médecin traitant », « la patiente ») et les noms communs ;
- si rien n'est trouvé, renvoie une liste vide.
Exemple — texte : « Mme Lucie Bernard est suivie à la Clinique des Pins, à Nîmes. »
Réponse : {"entites": [{"texte": "Lucie Bernard", "type": "PERSONNE"},
{"texte": "Clinique des Pins", "type": "ORGANISATION"}, {"texte": "Nîmes", "type": "LIEU"}]}"""


class ClientLLM(Protocol):
    """Tout objet capable de proposer des mentions à partir d'un texte."""

    def extraire(self, texte: str) -> list[dict[str, str]]: ...


@dataclass
class ClientOllama:
    """Client minimal pour un serveur Ollama local."""

    modele: str = "mistral"
    url: str = "http://localhost:11434"
    delai: float = 300.0

    def disponible(self) -> bool:
        try:
            requests.get(f"{self.url}/api/tags", timeout=3).raise_for_status()
            return True
        except requests.RequestException:
            return False

    def extraire(self, texte: str) -> list[dict[str, str]]:
        reponse = requests.post(
            f"{self.url}/api/chat",
            json={
                "model": self.modele,
                "messages": [
                    {"role": "system", "content": CONSIGNE},
                    {"role": "user", "content": texte},
                ],
                "format": SCHEMA,
                "stream": False,
                "options": {"temperature": 0},
            },
            timeout=self.delai,
        )
        reponse.raise_for_status()
        return analyser_reponse(reponse.json()["message"]["content"])


def analyser_reponse(contenu: str) -> list[dict[str, str]]:
    """Lit la réponse du modèle et ne garde que des mentions bien formées.

    Tolère un texte parasite autour du JSON ; une réponse illisible donne une
    liste vide (l'erreur est journalisée, le traitement continue)."""
    try:
        donnees = json.loads(contenu)
    except json.JSONDecodeError:
        bloc = re.search(r"\{.*\}", contenu, re.DOTALL)
        try:
            donnees = json.loads(bloc.group()) if bloc else None
        except json.JSONDecodeError:
            donnees = None
        if donnees is None:
            journal.warning("Réponse du modèle illisible, bloc ignoré : %.80s", contenu)
            return []
    elements = donnees.get("entites", []) if isinstance(donnees, dict) else []
    propres = []
    for element in elements:
        if not isinstance(element, dict):
            continue
        texte, type_ = element.get("texte"), element.get("type")
        if isinstance(texte, str) and type_ in TYPES_LLM and len(texte.strip()) >= 2:
            propres.append({"texte": texte.strip(), "type": type_})
    return propres


def decouper(texte: str, taille: int = 1500) -> list[str]:
    """Découpe le texte en blocs d'environ ``taille`` caractères, aux limites
    de paragraphes, pour rester dans la fenêtre de contexte du modèle."""
    blocs: list[str] = []
    courant = ""
    for paragraphe in re.split(r"\n\s*\n", texte):
        if courant and len(courant) + len(paragraphe) > taille:
            blocs.append(courant)
            courant = paragraphe
        else:
            courant = f"{courant}\n\n{paragraphe}" if courant else paragraphe
    if courant.strip():
        blocs.append(courant)
    return blocs


def occurrences(texte: str, mention: str) -> Iterator[tuple[int, int]]:
    """Positions exactes d'une mention (mots entiers, espaces souples)."""
    motif = r"\s+".join(re.escape(mot) for mot in mention.split())
    for m in re.finditer(rf"(?<!\w){motif}(?!\w)", texte):
        yield m.span()


def jetons_nom(mention: str) -> list[str]:
    """Noms et prénoms d'une mention de personne, sans les civilités."""
    return [
        jeton
        for jeton in re.findall(r"[A-ZÀ-ÖØ-Þ][\w'’-]*", mention)
        if len(jeton) >= 3 and jeton.casefold().rstrip(".") not in CIVILITES
    ]


def _occurrences_nom(texte: str, nom: str) -> Iterator[tuple[int, int]]:
    """Occurrences d'un nom isolé, quelle que soit la casse (« Ferrand »,
    « FERRAND »), mais seulement avec une majuscule initiale : on évite ainsi
    de masquer un nom commun homonyme (« Petit » / « petit »)."""
    for m in re.finditer(rf"(?<!\w){re.escape(nom)}(?!\w)", texte, re.IGNORECASE):
        if m.group()[0].isupper():
            yield m.span()


def relier_personnes(mentions: list[str]) -> dict[str, str]:
    """Associe chaque mention à l'identité la plus complète qui la contient :
    « Mme Ferrand » → « Josiane Ferrand ». En cas d'homonymie (deux Ferrand),
    la première identité rencontrée l'emporte."""
    identites: list[tuple[str, set[str]]] = []
    canon: dict[str, str] = {}
    for mention in sorted(mentions, key=lambda m: -len(jetons_nom(m))):
        jetons = {j.casefold() for j in jetons_nom(mention)}
        for identite, ensemble in identites:
            if jetons and jetons <= ensemble:
                canon[mention] = identite
                break
        else:
            identites.append((mention, jetons))
            canon[mention] = mention
    return canon


def plausible(mention: str, type_: str) -> bool:
    """Écarte les propositions qui ne peuvent pas désigner une personne, un
    lieu ou une organisation : une civilité seule (« Dr »), ou, pour un lieu ou
    une organisation, des mots sans aucune majuscule (« si douleur »). Un
    nombre d'au moins quatre chiffres est gardé : s'il a échappé aux règles,
    mieux vaut le masquer."""
    if re.search(r"\d{4}", mention):
        return True
    mots = re.findall(r"[^\W\d_]+", mention)
    if type_ == "PERSONNE":
        # Pas d'exigence de majuscule : un message d'usager peut écrire « marie dupont ».
        return any(mot.casefold() not in CIVILITES for mot in mots)
    return any(caractere.isupper() for caractere in mention)


@dataclass
class ResultatLLM:
    entites: list[Entite] = field(default_factory=list)
    #: Mentions proposées par le modèle puis écartées : absentes du texte
    #: (hallucinations) ou invraisemblables (voir :func:`plausible`).
    rejetees: list[str] = field(default_factory=list)


def detecter_par_llm(texte: str, client: ClientLLM, taille_bloc: int = 1500) -> ResultatLLM:
    """Interroge le modèle bloc par bloc, puis localise ses propositions dans
    tout le document : un nom repéré au début est aussi masqué à la fin."""
    mentions: dict[str, str] = {}
    for bloc in decouper(texte, taille_bloc):
        for element in client.extraire(bloc):
            mentions.setdefault(element["texte"], element["type"])

    resultat = ResultatLLM()
    presentes: dict[str, tuple[str, list[tuple[int, int]]]] = {}
    for mention, type_ in mentions.items():
        positions = list(occurrences(texte, mention))
        if positions and plausible(mention, type_):
            presentes[mention] = (type_, positions)
        else:
            resultat.rejetees.append(mention)

    canon = relier_personnes([m for m, (t, _) in presentes.items() if t == "PERSONNE"])
    for mention, (type_, positions) in presentes.items():
        cle = f"PERSONNE:{canon[mention].casefold()}" if type_ == "PERSONNE" else ""
        resultat.entites += [Entite(d, f, type_, texte[d:f], "llm", cle) for d, f in positions]

    # Noms et prénoms employés seuls (« Mme Ferrand », « Josiane a signalé… »).
    proprietaires: dict[str, tuple[str, str]] = {}
    for mention in sorted(canon, key=lambda m: -len(jetons_nom(m))):
        for jeton in jetons_nom(mention):
            proprietaires.setdefault(jeton.casefold(), (jeton, canon[mention]))
    couverts = [(e.debut, e.fin) for e in resultat.entites]
    for jeton, identite in proprietaires.values():
        for d, f in _occurrences_nom(texte, jeton):
            if not any(a <= d and f <= b for a, b in couverts):
                resultat.entites.append(
                    Entite(d, f, "PERSONNE", texte[d:f], "llm", f"PERSONNE:{identite.casefold()}")
                )
    return resultat
