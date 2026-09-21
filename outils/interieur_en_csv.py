#!/usr/bin/env python3
"""Recopie en CSV une feuille des résultats du ministère de l'Intérieur.

Le ministère publie ses résultats départementaux en Excel jusqu'en 2017, et
en texte séparé par des points-virgules, encodé en Latin-1, à partir de 2022.
La pipeline ne lit ni l'un ni l'autre : elle lit le CSV produit ici, commité
dans `raw/resultats/interieur/`, en UTF-8 et séparé par des points-virgules.

La conversion est volontairement bête. Chaque cellule est recopiée telle
quelle, à deux exceptions près, qui ne sont pas des interprétations mais des
artefacts du format : un nombre qu'Excel stocke en flottant — « 415886.0 » —
redevient l'entier qu'il est, et l'espace insécable des milliers — « 46 028
542 » — disparaît. Lire ce que ces lignes veulent dire est le travail de la
pipeline, qui se relit et se teste.

Usage :

    python outils/interieur_en_csv.py Presidentielle_2017_Resultats_Tour_1_c.xls \\
        --feuille "Départements Tour 1" \\
        --sortie raw/resultats/interieur/2017-t1-definitifs-departements.csv

    python outils/interieur_en_csv.py resultats-par-niveau-dpt-t1-france-entiere.txt \\
        --sortie raw/resultats/interieur/2022-t1-definitifs-departements.csv

`raw/resultats/interieur/SOURCES.md` dit d'où vient chaque fichier et quelle
feuille en a été tirée. Lire l'Excel demande `xlrd`, dans les dépendances
`outils` du paquet : la pipeline, elle, n'en a pas besoin.
"""

from __future__ import annotations

import argparse
import csv
import io
import re
import sys
from pathlib import Path

#: L'espace insécable, fine ou non, dont le ministère sépare les milliers.
ESPACES = re.compile(r"[  ]")


def _cellule(valeur: object) -> str:
    """Une cellule en texte, sans les artefacts du format."""
    if isinstance(valeur, float) and valeur.is_integer():
        return str(int(valeur))
    texte = ESPACES.sub("", str(valeur)) if re.fullmatch(r"[\d  ]+", str(valeur)) else str(valeur)
    return texte.strip()


def _lignes_excel(chemin: Path, feuille: str) -> list[list[str]]:
    import xlrd

    classeur = xlrd.open_workbook(chemin)
    table = classeur.sheet_by_name(feuille)
    return [[_cellule(v) for v in table.row_values(r)] for r in range(table.nrows)]


def _lignes_texte(chemin: Path) -> list[list[str]]:
    contenu = chemin.read_bytes().decode("latin-1")
    return [[c.strip() for c in ligne] for ligne in csv.reader(io.StringIO(contenu), delimiter=";")]


def main(argv: list[str] | None = None) -> int:
    parseur = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parseur.add_argument("source", type=Path, help="le fichier publié, .xls ou .txt")
    parseur.add_argument("--feuille", help="la feuille à recopier, pour un classeur Excel")
    parseur.add_argument("--sortie", type=Path, required=True)
    args = parseur.parse_args(argv)

    if args.source.suffix.lower() == ".xls":
        if not args.feuille:
            parseur.error("un classeur Excel demande --feuille")
        lignes = _lignes_excel(args.source, args.feuille)
    else:
        lignes = _lignes_texte(args.source)

    # Les lignes entièrement vides ne portent rien : ce sont les marges de la
    # mise en page Excel. Les cellules vides en fin de ligne, de même.
    propres = []
    for ligne in lignes:
        while ligne and not ligne[-1]:
            ligne = ligne[:-1]
        if ligne:
            propres.append(ligne)

    args.sortie.parent.mkdir(parents=True, exist_ok=True)
    with args.sortie.open("w", encoding="utf-8", newline="") as sortie:
        csv.writer(sortie, delimiter=";", lineterminator="\n").writerows(propres)
    print(f"{args.source.name} -> {args.sortie} ({len(propres)} lignes)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
