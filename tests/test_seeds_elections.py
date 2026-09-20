"""Le seed est saisi à la main : ces tests sont sa relecture automatique."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from candidatheque.pipeline.seeds import load_elections
from candidatheque.pipeline.seeds.elections import Election


@pytest.fixture(scope="module")
def elections():
    return load_elections()


def test_le_seed_du_depot_est_valide(elections):
    assert len(elections) == 11


def test_les_elections_sont_ordonnees_et_uniques(elections):
    annees = [election.annee for election in elections]
    assert annees == sorted(annees)
    assert len(set(annees)) == len(annees)


def test_les_bornes_du_seed(elections):
    assert elections[0].id == "PR-1965"
    assert elections[-1].id == "PR-2022"


@pytest.mark.parametrize(
    "identifiant",
    ["2012", "PR-12", "PR-20123", "LG-2012", "pr-2012", "PR-2012 ", "cdt:PR-2012"],
)
def test_identifiants_mal_formes_rejetes(identifiant):
    with pytest.raises(ValidationError):
        Election(id=identifiant, annee=2012)


def test_annee_incoherente_avec_l_identifiant_rejetee():
    with pytest.raises(ValidationError, match="contredit l'identifiant"):
        Election(id="PR-2012", annee=2017)


def test_champ_inconnu_rejete():
    with pytest.raises(ValidationError):
        Election.model_validate({"id": "PR-2012", "annee": 2012, "couleur": "bleu"})


def test_elections_non_ordonnees_rejetees(tmp_path):
    seed = tmp_path / "elections.yaml"
    seed.write_text(
        'elections:\n  - id: "PR-2022"\n    annee: 2022\n'
        '  - id: "PR-2012"\n    annee: 2012\n',
        encoding="utf-8",
    )
    with pytest.raises(ValidationError, match="année croissante"):
        load_elections(seed)


def test_annees_en_double_rejetees(tmp_path):
    seed = tmp_path / "elections.yaml"
    seed.write_text(
        'elections:\n  - id: "PR-2012"\n    annee: 2012\n'
        '  - id: "PR-2012"\n    annee: 2012\n',
        encoding="utf-8",
    )
    with pytest.raises(ValidationError, match="même année"):
        load_elections(seed)
