"""Pseudonymisation de documents français, 100 % locale.

Exemple ::

    from pseudonymiseur import ClientOllama, traiter

    traitement = traiter(texte, client=ClientOllama(modele="mistral"))
    print(traitement.resultat.texte)
"""

from .entites import TYPES, Entite
from .llm import ClientOllama
from .pipeline import Traitement, detecter, traiter
from .remplacement import Resultat, remplacer

__all__ = [
    "TYPES",
    "ClientOllama",
    "Entite",
    "Resultat",
    "Traitement",
    "detecter",
    "remplacer",
    "traiter",
]
__version__ = "0.1.0"
