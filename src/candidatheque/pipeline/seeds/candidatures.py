"""Candidatures aux élections, et participation aux tours.

Une candidature est à l'élection, pas au tour : on ne se porte pas candidat au
second tour, on s'y qualifie. Le Conseil constitutionnel arrête une liste, une
seule, pour le scrutin.

La participation à un tour, elle, se rattache au tour, et porte la ou les
sources qui l'établissent — pour les élections passées, la décision qui arrête
la liste du premier tour puis celle des candidats habilités au second.

Le nom n'est pas dénormalisé depuis le registre des personnes : c'est le nom
porté lors de ce scrutin. Une même personne peut se présenter sous deux noms à
deux élections, et chacun est exact à sa date.
"""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from candidatheque.pipeline.paths import CANDIDATURES_SEED


class Etat(StrEnum):
    """Où en est la candidature.

    Le décompte des parrainages n'est pas un état : il vaut pour toutes les
    candidatures d'une même période et relèvera d'un document propre.
    """

    #: Annoncée publiquement, sans validation d'aucune sorte.
    DECLAREE = "declaree"
    #: Figure sur la liste arrêtée par le Conseil constitutionnel.
    VALIDEE = "validee"
    #: La personne a renoncé après avoir annoncé.
    RETIREE = "retiree"
    #: N'a pas été retenue sur la liste officielle.
    ECARTEE = "ecartee"


class Participation(BaseModel):
    """La présence d'une candidature à un tour donné, et ce qui l'établit."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    numero: int = Field(ge=1)
    #: Identifiants du registre des sources. Au moins un : une participation
    #: sans provenance est invérifiable.
    sources: tuple[str, ...] = Field(min_length=1)


class Candidature(BaseModel):
    """Une personne se présentant à une élection."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    personne: str
    nom: str = Field(min_length=1)
    prenom: str = Field(min_length=1)
    etat: Etat
    tours: tuple[Participation, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _tours_ordonnes_et_uniques(self) -> Candidature:
        numeros = [participation.numero for participation in self.tours]
        if numeros != sorted(set(numeros)):
            raise ValueError(
                f"{self.personne}: les tours doivent être listés une fois, "
                f"par numéro croissant, trouvé {numeros}"
            )
        return self


class CandidaturesElection(BaseModel):
    """Toutes les candidatures d'une élection."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    election: str
    candidats: tuple[Candidature, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _une_candidature_par_personne(self) -> CandidaturesElection:
        ids = [candidat.personne for candidat in self.candidats]
        doublons = sorted({i for i in ids if ids.count(i) > 1})
        if doublons:
            raise ValueError(
                f"{self.election}: deux candidatures pour la même personne : "
                + ", ".join(doublons)
            )
        return self


class _SeedCandidatures(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidatures: tuple[CandidaturesElection, ...] = ()

    @model_validator(mode="after")
    def _une_entree_par_election(self) -> _SeedCandidatures:
        ids = [entree.election for entree in self.candidatures]
        doublons = sorted({i for i in ids if ids.count(i) > 1})
        if doublons:
            raise ValueError("deux entrées pour la même élection : " + ", ".join(doublons))
        return self


def load_candidatures(path: Path | None = None) -> tuple[CandidaturesElection, ...]:
    """Charge les candidatures, validées.

    `path` vaut `seeds/candidatures.yaml` par défaut.
    """
    path = path or CANDIDATURES_SEED
    contenu = yaml.safe_load(path.read_text(encoding="utf-8"))
    return _SeedCandidatures.model_validate(contenu).candidatures
