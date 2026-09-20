"""Lecture des fichiers saisis à la main."""

from candidatheque.pipeline.seeds.autorites import Autorite, Nature, load_autorites
from candidatheque.pipeline.seeds.candidatures import (
    Affiliation,
    Candidature,
    CandidaturesElection,
    Etat,
    Participation,
    load_candidatures,
)
from candidatheque.pipeline.seeds.elections import Election, Tour, load_elections
from candidatheque.pipeline.seeds.partis import Parti, load_partis
from candidatheque.pipeline.seeds.personnes import Personne, load_personnes
from candidatheque.pipeline.seeds.sources import Source, load_sources

__all__ = [
    "Affiliation",
    "Autorite",
    "Candidature",
    "CandidaturesElection",
    "Election",
    "Etat",
    "Nature",
    "Parti",
    "Participation",
    "Personne",
    "Source",
    "Tour",
    "load_autorites",
    "load_candidatures",
    "load_elections",
    "load_partis",
    "load_personnes",
    "load_sources",
]
