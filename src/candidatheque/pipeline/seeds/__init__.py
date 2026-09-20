"""Lecture des fichiers saisis à la main."""

from candidatheque.pipeline.seeds.elections import Election, Tour, load_elections
from candidatheque.pipeline.seeds.personnes import Personne, load_personnes

__all__ = ["Election", "Personne", "Tour", "load_elections", "load_personnes"]
