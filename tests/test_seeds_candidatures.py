"""Les candidatures viennent des décisions du Conseil constitutionnel.

Ces tests relisent l'extraction autant qu'ils vérifient le modèle : les
effectifs par élection sont des faits publics, vérifiables sans ouvrir le seed.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from candidatheque.pipeline.seeds import load_candidatures
from candidatheque.pipeline.seeds.candidatures import Candidature, CandidaturesElection

UNE = {
    "personne": "PE-0001",
    "etat": "validee",
    "tours": [{"numero": 1, "sources": ["conseil-constitutionnel:65-3-PDR"]}],
}


@pytest.fixture(scope="module")
def par_election():
    return {entree.election: entree for entree in load_candidatures()}


@pytest.mark.parametrize(
    "election, attendu",
    [("PR-1965", 6), ("PR-1969", 7), ("PR-1974", 12), ("PR-1981", 10), ("PR-1988", 9),
     ("PR-1995", 9), ("PR-2002", 16), ("PR-2007", 12), ("PR-2012", 10), ("PR-2017", 11),
     ("PR-2022", 12)],
)
def test_effectifs_par_election(par_election, election, attendu):
    assert len(par_election[election].candidats) == attendu


def test_chaque_second_tour_compte_deux_candidatures(par_election):
    for election, entree in par_election.items():
        au_second = [c for c in entree.candidats if any(t.numero == 2 for t in c.tours)]
        assert len(au_second) == 2, election


def test_2027_n_a_pas_encore_de_candidatures(par_election):
    """Rien n'est inventé pour une élection à venir."""
    assert "PR-2027" not in par_election


def test_une_personne_suivie_d_une_election_a_l_autre(par_election):
    """Mitterrand s'est présenté quatre fois, et quatre fois au second tour."""
    elections = [
        e for e, entree in par_election.items()
        if any(c.personne == "PE-0005" for c in entree.candidats)
    ]
    assert sorted(elections) == ["PR-1965", "PR-1974", "PR-1981", "PR-1988"]


def test_toutes_les_participations_sont_sourcees(par_election):
    for entree in par_election.values():
        for candidat in entree.candidats:
            for participation in candidat.tours:
                assert participation.sources


def test_une_participation_sans_source_rejetee():
    with pytest.raises(ValidationError):
        Candidature.model_validate(UNE | {"tours": [{"numero": 1, "sources": []}]})


def test_une_candidature_sans_tour_rejetee():
    with pytest.raises(ValidationError):
        Candidature.model_validate(UNE | {"tours": []})


def test_tours_en_double_rejetes():
    with pytest.raises(ValidationError, match="une fois"):
        Candidature.model_validate(
            UNE | {"tours": [{"numero": 1, "sources": ["a:b"]}, {"numero": 1, "sources": ["a:b"]}]}
        )


def test_tours_dans_le_desordre_rejetes():
    with pytest.raises(ValidationError, match="croissant"):
        Candidature.model_validate(
            UNE | {"tours": [{"numero": 2, "sources": ["a:b"]}, {"numero": 1, "sources": ["a:b"]}]}
        )


def test_etat_hors_enumeration_rejete():
    with pytest.raises(ValidationError):
        Candidature.model_validate(UNE | {"etat": "peut-etre"})


def test_deux_candidatures_pour_la_meme_personne_rejetees():
    with pytest.raises(ValidationError, match="même personne"):
        CandidaturesElection.model_validate({"election": "PR-1965", "candidats": [UNE, UNE]})


def test_le_seed_ne_repete_pas_les_noms(par_election):
    """Le nom se déduit du registre ; le saisir est réservé à l'exception."""
    saisis = [
        (entree.election, candidat.personne)
        for entree in par_election.values()
        for candidat in entree.candidats
        if candidat.nom is not None or candidat.prenom is not None
    ]
    assert saisis == [], f"noms saisis sans nécessité : {saisis}"


def test_le_nom_est_absent_par_defaut():
    candidature = Candidature.model_validate(UNE)
    assert (candidature.nom, candidature.prenom) == (None, None)


def test_un_nom_peut_etre_saisi_quand_il_differe():
    """Le champ existe pour la personne qui a porté un autre nom à ce scrutin."""
    candidature = Candidature.model_validate(UNE | {"nom": "DURAND", "prenom": "Marcel"})
    assert (candidature.nom, candidature.prenom) == ("DURAND", "Marcel")
