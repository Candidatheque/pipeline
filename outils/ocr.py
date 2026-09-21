#!/usr/bin/env python3
"""Océrise un PDF scanné de parrainages et écrit le texte à côté.

La pipeline n'océrise pas : elle lit le texte produit ici, commité dans `raw/`
et relu comme n'importe quelle donnée. Installer tesseract dans la CI pour
trois fichiers qui ne changeront jamais n'aurait pas de sens.

Cet outil est dans le dépôt pour que le texte publié soit vérifiable : rejouer
la commande sur le même PDF doit rendre le même texte, à la version de
tesseract près.

Dépendances système, hors du paquet Python :

    apt-get install tesseract-ocr tesseract-ocr-fra poppler-utils

Usage :

    python outils/ocr.py raw/parrainages/1995.pdf

Écrit `raw/parrainages/1995.txt`. Les pages sont rendues en niveaux de gris à
300 points par pouce, puis lues en mode `--psm 3`, qui analyse la mise en page.
Ce mode est indispensable : les listes du Journal officiel sont sur deux
colonnes, et un mode sans analyse lit à travers, mêlant la fin d'une entrée au
début d'une autre.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

RESOLUTION = 300
LANGUE = "fra"
#: Analyse de mise en page automatique. Voir la note du module sur les colonnes.
SEGMENTATION = "3"


def pages(pdf: Path, dossier: Path) -> list[Path]:
    """Rend chaque page du PDF en une image, et les rend dans l'ordre."""
    subprocess.run(
        ["pdftoppm", "-r", str(RESOLUTION), "-gray", "-png", str(pdf), str(dossier / "page")],
        check=True,
    )
    return sorted(dossier.glob("page-*.png"))


def lire(image: Path) -> str:
    """Le texte d'une image, par tesseract."""
    fini = subprocess.run(
        ["tesseract", str(image), "stdout", "-l", LANGUE, "--psm", SEGMENTATION],
        check=True, capture_output=True, text=True,
    )
    return fini.stdout


def ocreriser(pdf: Path) -> str:
    with tempfile.TemporaryDirectory() as tmp:
        images = pages(pdf, Path(tmp))
        print(f"{pdf.name} : {len(images)} pages", file=sys.stderr)
        morceaux = []
        for i, image in enumerate(images, start=1):
            morceaux.append(lire(image))
            print(f"  page {i}/{len(images)}", file=sys.stderr, end="\r")
        print(file=sys.stderr)
    return "\n".join(morceaux)


def main(argv: list[str] | None = None) -> int:
    parseur = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parseur.add_argument("pdf", type=Path, help="le PDF scanné à océriser")
    parseur.add_argument(
        "--sortie", type=Path, default=None,
        help="où écrire le texte (défaut : le PDF avec l'extension .txt)",
    )
    args = parseur.parse_args(argv)

    version = subprocess.run(
        ["tesseract", "--version"], capture_output=True, text=True, check=True
    )
    print(version.stdout.splitlines()[0], file=sys.stderr)

    sortie = args.sortie or args.pdf.with_suffix(".txt")
    sortie.write_text(ocreriser(args.pdf), encoding="utf-8")
    print(f"écrit : {sortie} ({sortie.stat().st_size} octets)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
