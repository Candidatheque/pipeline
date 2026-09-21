"""Les fonctions occupées par les candidats, datées et sourcées.

Le seed tient la biographie entière. Le filtrage par élection — ne garder que
ce qui avait commencé avant le premier tour — se fait à la publication : une
même fonction sert à plusieurs candidatures, et la saisir une fois évite
qu'elle diverge de l'une à l'autre.
"""

from __future__ import annotations

import datetime as dt
from enum import StrEnum
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from candidatheque.pipeline.paths import FONCTIONS_SEED
from candidatheque.pipeline.seeds.personnes import PERSONNE_ID


class Fonction(StrEnum):
    """Vocabulaire fixe des fonctions.

    Un renommage garde deux codes, comme pour les mandats des parrains : le
    conseiller général est devenu conseiller départemental en 2015, et les
    confondre effacerait la réforme.
    """

    PRESIDENT_DE_LA_REPUBLIQUE = "president-de-la-republique"
    PREMIER_MINISTRE = "premier-ministre"
    MINISTRE = "ministre"
    MINISTRE_DELEGUE = "ministre-delegue"
    SECRETAIRE_D_ETAT = "secretaire-d-etat"
    DEPUTE = "depute"
    SENATEUR = "senateur"
    DEPUTE_EUROPEEN = "depute-europeen"
    MAIRE = "maire"
    CONSEILLER_MUNICIPAL = "conseiller-municipal"
    CONSEILLER_GENERAL = "conseiller-general"
    CONSEILLER_DEPARTEMENTAL = "conseiller-departemental"
    CONSEILLER_REGIONAL = "conseiller-regional"
    PRESIDENT_DE_CONSEIL_GENERAL = "president-de-conseil-general"
    PRESIDENT_DE_CONSEIL_DEPARTEMENTAL = "president-de-conseil-departemental"
    PRESIDENT_DE_CONSEIL_REGIONAL = "president-de-conseil-regional"


#: Les fonctions dont le titre ne dit pas tout : le décret nomme un ministre
#: « de l'Intérieur », et c'est ce portefeuille qu'on veut lire.
GOUVERNEMENTALES = frozenset(
    {Fonction.MINISTRE, Fonction.MINISTRE_DELEGUE, Fonction.SECRETAIRE_D_ETAT}
)

#: Fonctions nationales, sans territoire. Un député européen n'en a pas non
#: plus : la circonscription unique de 1979 à 2004, et de nouveau depuis 2019,
#: rendrait le champ vide une fois sur deux.
SANS_RESSORT = GOUVERNEMENTALES | {
    Fonction.PRESIDENT_DE_LA_REPUBLIQUE,
    Fonction.PREMIER_MINISTRE,
    Fonction.DEPUTE_EUROPEEN,
}

#: Mandats locaux : les seuls pour lesquels une source encyclopédique est
#: admise. Pour les autres, l'institution publie la liste de ses membres, et
#: citer Wikidata à sa place serait citer une copie.
LOCALES = frozenset(
    {
        Fonction.MAIRE,
        Fonction.CONSEILLER_MUNICIPAL,
        Fonction.CONSEILLER_GENERAL,
        Fonction.CONSEILLER_DEPARTEMENTAL,
        Fonction.CONSEILLER_REGIONAL,
        Fonction.PRESIDENT_DE_CONSEIL_GENERAL,
        Fonction.PRESIDENT_DE_CONSEIL_DEPARTEMENTAL,
        Fonction.PRESIDENT_DE_CONSEIL_REGIONAL,
    }
)


class Occupation(BaseModel):
    """Une fonction tenue par une personne, entre deux dates."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    fonction: Fonction
    ressort: str | None = Field(default=None, min_length=1)
    intitule: str | None = Field(default=None, min_length=1)
    debut: dt.date
    #: Absente tant que la fonction est en cours.
    fin: dt.date | None = None
    sources: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _champs_selon_la_fonction(self) -> Occupation:
        if self.fonction in SANS_RESSORT and self.ressort is not None:
            raise ValueError(f"{self.fonction} : fonction sans ressort, « {self.ressort} » en trop")
        if self.fonction not in SANS_RESSORT and self.ressort is None:
            raise ValueError(f"{self.fonction} : ressort manquant")
        if self.fonction in GOUVERNEMENTALES and self.intitule is None:
            raise ValueError(f"{self.fonction} : intitulé du portefeuille manquant")
        if self.fonction not in GOUVERNEMENTALES and self.intitule is not None:
            raise ValueError(f"{self.fonction} : l'intitulé est réservé aux membres du gouvernement")
        if self.fin is not None and self.fin < self.debut:
            raise ValueError(f"{self.fonction} : fin ({self.fin}) antérieure au début ({self.debut})")
        return self


class Parcours(BaseModel):
    """Les fonctions d'une personne, par date de début."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    personne: str
    fonctions: tuple[Occupation, ...] = Field(min_length=1)

    @field_validator("personne")
    @classmethod
    def _personne_bien_formee(cls, value: str) -> str:
        if not PERSONNE_ID.match(value):
            raise ValueError(f"identifiant attendu sous la forme « PE-0001 » : {value!r}")
        return value

    @model_validator(mode="after")
    def _chronologie(self) -> Parcours:
        debuts = [occupation.debut for occupation in self.fonctions]
        if debuts != sorted(debuts):
            raise ValueError(f"{self.personne} : fonctions à lister par date de début")

        # Deux mandats successifs peuvent se recouvrir de quelques semaines :
        # pour les législatures anciennes, Sycomore fait commencer un mandat le
        # jour de l'élection, avant la fin officielle du précédent. On garde
        # les dates de la source. Un mandat contenu dans un autre, ou ouvert
        # alors que le précédent n'a pas de fin, est en revanche un doublon.
        vues: dict[tuple[Fonction, str | None, str | None], Occupation] = {}
        for occupation in self.fonctions:
            cle = (occupation.fonction, occupation.ressort, occupation.intitule)
            precedente = vues.get(cle)
            if precedente is not None and (
                precedente.fin is None
                or (occupation.fin is not None and occupation.fin <= precedente.fin)
            ):
                raise ValueError(
                    f"{self.personne} : {occupation.fonction} du {occupation.debut} "
                    f"compris dans le précédent"
                )
            vues[cle] = occupation
        return self


class _SeedFonctions(BaseModel):
    model_config = ConfigDict(extra="forbid")

    parcours: tuple[Parcours, ...] = ()

    @model_validator(mode="after")
    def _une_entree_par_personne(self) -> _SeedFonctions:
        ids = [parcours.personne for parcours in self.parcours]
        doublons = sorted({i for i in ids if ids.count(i) > 1})
        if doublons:
            raise ValueError("personnes listées deux fois : " + ", ".join(doublons))
        if ids != sorted(ids):
            raise ValueError("les personnes doivent être listées par identifiant croissant")
        return self


def load_fonctions(path: Path | None = None) -> tuple[Parcours, ...]:
    """Charge les parcours, validés, par identifiant de personne croissant.

    `path` vaut `seeds/fonctions.yaml` par défaut.
    """
    path = path or FONCTIONS_SEED
    contenu = yaml.safe_load(path.read_text(encoding="utf-8"))
    return _SeedFonctions.model_validate(contenu).parcours
