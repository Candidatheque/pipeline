#!/usr/bin/env python3
"""Extrait le texte d'un article du Journal officiel publié en XML par la DILA.

Les éditions anciennes du Journal officiel existent en fac-similé, qu'il faut
océriser ou lire par coordonnées, mais aussi en texte transcrit dans les jeux
de données ouverts de la DILA. Quand la transcription existe, elle vaut mieux :
elle ne porte aucune des blessures de l'impression, et il n'y a rien à
rattraper.

L'archive `Freemium_jorf_global` est un tar gzippé de 1,6 Go. Le gzip n'a pas
d'index, donc on ne saute pas au fichier voulu ; en revanche son chemin se
déduit de l'identifiant, ce qui évite d'ouvrir les autres. La règle : les dix
premiers chiffres de l'identifiant, par paires.

    JORFTEXT000000407519 -> texte/struct/JORF/TEXT/00/00/00/40/75/…
    JORFARTI000001822602 -> article/JORF/ARTI/00/00/01/82/26/…

Le fichier de structure donne les articles du texte ; l'article porte le
contenu. Télécharger l'archive une fois sur disque plutôt que la relire en
flux : le serveur coupe la connexion sans prévenir, et `tar` ne le signale pas.

    curl -O https://echanges.dila.gouv.fr/OPENDATA/JORF/Freemium_jorf_global_<horodatage>.tar.gz
    tar -xzf Freemium_jorf_global_<horodatage>.tar.gz \
        jorf/global/texte/struct/JORF/TEXT/00/00/00/40/75/JORFTEXT000000407519.xml
    tar -xzf Freemium_jorf_global_<horodatage>.tar.gz \
        jorf/global/article/JORF/ARTI/00/00/01/82/26/JORFARTI000001822602.xml
    python outils/jorf_xml_en_texte.py JORFARTI000001822602.xml \
        --sortie raw/parrainages/2002.txt

Usage :

    python outils/jorf_xml_en_texte.py <article.xml> [--sortie <fichier.txt>]
"""

from __future__ import annotations

import argparse
import html
import re
import sys
from pathlib import Path

#: Le corps de l'article, entre ces deux balises.
CORPS = re.compile(r"<BLOC_TEXTUEL>(.*?)</BLOC_TEXTUEL>", re.DOTALL)
#: Chaque paragraphe : un titre de candidat, ou sa liste entière.
PARAGRAPHE = re.compile(r"<p[^>]*>(.*?)</p>", re.DOTALL)
BALISE = re.compile(r"<[^>]+>")


def texte(xml: str) -> str:
    """Le texte de l'article, un paragraphe par ligne.

    Le Journal officiel met le nom du candidat dans un paragraphe centré et sa
    liste dans le suivant. Garder ce découpage suffit à la lecture : le titre
    tient sa ligne, et rien d'autre ne la tient.
    """
    corps = CORPS.search(xml)
    if corps is None:
        raise ValueError("pas de bloc textuel dans cet article")
    lignes = []
    for paragraphe in PARAGRAPHE.finditer(corps.group(1)):
        ligne = " ".join(html.unescape(BALISE.sub(" ", paragraphe.group(1))).split())
        if ligne:
            lignes.append(ligne)
    return "\n".join(lignes) + "\n"


def main(argv: list[str] | None = None) -> int:
    parseur = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parseur.add_argument("xml", type=Path)
    parseur.add_argument(
        "--sortie",
        type=Path,
        default=None,
        help="où écrire le texte (défaut : le XML avec l'extension .txt)",
    )
    args = parseur.parse_args(argv)

    contenu = texte(args.xml.read_text(encoding="utf-8"))
    sortie = args.sortie or args.xml.with_suffix(".txt")
    sortie.write_text(contenu, encoding="utf-8")
    print(f"{args.xml.name} -> {sortie} ({len(contenu)} caractères)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
