#!/usr/bin/env python3
"""Extrait le texte d'un PDF de parrainages, par lecture ou par océrisation.

La pipeline n'ouvre pas de PDF : elle lit le texte produit ici, commité dans
`raw/` et relu comme n'importe quelle donnée. Installer tesseract dans la CI
pour cinq fichiers qui ne changeront jamais n'aurait pas de sens.

Cet outil est dans le dépôt pour que le texte publié soit vérifiable : rejouer
la commande sur le même PDF doit rendre le même texte.

Deux chemins, et l'outil choisit seul :

- le PDF porte du texte — les éditions du Journal officiel mises en ligne par
  Légifrance — et il est lu directement, mais en remettant les deux colonnes
  dans l'ordre : voir `colonnes.py` ;
- le PDF ne porte que des images scannées et il est océrisé.

Le seed enregistre lequel a servi, sous les formats `texte-jo` et `texte-ocr` :
un défaut de lecture ne se cherche pas au même endroit selon le cas.

Dépendances système pour l'océrisation, hors du paquet Python :

    apt-get install tesseract-ocr tesseract-ocr-fra poppler-utils

Usage :

    python outils/pdf_en_texte.py JORF_19950412_87.pdf --pages 8-30 \\
        --sortie raw/parrainages/1995.txt

Les éditions du Journal officiel pèsent des dizaines de mégaoctets et ne sont
pas dans le dépôt ; `raw/parrainages/SOURCES.md` dit où les reprendre et sur
quelles pages, pour que le texte commité se rejoue.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

import pypdf
from colonnes import texte_en_colonnes

RESOLUTION = 300
LANGUE = "fra"
#: Analyse de mise en page automatique. Indispensable : les listes du Journal
#: officiel sont sur deux colonnes, et un mode sans analyse lit à travers,
#: collant la fin d'une entrée au début d'une autre.
SEGMENTATION = "3"
#: En deçà, on considère que la page ne porte pas de texte exploitable. Une
#: page scannée en rend zéro ; une page de texte en rend plusieurs milliers.
SEUIL_TEXTE = 200


def porte_du_texte(pdf: Path) -> bool:
    """Le PDF contient-il du texte, ou seulement des images ?"""
    lecteur = pypdf.PdfReader(pdf)
    echantillon = lecteur.pages[: min(4, len(lecteur.pages))]
    total = sum(len(page.extract_text() or "") for page in echantillon)
    return total >= SEUIL_TEXTE * len(echantillon)


def lire_texte(pdf: Path, pages: tuple[int, int]) -> str:
    """Le texte du PDF, colonnes remises dans l'ordre de lecture."""
    return texte_en_colonnes(pdf, *pages)


def ocreriser(pdf: Path) -> str:
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run(
            ["pdftoppm", "-r", str(RESOLUTION), "-gray", "-png", str(pdf), str(Path(tmp) / "page")],
            check=True,
        )
        images = sorted(Path(tmp).glob("page-*.png"))
        print(f"  {len(images)} pages à océriser", file=sys.stderr)
        morceaux = []
        for i, image in enumerate(images, start=1):
            fini = subprocess.run(
                ["tesseract", str(image), "stdout", "-l", LANGUE, "--psm", SEGMENTATION],
                check=True,
                capture_output=True,
                text=True,
            )
            morceaux.append(fini.stdout)
            print(f"  page {i}/{len(images)}", file=sys.stderr, end="\r")
        print(file=sys.stderr)
    return "\n".join(morceaux)


def convertir(pdf: Path, pages: tuple[int, int]) -> tuple[str, str]:
    """Rend le texte du PDF, et le nom du chemin suivi."""
    if porte_du_texte(pdf):
        return lire_texte(pdf, pages), "texte-jo"
    return ocreriser(pdf), "texte-ocr"


def main(argv: list[str] | None = None) -> int:
    parseur = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parseur.add_argument("pdf", type=Path)
    parseur.add_argument(
        "--pages",
        default=None,
        help="les pages à lire, « 8-30 » (défaut : tout le document)",
    )
    parseur.add_argument(
        "--sortie",
        type=Path,
        default=None,
        help="où écrire le texte (défaut : le PDF avec l'extension .txt)",
    )
    args = parseur.parse_args(argv)

    debut, fin = (
        (int(n) for n in args.pages.split("-"))
        if args.pages
        else (1, len(pypdf.PdfReader(args.pdf).pages))
    )
    texte, chemin = convertir(args.pdf, (debut, fin))
    sortie = args.sortie or args.pdf.with_suffix(".txt")
    sortie.write_text(texte, encoding="utf-8")
    print(f"{args.pdf.name} : {chemin} -> {sortie} ({len(texte)} caractères)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
