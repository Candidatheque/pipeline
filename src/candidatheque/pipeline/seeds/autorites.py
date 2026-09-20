"""Autorités dont on accepte de citer les publications.

Toute source doit relever d'une autorité listée : l'identifiant d'une source
commence par celui de son autorité, et son URL doit être servie par l'un de ses
domaines. Citer un site absent de la liste fait échouer la validation, ce qui
est le but — ajouter une autorité est une décision prise en revue, pas un effet
de bord de la saisie d'une donnée.
"""

from __future__ import annotations

import re
from enum import StrEnum
from pathlib import Path
from urllib.parse import urlparse

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from candidatheque.pipeline.paths import AUTORITES_SEED

AUTORITE_ID = re.compile(r"^[a-z][a-z0-9-]*$")


class Nature(StrEnum):
    """La relation entre l'autorité et le fait qu'elle établit.

    Ce n'est pas un classement. Une déclaration de candidature publiée par le
    parti du candidat vaut mieux qu'un article de presse qui la rapporte : le
    parti est l'auteur de l'acte. Le même site ne vaudrait rien pour établir le
    score de ce candidat. La fiabilité se juge donc sur le couple source-fait,
    pas sur la source seule — d'où une nature qui décrit la relation et laisse
    le consommateur conclure.
    """

    #: L'institution qui produit le fait par son acte même. Une décision du
    #: Conseil constitutionnel ne rapporte pas la liste des candidats, elle
    #: l'arrête.
    OFFICIELLE = "officielle"
    #: L'organisation ou la personne que le fait concerne : un parti qui annonce
    #: son candidat, un candidat qui annonce son retrait. Source primaire d'une
    #: déclaration, et juge et partie sur tout le reste.
    PARTIE_PRENANTE = "partie-prenante"
    #: Un média à responsabilité éditoriale identifiée, extérieur au fait.
    PRESSE = "presse"
    #: Une synthèse collaborative et révisable, qui cite ses propres sources.
    #: Utile pour trouver, faible pour établir.
    ENCYCLOPEDIQUE = "encyclopedique"


class Autorite(BaseModel):
    """Un organisme dont on cite les publications."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    nom: str = Field(min_length=1)
    nature: Nature
    #: Les domaines qui servent ses publications. Une URL de source doit être
    #: servie par l'un d'eux, ou par un de leurs sous-domaines.
    domaines: tuple[str, ...] = Field(min_length=1)

    @field_validator("id")
    @classmethod
    def _id_bien_forme(cls, value: str) -> str:
        if not AUTORITE_ID.match(value):
            raise ValueError(f"identifiant d'autorité attendu en minuscules : {value!r}")
        return value

    @field_validator("domaines")
    @classmethod
    def _domaines_bien_formes(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        for domaine in value:
            if "/" in domaine or domaine.startswith("http"):
                raise ValueError(f"domaine attendu sans schéma ni chemin : {domaine!r}")
        return value

    def sert(self, url: str) -> bool:
        """Cette autorité sert-elle cette URL ?

        Un sous-domaine convient : `www.lemonde.fr` relève de `lemonde.fr`.
        """
        hote = (urlparse(url).hostname or "").lower()
        return any(hote == d or hote.endswith("." + d) for d in self.domaines)


class _SeedAutorites(BaseModel):
    model_config = ConfigDict(extra="forbid")

    autorites: tuple[Autorite, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _identifiants_et_domaines_uniques(self) -> _SeedAutorites:
        ids = [autorite.id for autorite in self.autorites]
        doublons = sorted({i for i in ids if ids.count(i) > 1})
        if doublons:
            raise ValueError("identifiants d'autorité en double : " + ", ".join(doublons))

        # Un domaine partagé rendrait l'attribution d'une URL ambiguë.
        domaines = [d for autorite in self.autorites for d in autorite.domaines]
        partages = sorted({d for d in domaines if domaines.count(d) > 1})
        if partages:
            raise ValueError("domaines revendiqués par deux autorités : " + ", ".join(partages))

        return self


def load_autorites(path: Path | None = None) -> tuple[Autorite, ...]:
    """Charge la liste des autorités de confiance, validée.

    `path` vaut `seeds/autorites.yaml` par défaut.
    """
    path = path or AUTORITES_SEED
    contenu = yaml.safe_load(path.read_text(encoding="utf-8"))
    return _SeedAutorites.model_validate(contenu).autorites
