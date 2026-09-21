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

Le texte des décisions du Conseil est commité dans `raw/resultats/`, les
résultats du ministère dans `raw/resultats/interieur/`, jamais téléchargés.
"""

from __future__ import annotations

import datetime as dt
from enum import StrEnum
from itertools import pairwise
from pathlib import Path
from typing import Literal

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


class Format(StrEnum):
    """Comment lire le fichier d'une version."""

    #: Le texte d'une décision du Conseil constitutionnel, tiré de son site par
    #: `outils/decision_cc_en_texte.py`.
    DECISION = "decision"
    #: Les CSV du ministère de l'Intérieur, recopiés de ses fichiers par
    #: `outils/interieur_en_csv.py` : un national, et un par département.
    INTERIEUR = "interieur"
    #: Les tableaux annexés à une proclamation au Journal officiel, extraits
    #: de l'édition par `outils/tableau_pdf_en_texte.py`.
    TABLEAU_JO = "tableau-jo"


class TableauJO(BaseModel):
    """Un tableau du Journal officiel : ses pages, et ce que porte chaque colonne.

    Un tableau coupé en deux moitiés sur des pages alternées — le premier tour
    de 1995 — se déclare en deux tableaux, que la lecture réunit département
    par département.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    #: Les pages du texte extrait, à partir de 1, séparées par des sauts de page.
    pages: tuple[int, ...] = Field(min_length=1)
    #: Dans l'ordre du tableau : « inscrits », « votants », « suffrages_exprimes »,
    #: « total » pour la colonne qui redit les exprimés en fin de seconde moitié,
    #: et pour un candidat le titre que `candidats` rapproche d'une personne.
    colonnes: tuple[str, ...] = Field(min_length=2)
    #: Comment le tableau sépare les milliers : « 262.000 » ou « 284 999 ».
    milliers: Literal["point", "espace"]
    #: Le tableau imprime-t-il un pourcentage après les voix de chaque candidat ?
    pourcentages: bool = False


class CorrectionJO(BaseModel):
    """Une ligne que la lecture ne sait pas établir, lue à la main sur l'image.

    Elle n'entre ici que lorsque les contrôles ne suffisent pas : plusieurs
    lignes illisibles dans un même tableau, que le total ne départage plus.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    #: Le code du département, ou « etranger » pour les Français établis hors
    #: de France.
    departement: str
    #: Colonne → valeur, pour les seules colonnes corrigées.
    valeurs: dict[str, int] = Field(min_length=1)
    motif: str = Field(min_length=20)


class VersionResultats(BaseModel):
    """Une version des résultats d'un tour, et le document qui la porte."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    etape: Etape
    format: Format = Format.DECISION
    #: La date du document : celle de la décision pour le Conseil. Elle est
    #: publiée, mais ne range pas les versions.
    date: dt.date
    #: Chemin sous `raw/` : la décision, ou les résultats nationaux.
    fichier: str
    #: Chemin sous `raw/` des résultats par département, quand la source en
    #: publie.
    departements: str | None = None
    #: Les tableaux du Journal officiel, pour le format `tableau-jo`.
    tableaux: tuple[TableauJO, ...] = ()
    #: Les libellés que le scan a trop abîmés pour que le registre des
    #: départements les reconnaisse — « CARD » pour le Gard en 1981 —, rapprochés
    #: ici de leur code, lu sur l'ordre du tableau.
    libelles: dict[str, str] = Field(default_factory=dict)
    #: Les lignes lues à la main, pour le format `tableau-jo`.
    corrections: tuple[CorrectionJO, ...] = ()
    #: La décision ou le jeu de données, dans le registre des sources.
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
        """Le fichier national, ou le texte de la décision, sous `raw/`."""
        return (racine or RAW_DIR) / self.fichier

    def chemin_departements(self, racine: Path | None = None) -> Path | None:
        """Le fichier départemental, sous `raw/`, quand il y en a un."""
        return (racine or RAW_DIR) / self.departements if self.departements else None

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
