"""Ligne de commande.

    pseudonymiser traiter courrier.txt
    pseudonymiser traiter courrier.txt --anonymiser
    pseudonymiser evaluer corpus/
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .evaluation import evaluer_corpus
from .lecture import lire_document
from .llm import ClientOllama
from .pipeline import traiter


def _client(args: argparse.Namespace) -> ClientOllama | None:
    if args.sans_llm:
        return None
    client = ClientOllama(modele=args.modele, url=args.url)
    if not client.disponible():
        sys.exit(
            f"Ollama est injoignable sur {args.url}. Lancez « ollama serve », "
            "ou utilisez --sans-llm (règles seules : les noms ne seront pas détectés)."
        )
    return client


def _commande_traiter(args: argparse.Namespace) -> None:
    source = Path(args.fichier)
    traitement = traiter(lire_document(source), _client(args), anonymiser=args.anonymiser)
    resultat = traitement.resultat

    sortie = Path(args.sortie) if args.sortie else source.with_suffix(".pseudonymise.txt")
    sortie.write_text(resultat.texte, encoding="utf-8")
    print(f"Texte traité → {sortie}")
    if not args.anonymiser:
        table = Path(args.table) if args.table else source.with_suffix(".table.json")
        table.write_text(json.dumps(resultat.table, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Table de correspondance → {table}  (donnée sensible : à conserver à part)")

    resume = ", ".join(f"{n} {t}" for t, n in resultat.compteurs.most_common())
    print(f"{len(resultat.entites)} données masquées en {traitement.duree_s:.1f} s : {resume or 'aucune'}")
    if traitement.rejetees:
        print(
            f"{len(traitement.rejetees)} proposition(s) du modèle écartée(s) "
            "(absentes du texte ou invraisemblables)."
        )
    if args.details:
        for e in resultat.entites:
            print(f"  {e.type:<12} {e.source:<5} {e.texte!r}")
    print("Relisez toujours le résultat : aucun outil automatique ne garantit 100 %.")


def _commande_evaluer(args: argparse.Namespace) -> None:
    rapport = evaluer_corpus(args.dossier, _client(args))
    print(rapport.en_markdown())
    if rapport.fuites:
        print("\nDonnées non masquées :")
        for fuite in rapport.fuites:
            print(f"  [{fuite.type}] {fuite.texte!r} ({fuite.document})")
    if args.details and rapport.faux_positifs:
        print("\nSur-masquages :")
        for document, texte, type_ in rapport.faux_positifs:
            print(f"  [{type_}] {texte!r} ({document})")


def main(argv: list[str] | None = None) -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(
        prog="pseudonymiser",
        description="Pseudonymisation de documents français, 100 % locale (règles + LLM via Ollama).",
    )
    commun = argparse.ArgumentParser(add_help=False)
    commun.add_argument("--modele", default="mistral", help="modèle Ollama (défaut : mistral)")
    commun.add_argument("--url", default="http://localhost:11434", help="adresse du serveur Ollama")
    commun.add_argument("--sans-llm", action="store_true", help="règles seules, sans modèle")
    commun.add_argument("--details", action="store_true", help="afficher le détail")
    sous = parser.add_subparsers(dest="commande", required=True)

    p_traiter = sous.add_parser("traiter", parents=[commun], help="pseudonymiser un document")
    p_traiter.add_argument("fichier", help="document .txt, .md ou .pdf")
    p_traiter.add_argument("-o", "--sortie", help="fichier de sortie")
    p_traiter.add_argument("--table", help="fichier de la table de correspondance")
    p_traiter.add_argument(
        "--anonymiser", action="store_true", help="étiquettes génériques, sans table de correspondance"
    )
    p_traiter.set_defaults(fonction=_commande_traiter)

    p_evaluer = sous.add_parser("evaluer", parents=[commun], help="mesurer la qualité sur un corpus annoté")
    p_evaluer.add_argument("dossier", help="dossier de documents .txt et de leurs .annotations.json")
    p_evaluer.set_defaults(fonction=_commande_evaluer)

    args = parser.parse_args(argv)
    args.fonction(args)


if __name__ == "__main__":
    main()
