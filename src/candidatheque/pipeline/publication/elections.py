"""Publication des élections dans le dépôt de destination.

Le dépôt de destination est entièrement produit par la pipeline : rien n'y est
édité à la main, chaque fichier est réécrit à partir du seed. Deux formes y
coexistent :

- ``elections.json``, l'index, de quoi énumérer les élections ;
- ``elections/<ID>/election.json``, les métadonnées d'une élection, qui
  s'enrichiront à mesure que la pipeline collecte.

L'écriture est idempotente : un fichier au contenu inchangé n'est pas réécrit,
pour qu'un commit dans le dépôt de destination signifie toujours que les données
ont bougé.
"""

from __future__ import annotations

import json
import shutil
from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from candidatheque.pipeline.paths import DATA_REPO, SCHEMAS_DIR
from candidatheque.pipeline.seeds import Election, load_elections

#: Nom du répertoire qui porte une élection, sous la racine du dépôt.
ELECTIONS_DIR = "elections"
#: Nom du document de métadonnées, dans le répertoire d'une élection.
ELECTION_FILE = "election.json"
#: Nom de l'index, à la racine du dépôt.
INDEX_FILE = "elections.json"
#: Répertoire où les schémas sont recopiés, dans le dépôt de destination.
SCHEMAS_SUBDIR = "schemas"


class Statut(StrEnum):
    CREE = "créé"
    MODIFIE = "modifié"
    INCHANGE = "inchangé"
    SUPPRIME = "supprimé"


@dataclass(frozen=True)
class Ecriture:
    """Ce qui est arrivé à un fichier pendant la publication."""

    chemin: Path
    statut: Statut


def index(elections: Iterable[Election]) -> dict:
    """Contenu de l'index, avant sérialisation."""
    return {
        "$schema": f"{SCHEMAS_SUBDIR}/elections.schema.json",
        "elections": [
            {"id": election.id, "annee": election.annee} for election in elections
        ],
    }


def metadonnees(election: Election) -> dict:
    """Contenu du document de métadonnées d'une élection.

    Le chemin du schéma est relatif au fichier, qui se trouve deux niveaux sous
    la racine du dépôt.
    """
    return {
        "$schema": f"../../{SCHEMAS_SUBDIR}/election.schema.json",
        "id": election.id,
        "annee": election.annee,
    }


def _ecrire(chemin: Path, contenu: str) -> Ecriture:
    """Écrit `contenu` dans `chemin`, sans toucher au fichier s'il est identique."""
    if chemin.exists():
        if chemin.read_text(encoding="utf-8") == contenu:
            return Ecriture(chemin, Statut.INCHANGE)
        statut = Statut.MODIFIE
    else:
        statut = Statut.CREE

    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(contenu, encoding="utf-8")
    return Ecriture(chemin, statut)


def _ecrire_json(chemin: Path, donnees: dict) -> Ecriture:
    # `ensure_ascii=False` garde les accents lisibles dans les diffs ; l'ordre
    # des clés est celui de construction, pas l'ordre alphabétique, pour que
    # `$schema` et `id` restent en tête.
    return _ecrire(chemin, json.dumps(donnees, ensure_ascii=False, indent=2) + "\n")


def publier(destination: Path | None = None) -> list[Ecriture]:
    """Écrit le seed dans le dépôt de destination et rend le détail des écritures.

    Les répertoires d'élections sans entrée correspondante dans le seed sont
    supprimés : le dépôt de destination reflète l'état courant du seed, il ne
    garde rien des états précédents.
    """
    destination = destination or DATA_REPO
    elections = load_elections()
    ecritures: list[Ecriture] = []

    for schema in sorted(SCHEMAS_DIR.glob("*.schema.json")):
        cible = destination / SCHEMAS_SUBDIR / schema.name
        ecritures.append(_ecrire(cible, schema.read_text(encoding="utf-8")))

    ecritures.append(_ecrire_json(destination / INDEX_FILE, index(elections)))

    racine_elections = destination / ELECTIONS_DIR
    for election in elections:
        cible = racine_elections / election.id / ELECTION_FILE
        ecritures.append(_ecrire_json(cible, metadonnees(election)))

    attendus = {election.id for election in elections}
    if racine_elections.is_dir():
        for repertoire in sorted(racine_elections.iterdir()):
            if repertoire.is_dir() and repertoire.name not in attendus:
                shutil.rmtree(repertoire)
                ecritures.append(Ecriture(repertoire, Statut.SUPPRIME))

    return ecritures
