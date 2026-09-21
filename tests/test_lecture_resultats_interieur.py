"""La lecture des résultats du ministère de l'Intérieur."""

from __future__ import annotations

import pytest

from candidatheque.pipeline.lecture import resultats as lecture_conseil
from candidatheque.pipeline.lecture import resultats_interieur
from candidatheque.pipeline.seeds.resultats import Etape, Format, load_resultats

DECOMPTES = ("inscrits", "votants", "suffrages_exprimes")


@pytest.fixture(scope="module")
def versions():
    """Chaque version du ministère, lue une fois, avec la proclamation du tour."""
    lues = {}
    for entree in load_resultats():
        for tour in entree.tours:
            proclamation = next(v for v in tour.versions if v.etape is Etape.PROCLAMATION)
            for version in tour.versions:
                if version.format is Format.INTERIEUR:
                    lues[(entree.election, tour.numero, version.etape)] = (
                        resultats_interieur.lire(version, tour.numero),
                        lecture_conseil.lire(proclamation),
                    )
    return lues


def test_le_ministere_est_collecte_de_2007_a_2022(versions):
    """Les définitifs pour les quatre élections, les provisoires depuis 2017."""
    definitifs = {(e, n) for e, n, etape in versions if etape is Etape.RESULTATS_DEFINITIFS}
    provisoires = {(e, n) for e, n, etape in versions if etape is Etape.RESULTATS_PROVISOIRES}
    assert definitifs == {(e, n) for e in ("PR-2007", "PR-2012", "PR-2017", "PR-2022") for n in (1, 2)}
    assert provisoires == {(e, n) for e in ("PR-2017", "PR-2022") for n in (1, 2)}


def test_la_somme_des_voix_fait_les_suffrages_exprimes(versions):
    for cle, (lu, _) in versions.items():
        assert sum(v.voix for v in lu.voix) == lu.suffrages_exprimes, cle
        for departement in lu.departements:
            somme = sum(v.voix for v in departement.voix)
            assert somme == departement.suffrages_exprimes, (cle, departement.code)


def test_les_definitifs_du_ministere_sont_les_chiffres_proclames(versions):
    """À l'unité près, sur les huit tours : ce sont les mêmes chiffres.

    Ils restent une version à part, avec leur source et leur date. Mais un
    écart ici voudrait dire qu'un des deux fichiers est mal lu.
    """
    for (election, numero, etape), (lu, proclame) in versions.items():
        if etape is not Etape.RESULTATS_DEFINITIFS:
            continue
        for champ in DECOMPTES:
            assert getattr(lu, champ) == getattr(proclame, champ), (election, numero, champ)
        assert {v.personne: v.voix for v in lu.voix} == {
            v.personne: v.voix for v in proclame.voix
        }, (election, numero)


def test_les_departements_des_definitifs_font_le_total_national(versions):
    """La somme se vérifie, elle n'est jamais publiée à la place du total.

    Elle ne tombe juste qu'avec les lignes qui ne sont pas des départements :
    les Français de l'étranger, et Saint-Barthélemy avec Saint-Martin.
    """
    for (election, numero, etape), (lu, _) in versions.items():
        if etape is not Etape.RESULTATS_DEFINITIFS:
            continue
        for champ in DECOMPTES:
            somme = sum(getattr(d, champ) for d in lu.departements)
            assert somme == getattr(lu, champ), (election, numero, champ)


def test_les_provisoires_sont_des_instantanes_de_la_soiree(versions):
    """Le vote des Français de l'étranger manque au premier tour de 2022.

    Les résultats de la soirée sont arrêtés avant que toutes les commissions
    aient fini : leur somme départementale n'a pas à faire le total, et ils
    diffèrent des chiffres proclamés.
    """
    lu, proclame = versions[("PR-2022", 1, Etape.RESULTATS_PROVISOIRES)]
    assert "ZZ" not in {d.code for d in lu.departements}
    assert lu.suffrages_exprimes != proclame.suffrages_exprimes


def test_la_ligne_de_total_du_classeur_de_2012_n_est_pas_un_departement(versions):
    """Sans code, elle aurait doublé les inscrits du second tour."""
    lu, _ = versions[("PR-2012", 2, Etape.RESULTATS_DEFINITIFS)]
    assert all(d.code for d in lu.departements)
    assert sum(d.inscrits for d in lu.departements) == lu.inscrits


def test_les_blancs_et_les_nuls_suivent_ce_que_la_source_separe(versions):
    """Ensemble en 2007 et 2012, séparés à partir de 2017, jamais recalculés."""
    lu_2012, _ = versions[("PR-2012", 1, Etape.RESULTATS_DEFINITIFS)]
    assert lu_2012.bulletins_blancs_et_nuls == 701190
    assert lu_2012.bulletins_blancs is None and lu_2012.bulletins_nuls is None
    lu_2017, _ = versions[("PR-2017", 1, Etape.RESULTATS_DEFINITIFS)]
    assert (lu_2017.bulletins_blancs, lu_2017.bulletins_nuls) == (659997, 289337)
    assert lu_2017.bulletins_blancs_et_nuls is None
