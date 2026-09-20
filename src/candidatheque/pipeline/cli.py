"""Point d'entrée en ligne de commande de la pipeline."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from pydantic import ValidationError

from candidatheque.pipeline.paths import DATA_REPO
from candidatheque.pipeline.publication import Statut, publier
from candidatheque.pipeline.seeds import load_elections

MARQUES = {
    Statut.CREE: "+",
    Statut.MODIFIE: "~",
    Statut.INCHANGE: " ",
    Statut.SUPPRIME: "-",
}


def _cmd_valider(_: argparse.Namespace) -> int:
    try:
        elections = load_elections()
    except ValidationError as erreur:
        print("Seed invalide :", file=sys.stderr)
        print(erreur, file=sys.stderr)
        return 1

    print(f"{len(elections)} élections, seed valide.")
    return 0


def _cmd_lister(_: argparse.Namespace) -> int:
    for election in load_elections():
        print(f"{election.id:<14} {election.annee}")
    return 0


def _cmd_publier(args: argparse.Namespace) -> int:
    ecritures = publier(args.destination)

    for ecriture in ecritures:
        chemin = ecriture.chemin.relative_to(args.destination)
        print(f"{MARQUES[ecriture.statut]} {chemin}")

    comptes = {statut: sum(1 for e in ecritures if e.statut is statut) for statut in Statut}
    print(
        f"\n{comptes[Statut.CREE]} créés, {comptes[Statut.MODIFIE]} modifiés, "
        f"{comptes[Statut.INCHANGE]} inchangés, {comptes[Statut.SUPPRIME]} supprimés "
        f"dans {args.destination}."
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parseur = argparse.ArgumentParser(prog="candidatheque")
    sous = parseur.add_subparsers(dest="commande", required=True)

    sous.add_parser("valider", help="valide les fichiers de seeds").set_defaults(fn=_cmd_valider)
    sous.add_parser("lister", help="affiche les élections du seed").set_defaults(fn=_cmd_lister)

    publication = sous.add_parser("publier", help="écrit les données dans le dépôt de destination")
    publication.add_argument(
        "--destination",
        type=Path,
        default=DATA_REPO,
        help=f"racine du dépôt de destination (défaut : {DATA_REPO})",
    )
    publication.set_defaults(fn=_cmd_publier)

    args = parseur.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
