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
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from candidatheque.pipeline.lecture import resultats as lecture_resultats
from candidatheque.pipeline.lecture import resultats_interieur as lecture_interieur
from candidatheque.pipeline.lecture import resultats_jo as lecture_jo
from candidatheque.pipeline.lecture.parrainages import Parrainage, lire
from candidatheque.pipeline.paths import DATA_REPO, SCHEMAS_DIR
from candidatheque.pipeline.publication import parrainages as publication_parrainages
from candidatheque.pipeline.publication import resultats as publication_resultats
from candidatheque.pipeline.seeds import (
    Affiliation,
    Candidature,
    Election,
    Parti,
    Personne,
    Source,
    load_candidatures,
    load_elections,
    load_partis,
    load_personnes,
    load_sources,
)
from candidatheque.pipeline.seeds.parrainages import SourceParrainages, load_parrainages
from candidatheque.pipeline.seeds.resultats import (
    Format,
    SourceResultats,
    VersionResultats,
    load_resultats,
)

#: Nom du répertoire qui porte une élection, sous la racine du dépôt.
ELECTIONS_DIR = "elections"
#: Nom du document de métadonnées, dans le répertoire d'une élection.
ELECTION_FILE = "election.json"
#: Nom du document des candidatures, dans le répertoire d'une élection.
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
        # Le QID d'un tour est omis quand il n'existe pas, plutôt que publié à
        # `null` : absent se lit « Wikidata ne modélise pas ce tour », là où
        # `null` inviterait à y voir une valeur.
        "tours": [
            {"numero": tour.numero, "date": tour.date.isoformat()}
            | ({"wikidata": tour.wikidata} if tour.wikidata else {})
            for tour in election.tours
        ],
    }


def _source_publiee(source: Source) -> dict:
    """Une source, telle qu'elle est recopiée à côté de la donnée qu'elle établit.

    Le seed cite les sources par identifiant pour ne pas les répéter à la main ;
    la publication les développe pour qu'un fichier se lise sans résoudre de
    référence.
    """
    return {
        "id": source.id,
        "url": source.url,
        "commentaire": source.commentaire,
        "consultee_le": source.consultee_le.isoformat(),
    }


def _parti_publie(
    affiliation: Affiliation, parti: Parti, sources: Mapping[str, Source]
) -> dict:
    """Un parti tel qu'il est publié à côté de la candidature.

    Le sigle est omis quand le parti n'en a pas : beaucoup de petits mouvements
    sont dans ce cas, et publier une chaîne vide en inventerait un.
    """
    entree = {
        "id": affiliation.parti,
        "nom_complet": affiliation.nom_complet or parti.nom_complet,
    }
    if parti.sigle:
        entree["sigle"] = parti.sigle
    entree["sources"] = [
        _source_publiee(sources[identifiant]) for identifiant in affiliation.sources
    ]
    return entree


def candidatures(
    election: Election,
    candidats: Iterable[Candidature],
    sources: Mapping[str, Source],
    personnes: Mapping[str, Personne],
    partis: Mapping[str, Parti],
) -> dict:
    """Le contenu du document des candidatures d'une élection.

    Le nom absent du seed est résolu depuis le registre : le seed ne le répète
    pas, le document publié le porte toujours.
    """
    return {
        "$schema": f"../../{SCHEMAS_SUBDIR}/candidatures.schema.json",
        "election": election.id,
        "candidatures": [
            {
                "personne": candidat.personne,
                "nom_complet": candidat.nom_complet or personnes[candidat.personne].nom_complet,
                "etats": [
                    {"etat": str(changement.etat)}
                    | ({"date": changement.date.isoformat()} if changement.date else {})
                    | {
                        "sources": [
                            _source_publiee(sources[identifiant])
                            for identifiant in changement.sources
                        ],
                    }
                    for changement in candidat.etats
                ],
                "partis": [
                    _parti_publie(affiliation, partis[affiliation.parti], sources)
                    for affiliation in candidat.partis
                ],
                "tours": [
                    {
                        "numero": participation.numero,
                        "sources": [
                            _source_publiee(sources[identifiant])
                            for identifiant in participation.sources
                        ],
                    }
                    for participation in candidat.tours
                ],
            }
            for candidat in candidats
        ],
    }


def documents(
    election: Election,
    candidats: Iterable[Candidature] = (),
    sources: Mapping[str, Source] | None = None,
    personnes: Mapping[str, Personne] | None = None,
    partis: Mapping[str, Parti] | None = None,
    presentations: tuple[SourceParrainages, list[Parrainage]] | None = None,
    resultats: tuple[SourceResultats, dict[tuple[int, int], lecture_resultats.Tour]] | None = None,
) -> Iterator[tuple[str, dict]]:
    """Les documents à publier dans le répertoire d'une élection.

    Point d'extension : un sujet collecté de plus, c'est un `yield` de plus.
    Une élection sans candidature connue ne publie pas de document vide — deux
    élections n'ont pas les mêmes documents, selon leur stade.

    Le nom rendu est un chemin relatif au répertoire de l'élection : les
    parrainages vivent sous `candidats/<PE>/`, un répertoire par candidat.
    """
    candidats = tuple(candidats)
    yield ELECTION_FILE, metadonnees(election)
    if candidats:
        yield CANDIDATURES_FILE, candidatures(
            election, candidats, sources or {}, personnes or {}, partis or {}
        )
    if presentations is not None:
        source, lus = presentations
        yield from publication_parrainages.documents(
            source,
            lus,
            {candidat.personne for candidat in candidats},
            {identifiant: p.nom_complet for identifiant, p in (personnes or {}).items()},
            sources or {},
            _source_publiee,
        )
    if resultats is not None:
        source, lus = resultats
        # Le nom porté lors de ce scrutin, celui que publie la candidature.
        noms = {
            candidat.personne: candidat.nom_complet
            or (personnes or {})[candidat.personne].nom_complet
            for candidat in candidats
        }
        yield publication_resultats.RESULTATS_FILE, publication_resultats.resultats(
            election, source, lus, noms, sources or {}, _source_publiee
        )


def lire_version(version: VersionResultats, numero: int) -> lecture_resultats.Tour:
    """Une version des résultats d'un tour, lue selon le format de sa source."""
    if version.format is Format.INTERIEUR:
        return lecture_interieur.lire(version, numero)
    if version.format is Format.TABLEAU_JO:
        tour, problemes = lecture_jo.lire(version)
        # Une case qui n'a pu être établie ne se publie pas à moitié : la
        # version entière attend qu'elle le soit, au seed.
        if problemes:
            raise ValueError(f"{version.fichier} : " + " ; ".join(problemes))
        return tour
    return lecture_resultats.lire(version)


def _supprimer_orphelins(repertoire: Path, attendus: set[str]) -> list[Ecriture]:
    """Retire d'un répertoire d'élection les documents qui ne sont plus produits.

    Un sujet peut cesser d'exister : une élection à venir perd ses candidatures
    provisoires le jour où la liste officielle les remplace, et un candidat
    perd son répertoire le jour où sa candidature est retirée du seed. Le
    parcours est récursif depuis que les parrainages vivent un cran plus bas.
    """
    if not repertoire.is_dir():
        return []

    ecritures = []
    for chemin in sorted(repertoire.rglob("*")):
        if chemin.is_file() and str(chemin.relative_to(repertoire)) not in attendus:
            chemin.unlink()
            ecritures.append(Ecriture(chemin, Statut.SUPPRIME))
    # Un répertoire vidé de ses documents n'a plus de raison d'être ; il est
    # retiré après coup, du plus profond au moins profond.
    for chemin in sorted(repertoire.rglob("*"), reverse=True):
        if chemin.is_dir() and not any(chemin.iterdir()):
            chemin.rmdir()
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
    sources = {source.id: source for source in load_sources()}
    personnes = {personne.id: personne for personne in load_personnes()}
    partis = {parti.id: parti for parti in load_partis()}
    par_election = {entree.election: entree.candidats for entree in load_candidatures()}
    # Les parrainages sont lus depuis `raw/` à chaque publication, comme le
    # reste : le seed déclare le fichier et la façon de le lire, rien n'est mis
    # en cache entre deux passages.
    presentations = {
        entree.election: (entree, lire(entree)) for entree in load_parrainages()
    }
    resultats = {
        entree.election: (
            entree,
            {
                (tour.numero, rang): lire_version(version, tour.numero)
                for tour in entree.tours
                for rang, version in enumerate(tour.versions)
            },
        )
        for entree in load_resultats()
    }
    ecritures: list[Ecriture] = []

    for schema in sorted(SCHEMAS_DIR.glob("*.schema.json")):
        cible = destination / SCHEMAS_SUBDIR / schema.name
        ecritures.append(_ecrire(cible, schema.read_text(encoding="utf-8")))

    ecritures.append(_ecrire_json(destination / INDEX_FILE, index(elections)))

    racine_elections = destination / ELECTIONS_DIR
    for election in elections:
        repertoire = racine_elections / election.id
        attendus = set()
        for nom, contenu in documents(
            election,
            par_election.get(election.id, ()),
            sources,
            personnes,
            partis,
            presentations.get(election.id),
            resultats.get(election.id),
        ):
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
