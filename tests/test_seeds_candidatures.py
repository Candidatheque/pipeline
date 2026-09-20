"""Les candidatures viennent des décisions du Conseil constitutionnel.

Ces tests relisent l'extraction autant qu'ils vérifient le modèle : les
effectifs par élection sont des faits publics, vérifiables sans ouvrir le seed.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from candidatheque.pipeline.seeds import load_candidatures
from candidatheque.pipeline.seeds.candidatures import Candidature, CandidaturesElection

VALIDEE = {
    "etat": "validee",
    "date": "1965-11-18",
    "sources": ["conseil-constitutionnel:65-3-PDR"],
}
UNE = {
    "personne": "PE-0001",
    "etats": [VALIDEE],
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
def test_effectifs_valides_par_election(par_election, election, attendu):
    """Faits publics : 6 candidats en 1965, 16 en 2002, 12 en 2022."""
    valides = [c for c in par_election[election].candidats if c.etat == "validee"]
    assert len(valides) == attendu


def test_les_candidatures_non_validees_n_ont_aucun_tour(par_election):
    """Une candidature écartée ou retirée n'a pris part à aucun tour."""
    for entree in par_election.values():
        for candidat in entree.candidats:
            if candidat.etat != "validee":
                assert candidat.tours == (), (entree.election, candidat.personne)


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


def test_une_candidature_sans_etat_rejetee():
    with pytest.raises(ValidationError):
        Candidature.model_validate(UNE | {"etats": []})


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
        Candidature.model_validate(UNE | {"etats": [VALIDEE | {"etat": "peut-etre"}]})


def test_deux_candidatures_pour_la_meme_personne_rejetees():
    with pytest.raises(ValidationError, match="même personne"):
        CandidaturesElection.model_validate({"election": "PR-1965", "candidats": [UNE, UNE]})


def test_le_seed_ne_repete_pas_les_noms(par_election):
    """Le nom se déduit du registre ; le saisir est réservé à l'exception."""
    saisis = [
        (entree.election, candidat.personne)
        for entree in par_election.values()
        for candidat in entree.candidats
        if candidat.nom_complet is not None
    ]
    assert saisis == [], f"noms saisis sans nécessité : {saisis}"


def test_le_nom_est_absent_par_defaut():
    assert Candidature.model_validate(UNE).nom_complet is None


def test_un_nom_peut_etre_saisi_quand_il_differe():
    """Le champ existe pour la personne qui a porté un autre nom à ce scrutin."""
    candidature = Candidature.model_validate(UNE | {"nom_complet": "Marcel DURAND"})
    assert candidature.nom_complet == "Marcel DURAND"


class TestTrajectoire:
    """L'état d'une candidature est une trajectoire, pas un instantané."""

    @staticmethod
    def _etat(etat, date):
        return {"etat": etat, "date": date, "sources": ["presse:a"]}

    def test_l_etat_courant_est_le_dernier(self):
        candidature = Candidature.model_validate(
            UNE | {"etats": [self._etat("declaree", "1965-09-01"), VALIDEE]}
        )
        assert candidature.etat == "validee"

    def test_declaree_puis_retiree_sans_aucun_tour(self):
        """Le cas que le modèle précédent ne savait pas représenter."""
        candidature = Candidature.model_validate(
            {
                "personne": "PE-0001",
                "etats": [
                    self._etat("declaree", "2026-05-01"),
                    self._etat("retiree", "2026-11-03"),
                ],
                "tours": [],
            }
        )
        assert candidature.etat == "retiree"
        assert candidature.tours == ()
        assert candidature.etats[0].etat == "declaree", "la déclaration reste tracée"

    def test_la_source_de_declaration_survit_a_la_validation(self):
        """Une candidature validée garde qui l'avait annoncée."""
        candidature = Candidature.model_validate(
            UNE | {"etats": [self._etat("declaree", "1965-09-01"), VALIDEE]}
        )
        assert candidature.etats[0].sources == ("presse:a",)
        assert candidature.etat == "validee"

    def test_etats_antidates_rejetes(self):
        with pytest.raises(ValidationError, match="date croissante"):
            Candidature.model_validate(
                UNE | {"etats": [VALIDEE, self._etat("retiree", "1965-01-01")]}
            )

    def test_meme_etat_repete_rejete(self):
        """Deux fois le même état d'affilée ne dit rien de plus que le premier."""
        with pytest.raises(ValidationError, match="répété"):
            Candidature.model_validate(
                UNE | {"etats": [self._etat("declaree", "2026-05-01"),
                                 self._etat("declaree", "2026-06-01")]}
            )

    def test_un_etat_sans_source_rejete(self):
        with pytest.raises(ValidationError):
            Candidature.model_validate(UNE | {"etats": [VALIDEE | {"sources": []}]})

    def test_toutes_les_trajectoires_du_seed_sont_sourcees(self, par_election):
        for entree in par_election.values():
            for candidat in entree.candidats:
                assert candidat.etats
                assert all(changement.sources for changement in candidat.etats)


def test_un_etat_sans_date_est_accepte():
    """Une source peut établir un retrait sans dire quand."""
    candidature = Candidature.model_validate(
        UNE | {"etats": [{"etat": "retiree", "sources": ["wikipedia-fr:a"]}], "tours": []}
    )
    assert candidature.etats[0].date is None
    assert candidature.etat == "retiree"


def test_l_ordre_est_verifie_sur_les_seules_dates_connues():
    """Un état non daté ne doit pas faire échouer le contrôle chronologique."""
    candidature = Candidature.model_validate(
        UNE
        | {
            "etats": [
                {"etat": "declaree", "sources": ["wikipedia-fr:a"]},
                {"etat": "validee", "date": "1965-11-18", "sources": ["c:d"]},
            ]
        }
    )
    assert len(candidature.etats) == 2


@pytest.mark.parametrize(
    "election, attendu",
    [("PR-1969", 4), ("PR-1974", 27), ("PR-1981", 3), ("PR-1995", 5), ("PR-2002", 1),
     ("PR-2022", 52)],
)
def test_effectifs_non_valides_par_election(par_election, election, attendu):
    """Les élections antérieures à 2007 n'ont pas d'article Wikipédia dédié.

    Ce qu'on en sait vient des décisions du Conseil constitutionnel rejetant
    une réclamation contre la liste arrêtée, et pour 1974 d'un tableau de
    l'article principal. 1965, 1988, 1995 et 2002 n'ont rien d'exploitable.
    """
    non_valides = [c for c in par_election[election].candidats if c.etat != "validee"]
    assert len(non_valides) == attendu


@pytest.mark.parametrize("election", ["PR-1965", "PR-1988"])
def test_elections_sans_candidature_non_validee(par_election, election):
    """Rien n'a été importé faute de source exploitable, plutôt qu'à peu près.

    1965 ne parle que de personnalités « pressenties », 1988 n'a pas de section.
    """
    assert all(c.etat == "validee" for c in par_election[election].candidats)


def test_une_personne_validee_puis_ecartee_ailleurs(par_election):
    """Brice LALONDE : validé en 1981, écarté en 1995 et 2002, faute de parrainages.

    C'est le registre qui relie ces trois candidatures : rien dans les données
    d'une élection ne renvoie à une autre.
    """
    etats = {
        election: next(
            c.etat for c in entree.candidats if c.personne == "PE-0027"
        )
        for election, entree in par_election.items()
        if any(c.personne == "PE-0027" for c in entree.candidats)
    }
    assert etats == {"PR-1981": "validee", "PR-1995": "ecartee", "PR-2002": "ecartee"}


def test_les_ecartees_anciennes_sont_sourcees_par_le_conseil(par_election):
    """Une réclamation rejetée établit une candidature écartée mieux qu'une
    mention encyclopédique."""
    for election in ("PR-1969", "PR-1981"):
        for candidat in par_election[election].candidats:
            if candidat.etat == "ecartee":
                sources = [s for c in candidat.etats for s in c.sources]
                assert all(s.startswith("conseil-constitutionnel:") for s in sources)


def test_une_trajectoire_a_deux_etats_de_sources_differentes(par_election):
    """Brice LALONDE en 2002 : déclaration attestée par la presse, écartement
    par l'encyclopédie.

    C'est la forme que prendront les candidatures de 2027 : une annonce datée
    et sourcée, puis ce qu'il en advient, chaque état avec sa propre source.
    """
    candidat = next(
        c for c in par_election["PR-2002"].candidats if c.personne == "PE-0027"
    )
    assert [c.etat for c in candidat.etats] == ["declaree", "ecartee"]
    assert str(candidat.etats[0].date) == "2001-06-23"
    assert candidat.etats[0].sources == ("le-parisien:lalonde-candidat-elysee-2002",)
    assert candidat.etat == "ecartee", "l'état courant reste le dernier"
