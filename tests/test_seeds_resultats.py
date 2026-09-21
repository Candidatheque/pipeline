"""La déclaration des résultats proclamés, tour par tour."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from candidatheque.pipeline.seeds import load_elections, load_sources
from candidatheque.pipeline.seeds.resultats import SourceResultats, load_resultats


def _version(**champs) -> dict:
    return {
        "etape": "proclamation",
        "date": "2022-04-13",
        "fichier": "resultats/2022-195-PDR.txt",
        "origine": "conseil-constitutionnel:2022-195-PDR",
        "candidats": [{"titre": "M. Emmanuel MACRON", "personne": "PE-0072"}],
    } | champs


def _entree(**champs) -> dict:
    return {
        "election": "PR-2022",
        "tours": [{"numero": 1, "versions": [_version()]}],
    } | champs


def _versions():
    return [
        (entree.election, tour.numero, version)
        for entree in load_resultats()
        for tour in entree.tours
        for version in tour.versions
    ]


def test_le_depot_declare_les_deux_tours_de_chaque_election_tenue():
    """Onze élections tenues, deux tours chacune : vingt-deux décisions.

    2027 n'y est pas et ne peut pas y être : aucune source ne publiera de
    résultats avant le scrutin.
    """
    entrees = load_resultats()
    assert len(entrees) == 11
    assert sum(len(entree.tours) for entree in entrees) == 22
    elections = {election.id for election in load_elections()}
    assert {entree.election for entree in entrees} <= elections
    assert "PR-2027" not in {entree.election for entree in entrees}


def test_le_texte_de_chaque_decision_est_dans_le_depot():
    """La pipeline ne télécharge rien : le fichier déclaré doit être là."""
    for _, _, version in _versions():
        assert version.chemin().is_file(), version.fichier


def test_chaque_tour_cite_la_decision_qui_le_proclame():
    sources = {source.id for source in load_sources()}
    origines = set()
    for election, numero, version in _versions():
        assert version.origine in sources, f"{election}/T{numero}"
        origines.add(version.origine)
    # Une décision proclame un tour et un seul : deux tours qui citeraient la
    # même auraient les mêmes chiffres sans que rien ne le dise.
    assert len(origines) == 22


def test_le_rapprochement_des_noms_est_declare_et_non_devine():
    """Les transcriptions anciennes abîment les noms.

    « Jean-Louis TIXIER-VIGNANCOU » y perd son R final, Arlette LAGUILLER y
    devient « Ariette ». Ces noms-là sont dans le seed, écrits noir sur blanc.
    """
    titres = {candidat.titre for _, _, version in _versions() for candidat in version.candidats}
    assert "Jean-Louis TIXIER-VIGNANCOU" in titres
    assert "Ariette LAGUILLER" in titres


def test_les_tours_se_numerotent_a_partir_de_un_et_dans_l_ordre():
    """Un tour sauté ou inversé est une erreur de saisie, pas une donnée."""
    with pytest.raises(ValidationError, match="à partir de 1"):
        SourceResultats.model_validate(
            _entree(tours=[{"numero": 2, "versions": [_version()]}])
        )


def test_un_candidat_ne_figure_qu_une_fois_par_tour():
    """Deux lignes pour la même personne compteraient ses voix deux fois."""
    with pytest.raises(ValidationError, match="deux fois"):
        SourceResultats.model_validate(
            _entree(
                tours=[
                    {
                        "numero": 1,
                        "versions": [
                            _version(
                                candidats=[
                                    {"titre": "M. Emmanuel MACRON", "personne": "PE-0072"},
                                    {"titre": "M. Emmanuel Macron", "personne": "PE-0072"},
                                ]
                            )
                        ],
                    }
                ]
            )
        )


def test_les_versions_se_rangent_dans_l_ordre_des_etapes_et_non_des_dates():
    """La proclamation fait foi, même quand le ministère publie après elle.

    Les résultats définitifs de l'Intérieur peuvent paraître après la
    décision du Conseil ; rangés par date, ils prendraient sa place.
    """
    tardifs = _version(etape="resultats-definitifs", date="2022-05-02")
    SourceResultats.model_validate(
        _entree(tours=[{"numero": 1, "versions": [tardifs, _version(date="2022-04-13")]}])
    )
    with pytest.raises(ValidationError, match="ordre des étapes"):
        SourceResultats.model_validate(
            _entree(tours=[{"numero": 1, "versions": [_version(), tardifs]}])
        )


def test_une_etape_ne_donne_qu_une_version_par_tour():
    """Deux proclamations d'un même tour se contrediraient sans que rien le dise."""
    with pytest.raises(ValidationError, match="une par étape"):
        SourceResultats.model_validate(
            _entree(tours=[{"numero": 1, "versions": [_version(), _version()]}])
        )


def test_une_election_ne_se_declare_qu_une_fois():
    entrees = [entree.election for entree in load_resultats()]
    assert len(entrees) == len(set(entrees))
