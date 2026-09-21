"""D'où viennent les résultats de chaque tour, version après version.

Un tour connaît plusieurs versions de ses résultats : ceux que le ministère de
l'Intérieur publie le soir du scrutin puis après recensement, ceux que le
Conseil constitutionnel déclare au premier tour puis proclame pour l'élection,
et, jusqu'en 1995, ceux que les tableaux annexés au Journal officiel rectifient
encore. L'écart entre deux versions est une information, pas un doublon.

Elles se rangent dans l'ordre des étapes du processus, et non dans celui de
leur publication : les résultats définitifs du ministère peuvent paraître après
la proclamation, et c'est pourtant elle qui fait foi. La dernière version d'un
tour fait donc foi par construction.

Seule la version du Conseil est collectée à ce jour. Le texte de ses décisions
est commité dans `raw/resultats/`, jamais téléchargé.
"""

from __future__ import annotations

import datetime as dt
from enum import StrEnum
from itertools import pairwise
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from candidatheque.pipeline.paths import RAW_DIR, RESULTATS_SEED


class CandidatSource(BaseModel):
    """Un nom tel que la décision l'écrit, et la personne qu'il désigne.

    Le rapprochement est déclaré ici plutôt que deviné à la lecture, comme pour
    les parrainages. La transcription de 1965 écrit « Jean-Louis
    TIXIER-VIGNANCOU » sans son R final, celle de 1988 « Ariette LAGUILLER »
    pour Arlette : un nom écrit noir sur blanc dans le seed se relit et se
    corrige, un seuil de ressemblance non.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    titre: str = Field(min_length=1)
    personne: str


class Etape(StrEnum):
    """Quelle version des résultats, dans l'ordre du processus.

    L'ordre de déclaration est celui des étapes : c'est lui qui range les
    versions d'un tour, et la dernière fait foi.
    """

    #: Les résultats que le ministère de l'Intérieur publie le soir du scrutin.
    RESULTATS_PROVISOIRES = "resultats-provisoires"
    #: Ceux qu'il publie après le recensement des votes.
    RESULTATS_DEFINITIFS = "resultats-definitifs"
    #: Ceux du Conseil constitutionnel : la déclaration du premier tour, la
    #: proclamation de l'élection. Nets des suffrages qu'il annule.
    PROCLAMATION = "proclamation"
    #: Ceux que les tableaux annexés au Journal officiel arrêtent en dernier,
    #: jusqu'en 1995.
    RECTIFICATION = "rectification"

    @property
    def rang(self) -> int:
        """La place de l'étape dans le processus."""
        return list(Etape).index(self)


class VersionResultats(BaseModel):
    """Une version des résultats d'un tour, et le document qui la porte."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    etape: Etape
    #: La date du document : celle de la décision pour le Conseil. Elle est
    #: publiée, mais ne range pas les versions.
    date: dt.date
    #: Chemin sous `raw/`.
    fichier: str
    #: La décision, dans le registre des sources.
    origine: str
    #: Tous les candidats du tour. Ils doivent y être tous : c'est ce qui
    #: garantit qu'aucune ligne de voix n'est ignorée. Leur ordre est indifférent,
    #: la publication suit celui du document.
    candidats: tuple[CandidatSource, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _un_candidat_une_fois(self) -> VersionResultats:
        for champ in ("titre", "personne"):
            valeurs = [getattr(candidat, champ) for candidat in self.candidats]
            doublons = sorted({v for v in valeurs if valeurs.count(v) > 1})
            if doublons:
                raise ValueError(f"{self.origine} : deux fois " + ", ".join(doublons))
        return self

    def chemin(self, racine: Path | None = None) -> Path:
        """Le texte de la décision, sous `raw/`."""
        return (racine or RAW_DIR) / self.fichier

    def personne_de(self, titre: str) -> str | None:
        """La personne que ce nom désigne."""
        return next((c.personne for c in self.candidats if c.titre == titre), None)


class TourResultats(BaseModel):
    """Les versions successives des résultats d'un tour."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    numero: int = Field(ge=1)
    #: Dans l'ordre des étapes, une version par étape : la dernière fait foi.
    versions: tuple[VersionResultats, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _versions_dans_l_ordre_des_etapes(self) -> TourResultats:
        rangs = [version.etape.rang for version in self.versions]
        if any(suivant <= precedent for precedent, suivant in pairwise(rangs)):
            raise ValueError(
                f"tour {self.numero} : les versions se rangent dans l'ordre des étapes, "
                f"une par étape — vu {[str(v.etape) for v in self.versions]}"
            )
        return self


class SourceResultats(BaseModel):
    """Les résultats d'une élection, tour par tour."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    election: str
    tours: tuple[TourResultats, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _tours_numerotes_dans_l_ordre(self) -> SourceResultats:
        numeros = [tour.numero for tour in self.tours]
        if numeros[0] != 1 or any(b != a + 1 for a, b in pairwise(numeros)):
            raise ValueError(
                f"{self.election} : les tours se numérotent à partir de 1 et dans l'ordre, "
                f"vu {numeros}"
            )
        return self


class _SeedResultats(BaseModel):
    model_config = ConfigDict(extra="forbid")

    resultats: tuple[SourceResultats, ...] = ()

    @model_validator(mode="after")
    def _une_entree_par_election(self) -> _SeedResultats:
        ids = [entree.election for entree in self.resultats]
        doublons = sorted({i for i in ids if ids.count(i) > 1})
        if doublons:
            raise ValueError("deux entrées pour la même élection : " + ", ".join(doublons))
        return self


def load_resultats(path: Path | None = None) -> tuple[SourceResultats, ...]:
    """Charge la déclaration des résultats, validée.

    `path` vaut `seeds/resultats.yaml` par défaut.
    """
    path = path or RESULTATS_SEED
    contenu = yaml.safe_load(path.read_text(encoding="utf-8"))
    return _SeedResultats.model_validate(contenu).resultats
