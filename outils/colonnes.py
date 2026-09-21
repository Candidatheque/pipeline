"""Remet un Journal officiel sur deux colonnes dans son ordre de lecture.

`pdftotext` rend les mots dans l'ordre où le PDF les pose, qui n'est pas
celui où on les lit : sur deux colonnes, une entrée de la colonne de gauche
peut sortir collée à une entrée de la colonne de droite. Le mode `-layout`
ne règle rien — il rend les deux colonnes côte à côte sur la même ligne.

D'où cette lecture par coordonnées : `pdftotext -bbox` donne la boîte de
chaque mot, et il suffit alors de les trier par colonne puis par hauteur.
Sans cela, les listes de présentateurs se mélangent d'un candidat à l'autre
et aucune ne compte les 500 noms qu'elle devrait.

Dépendance système : `apt-get install poppler-utils`.
"""

from __future__ import annotations

import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


def mots_par_page(pdf: Path, debut: int, fin: int):
    """Les mots du PDF avec leurs coordonnées, page par page."""
    xml = subprocess.run(
        ["pdftotext", "-bbox", "-f", str(debut), "-l", str(fin), str(pdf), "-"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    racine = ET.fromstring(xml)
    espace = racine.tag.split("}")[0].strip("{") if "}" in racine.tag else ""
    balise = (lambda nom: f"{{{espace}}}{nom}") if espace else (lambda nom: nom)
    for page in racine.iter(balise("page")):
        mots = []
        for mot in page.iter(balise("word")):
            mots.append(
                {
                    "x": float(mot.get("xMin")),
                    "y": float(mot.get("yMin")),
                    "xmax": float(mot.get("xMax")),
                    "ymax": float(mot.get("yMax")),
                    "t": (mot.text or ""),
                }
            )
        yield float(page.get("width")), mots


def gouttiere(largeur: float, mots: list[dict]) -> float:
    """L'abscisse qui sépare les deux colonnes.

    La gouttière est la bande verticale la moins encombrée près du milieu de
    la page. Faute de creux net, la page est sur une seule colonne et tout
    revient à gauche.
    """
    pas = largeur / 200
    densite = [0] * 202
    for m in mots:
        densite[int((m["x"] + m["xmax"]) / 2 / pas)] += 1
    creux = min(range(80, 120), key=lambda i: sum(densite[i - 1 : i + 2]))
    plein = sorted(densite[20:180])[80]  # densité médiane de la page
    if sum(densite[creux - 1 : creux + 2]) > plein:
        return largeur
    return creux * pas


def _rangees(mots: list[dict]) -> list[list[dict]]:
    """Les mots regroupés en rangées, de haut en bas.

    Le regroupement se fait par écart à la rangée en cours, et non par tranches
    de hauteur fixes : deux mots d'une même ligne ne sont pas posés exactement
    à la même ordonnée, et une tranche fixe en renvoie régulièrement un dans
    une rangée à lui seul. Ce mot-là sortait alors hors de sa présentation —
    « Jacques VERDIER, » privé de son « maire ».
    """
    if not mots:
        return []
    hauteurs = sorted(m["ymax"] - m["y"] for m in mots)
    tolerance = hauteurs[len(hauteurs) // 2] / 2
    rangees: list[list[dict]] = []
    courante: list[dict] = []
    reference = None
    for mot in sorted(mots, key=lambda m: (m["y"], m["x"])):
        if reference is None or mot["y"] - reference > tolerance:
            if courante:
                rangees.append(sorted(courante, key=lambda m: m["x"]))
            courante, reference = [], mot["y"]
        courante.append(mot)
    if courante:
        rangees.append(sorted(courante, key=lambda m: m["x"]))
    return rangees


def _centree(rangee: list[dict], coupe: float, largeur: float) -> bool:
    """La rangée est-elle un titre centré, courant sur les deux colonnes ?

    Un titre tient en quelques mots posés à cheval sur la gouttière ; une
    rangée de texte, elle, s'appuie sur la marge d'une colonne au moins.
    """
    if any(m["x"] < coupe < m["xmax"] for m in rangee):
        return True
    milieu = (min(m["x"] for m in rangee) + max(m["xmax"] for m in rangee)) / 2
    return len(rangee) <= 6 and abs(milieu - coupe) < largeur * 0.06


def _vider(bande: list[list[dict]], coupe: float, sortie: list[str]) -> None:
    """Écrit une bande : la colonne de gauche d'abord, celle de droite ensuite."""
    for gauche in (True, False):
        for rangee in bande:
            mots = [m for m in rangee if ((m["x"] + m["xmax"]) / 2 < coupe) == gauche]
            if mots:
                sortie.append(" ".join(m["t"] for m in mots))
    bande.clear()


def texte_en_colonnes(pdf: Path, debut: int, fin: int) -> str:
    """Le texte du PDF remis dans son ordre de lecture.

    Une rangée dont un mot enjambe la gouttière court sur toute la largeur :
    c'est un titre centré, et il sépare ce qui le précède de ce qui le suit.
    Entre deux titres, la colonne de gauche se lit avant celle de droite.
    """
    sortie: list[str] = []
    for largeur, mots in mots_par_page(pdf, debut, fin):
        if not mots:
            continue
        coupe = gouttiere(largeur, mots)
        bande: list[list[dict]] = []
        for rangee in _rangees(mots):
            if _centree(rangee, coupe, largeur):
                _vider(bande, coupe, sortie)
                sortie.append(" ".join(m["t"] for m in rangee))
            else:
                bande.append(rangee)
        _vider(bande, coupe, sortie)
    return "\n".join(sortie)


if __name__ == "__main__":
    print(texte_en_colonnes(Path(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3])))
