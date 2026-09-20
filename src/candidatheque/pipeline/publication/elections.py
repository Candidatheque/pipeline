"""Publication des élections dans le dépôt de destination.

Le dépôt de destination est entièrement produit par la pipeline : rien n'y est
édité à la main, chaque fichier est réécrit à partir du seed. Deux formes y
coexistent :

- ``elections.json``, l'index, de quoi énumérer les élections ;
- ``elections/<ID>/``, un répertoire par élection, qui porte un document par
  sujet.

Le découpage en documents suit la volatilité, pas le thème. Les résultats d'un
scrutin proclamé ne changeront plus jamais ; les candidatures à une élection à
venir changent toutes les semaines et sont fausses une partie du temps. Dans un
même fichier, la donnée provisoire ferait bouger la donnée définitive à chaque
passage, et personne ne pourrait plus les mettre en cache séparément.

Deux élections n'ont donc pas les mêmes documents : c'est la conséquence normale
du fait qu'elles ne sont pas au même stade.

L'écriture est idempotente : un fichier au contenu inchangé n'est pas réécrit,
pour qu'un commit dans le dépôt de destination signifie toujours que les données
ont bougé. Un corollaire contraignant pour la suite : aucun document ne porte de
date de génération. Les dates publiées viennent des sources, jamais de l'horloge
au moment de publier.
"""

from __future__ import annotations

import json
import shutil
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from candidatheque.pipeline.paths import DATA_REPO, SCHEMAS_DIR
from candidatheque.pipeline.seeds import Election, load_elections

#: Nom du répertoire qui porte une élection, sous la racine du dépôt.
ELECTIONS_DIR = "elections"
#: Nom du document de métadonnées, dans le répertoire d'une élection.
ELECTION_FILE = "election.json"
#: Nom du document des candidatures. Aucun producteur pour l'instant : le
#: schéma existe, la collecte qui le remplira reste à écrire.
CANDIDATURES_FILE = "candidatures.json"
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
        "wikidata": election.wikidata,
    }


def documents(election: Election) -> Iterator[tuple[str, dict]]:
    """Les documents à publier dans le répertoire d'une élection.

    Point d'extension : un sujet collecté de plus, c'est un `yield` de plus.
    Seules les métadonnées existent aujourd'hui.
    """
    yield ELECTION_FILE, metadonnees(election)


def _supprimer_orphelins(repertoire: Path, attendus: set[str]) -> list[Ecriture]:
    """Retire d'un répertoire d'élection les documents qui ne sont plus produits.

    Un sujet peut cesser d'exister : une élection à venir perd ses candidatures
    provisoires le jour où la liste officielle les remplace.
    """
    if not repertoire.is_dir():
        return []

    ecritures = []
    for chemin in sorted(repertoire.iterdir()):
        if chemin.is_file() and chemin.name not in attendus:
            chemin.unlink()
            ecritures.append(Ecriture(chemin, Statut.SUPPRIME))
    return ecritures


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

    Les répertoires d'élections sans entrée correspondante dans le seed, et les
    documents qu'aucun sujet ne produit plus, sont supprimés : le dépôt de
    destination reflète l'état courant du seed, il ne garde rien des états
    précédents.
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
        repertoire = racine_elections / election.id
        attendus = set()
        for nom, contenu in documents(election):
            attendus.add(nom)
            ecritures.append(_ecrire_json(repertoire / nom, contenu))
        ecritures.extend(_supprimer_orphelins(repertoire, attendus))

    connues = {election.id for election in elections}
    if racine_elections.is_dir():
        for repertoire in sorted(racine_elections.iterdir()):
            if repertoire.is_dir() and repertoire.name not in connues:
                shutil.rmtree(repertoire)
                ecritures.append(Ecriture(repertoire, Statut.SUPPRIME))

    return ecritures
