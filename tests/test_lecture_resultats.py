"""La lecture des décisions de résultats."""

from __future__ import annotations

import pytest

from candidatheque.pipeline.lecture.resultats import lire
from candidatheque.pipeline.seeds.resultats import load_resultats


@pytest.fixture(scope="module")
def tours():
    """Les vingt-deux tours, lus une fois."""
    return {
        (entree.election, tour.numero): (tour, lire(tour))
        for entree in load_resultats()
        for tour in entree.tours
    }


def test_la_somme_des_voix_fait_les_suffrages_exprimes(tours):
    """Le contrôle qui vaut tous les autres.

    Une décision se contrôle elle-même : si la somme des voix lues tombe sur
    les suffrages exprimés annoncés, c'est qu'aucune ligne n'a été ratée,
    qu'aucun nombre n'a été mal recollé et qu'aucun candidat n'a été compté
    deux fois. Les vingt-deux tours tombent juste.
    """
    for (election, numero), (_, lu) in tours.items():
        assert sum(v.voix for v in lu.voix) == lu.suffrages_exprimes, f"{election} T{numero}"


def test_chaque_candidat_declare_porte_ses_voix(tours):
    """Un candidat sans voix serait une ligne perdue, pas un candidat à zéro."""
    for (election, numero), (source, lu) in tours.items():
        assert len(lu.voix) == len(source.candidats), f"{election} T{numero}"
        assert all(v.voix > 0 for v in lu.voix), f"{election} T{numero}"


def test_les_decomptes_communs_sont_lus_partout(tours):
    """Inscrits, votants et exprimés : les trois que toute décision donne."""
    for (election, numero), (_, lu) in tours.items():
        ou = f"{election} T{numero}"
        assert lu.inscrits and lu.votants and lu.suffrages_exprimes, ou
        assert lu.votants <= lu.inscrits, ou
        assert lu.suffrages_exprimes <= lu.votants, ou


def test_les_blancs_et_les_nuls_ne_sont_donnes_que_par_les_recentes(tours):
    """Le Conseil ne les a pas toujours publiés, et ils ne se calculent pas.

    2017 donne les blancs sans les nuls, 2022 les deux, et rien avant. Les
    déduire de « votants moins exprimés » donnerait un nombre que la décision
    ne dit pas.
    """
    avec_blancs = {cle for cle, (_, lu) in tours.items() if lu.bulletins_blancs is not None}
    avec_nuls = {cle for cle, (_, lu) in tours.items() if lu.bulletins_nuls is not None}
    assert avec_blancs == {("PR-2017", 1), ("PR-2017", 2), ("PR-2022", 1), ("PR-2022", 2)}
    assert avec_nuls == {("PR-2022", 1), ("PR-2022", 2)}


def test_la_majorite_absolue_manque_a_la_proclamation_de_1965(tours):
    """Elle n'est pas dans le texte : la publier serait l'inventer."""
    _, lu = tours[("PR-1965", 2)]
    assert lu.majorite_absolue is None
    assert lu.suffrages_exprimes == 23703434


def test_le_un_perdu_par_l_impression_est_rendu(tours):
    """« l 260 208 » est le nombre de voix de Jean-Louis Tixier-Vignancour.

    La transcription de 1965 y a lu un « l » là où le Journal officiel imprime
    un 1. Le garder ferait un nombre illisible ; le jeter, un candidat sans
    voix. La somme du tour dit lequel des deux est le bon.
    """
    _, lu = tours[("PR-1965", 1)]
    tixier = next(v for v in lu.voix if v.titre.startswith("Jean-Louis"))
    assert tixier.voix == 1260208


def test_les_decomptes_cousus_de_2002_sont_separes(tours):
    """La proclamation de 2002 tient sur une ligne, sans séparateur.

    « 41 191 169Votants : 32 832 295 » : un chiffre suivi d'une capitale n'est
    jamais un nombre, c'est une couture.
    """
    _, lu = tours[("PR-2002", 2)]
    assert lu.inscrits == 41191169
    assert lu.votants == 32832295
    assert lu.suffrages_exprimes == 31062988
