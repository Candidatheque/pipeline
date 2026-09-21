"""La lecture des tableaux de résultats annexés aux proclamations, au JO."""

from __future__ import annotations

import pytest

from candidatheque.pipeline.lecture import resultats as lecture_conseil
from candidatheque.pipeline.lecture import resultats_jo
from candidatheque.pipeline.seeds.resultats import Etape, Format, load_resultats


@pytest.fixture(scope="module")
def tableaux():
    """Chaque rectification lue une fois, avec la proclamation de son tour."""
    lus = {}
    for entree in load_resultats():
        for tour in entree.tours:
            versions = {v.etape: v for v in tour.versions}
            rectification = versions.get(Etape.RECTIFICATION)
            if rectification is None:
                continue
            assert rectification.format is Format.TABLEAU_JO
            lus[(entree.election, tour.numero)] = (
                *resultats_jo.lire(rectification),
                lecture_conseil.lire(versions[Etape.PROCLAMATION]),
            )
    return lus


def test_les_six_tableaux_sont_ceux_de_1981_1988_et_1995(tableaux):
    """L'édition de 1974 n'est pas accessible ; avant, les listes n'existent pas."""
    assert set(tableaux) == {(e, n) for e in ("PR-1981", "PR-1988", "PR-1995") for n in (1, 2)}


def test_chaque_tableau_se_lit_en_entier(tableaux):
    """Aucune case que ni la lecture, ni la grille, ni le seed n'aient établie."""
    for cle, (_, problemes, _) in tableaux.items():
        assert problemes == [], cle


def test_chaque_ligne_fait_ses_exprimes_et_chaque_colonne_son_total(tableaux):
    """Les deux contrôles que le tableau porte lui-même, vérifiés sur le résultat."""
    for cle, (tour, _, _) in tableaux.items():
        for departement in tour.departements:
            somme = sum(v.voix for v in departement.voix)
            assert somme == departement.suffrages_exprimes, (cle, departement.code)
            assert departement.inscrits >= departement.votants >= departement.suffrages_exprimes
        for champ in ("inscrits", "votants", "suffrages_exprimes"):
            somme = sum(getattr(d, champ) for d in tour.departements)
            assert somme == getattr(tour, champ), (cle, champ)
        for voix in tour.voix:
            somme = sum(v.voix for d in tour.departements for v in d.voix if v.personne == voix.personne)
            assert somme == voix.voix, (cle, voix.titre)


def test_chaque_tableau_porte_tous_les_departements(tableaux):
    """106 lignes : 96 départements, l'outre-mer, les Français de l'étranger.

    Une ligne absente ne se remarquerait pas autrement : la case qu'une autre
    ligne déduirait du total l'absorberait. C'est arrivé au Territoire de
    Belfort en 1988, avant que la lecture l'exige.
    """
    for cle, (tour, _, _) in tableaux.items():
        codes = {d.code for d in tour.departements}
        assert resultats_jo.METROPOLE <= codes, cle
        assert resultats_jo.ETRANGER in codes, cle
        assert len(codes) == 106, cle


def test_le_second_tour_et_1981_redisent_la_proclamation(tableaux):
    """Là où rien n'est rectifié, le tableau et la décision disent la même chose."""
    for cle in [("PR-1981", 1), ("PR-1981", 2), ("PR-1988", 2), ("PR-1995", 2)]:
        tour, _, proclame = tableaux[cle]
        assert tour.suffrages_exprimes == proclame.suffrages_exprimes, cle
        assert {v.personne: v.voix for v in tour.voix} == {
            v.personne: v.voix for v in proclame.voix
        }, cle


def test_le_premier_tour_de_1988_et_de_1995_est_rectifie(tableaux):
    """La raison d'être de l'étape : des chiffres qui ne sont pas ceux déclarés."""
    ecarts = {}
    for cle in [("PR-1988", 1), ("PR-1995", 1)]:
        tour, _, proclame = tableaux[cle]
        ecarts[cle] = tour.suffrages_exprimes - proclame.suffrages_exprimes
    assert ecarts == {("PR-1988", 1): 30706, ("PR-1995", 1): 1919}


def test_une_ligne_seule_illisible_se_deduit_du_total(tableaux):
    """La Dordogne de 1988 : l'océrisation lit 87 846 voix pour Mitterrand.

    La ligne ne fait pas ses exprimés ; seule dans ce cas, elle se déduit du
    total moins les autres lignes, et le total impose 87 646.
    """
    tour, _, _ = tableaux[("PR-1988", 1)]
    dordogne = next(d for d in tour.departements if d.code == "24")
    mitterrand = next(v for v in dordogne.voix if v.personne == "PE-0005")
    assert mitterrand.voix == 87646


def test_les_moities_d_un_tableau_coupe_se_reunissent(tableaux):
    """1995 : les cinq premiers candidats sur une page, les quatre autres sur la suivante."""
    tour, _, _ = tableaux[("PR-1995", 1)]
    assert all(len(d.voix) == 9 for d in tour.departements)


@pytest.mark.parametrize(
    ("lu", "attendu"),
    [
        ("363 1 14 45,54%", "363 114 45,54%"),
        ("1 1 2 406 41,13%", "112 406 41,13%"),
        ("160 91 1 58,87%", "160 911 58,87%"),
        ("35 8 648  281 239", "358 648  281 239"),
        # Deux nombres voisins restent deux nombres.
        ("4 120 36 464", "4 120 36 464"),
    ],
)
def test_un_chiffre_detache_retrouve_son_nombre(lu, attendu):
    assert resultats_jo._recolle(lu) == attendu


@pytest.mark.parametrize(
    ("lu", "attendu"),
    [
        ("262.000    205,332", [262000, 205332]),
        ("106-794     92.807", [106794, 92807]),
        ("84'. 136", [84136]),
        ("i.688    2S.82S", [1688, 25825]),
        ("—  4.991", [4991]),
        ("18.2(9", [None]),
    ],
)
def test_les_nombres_a_points_et_leurs_blessures(lu, attendu):
    assert resultats_jo._nombres_points(lu) == attendu


@pytest.mark.parametrize(
    ("lu", "attendu"),
    [
        ("ALPES (HAUTES-)", "HAUTES-ALPES"),
        ("RHIN (BAS-)", "BAS-RHIN"),
        ("REUNION (LA)", "LA REUNION"),
        ("SEVRES-(DEUX-)", "DEUX-SEVRES"),
    ],
)
def test_un_libelle_a_l_ancienne_se_remet_a_l_endroit(lu, attendu):
    assert resultats_jo._remis_a_l_endroit(lu) == attendu
