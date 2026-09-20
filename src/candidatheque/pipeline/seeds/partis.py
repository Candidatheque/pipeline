"""Registre des partis politiques.

Un parti se présente à plusieurs élections, et l'identifiant le suit d'un
scrutin à l'autre. Son nom, lui, appartient à la candidature : le Front
national est devenu Rassemblement national en 2018, et une candidature de 2012
doit garder l'étiquette portée cette année-là. Même partage que pour les
personnes — le registre dit qui est qui, la candidature dit ce qui était écrit
sur le bulletin.

Le registre n'est pas publié : rapprocher les candidatures d'un même parti ne
demande que l'identifiant.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from candidatheque.pipeline.paths import PARTIS_SEED

PARTI_ID = re.compile(r"^PA-(?P<numero>\d{4})$")
WIKIDATA_ID = re.compile(r"^Q[1-9]\d*$")


class Parti(BaseModel):
    """Un parti ou mouvement politique, identifié par « PA-<numéro> »."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    #: Orthographe de référence, pour la relecture. Le nom publié est celui
    #: porté lors du scrutin, qui appartient à la candidature.
    nom_complet: str = Field(min_length=1)
    #: Le sigle sous lequel le parti est couramment désigné, quand il en a un —
    #: on dit « le PCF », rarement « le Parti communiste français ». C'est un
    #: fait publié, pas une abréviation qu'on lui invente : il vient de la
    #: propriété P1813 de Wikidata, et reste absent quand elle l'est.
    sigle: str | None = Field(default=None, min_length=1)
    wikidata: str | None = None

    @field_validator("id")
    @classmethod
    def _id_bien_forme(cls, value: str) -> str:
        if not PARTI_ID.match(value):
            raise ValueError(f"identifiant attendu sous la forme « PA-0001 » : {value!r}")
        return value

    @field_validator("nom_complet", "sigle")
    @classmethod
    def _non_vide(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("un nom vide ne sert à rien en relecture")
        return value

    @field_validator("wikidata")
    @classmethod
    def _wikidata_bien_forme(cls, value: str | None) -> str | None:
        if value is not None and not WIKIDATA_ID.match(value):
            raise ValueError(f"identifiant Wikidata invalide : {value!r}")
        return value

    @property
    def numero(self) -> int:
        match = PARTI_ID.match(self.id)
        assert match is not None  # garanti par la validation du champ
        return int(match.group("numero"))


class _SeedPartis(BaseModel):
    model_config = ConfigDict(extra="forbid")

    partis: tuple[Parti, ...] = ()

    @model_validator(mode="after")
    def _numerotation_et_identifiants(self) -> _SeedPartis:
        numeros = [parti.numero for parti in self.partis]
        doublons = sorted({n for n in numeros if numeros.count(n) > 1})
        if doublons:
            raise ValueError(
                "identifiants de parti en double : " + ", ".join(f"PA-{n:04d}" for n in doublons)
            )
        if numeros != sorted(numeros):
            raise ValueError("les partis doivent être listés par numéro croissant")

        qids = [p.wikidata for p in self.partis if p.wikidata is not None]
        partages = sorted({q for q in qids if qids.count(q) > 1})
        if partages:
            raise ValueError("identifiants Wikidata partagés entre partis : " + ", ".join(partages))

        return self


def load_partis(path: Path | None = None) -> tuple[Parti, ...]:
    """Charge le registre des partis, validé, par numéro croissant.

    `path` vaut `seeds/partis.yaml` par défaut.
    """
    path = path or PARTIS_SEED
    contenu = yaml.safe_load(path.read_text(encoding="utf-8"))
    return _SeedPartis.model_validate(contenu).partis
