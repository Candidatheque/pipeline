"""Lecture des résultats publiés par le ministère de l'Intérieur.

Le ministère publie, pour chaque tour, un fichier national et un fichier par
département, recopiés en CSV sous `raw/resultats/interieur/` par
`outils/interieur_en_csv.py`. Deux mises en page s'y rencontrent :

- le **tableau**, une ligne par département — ou une seule ligne « FE » pour
  la France entière en 2022 — avec les décomptes, puis un bloc de colonnes par
  candidat : sexe, nom, prénom, voix, pourcentages ;
- la **fiche** nationale des classeurs de 2007 à 2017 : les décomptes en
  colonne, un libellé et sa valeur par ligne, et à côté la liste des candidats
  avec leurs voix. Celle de 2007 et 2012 porte les deux tours côte à côte.

Les colonnes se repèrent à leur intitulé, jamais à leur rang : le ministère en
a ajouté d'une élection à l'autre — l'« Etat saisie » de 2022, le « N°Panneau »
des candidats —, et les séparer des blancs et des nuls en 2017.

Les pourcentages ne sont pas lus. Ils se recalculent, et les recopier ne
ferait que reprendre les arrondis du ministère.
"""

from __future__ import annotations

import csv
import re

from candidatheque.pipeline.lecture.resultats import Departement, Tour, Voix
from candidatheque.pipeline.seeds.resultats import VersionResultats

#: L'intitulé de chaque décompte, dans les deux mises en page.
DECOMPTES = {
    "Inscrits": "inscrits",
    "Votants": "votants",
    "Blancs": "bulletins_blancs",
    "Nuls": "bulletins_nuls",
    "Blancs et nuls": "bulletins_blancs_et_nuls",
    "Exprimés": "suffrages_exprimes",
}
#: La civilité devant le nom, dans la fiche : « M. MACRON Emmanuel ».
CIVILITE = re.compile(r"^(?:M\.|Mme|Mlle)\s+")


def _lignes(chemin) -> list[list[str]]:
    with chemin.open(encoding="utf-8", newline="") as fichier:
        return list(csv.reader(fichier, delimiter=";"))


def _entier(valeur: str) -> int:
    return int(valeur.replace(" ", ""))


def _personne(version: VersionResultats, titre: str) -> str:
    """La personne que ce nom désigne, déclarée au seed et jamais devinée."""
    personne = version.personne_de(titre)
    if personne is None:
        raise ValueError(f"{version.fichier} : « {titre} » n'est pas déclaré au seed")
    return personne


def _tableau(lignes: list[list[str]], version: VersionResultats) -> list[Departement]:
    """Les lignes d'un tableau, une par niveau géographique."""
    entete_rang = next(
        i for i, ligne in enumerate(lignes) if ligne and ligne[0].startswith("Code du")
    )
    entete = lignes[entete_rang]
    decomptes = {DECOMPTES[nom]: i for i, nom in enumerate(entete) if nom in DECOMPTES}
    # Chaque candidat occupe un bloc de colonnes de même largeur. Les classeurs
    # d'avant 2022 en répètent l'en-tête ; les fichiers de 2022 ne nomment que
    # le premier, et les suivants s'enchaînent sur la même largeur. La largeur
    # se mesure donc d'un « Nom » au suivant, ou, faute de second, du début du
    # bloc à la fin de l'en-tête.
    noms = [i for i, nom in enumerate(entete) if nom == "Nom"]
    debut = next(i for i, nom in enumerate(entete) if nom in ("N°Panneau", "Sexe"))
    largeur = noms[1] - noms[0] if len(noms) > 1 else len(entete) - debut
    decalage = noms[0] - debut

    departements = []
    for ligne in lignes[entete_rang + 1 :]:
        # La ligne de total que le classeur de 2012 ajoute sous le tableau
        # n'a pas de code : ce n'est pas un département, et la compter
        # doublerait les inscrits.
        if not ligne or not ligne[0]:
            continue
        voix = []
        for bloc in range(debut, len(ligne), largeur):
            nom = bloc + decalage
            if nom + 2 >= len(ligne) or not ligne[nom]:
                continue
            titre = f"{ligne[nom]} {ligne[nom + 1]}"
            voix.append(
                Voix(titre=titre, personne=_personne(version, titre), voix=_entier(ligne[nom + 2]))
            )
        departements.append(
            Departement(
                code=ligne[0],
                libelle=ligne[1],
                voix=tuple(voix),
                **{champ: _entier(ligne[i]) for champ, i in decomptes.items() if ligne[i]},
            )
        )
    return departements


def _fiche(lignes: list[list[str]], version: VersionResultats, numero: int) -> Tour:
    """Le bloc « France entière » d'une fiche nationale.

    La fiche de 2007 et 2012 porte les deux tours : la colonne se choisit sur
    son intitulé, « Tour_1 » ou « Tour_2 », et les voix sur « Voix_T1 » ou
    « Voix_T2 ». Les blocs suivants, « Métropole » et « Outre-mer », ne sont
    pas lus : ils redisent la France entière en deux morceaux.
    """
    entete_rang = next(i for i, ligne in enumerate(lignes) if ligne and ligne[0] == ".")
    entete = lignes[entete_rang]
    valeur = entete.index(f"Tour_{numero}") if f"Tour_{numero}" in entete else entete.index("Nombre")
    candidat = entete.index("Candidat")
    colonne_voix = entete.index(f"Voix_T{numero}") if f"Voix_T{numero}" in entete else entete.index("Voix")

    decomptes: dict[str, int] = {}
    voix: list[Voix] = []
    for ligne in lignes[entete_rang + 1 :]:
        ligne = ligne + [""] * (len(entete) - len(ligne))
        # Le bloc s'arrête au premier libellé qui n'est pas un décompte :
        # « Métropole » ouvre le suivant.
        if ligne[0] and ligne[0] not in DECOMPTES and ligne[0] != "Abstentions":
            break
        if ligne[0] in DECOMPTES and ligne[valeur]:
            decomptes[DECOMPTES[ligne[0]]] = _entier(ligne[valeur])
        nom = CIVILITE.sub("", ligne[candidat])
        # La ligne sans nom qui ferme la liste porte le total des voix, et
        # la note de 2017 — « inclus une partie des Français établis hors de
        # France » — n'a pas de voix : ni l'une ni l'autre n'est un candidat.
        if nom and ligne[colonne_voix]:
            voix.append(
                Voix(titre=nom, personne=_personne(version, nom), voix=_entier(ligne[colonne_voix]))
            )
    return Tour(voix=tuple(voix), **decomptes)


def lire(version: VersionResultats, numero: int, racine=None) -> Tour:
    """Les résultats d'un tour selon le ministère : national et départements."""
    national = _lignes(version.chemin(racine))
    if national and national[0] and national[0][0].startswith("Code du"):
        (france,) = _tableau(national, version)
        tour = Tour(
            voix=france.voix,
            **{
                champ: getattr(france, champ)
                for champ in DECOMPTES.values()
                if getattr(france, champ) is not None
            },
        )
    else:
        tour = _fiche(national, version, numero)

    departements: tuple[Departement, ...] = ()
    if chemin := version.chemin_departements(racine):
        departements = tuple(_tableau(_lignes(chemin), version))
    return Tour(
        **{champ: getattr(tour, champ) for champ in DECOMPTES.values()},
        voix=tour.voix,
        departements=departements,
    )
