"""Registre des sources citées par les données publiées.

Une source est décrite une fois ici, et les données la citent par son
identifiant. La publication recopie la description complète à côté de chaque
donnée qui s'y rattache : le seed est optimisé pour la maintenance, les fichiers
publiés pour la lecture, et un consommateur n'a jamais de référence à résoudre.
"""

from __future__ import annotations

import datetime as dt
import re
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from candidatheque.pipeline.paths import SOURCES_SEED

#: « <autorité>:<identifiant chez elle> ». Le préfixe dit qui fait autorité, ce
#: qui suit est l'identifiant tel que cette autorité le publie.
SOURCE_ID = re.compile(r"^(?P<autorite>[a-z][a-z0-9-]*):(?P<externe>[A-Za-z0-9._-]+)$")


class Source(BaseModel):
    """Un document qui établit un fait publié."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    url: str
    #: De quoi il s'agit, en clair : l'intitulé de la décision, le titre de
    #: l'article. Ce qui permet de savoir ce qu'on cite sans ouvrir le lien.
    commentaire: str = Field(min_length=1)
    #: Saisie, jamais calculée à la publication. Une date d'horloge ferait bouger
    #: les fichiers publiés à chaque passage et viderait l'idempotence de son sens.
    consultee_le: dt.date

    @field_validator("id")
    @classmethod
    def _id_bien_forme(cls, value: str) -> str:
        if not SOURCE_ID.match(value):
            raise ValueError(
                f"identifiant attendu sous la forme « autorité:identifiant » : {value!r}"
            )
        return value

    @field_validator("url")
    @classmethod
    def _url_en_https(cls, value: str) -> str:
        if not value.startswith("https://"):
            raise ValueError(f"URL de source attendue en https : {value!r}")
        return value

    @property
    def autorite(self) -> str:
        match = SOURCE_ID.match(self.id)
        assert match is not None  # garanti par la validation du champ
        return match.group("autorite")


class _SeedSources(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sources: tuple[Source, ...] = ()

    @model_validator(mode="after")
    def _identifiants_uniques(self) -> _SeedSources:
        ids = [source.id for source in self.sources]
        doublons = sorted({i for i in ids if ids.count(i) > 1})
        if doublons:
            raise ValueError("identifiants de source en double : " + ", ".join(doublons))
        return self


def load_sources(path: Path | None = None) -> tuple[Source, ...]:
    """Charge le registre des sources, validé.

    `path` vaut `seeds/sources.yaml` par défaut.
    """
    path = path or SOURCES_SEED
    contenu = yaml.safe_load(path.read_text(encoding="utf-8"))
    return _SeedSources.model_validate(contenu).sources
