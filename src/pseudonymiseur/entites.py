"""Modèle de données : une donnée personnelle repérée dans un texte."""

from __future__ import annotations

from dataclasses import dataclass

#: Types de données personnelles reconnus.
TYPES: tuple[str, ...] = (
    "PERSONNE",
    "LIEU",
    "ORGANISATION",
    "ADRESSE",
    "DATE",
    "EMAIL",
    "TELEPHONE",
    "NIR",
    "IBAN",
    "IDENTIFIANT",
)

#: Types confiés au modèle de langue (les autres sont détectés par des règles).
TYPES_LLM: tuple[str, ...] = ("PERSONNE", "LIEU", "ORGANISATION")


@dataclass(frozen=True)
class Entite:
    """Une donnée personnelle : sa position dans le texte, son type et son origine.

    ``cle`` relie plusieurs mentions d'une même personne (« Jean Dupont »,
    « M. Dupont », « Dupont ») pour qu'elles reçoivent le même pseudonyme.
    """

    debut: int
    fin: int
    type: str
    texte: str
    source: str = "regle"  # « regle » ou « llm »
    cle: str = ""

    @property
    def longueur(self) -> int:
        return self.fin - self.debut

    def chevauche(self, autre: Entite) -> bool:
        return self.debut < autre.fin and autre.debut < self.fin
