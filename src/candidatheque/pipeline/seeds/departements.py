"""Départements et collectivités, pour normaliser ce que les sources écrivent.

Quarante ans de publications désignent le même département de trois façons :
un numéro jusqu'en 2007, un nom en capitales en 2012, un nom en casse normale
depuis 2017. Le Journal officiel y ajoute ses propres accidents — « HAUTS-DESEINE »
quand l'impression a mangé le trait d'union, « 68i » quand elle a pris la
parenthèse pour un i.

Ce registre n'est pas publié. Il sert à ramener ces formes au code INSEE
d'aujourd'hui, et rien d'autre ne le regarde.

Un piège vaut d'être dit : les numéros ultramarins ont changé de sens. Avant
que Saint-Barthélemy et Saint-Martin ne reçoivent 977 et 978 en 2007, ces
numéros désignaient Wallis-et-Futuna et la Nouvelle-Calédonie. Un parrainage
wallisien de 1995 publié à Saint-Barthélemy serait faux, et rien dans la donnée
ne le signalerait : `codes_anciens` existe pour cela.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from candidatheque.pipeline.paths import DEPARTEMENTS_SEED

#: Deux chiffres, « 2A » ou « 2B » pour la Corse, trois chiffres outre-mer.
CODE = re.compile(r"^(?:\d{2}|2[AB]|9[78]\d)$")


class CodeAncien(BaseModel):
    """Un numéro qu'une source ancienne emploie, et qui a changé de sens depuis."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str
    #: La première année où le numéro ne désigne plus cette collectivité. Une
    #: source antérieure se résout ici, une source postérieure au code courant.
    jusqu_en: int = Field(ge=1958, le=2100)

    @field_validator("code")
    @classmethod
    def _code_bien_forme(cls, value: str) -> str:
        if not CODE.match(value):
            raise ValueError(f"code INSEE attendu : {value!r}")
        return value


class Departement(BaseModel):
    """Un département ou une collectivité, sous son code INSEE courant."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str
    #: L'orthographe de référence, accents et traits d'union compris. C'est
    #: elle qui sert de point de comparaison aux formes abîmées.
    nom: str = Field(min_length=1)
    #: Les numéros qu'une source ancienne emploie pour cette collectivité et
    #: qui en désignent une autre depuis.
    codes_anciens: tuple[CodeAncien, ...] = ()

    @field_validator("code")
    @classmethod
    def _code_bien_forme(cls, value: str) -> str:
        if not CODE.match(value):
            raise ValueError(f"code INSEE attendu, par exemple « 59 » ou « 2A » : {value!r}")
        return value


class Correction(BaseModel):
    """Une forme qu'aucune règle ne résout, et le code qu'elle désigne.

    Le motif n'est pas un ornement : c'est lui qui se relit en revue. Une
    correction sans justification vérifiable dans la donnée serait une
    devinette écrite en dur.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    #: La forme exacte que la source écrit.
    brut: str = Field(min_length=1)
    code: str
    #: Ce qui établit le code, en général la commune nommée à côté.
    motif: str = Field(min_length=20)

    @field_validator("code")
    @classmethod
    def _code_bien_forme(cls, value: str) -> str:
        if not CODE.match(value):
            raise ValueError(f"code INSEE attendu : {value!r}")
        return value


class _SeedDepartements(BaseModel):
    model_config = ConfigDict(extra="forbid")

    departements: tuple[Departement, ...]
    corrections: tuple[Correction, ...] = ()

    @model_validator(mode="after")
    def _aucun_code_en_double(self) -> _SeedDepartements:
        """Un code ne peut désigner qu'une collectivité à une date donnée.

        Un numéro courant et un numéro ancien peuvent coïncider — « 977 » est
        Saint-Barthélemy aujourd'hui et fut Wallis-et-Futuna — et c'est
        précisément ce que `jusqu_en` départage. Deux courants ou deux anciens
        identiques, en revanche, rendraient la résolution dépendante de l'ordre
        du fichier, ce qui ne se verrait qu'au moment où deux territoires se
        mélangeraient.
        """
        for champ, codes in (
            ("courant", [d.code for d in self.departements]),
            ("ancien", [a.code for d in self.departements for a in d.codes_anciens]),
        ):
            doubles = {c for c in codes if codes.count(c) > 1}
            if doubles:
                raise ValueError(f"code {champ} en double : {sorted(doubles)}")
        return self


    @model_validator(mode="after")
    def _les_corrections_visent_un_departement_connu(self) -> _SeedDepartements:
        """Corriger vers un code absent du registre ne corrigerait rien."""
        connus = {d.code for d in self.departements}
        for correction in self.corrections:
            if correction.code not in connus:
                raise ValueError(
                    f"la correction de {correction.brut!r} vise {correction.code!r}, "
                    "qui n'est pas au registre"
                )
        return self


def load_departements(path: Path | None = None) -> tuple[Departement, ...]:
    """Le registre des départements, validé."""
    return _charger(path).departements


def load_corrections(path: Path | None = None) -> tuple[Correction, ...]:
    """Les formes corrigées à la main, validées."""
    return _charger(path).corrections


def _charger(path: Path | None = None) -> _SeedDepartements:
    chemin = path or DEPARTEMENTS_SEED
    contenu = yaml.safe_load(chemin.read_text(encoding="utf-8")) or {}
    return _SeedDepartements.model_validate(contenu)
