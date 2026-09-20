"""La CLI est la surface utilisée par la CI : son code de retour fait foi."""

from __future__ import annotations

from candidatheque.pipeline.cli import main


def test_valider_reussit_sur_le_seed_du_depot(capsys):
    assert main(["valider"]) == 0
    assert "11 élections" in capsys.readouterr().out


def test_lister_affiche_chaque_election(capsys):
    assert main(["lister"]) == 0
    lignes = capsys.readouterr().out.splitlines()
    assert len(lignes) == 11
    assert lignes[-1].split() == ["PR-2022", "2022"]


def test_publier_ecrit_dans_la_destination_demandee(tmp_path, capsys):
    assert main(["publier", "--destination", str(tmp_path)]) == 0
    assert (tmp_path / "elections.json").is_file()
    assert "créés" in capsys.readouterr().out
