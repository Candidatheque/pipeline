"""La lecture des décisions de résultats."""

from __future__ import annotations

import pytest

from candidatheque.pipeline.lecture import resultats
from candidatheque.pipeline.lecture.resultats import lire, lire_en_detail
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


# ---------------------------------------------------------------------------
# Les annulations
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def en_detail():
    """Les vingt-deux tours, avec ce que la lecture n'a pas su lire."""
    return {
        (entree.election, tour.numero): lire_en_detail(tour)
        for entree in load_resultats()
        for tour in entree.tours
    }


def _annulations(tours, election, numero, considerant=None):
    _, lu = tours[(election, numero)]
    return [a for a in lu.annulations if considerant is None or a.considerant == considerant]


def test_chaque_considerant_qui_annule_est_lu_en_entier(en_detail):
    """Un lieu non reconnu serait une annulation perdue, sans bruit."""
    for (election, numero), (_, sans_lieu, sans_suffrages) in en_detail.items():
        assert not sans_lieu, f"{election} T{numero} : aucun lieu lu dans {sans_lieu}"
        assert not sans_suffrages, f"{election} T{numero} : suffrages non attribués {sans_suffrages}"


def test_chaque_nombre_de_suffrages_ecrit_se_retrouve_dans_les_annulations(tours):
    """Le contrôle croisé des annulations.

    Les nombres « N suffrages » que la décision écrit avant sa formule
    d'annulation sont ceux des lieux annulés. Chacun doit se retrouver dans une
    annulation lue, et aucun ne doit y être en trop.
    """
    for (election, numero), (source, lu) in tours.items():
        lignes = resultats._lignes(source.chemin().read_text(encoding="utf-8"))
        for ligne in lignes:
            m = resultats.CONSIDERANT.match(ligne)
            if m is None:
                continue
            texte = m.group("texte")
            formule = resultats.ANNULE.search(texte)
            if formule is None or resultats.REDRESSEMENT.search(texte):
                continue
            if resultats.PARTIELLE.search(texte):
                continue
            ecrits = sorted(
                n
                for s in resultats.SUFFRAGES.finditer(texte[: formule.start()])
                for n in resultats._suffrages(s.group("nombres"))
            )
            lus = sorted(
                a.suffrages_exprimes
                for a in lu.annulations
                if a.considerant == int(m.group("numero")) and a.suffrages_exprimes is not None
            )
            assert ecrits == lus, f"{election} T{numero} cons. {m.group('numero')}"


def test_le_compte_des_annulations(tours):
    """195 lieux annulés en quarante ans, dont 114 bureaux et 81 communes.

    Un changement de ce compte est un changement de lecture, à relire.
    """
    toutes = [a for _, lu in tours.values() for a in lu.annulations]
    assert len(toutes) == 195
    assert sum(a.portee == "bureau-de-vote" for a in toutes) == 114
    assert sum(a.portee == "commune" for a in toutes) == 81


def test_les_suffrages_donnes_bureau_par_bureau_se_repartissent(tours):
    """« dans lesquels ont été respectivement exprimés 769 et 765 suffrages »."""
    montigny = [
        (a.bureaux, a.suffrages_exprimes)
        for a in _annulations(tours, "PR-2022", 2, 3)
        if a.commune == "Montigny-sur-Loing"
    ]
    assert montigny == [((1,), 769), ((2,), 765)]


def test_un_total_pour_plusieurs_bureaux_ne_se_repartit_pas(tours):
    """« les bureaux de vote n° 3 et 4 […], dans lesquels 817 suffrages ».

    La décision ne dit pas combien dans chacun. Séparer les deux bureaux
    obligerait à inventer la répartition, ou à perdre le nombre.
    """
    (mazingarbe,) = _annulations(tours, "PR-2002", 2, 4)
    assert mazingarbe.bureaux == (3, 4)
    assert mazingarbe.suffrages_exprimes == 817


def test_le_departement_ecrit_une_fois_vaut_pour_toute_l_enumeration(tours):
    """« les bureaux n° 1 de la commune de Furiani et n° 15 de la commune de
    Bastia (Haute Corse) » : un département pour deux communes."""
    lieux = [(a.commune, a.departement, a.bureaux) for a in _annulations(tours, "PR-2002", 2, 2)]
    assert lieux == [("Furiani", "Haute Corse", (1,)), ("Bastia", "Haute Corse", (15,))]


def test_la_commune_retrouve_l_article_que_la_preposition_avait_absorbe(tours):
    """« la commune du Blanc-Mesnil » est Le Blanc-Mesnil."""
    communes = {a.commune for a in _annulations(tours, "PR-1981", 2)}
    assert "Le Blanc-Mesnil" in communes
    assert "Les Riceys" in {a.commune for a in _annulations(tours, "PR-1995", 2)}


def test_un_bureau_de_paris_se_situe_dans_son_arrondissement(tours):
    """Les bureaux parisiens sont numérotés par arrondissement."""
    (bureau,) = _annulations(tours, "PR-2002", 1, 3)
    assert (bureau.commune, bureau.bureaux) == ("Paris 13e arrondissement", (27,))


def test_la_formule_dit_la_portee_quand_rien_ne_designe_de_bureau(tours):
    """À Chenevelles, la commune avait ouvert un second bureau sans droit.

    « il y a lieu d'annuler les suffrages exprimés dans ce bureau » : c'est un
    bureau qui est annulé, pas la commune, même si la décision ne le numérote
    pas. À Lamastre, la formule vise « ce bureau et cette commune » et ne
    tranche pas ; le lieu nommé comme commune le reste.
    """
    (chenevelles,) = _annulations(tours, "PR-2022", 1, 3)
    assert chenevelles.portee == "bureau-de-vote"
    assert chenevelles.bureaux == ()
    lamastre = next(a for a in _annulations(tours, "PR-2017", 1, 7) if a.commune == "Lamastre")
    assert lamastre.portee == "commune"


def test_les_decisions_anciennes_ne_donnent_pas_les_suffrages_annules(tours):
    """1981 nomme les bureaux sans dire combien de suffrages ils portaient."""
    anciennes = _annulations(tours, "PR-1981", 2, 1)
    assert [a.commune for a in anciennes] == ["Aulnay-sous-Bois", "Le Blanc-Mesnil", "Arles", "Rouen"]
    assert all(a.suffrages_exprimes is None for a in anciennes)


def test_un_redressement_n_est_pas_une_annulation(tours):
    """En 2007, la commission de la Haute-Marne avait retranché quinze voix.

    Le Conseil les rétablit : « il y a lieu de rectifier […] et de majorer ».
    Le considérant parle d'annulation, mais pour la défaire.
    """
    assert not _annulations(tours, "PR-2007", 1, 6)


def test_l_annulation_des_seuls_votes_par_correspondance_est_ecartee(tours):
    """1974, Bastia et Albertacce : ni le bureau, ni la commune n'est annulé.

    Seuls les votes par correspondance le sont, sans que leur nombre soit
    donné. Les ranger avec les autres ferait croire à un bureau entier annulé.
    """
    assert not _annulations(tours, "PR-1974", 2, 6)


def test_chaque_annulation_porte_son_motif_et_les_rubriques_du_conseil(tours):
    """Le motif est le texte du considérant ; les rubriques, son classement."""
    (lourdios,) = _annulations(tours, "PR-2022", 2, 1)
    assert lourdios.motif.startswith("Dans la commune de Lourdios-Ichère")
    assert lourdios.nomenclature == (
        ("8.1.5.6", "Principe de dignité du scrutin"),
        ("8.2.3.2", "Propagande"),
    )
    # Les décisions anciennes n'ont pas d'abstracts pour tous leurs considérants.
    assert all(a.motif for _, lu in tours.values() for a in lu.annulations)
