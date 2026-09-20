"""La CLI est la surface utilisée par la CI : son code de retour fait foi."""

from __future__ import annotations

from candidatheque.pipeline.cli import main


def test_valider_reussit_sur_le_seed_du_depot(capsys):
    assert main(["valider"]) == 0
    sortie = capsys.readouterr().out
    assert "12 élections" in sortie
    assert "241 personnes" in sortie
    assert "316 candidatures" in sortie
    assert "cohérents" in sortie


def test_lister_affiche_chaque_election(capsys):
    assert main(["lister"]) == 0
    lignes = capsys.readouterr().out.splitlines()
    assert len(lignes) == 12
    assert lignes[-1].split() == ["PR-2027", "2027"]


def test_publier_ecrit_dans_la_destination_demandee(tmp_path, capsys):
    assert main(["publier", "--destination", str(tmp_path)]) == 0
    assert (tmp_path / "elections.json").is_file()
    assert "créés" in capsys.readouterr().out
