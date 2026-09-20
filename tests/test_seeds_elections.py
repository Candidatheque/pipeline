"""Le seed est saisi à la main : ces tests sont sa relecture automatique."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from candidatheque.pipeline.seeds import load_elections
from candidatheque.pipeline.seeds.elections import Election

#: De quoi construire une élection valide quand le test porte sur autre chose.
UN_TOUR = [{"numero": 1, "date": "2012-04-22"}]


@pytest.fixture(scope="module")
def elections():
    return load_elections()


def test_le_seed_du_depot_est_valide(elections):
    assert len(elections) == 12


def test_les_elections_sont_ordonnees_et_uniques(elections):
    annees = [election.annee for election in elections]
    assert annees == sorted(annees)
    assert len(set(annees)) == len(annees)


def test_les_bornes_du_seed(elections):
    assert elections[0].id == "PR-1965"
    assert elections[-1].id == "PR-2027"


def test_chaque_election_porte_son_identifiant_wikidata(elections):
    assert all(election.wikidata.startswith("Q") for election in elections)
    qids = [election.wikidata for election in elections]
    assert len(set(qids)) == len(qids)


def test_quelques_identifiants_wikidata_connus(elections):
    """Vérifiés le 2026-09-20 contre `requetes/elections-wikidata.rq`."""
    par_id = {election.id: election.wikidata for election in elections}
    assert par_id["PR-1965"] == "Q1450635"
    assert par_id["PR-2012"] == "Q487666"
    assert par_id["PR-2027"] == "Q111594692"


@pytest.mark.parametrize(
    "identifiant",
    ["2012", "PR-12", "PR-20123", "LG-2012", "pr-2012", "PR-2012 ", "cdt:PR-2012"],
)
def test_identifiants_mal_formes_rejetes(identifiant):
    with pytest.raises(ValidationError):
        Election(id=identifiant, annee=2012, wikidata="Q487666", tours=UN_TOUR)


def test_annee_incoherente_avec_l_identifiant_rejetee():
    with pytest.raises(ValidationError, match="contredit l'identifiant"):
        Election(id="PR-2012", annee=2017, wikidata="Q487666", tours=UN_TOUR)


@pytest.mark.parametrize("qid", ["Q0", "P42", "487666", "q487666", ""])
def test_wikidata_mal_forme_rejete(qid):
    with pytest.raises(ValidationError):
        Election(id="PR-2012", annee=2012, wikidata=qid, tours=UN_TOUR)


def test_wikidata_manquant_rejete():
    """Les douze élections en ont un : son absence est une omission, pas un cas."""
    with pytest.raises(ValidationError):
        Election.model_validate({"id": "PR-2012", "annee": 2012, "tours": UN_TOUR})


def test_champ_inconnu_rejete():
    with pytest.raises(ValidationError):
        Election.model_validate({"id": "PR-2012", "annee": 2012, "wikidata": "Q487666", "tours": UN_TOUR, "couleur": "bleu"})


def test_elections_non_ordonnees_rejetees(tmp_path):
    seed = tmp_path / "elections.yaml"
    seed.write_text(
        'elections:\n  - id: "PR-2022"\n    annee: 2022\n    wikidata: "Q30638578"\n    tours:\n      - numero: 1\n        date: 2022-04-10\n'
        '  - id: "PR-2012"\n    annee: 2012\n    wikidata: "Q487666"\n'
        '    tours:\n      - numero: 1\n        date: 2012-04-22\n',
        encoding="utf-8",
    )
    with pytest.raises(ValidationError, match="année croissante"):
        load_elections(seed)


def test_annees_en_double_rejetees(tmp_path):
    seed = tmp_path / "elections.yaml"
    seed.write_text(
        'elections:\n  - id: "PR-2012"\n    annee: 2012\n    wikidata: "Q487666"\n    tours:\n      - numero: 1\n        date: 2012-04-22\n'
        '  - id: "PR-2012"\n    annee: 2012\n    wikidata: "Q1129306"\n'
        '    tours:\n      - numero: 1\n        date: 2012-04-22\n',
        encoding="utf-8",
    )
    with pytest.raises(ValidationError, match="même année"):
        load_elections(seed)


class TestTours:
    """Les tours viennent du seed : ces tests sont leur relecture automatique."""

    @staticmethod
    def _election(tours):
        return {"id": "PR-2012", "annee": 2012, "wikidata": "Q487666", "tours": tours}

    def test_le_seed_du_depot_a_deux_tours_partout(self, elections):
        """Constat, pas règle : c'est arrivé à chaque fois, rien ne l'impose."""
        assert all(len(election.tours) == 2 for election in elections)

    def test_un_tour_unique_est_valide(self):
        """Une majorité absolue au premier tour rendrait le second inutile.

        Ce n'est jamais arrivé depuis 1965, mais le modèle ne doit pas
        l'interdire.
        """
        election = Election.model_validate(
            self._election([{"numero": 1, "date": "2012-04-22"}])
        )
        assert len(election.tours) == 1
        assert election.tour(2) is None

    def test_les_dates_des_tours_du_seed_sont_connues(self, elections):
        par_id = {election.id: election for election in elections}
        assert [str(t.date) for t in par_id["PR-2022"].tours] == ["2022-04-10", "2022-04-24"]
        assert par_id["PR-1965"].tour(1).wikidata == "Q112074051"

    def test_wikidata_de_tour_facultatif(self, elections):
        """Wikidata ne modélise pas les tours de 1969 : le seed doit l'assumer."""
        par_id = {election.id: election for election in elections}
        assert all(t.wikidata is None for t in par_id["PR-1969"].tours)

    def test_sans_tour_rejete(self):
        with pytest.raises(ValidationError):
            Election.model_validate(self._election([]))

    def test_numerotation_trouee_rejetee(self):
        with pytest.raises(ValidationError, match="numérotés"):
            Election.model_validate(
                self._election([{"numero": 1, "date": "2012-04-22"},
                                {"numero": 3, "date": "2012-05-06"}])
            )

    def test_tours_dans_le_desordre_rejetes(self):
        with pytest.raises(ValidationError, match="numérotés"):
            Election.model_validate(
                self._election([{"numero": 2, "date": "2012-04-22"},
                                {"numero": 1, "date": "2012-05-06"}])
            )

    def test_dates_non_croissantes_rejetees(self):
        with pytest.raises(ValidationError, match="strictement croissantes"):
            Election.model_validate(
                self._election([{"numero": 1, "date": "2012-05-06"},
                                {"numero": 2, "date": "2012-04-22"}])
            )

    def test_premier_tour_dans_une_autre_annee_rejete(self):
        with pytest.raises(ValidationError, match="contredit l'année"):
            Election.model_validate(
                self._election([{"numero": 1, "date": "2011-04-22"}])
            )

    def test_qid_de_tour_reutilise_ailleurs_rejete(self, tmp_path):
        """Un copier-coller d'un scrutin à l'autre ne se repère que là."""
        seed = tmp_path / "elections.yaml"
        seed.write_text(
            'elections:\n'
            '  - id: "PR-2012"\n    annee: 2012\n    wikidata: "Q487666"\n'
            '    tours:\n      - numero: 1\n        date: 2012-04-22\n'
            '        wikidata: "Q24102723"\n'
            '  - id: "PR-2017"\n    annee: 2017\n    wikidata: "Q7020999"\n'
            '    tours:\n      - numero: 1\n        date: 2017-04-23\n'
            '        wikidata: "Q24102723"\n',
            encoding="utf-8",
        )
        with pytest.raises(ValidationError, match="deux fois"):
            load_elections(seed)
