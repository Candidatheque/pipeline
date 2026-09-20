"""Lecture des fichiers sources de ``raw/``.

Un module par nature de contenu. Chaque lecteur rend la même chose quelle que
soit la forme du fichier : c'est là que les formats du seed se rejoignent.
"""

from candidatheque.pipeline.lecture.parrainages import Parrainage, lire

__all__ = ["Parrainage", "lire"]
