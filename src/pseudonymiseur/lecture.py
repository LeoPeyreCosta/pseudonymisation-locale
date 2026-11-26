"""Lecture des documents à traiter."""

from __future__ import annotations

from pathlib import Path


def lire_document(chemin: str | Path) -> str:
    """Renvoie le texte d'un fichier .txt, .md ou .pdf."""
    chemin = Path(chemin)
    if chemin.suffix.lower() == ".pdf":
        try:
            from pypdf import PdfReader
        except ImportError as erreur:  # dépendance optionnelle
            raise RuntimeError("Lecture des PDF : installez l'option « pdf » (pypdf).") from erreur
        return "\n".join(page.extract_text() or "" for page in PdfReader(chemin).pages)
    return chemin.read_text(encoding="utf-8")
