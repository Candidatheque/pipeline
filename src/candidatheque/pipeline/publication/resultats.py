"""Publication des résultats proclamés par le Conseil constitutionnel.

Un document par élection, `resultats-proclames.json`, qui porte ses tours. Le
nom dit l'autorité : ces chiffres sont ceux que le Conseil proclame, nets des
suffrages qu'il annule et des erreurs qu'il rectifie. Le ministère de
l'Intérieur publie les siens, qui ne se recoupent pas avec ceux-ci ; ils
auront leur propre document le jour où ils seront collectés.

Rien n'y est calculé. Ni pourcentage, ni abstention, ni total des suffrages
annulés : tout se redérive des entiers publiés, et une valeur calculée qui ne
tomberait pas juste sur un scrutin ancien ne se distinguerait pas d'une erreur
de lecture. Un décompte que la décision ne donne pas est absent, et non
reconstitué : les bulletins blancs n'apparaissent qu'en 2017.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping

from candidatheque.pipeline.lecture.resultats import Annulation, Tour
from candidatheque.pipeline.publication.departements import normaliser as normaliser_departement
from candidatheque.pipeline.seeds import Election, Source
from candidatheque.pipeline.seeds.resultats import SourceResultats, TourResultats

#: Document des résultats, sous le répertoire de l'élection.
RESULTATS_FILE = "resultats-proclames.json"

#: Les décomptes, dans l'ordre où les décisions les donnent.
DECOMPTES = (
    "inscrits",
    "votants",
    "bulletins_blancs",
    "bulletins_nuls",
    "suffrages_exprimes",
    "majorite_absolue",
)


def _annulation_publiee(annulation: Annulation, annee: int) -> dict:
    """Une annulation, telle qu'elle est publiée.

    Le département est ramené à son code, comme dans les parrainages — 20
    pour la Corse d'avant 1976 — et omis quand la décision ne le donne pas,
    comme pour le 7e bureau d'Oyonnax en 2007.
    """
    entree: dict = {
        "considerant": annulation.considerant,
        "portee": annulation.portee,
        "commune": annulation.commune,
    }
    departement = normaliser_departement(annulation.departement, annee)
    if departement:
        entree["departement"] = departement
    if annulation.bureaux:
        entree["bureaux"] = list(annulation.bureaux)
    if annulation.suffrages_exprimes is not None:
        entree["suffrages_exprimes"] = annulation.suffrages_exprimes
    entree["motif"] = annulation.motif
    if annulation.nomenclature:
        entree["nomenclature"] = [
            {"code": code, "intitule": intitule} for code, intitule in annulation.nomenclature
        ]
    return entree


def _tour_publie(
    election: Election,
    source: TourResultats,
    lu: Tour,
    noms: Mapping[str, str],
    sources: Mapping[str, Source],
    publiee_par: Callable[[Source], dict],
) -> dict:
    """Un tour : sa date, sa décision, ses décomptes, ses voix, ses annulations."""
    date = next(tour.date for tour in election.tours if tour.numero == source.numero)
    entree: dict = {
        "numero": source.numero,
        "date": date.isoformat(),
        "source": publiee_par(sources[source.origine]),
    }
    for champ in DECOMPTES:
        valeur = getattr(lu, champ)
        if valeur is not None:
            entree[champ] = valeur
    entree["voix"] = [
        {"personne": voix.personne, "nom_complet": noms[voix.personne], "voix": voix.voix}
        for voix in lu.voix
    ]
    entree["annulations"] = [
        _annulation_publiee(annulation, election.annee) for annulation in lu.annulations
    ]
    return entree


def resultats_proclames(
    election: Election,
    source: SourceResultats,
    lus: Iterable[Tour],
    noms: Mapping[str, str],
    sources: Mapping[str, Source],
    publiee_par: Callable[[Source], dict],
) -> dict:
    """Le document des résultats proclamés d'une élection.

    `noms` donne le nom de chaque candidat tel que ses candidatures le
    publient : celui porté lors de ce scrutin, qui peut différer du registre.
    """
    return {
        "$schema": "../../schemas/resultats-proclames.schema.json",
        "election": election.id,
        "tours": [
            _tour_publie(election, tour, lu, noms, sources, publiee_par)
            for tour, lu in zip(source.tours, lus, strict=True)
        ],
    }
