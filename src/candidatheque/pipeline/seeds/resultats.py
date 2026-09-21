"""D'où viennent les résultats proclamés, et à quoi ils se rattachent.

Un tour, une décision. Le Conseil constitutionnel déclare les résultats du
premier tour, puis proclame ceux de l'élection : ce sont les deux seuls
documents où ces chiffres existent, et leur texte est commité dans
`raw/resultats/`, jamais téléchargé.

Ces chiffres ne sont pas ceux du ministère de l'Intérieur. Le Conseil annule
des suffrages et rectifie des erreurs matérielles avant de proclamer ; ce qu'il
donne est net de ces annulations, et ne se recoupe donc pas avec un recensement
administratif.
"""

from __future__ import annotations

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


class TourResultats(BaseModel):
    """Les résultats d'un tour, et la décision qui les porte."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    numero: int = Field(ge=1)
    #: Chemin sous `raw/`.
    fichier: str
    #: La décision, dans le registre des sources.
    origine: str
    #: Tous les candidats du tour, dans l'ordre de la décision. Ils doivent y
    #: être tous : c'est ce qui garantit qu'aucune ligne de voix n'est ignorée.
    candidats: tuple[CandidatSource, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _un_candidat_une_fois(self) -> TourResultats:
        for champ in ("titre", "personne"):
            valeurs = [getattr(candidat, champ) for candidat in self.candidats]
            doublons = sorted({v for v in valeurs if valeurs.count(v) > 1})
            if doublons:
                raise ValueError(f"tour {self.numero} : deux fois " + ", ".join(doublons))
        return self

    def chemin(self, racine: Path | None = None) -> Path:
        """Le texte de la décision, sous `raw/`."""
        return (racine or RAW_DIR) / self.fichier

    def personne_de(self, titre: str) -> str | None:
        """La personne que ce nom désigne."""
        return next((c.personne for c in self.candidats if c.titre == titre), None)


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
