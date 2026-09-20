"""Lecture des fichiers saisis à la main."""

from candidatheque.pipeline.seeds.elections import Election, load_elections
from candidatheque.pipeline.seeds.personnes import Personne, load_personnes

__all__ = ["Election", "Personne", "load_elections", "load_personnes"]
