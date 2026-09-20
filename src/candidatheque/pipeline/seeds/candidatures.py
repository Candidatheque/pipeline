"""Candidatures aux élections, et participation aux tours.

Une candidature est à l'élection, pas au tour : on ne se porte pas candidat au
second tour, on s'y qualifie. Le Conseil constitutionnel arrête une liste, une
seule, pour le scrutin.

La participation à un tour, elle, se rattache au tour, et porte la ou les
sources qui l'établissent — pour les élections passées, la décision qui arrête
la liste du premier tour puis celle des candidats habilités au second.

Le nom n'est pas répété dans le seed : il se déduit du registre des personnes.
On ne le saisit que s'il diffère, c'est-à-dire si la personne a porté un autre
nom lors de ce scrutin. L'exception devient ainsi visible, au lieu de se perdre
parmi les répétitions.

Le nom publié, lui, est toujours celui porté lors du scrutin : la publication le
résout depuis le registre quand il n'est pas saisi.

L'état d'une candidature est une trajectoire, pas un instantané : une suite
datée et sourcée. Une candidature déclarée puis abandonnée garde trace de sa
déclaration, et une candidature validée garde qui l'avait annoncée. L'état
courant est le dernier élément, il n'est pas stocké à part.
"""

from __future__ import annotations

import datetime as dt
from enum import StrEnum
from itertools import pairwise
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


class ChangementEtat(BaseModel):
    """Un état par lequel la candidature est passée, à sa date et avec sa source.

    L'état courant n'est pas stocké : c'est le dernier de la trajectoire. Le
    stocker en plus serait une donnée dérivée, qui finirait par diverger.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    etat: Etat
    #: Date à laquelle la candidature a pris cet état, telle que la source
    #: l'établit — la date de la décision, celle de l'annonce. Jamais une date
    #: de traitement.
    #:
    #: Facultative : une source peut établir qu'une candidature a été retirée
    #: sans dire quand. Ne pas connaître la date est un fait ; en inventer une
    #: serait une faute. L'ordre de la liste fait alors foi.
    date: dt.date | None = None
    sources: tuple[str, ...] = Field(min_length=1)


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
    #: Absent quand il vaut celui du registre, ce qui est le cas courant. Saisi
    #: seulement quand la personne a porté un autre nom à ce scrutin.
    nom_complet: str | None = Field(default=None, min_length=1)
    #: La trajectoire de la candidature, dans l'ordre. Au moins un état.
    etats: tuple[ChangementEtat, ...] = Field(min_length=1)
    #: Les tours auxquels la candidature a pris part. Vide tant qu'aucun tour
    #: n'a eu lieu : quelqu'un qui se déclare puis renonce n'en a aucun.
    tours: tuple[Participation, ...] = ()

    @property
    def etat(self) -> Etat:
        """L'état courant : le dernier de la trajectoire."""
        return self.etats[-1].etat

    @model_validator(mode="after")
    def _trajectoire_chronologique(self) -> Candidature:
        dates = [c.date for c in self.etats if c.date is not None]
        if any(suivante < precedente for precedente, suivante in pairwise(dates)):
            raise ValueError(
                f"{self.personne}: les états datés doivent être listés par date croissante, "
                f"trouvé {[str(d) for d in dates]}"
            )

        # Deux fois le même état d'affilée ne dit rien de plus que le premier.
        etats = [changement.etat for changement in self.etats]
        for precedent, suivant in pairwise(etats):
            if precedent == suivant:
                raise ValueError(f"{self.personne}: état « {suivant} » répété d'affilée")

        return self

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
