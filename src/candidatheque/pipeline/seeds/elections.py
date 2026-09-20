"""Chargement et validation du seed des élections.

Le seed définit quelles élections existent et sous quel identifiant. Une erreur
ici se propagerait sans bruit jusqu'aux données publiées, d'où la validation
stricte.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from candidatheque.pipeline.paths import ELECTIONS_SEED

#: « PR » désigne le type de scrutin. Le groupe nommé sert à recouper l'année
#: déclarée dans le seed.
ELECTION_ID = re.compile(r"^PR-(?P<annee>\d{4})$")


class Election(BaseModel):
    """Une élection, identifiée par « PR-<année> ».

    L'identifiant sert tel quel de nom de répertoire à la publication.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    annee: int = Field(ge=1965, le=2100)

    @field_validator("id")
    @classmethod
    def _id_bien_forme(cls, value: str) -> str:
        if not ELECTION_ID.match(value):
            raise ValueError(f"identifiant attendu sous la forme « PR-<année> » : {value!r}")
        return value

    @model_validator(mode="after")
    def _annee_concorde_avec_l_identifiant(self) -> Election:
        match = ELECTION_ID.match(self.id)
        assert match is not None  # garanti par la validation du champ
        if int(match.group("annee")) != self.annee:
            raise ValueError(
                f"{self.id}: l'année déclarée ({self.annee}) contredit l'identifiant"
            )
        return self


class _SeedElections(BaseModel):
    model_config = ConfigDict(extra="forbid")

    elections: tuple[Election, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _identifiants_uniques_et_ordonnes(self) -> _SeedElections:
        annees = [election.annee for election in self.elections]

        doublons = sorted({annee for annee in annees if annees.count(annee) > 1})
        if doublons:
            raise ValueError(
                "plusieurs élections pour la même année : "
                + ", ".join(str(annee) for annee in doublons)
            )

        if annees != sorted(annees):
            raise ValueError("les élections doivent être listées par année croissante")

        return self


def load_elections(path: Path | None = None) -> tuple[Election, ...]:
    """Charge le seed, validé, par année croissante.

    `path` vaut `seeds/elections.yaml` par défaut.
    """
    path = path or ELECTIONS_SEED
    contenu = yaml.safe_load(path.read_text(encoding="utf-8"))
    return _SeedElections.model_validate(contenu).elections
