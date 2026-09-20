"""Chargement et validation du seed des élections.

Le seed définit quelles élections existent et sous quel identifiant. Une erreur
ici se propagerait sans bruit jusqu'aux données publiées, d'où la validation
stricte.
"""

from __future__ import annotations

import datetime as dt
import re
from itertools import pairwise
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from candidatheque.pipeline.paths import ELECTIONS_SEED

#: « PR » désigne le type de scrutin. Le groupe nommé sert à recouper l'année
#: déclarée dans le seed.
ELECTION_ID = re.compile(r"^PR-(?P<annee>\d{4})$")

WIKIDATA_ID = re.compile(r"^Q[1-9]\d*$")


class Tour(BaseModel):
    """Un tour de scrutin.

    `wikidata` reste souvent absent : Wikidata ne modélise les tours que pour
    une partie des élections.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    numero: int = Field(ge=1)
    date: dt.date
    wikidata: str | None = None

    @field_validator("wikidata")
    @classmethod
    def _wikidata_bien_forme(cls, value: str | None) -> str | None:
        if value is not None and not WIKIDATA_ID.match(value):
            raise ValueError(f"identifiant Wikidata invalide : {value!r}")
        return value


class Election(BaseModel):
    """Une élection, identifiée par « PR-<année> ».

    L'identifiant sert tel quel de nom de répertoire à la publication.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    annee: int = Field(ge=1965, le=2100)
    #: Obligatoire : les douze élections en ont un, y compris celle de 2027.
    #: Une élection nouvelle qui n'aurait pas encore d'élément Wikidata ferait
    #: échouer la validation, et ce serait une décision à prendre explicitement.
    wikidata: str
    #: Au moins un. Deux à chaque scrutin depuis 1965, mais une majorité absolue
    #: au premier tour en ferait un seul : le nombre n'est pas contraint.
    tours: tuple[Tour, ...] = Field(min_length=1)

    @field_validator("id")
    @classmethod
    def _id_bien_forme(cls, value: str) -> str:
        if not ELECTION_ID.match(value):
            raise ValueError(f"identifiant attendu sous la forme « PR-<année> » : {value!r}")
        return value

    @field_validator("wikidata")
    @classmethod
    def _wikidata_bien_forme(cls, value: str) -> str:
        if not WIKIDATA_ID.match(value):
            raise ValueError(f"identifiant Wikidata invalide : {value!r}")
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

    @model_validator(mode="after")
    def _tours_coherents(self) -> Election:
        numeros = [tour.numero for tour in self.tours]
        if numeros != list(range(1, len(numeros) + 1)):
            raise ValueError(
                f"{self.id}: les tours doivent être numérotés de 1 à {len(numeros)} "
                f"et listés dans l'ordre, trouvé {numeros}"
            )

        dates = [tour.date for tour in self.tours]
        if any(suivante <= precedente for precedente, suivante in pairwise(dates)):
            raise ValueError(f"{self.id}: les dates des tours doivent être strictement croissantes")

        if dates[0].year != self.annee:
            raise ValueError(
                f"{self.id}: le premier tour est daté de {dates[0].year}, "
                f"ce qui contredit l'année déclarée"
            )

        return self

    def tour(self, numero: int) -> Tour | None:
        """Le tour demandé, ou None s'il n'a pas eu lieu."""
        return next((t for t in self.tours if t.numero == numero), None)


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

        # Élections et tours confondus : un copier-coller d'un scrutin à l'autre
        # se repère là, et nulle part ailleurs.
        qids = [election.wikidata for election in self.elections]
        qids += [t.wikidata for e in self.elections for t in e.tours if t.wikidata is not None]
        partages = sorted({q for q in qids if qids.count(q) > 1})
        if partages:
            raise ValueError(
                "identifiants Wikidata employés deux fois : " + ", ".join(partages)
            )

        return self


def load_elections(path: Path | None = None) -> tuple[Election, ...]:
    """Charge le seed, validé, par année croissante.

    `path` vaut `seeds/elections.yaml` par défaut.
    """
    path = path or ELECTIONS_SEED
    contenu = yaml.safe_load(path.read_text(encoding="utf-8"))
    return _SeedElections.model_validate(contenu).elections
