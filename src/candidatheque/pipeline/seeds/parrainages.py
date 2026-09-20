"""D'où viennent les parrainages, et sous quelle forme les lire.

Le fichier source est commité dans ``raw/``, jamais téléchargé : ces documents
sont historiques et figés, et un fichier suivi par git est un meilleur
archivage qu'une copie reconstruite à chaque passage.

Le format déclaré ici est ce qui rend le code générique : la pipeline ne connaît
que des formats, jamais des années. Ajouter une élection, c'est ajouter une
entrée ; écrire du code n'est nécessaire que si sa forme est inédite.
"""

from __future__ import annotations

import datetime as dt
from enum import StrEnum
from itertools import pairwise
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from candidatheque.pipeline.paths import PARRAINAGES_SEED, RAW_DIR


class Format(StrEnum):
    """Comment lire le fichier source."""

    #: Un tableau, une entrée par parrainage. Forme de 2022.
    JSON_PLAT = "json-plat"
    #: Un tableau de candidats, chacun portant ses parrainages. Forme de 2017,
    #: aux champs accentués et aux dates en jj/mm/aaaa.
    JSON_PAR_CANDIDAT = "json-par-candidat"
    #: Le texte du Journal officiel, en prose continue. Extrait du PDF une
    #: fois hors ligne par `outils/pdf_en_texte.py` : la pipeline ne lit pas de
    #: PDF, elle relit le texte commité comme n'importe quelle donnée.
    TEXTE_JO = "texte-jo"


class Etendue(StrEnum):
    """Ce que la source publie : tout, ou un échantillon.

    Avant la réforme de 2016, la loi n'imposait de publier que 500 présentations
    par candidat, tirées au sort. Les compter donnerait donc 500 pour chacun, ce
    qui n'est pas leur nombre de parrainages. Depuis 2017, la publication est
    intégrale, et le compte a un sens.
    """

    #: Tous les parrainages reçus. À partir de 2017.
    INTEGRALE = "integrale"
    #: 500 par candidat, tirés au sort par le Conseil constitutionnel. Vérifié :
    #: 2007 et 2012 en comptent exactement 500 pour chaque candidat.
    TIRAGE_AU_SORT = "tirage-au-sort"


class Publication(BaseModel):
    """Une vague de publication, et la décision qui l'a rendue publique."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    date: dt.date
    source: str


class SourceParrainages(BaseModel):
    """Le fichier de parrainages d'une élection, et comment le lire."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    election: str
    #: Chemin sous `raw/`.
    fichier: str
    format: Format
    #: Ce que la source publie. Sans ce champ, un consommateur compterait les
    #: lignes et conclurait que Nicolas Sarkozy a eu 500 parrainages en 2007.
    etendue: Etendue
    #: Au moins une. À partir de 2017, le Conseil publie par vagues pendant la
    #: campagne, et chaque parrainage cite la décision qui le concerne.
    publications: tuple[Publication, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _publications_ordonnees(self) -> SourceParrainages:
        dates = [publication.date for publication in self.publications]
        if any(suivante <= precedente for precedente, suivante in pairwise(dates)):
            raise ValueError(
                f"{self.election}: les publications doivent être datées une fois, "
                f"par date croissante"
            )
        return self

    def chemin(self, racine: Path | None = None) -> Path:
        """Le fichier source, sous `raw/`."""
        return (racine or RAW_DIR) / self.fichier

    def source_du(self, jour: dt.date) -> str | None:
        """La décision qui a publié les parrainages de cette date."""
        return next((p.source for p in self.publications if p.date == jour), None)


class _SeedParrainages(BaseModel):
    model_config = ConfigDict(extra="forbid")

    parrainages: tuple[SourceParrainages, ...] = ()

    @model_validator(mode="after")
    def _une_entree_par_election(self) -> _SeedParrainages:
        ids = [entree.election for entree in self.parrainages]
        doublons = sorted({i for i in ids if ids.count(i) > 1})
        if doublons:
            raise ValueError("deux entrées pour la même élection : " + ", ".join(doublons))
        return self


def load_parrainages(path: Path | None = None) -> tuple[SourceParrainages, ...]:
    """Charge la déclaration des sources de parrainages, validée.

    `path` vaut `seeds/parrainages.yaml` par défaut.
    """
    path = path or PARRAINAGES_SEED
    contenu = yaml.safe_load(path.read_text(encoding="utf-8"))
    return _SeedParrainages.model_validate(contenu).parrainages
