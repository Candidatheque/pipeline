"""Publication des résultats de chaque tour, version après version.

Un document par élection, `resultats.json`. Chaque tour y empile ses versions
dans l'ordre où elles ont été publiées, et la dernière fait foi, comme les
états d'une candidature. Les chiffres du ministère de l'Intérieur, ceux que le
Conseil constitutionnel proclame et ceux que les tableaux annexés au Journal
officiel rectifient ne se recoupent pas, et c'est précisément ce qu'on veut
pouvoir lire : l'écart entre deux versions, et pour celle du Conseil les
annulations qui l'expliquent.

Seule la version du Conseil est collectée à ce jour.

Rien n'y est calculé. Ni pourcentage, ni abstention, ni total des suffrages
annulés : tout se redérive des entiers publiés, et une valeur calculée qui ne
tomberait pas juste sur un scrutin ancien ne se distinguerait pas d'une erreur
de lecture. Un décompte que la décision ne donne pas est absent, et non
reconstitué : les bulletins blancs n'apparaissent qu'en 2017.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping

from candidatheque.pipeline.lecture.resultats import Annulation, Tour
from candidatheque.pipeline.publication.departements import normaliser as normaliser_departement
from candidatheque.pipeline.seeds import Election, Source
from candidatheque.pipeline.seeds.resultats import SourceResultats, VersionResultats

#: Document des résultats, sous le répertoire de l'élection.
RESULTATS_FILE = "resultats.json"

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


def _version_publiee(
    version: VersionResultats,
    lu: Tour,
    annee: int,
    noms: Mapping[str, str],
    sources: Mapping[str, Source],
    publiee_par: Callable[[Source], dict],
) -> dict:
    """Une version : son étape, sa date, ses sources, ses décomptes, ses voix.

    `sources` a la forme qu'il a partout ailleurs dans les données publiées :
    une liste, chaque source recopiée en clair.
    """
    entree: dict = {
        "etape": str(version.etape),
        "date": version.date.isoformat(),
        "sources": [publiee_par(sources[version.origine])],
    }
    for champ in DECOMPTES:
        valeur = getattr(lu, champ)
        if valeur is not None:
            entree[champ] = valeur
    entree["voix"] = [
        {"personne": voix.personne, "nom_complet": noms[voix.personne], "voix": voix.voix}
        for voix in lu.voix
    ]
    entree["annulations"] = [_annulation_publiee(annulation, annee) for annulation in lu.annulations]
    return entree


def resultats(
    election: Election,
    source: SourceResultats,
    lus: Mapping[tuple[int, int], Tour],
    noms: Mapping[str, str],
    sources: Mapping[str, Source],
    publiee_par: Callable[[Source], dict],
) -> dict:
    """Le document des résultats d'une élection.

    `lus` donne chaque version lue, par numéro de tour et rang de la version.
    `noms` donne le nom de chaque candidat tel que ses candidatures le
    publient : celui porté lors de ce scrutin, qui peut différer du registre.
    """
    dates = {tour.numero: tour.date for tour in election.tours}
    return {
        "$schema": "../../schemas/resultats.schema.json",
        "election": election.id,
        "tours": [
            {
                "numero": tour.numero,
                "date": dates[tour.numero].isoformat(),
                "versions": [
                    _version_publiee(
                        version, lus[(tour.numero, rang)], election.annee, noms, sources, publiee_par
                    )
                    for rang, version in enumerate(tour.versions)
                ],
            }
            for tour in source.tours
        ],
    }
