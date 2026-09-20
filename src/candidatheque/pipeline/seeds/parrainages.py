"""D'où viennent les parrainages, et sous quelle forme les lire.

Le fichier source est commité dans ``raw/``, jamais téléchargé : ces documents
sont historiques et figés, et un fichier suivi par git est un meilleur
archivage qu'une copie reconstruite à chaque passage.

Le format déclaré ici est ce qui rend le code générique : la pipeline ne connaît
que des formats, jamais des années. Ajouter une élection, c'est ajouter une
entrée ; écrire du code n'est nécessaire que si sa forme est inédite.
"""

from __future__ import annotations

import datetime as dt
from enum import StrEnum
from itertools import pairwise
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from candidatheque.pipeline.paths import PARRAINAGES_SEED, RAW_DIR


class Format(StrEnum):
    """Comment lire le fichier source."""

    #: Un tableau, une entrée par parrainage. Forme de 2022.
    JSON_PLAT = "json-plat"
    #: Un tableau de candidats, chacun portant ses parrainages. Forme de 2017,
    #: aux champs accentués et aux dates en jj/mm/aaaa.
    JSON_PAR_CANDIDAT = "json-par-candidat"
    #: Le texte du Journal officiel, en prose continue. Extrait du PDF une
    #: fois hors ligne par `outils/pdf_en_texte.py` : la pipeline ne lit pas de
    #: PDF, elle relit le texte commité comme n'importe quelle donnée.
    TEXTE_JO = "texte-jo"


class Etendue(StrEnum):
    """Ce que la source publie : tout, ou un échantillon.

    Avant la réforme de 2016, la loi n'imposait de publier que 500 présentations
    par candidat, tirées au sort. Les compter donnerait donc 500 pour chacun, ce
    qui n'est pas leur nombre de parrainages. Depuis 2017, la publication est
    intégrale, et le compte a un sens.
    """

    #: Tous les parrainages reçus. À partir de 2017.
    INTEGRALE = "integrale"
    #: 500 par candidat, tirés au sort par le Conseil constitutionnel. Vérifié :
    #: 2007 et 2012 en comptent exactement 500 pour chaque candidat.
    TIRAGE_AU_SORT = "tirage-au-sort"


class CandidatSource(BaseModel):
    """Un nom tel que la source l'écrit, et la personne qu'il désigne.

    Le rapprochement est déclaré ici plutôt que deviné à la lecture. Les titres
    du Journal officiel sortent parfois abîmés de l'impression — « M. Michel
    DE3RE. », « Madame ArU 3 LAGUILLER » —, et une ressemblance approchée
    finirait par rapprocher deux homonymes. Un nom écrit noir sur blanc dans le
    seed se relit et se corrige ; un seuil de similarité, non.

    `personne` est vide pour qui a reçu des présentations sans être au registre
    : Thomas PESQUET et Édouard PHILIPPE en 2022 en ont reçu sans jamais être
    candidats.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    titre: str = Field(min_length=1)
    personne: str | None = None


class Publication(BaseModel):
    """Une vague de publication, et la décision qui l'a rendue publique."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    date: dt.date
    source: str


class SourceParrainages(BaseModel):
    """Le fichier de parrainages d'une élection, et comment le lire."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    election: str
    #: Chemin sous `raw/`.
    fichier: str
    format: Format
    #: Ce que la source publie. Sans ce champ, un consommateur compterait les
    #: lignes et conclurait que Nicolas Sarkozy a eu 500 parrainages en 2007.
    etendue: Etendue
    #: Les pages du document qui portent les listes, « 8-30 ». Le reste de
    #: l'édition porte d'autres textes ; `outils/pdf_en_texte.py` s'en sert
    #: pour rejouer l'extraction à l'identique.
    pages: str | None = None
    #: Les noms de candidats que porte la source, rapprochés du registre. Tous
    #: doivent y être : c'est ce qui garantit qu'aucune liste n'est ignorée.
    candidats: tuple[CandidatSource, ...] = ()
    #: Au moins une. À partir de 2017, le Conseil publie par vagues pendant la
    #: campagne, et chaque parrainage cite la décision qui le concerne.
    publications: tuple[Publication, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _publications_ordonnees(self) -> SourceParrainages:
        dates = [publication.date for publication in self.publications]
        if any(suivante <= precedente for precedente, suivante in pairwise(dates)):
            raise ValueError(
                f"{self.election}: les publications doivent être datées une fois, "
                f"par date croissante"
            )
        return self

    def chemin(self, racine: Path | None = None) -> Path:
        """Le fichier source, sous `raw/`."""
        return (racine or RAW_DIR) / self.fichier

    @model_validator(mode="after")
    def _titres_distincts(self) -> SourceParrainages:
        titres = [candidat.titre for candidat in self.candidats]
        doublons = sorted({t for t in titres if titres.count(t) > 1})
        if doublons:
            raise ValueError(
                f"{self.election}: deux fois le même titre : " + ", ".join(doublons)
            )
        return self

    def personne_de(self, titre: str) -> str | None:
        """La personne que ce nom désigne, si elle est au registre."""
        return next((c.personne for c in self.candidats if c.titre == titre), None)

    def source_du(self, jour: dt.date) -> str | None:
        """La décision qui a publié les parrainages de cette date."""
        return next((p.source for p in self.publications if p.date == jour), None)


class _SeedParrainages(BaseModel):
    model_config = ConfigDict(extra="forbid")

    parrainages: tuple[SourceParrainages, ...] = ()

    @model_validator(mode="after")
    def _une_entree_par_election(self) -> _SeedParrainages:
        ids = [entree.election for entree in self.parrainages]
        doublons = sorted({i for i in ids if ids.count(i) > 1})
        if doublons:
            raise ValueError("deux entrées pour la même élection : " + ", ".join(doublons))
        return self


def load_parrainages(path: Path | None = None) -> tuple[SourceParrainages, ...]:
    """Charge la déclaration des sources de parrainages, validée.

    `path` vaut `seeds/parrainages.yaml` par défaut.
    """
    path = path or PARRAINAGES_SEED
    contenu = yaml.safe_load(path.read_text(encoding="utf-8"))
    return _SeedParrainages.model_validate(contenu).parrainages
