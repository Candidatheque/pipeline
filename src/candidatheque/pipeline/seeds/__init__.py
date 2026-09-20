"""Lecture des fichiers saisis à la main."""

from candidatheque.pipeline.seeds.candidatures import (
    Candidature,
    CandidaturesElection,
    Etat,
    Participation,
    load_candidatures,
)
from candidatheque.pipeline.seeds.elections import Election, Tour, load_elections
from candidatheque.pipeline.seeds.personnes import Personne, load_personnes
from candidatheque.pipeline.seeds.sources import Source, load_sources

__all__ = [
    "Candidature",
    "CandidaturesElection",
    "Election",
    "Etat",
    "Participation",
    "Personne",
    "Source",
    "Tour",
    "load_candidatures",
    "load_elections",
    "load_personnes",
    "load_sources",
]
