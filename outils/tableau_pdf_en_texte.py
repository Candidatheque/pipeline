#!/usr/bin/env python3
"""Extrait le texte des tableaux d'une édition du Journal officiel.

Les tableaux de résultats annexés aux proclamations du Conseil constitutionnel
— un département par ligne, un candidat par colonne — ne se lisent pas comme la
prose des parrainages. `outils/pdf_en_texte.py` remet deux colonnes de texte
dans l'ordre de lecture, ce qui défait un tableau ; ici, `pdftotext -layout`
garde chaque ligne imprimée sur une ligne, avec ses colonnes à leur place.

La pipeline ne lit pas de PDF : elle lit le texte produit ici, commité dans
`raw/resultats/jo/`. Rejouer la commande sur la même édition rend le même
texte. Chaque page y est séparée de la suivante par un saut de page (`\\f`),
que la lecture utilise pour reconnaître le tableau d'une page à son en-tête.

Le texte est celui de la couche que Légifrance a océrisée, avec ses fautes :
chiffres collés ou coupés, noms abîmés. Les corriger est le travail de la
pipeline, qui s'appuie sur les totaux que le tableau imprime lui-même.

Dépendance système : `pdftotext`, de poppler-utils.

Usage :

    python outils/tableau_pdf_en_texte.py JORF_19950514_113.pdf --pages 8-15 \\
        --sortie raw/resultats/jo/1995.txt

Les éditions pèsent de 13 à 34 Mo et ne sont pas dans le dépôt ;
`raw/resultats/jo/SOURCES.md` dit lesquelles, et quelles pages.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def texte(pdf: Path, premiere: int, derniere: int) -> str:
    """Le texte des pages, mise en page conservée."""
    resultat = subprocess.run(
        ["pdftotext", "-q", "-layout", "-f", str(premiere), "-l", str(derniere), str(pdf), "-"],
        capture_output=True,
        check=True,
        text=True,
    )
    # Les espaces de fin de ligne ne portent rien, et varient d'une version de
    # poppler à l'autre : les ôter rend le texte stable. Le découpage se fait
    # page par page, `splitlines` tenant le saut de page pour une fin de ligne.
    pages = [
        "\n".join(ligne.rstrip() for ligne in page.split("\n")).strip("\n")
        for page in resultat.stdout.split("\f")
    ]
    return "\n\f\n".join(page for page in pages if page) + "\n"


def main(argv: list[str] | None = None) -> int:
    parseur = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parseur.add_argument("pdf", type=Path)
    parseur.add_argument("--pages", required=True, help="pages du PDF, « 8-15 »")
    parseur.add_argument("--sortie", type=Path, required=True)
    args = parseur.parse_args(argv)

    premiere, _, derniere = args.pages.partition("-")
    contenu = texte(args.pdf, int(premiere), int(derniere or premiere))
    args.sortie.parent.mkdir(parents=True, exist_ok=True)
    args.sortie.write_text(contenu, encoding="utf-8")
    print(f"{args.pdf.name} -> {args.sortie} ({len(contenu)} caractères)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
