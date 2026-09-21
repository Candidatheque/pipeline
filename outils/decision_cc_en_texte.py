#!/usr/bin/env python3
"""Extrait le texte d'une décision du Conseil constitutionnel, depuis son site.

La pipeline ne télécharge rien : elle lit le texte produit ici, commité dans
`raw/resultats/`, comme n'importe quelle autre donnée. Rejouer la commande sur
la même page doit rendre le même texte.

La page d'une décision porte deux blocs qui nous intéressent, et cet outil les
garde tous les deux, séparés par une ligne de titre :

- `DÉCISION`, le texte lui-même : les considérants numérotés qui annulent des
  suffrages, puis celui qui donne les résultats du tour.
- `ABSTRACTS`, le classement que le Conseil fait de ses propres motifs
  — « 8.2.5.4.1. Procédure de dépouillement » — avec le numéro du considérant
  que chacun résume. C'est sa nomenclature, pas la nôtre, et elle donne un code
  à chaque annulation sans qu'on ait à en inventer un. Les décisions anciennes
  n'en ont pas toutes : le bloc est alors vide.

Le rendu est volontairement bête : un paragraphe par ligne, aucune
interprétation. Lire ce que ces lignes veulent dire est le travail de la
pipeline, qui se relit et se teste.

Usage :

    python outils/decision_cc_en_texte.py \\
        https://www.conseil-constitutionnel.fr/decision/2022/2022197PDR.htm \\
        --sortie raw/resultats/2022-197-PDR.txt

Un chemin de fichier est accepté à la place de l'URL, pour rejouer la
conversion sur une page déjà téléchargée.
"""

from __future__ import annotations

import argparse
import html
import re
import sys
import urllib.request
from pathlib import Path

#: Le conteneur Drupal du texte de la décision. Les abstracts qui la suivent
#: ont le leur, `field--name-field-texte`, et ne s'y confondent pas.
CORPS = re.compile(
    r'<div[^>]*class="[^"]*field--name-field-contenu-original[^"]*"[^>]*>(.*)', re.DOTALL
)
#: Le bloc des abstracts, qui suit la décision.
ABSTRACTS = re.compile(r'<div[^>]*id="wrapper-abstrats"[^>]*>(.*)', re.DOTALL)
#: Ce qui suit la décision et ses abstracts, et qui appartient au site plutôt
#: qu'au document : le cartouche des annexes, puis les dernières décisions
#: publiées.
NAVIGATION = re.compile(
    r'<div[^>]*class="[^"]*(?:cartouche-decision-print|wrapper-dernieres-decisions)[^"]*"',
    re.DOTALL,
)
#: Ce qui ferme une ligne : fin de paragraphe, de titre, d'élément de liste, et
#: le saut de ligne que le Conseil met entre les membres d'une même phrase.
FIN_DE_LIGNE = re.compile(r"</(?:p|h\d|li|div|blockquote)>|<br\s*/?>", re.IGNORECASE)
BALISE = re.compile(r"<[^>]+>")
#: Le site n'écrit pas d'espace entre le numéro du considérant et son texte :
#: « 12. » tient sa propre ligne. La recoller évite de la prendre pour un titre.
NUMERO_SEUL = re.compile(r"^(\d{1,3})\.$")


def _lignes(fragment: str) -> list[str]:
    """Un fragment de HTML en lignes de texte, une par paragraphe."""
    lignes = []
    for morceau in FIN_DE_LIGNE.split(fragment):
        # `split()` sans argument coupe sur toutes les espaces Unicode, dont
        # l'insécable dont le Conseil sépare « n° » de son nombre.
        ligne = " ".join(html.unescape(BALISE.sub(" ", morceau)).split())
        if ligne:
            lignes.append(ligne)
    return lignes


def _recolle_les_numeros(lignes: list[str]) -> list[str]:
    """Rend au considérant son numéro, que la mise en page met à part.

    Le site met « 12. » dans son propre élément et le texte du considérant dans
    le suivant. Les laisser séparés ferait une ligne qui n'est qu'un nombre, et
    un considérant qui ne porte plus son rang.
    """
    recollees: list[str] = []
    for ligne in lignes:
        if recollees and NUMERO_SEUL.match(recollees[-1]):
            recollees[-1] = f"{recollees[-1]} {ligne}"
        else:
            recollees.append(ligne)
    return recollees


def texte(page: str) -> str:
    """Le texte d'une décision : la décision, puis ses abstracts."""
    avant_abstracts = ABSTRACTS.split(NAVIGATION.split(page)[0])
    corps = CORPS.search(avant_abstracts[0])
    if corps is None:
        raise ValueError("pas de texte de décision dans cette page")

    sections = ["DÉCISION", *_recolle_les_numeros(_lignes(corps.group(1)))]
    sections += ["", "ABSTRACTS"]
    if len(avant_abstracts) > 1:
        sections += _lignes(avant_abstracts[1])
    return "\n".join(sections) + "\n"


def _page(source: str) -> str:
    """La page, depuis le site du Conseil ou depuis un fichier local."""
    if source.startswith("http"):
        requete = urllib.request.Request(source, headers={"User-Agent": "candidatheque"})
        with urllib.request.urlopen(requete) as reponse:  # noqa: S310 — URL du seed
            return reponse.read().decode("utf-8")
    return Path(source).read_text(encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parseur = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parseur.add_argument("source", help="URL de la décision, ou page déjà téléchargée")
    parseur.add_argument("--sortie", type=Path, required=True, help="où écrire le texte")
    args = parseur.parse_args(argv)

    contenu = texte(_page(args.source))
    args.sortie.write_text(contenu, encoding="utf-8")
    print(f"{args.source} -> {args.sortie} ({len(contenu)} caractères)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
