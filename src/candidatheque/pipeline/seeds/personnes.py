"""Registre des personnes : attribution et unicité des identifiants.

Une personne se présente à plusieurs élections, et l'identifiant la suit d'un
scrutin à l'autre. Le nom qui fait foi reste celui de la candidature : il peut
changer entre deux élections, et c'est celui porté au moment du scrutin qui
compte. Le registre porte la même forme — un nom entier — mais pas le même
statut : une orthographe de référence, pour savoir qui est qui en relisant.

Il n'est pas publié. Regrouper les candidatures d'une même personne ne demande
que l'identifiant.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from candidatheque.pipeline.paths import PERSONNES_SEED

#: Quatre chiffres suffisent largement : on compte les candidats aux
#: présidentielles par centaines depuis 1965.
PERSONNE_ID = re.compile(r"^PE-(?P<numero>\d{4})$")

WIKIDATA_ID = re.compile(r"^Q[1-9]\d*$")


class Personne(BaseModel):
    """Une personne, identifiée par « PE-<numéro> »."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    #: De qui il s'agit, pour la relecture humaine. Même forme que dans une
    #: candidature, mais pas le même statut : le nom publié est celui porté lors
    #: du scrutin, qui appartient à la candidature. Ici, c'est l'orthographe de
    #: référence.
    #: Le nom entier, tel que la source l'écrit. Non découpé en nom et prénom :
    #: le découpage est une inférence, pas une donnée, et il se trompe dès qu'un
    #: nom sort du cas courant — « Jean Claude Matry » a deux prénoms, « Super
    #: Châtaigne » est un pseudonyme, « Fessard de Foucault » porte une
    #: particule au milieu. Qui veut la structure la tire de Wikidata, pour les
    #: personnes qui y ont un élément.
    nom_complet: str
    wikidata: str | None = None

    @field_validator("id")
    @classmethod
    def _id_bien_forme(cls, value: str) -> str:
        if not PERSONNE_ID.match(value):
            raise ValueError(f"identifiant attendu sous la forme « PE-0001 » : {value!r}")
        return value

    @field_validator("nom_complet")
    @classmethod
    def _non_vide(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("le nom sert à la relecture, il ne peut pas être vide")
        return value

    @field_validator("wikidata")
    @classmethod
    def _wikidata_bien_forme(cls, value: str | None) -> str | None:
        if value is not None and not WIKIDATA_ID.match(value):
            raise ValueError(f"identifiant Wikidata invalide : {value!r}")
        return value

    @property
    def numero(self) -> int:
        match = PERSONNE_ID.match(self.id)
        assert match is not None  # garanti par la validation du champ
        return int(match.group("numero"))


class _SeedPersonnes(BaseModel):
    model_config = ConfigDict(extra="forbid")

    personnes: tuple[Personne, ...] = ()

    @model_validator(mode="after")
    def _numerotation_croissante(self) -> _SeedPersonnes:
        numeros = [personne.numero for personne in self.personnes]

        doublons = sorted({n for n in numeros if numeros.count(n) > 1})
        if doublons:
            raise ValueError(
                "identifiants de personne en double : "
                + ", ".join(f"PE-{n:04d}" for n in doublons)
            )

        # Strictement croissant : l'attribution se lit dans l'ordre, et un trou
        # saute aux yeux en revue.
        if numeros != sorted(numeros):
            raise ValueError("les personnes doivent être listées par numéro croissant")

        qids = [p.wikidata for p in self.personnes if p.wikidata is not None]
        partages = sorted({q for q in qids if qids.count(q) > 1})
        if partages:
            raise ValueError(
                "identifiants Wikidata partagés entre personnes : " + ", ".join(partages)
            )

        return self


def load_personnes(path: Path | None = None) -> tuple[Personne, ...]:
    """Charge le registre des personnes, validé, par numéro croissant.

    `path` vaut `seeds/personnes.yaml` par défaut.
    """
    path = path or PERSONNES_SEED
    contenu = yaml.safe_load(path.read_text(encoding="utf-8"))
    return _SeedPersonnes.model_validate(contenu).personnes
