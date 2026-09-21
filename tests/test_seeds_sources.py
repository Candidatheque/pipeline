"""La représentation des sources fait précédent : ces tests la fixent."""

from __future__ import annotations

import datetime as dt

import pytest
from pydantic import ValidationError

from candidatheque.pipeline.seeds import load_sources
from candidatheque.pipeline.seeds.sources import Source

SOURCE = {
    "id": "conseil-constitutionnel:2022-187-PDR",
    "url": "https://www.conseil-constitutionnel.fr/decision/2022/2022187PDR.htm",
    "commentaire": "Liste des candidats à l'élection présidentielle",
    "consultee_le": "2026-09-20",
}


def test_le_registre_du_depot_est_valide():
    sources = load_sources()
    assert len(sources) == 201
    autorites = {source.autorite for source in sources}
    assert autorites == {
        "assemblee-nationale",
        "conseil-constitutionnel",
        "wikipedia-fr",
        "le-parisien",
        "wikidata",
        "legifrance",
        "data-gouv",
    }


def test_une_source_bien_formee():
    source = Source.model_validate(SOURCE)
    assert source.autorite == "conseil-constitutionnel"
    assert source.consultee_le == dt.date(2026, 9, 20)


@pytest.mark.parametrize(
    "identifiant",
    ["2022-187-PDR", "conseil constitutionnel:2022-187", "Conseil:2022-187", ":2022-187", "cc:"],
)
def test_identifiants_mal_formes_rejetes(identifiant):
    with pytest.raises(ValidationError, match="autorité"):
        Source.model_validate(SOURCE | {"id": identifiant})


def test_url_non_https_rejetee():
    with pytest.raises(ValidationError, match="https"):
        Source.model_validate(SOURCE | {"url": "http://exemple.fr/a"})


def test_commentaire_vide_rejete():
    """Sans commentaire, on ne sait pas ce qu'on cite sans ouvrir le lien."""
    with pytest.raises(ValidationError):
        Source.model_validate(SOURCE | {"commentaire": ""})


def test_date_de_consultation_obligatoire():
    manquante = dict(SOURCE)
    del manquante["consultee_le"]
    with pytest.raises(ValidationError):
        Source.model_validate(manquante)


def test_identifiants_en_double_rejetes(tmp_path):
    seed = tmp_path / "sources.yaml"
    ligne = (
        '  - id: "conseil-constitutionnel:2022-187-PDR"\n'
        '    url: "https://exemple.fr/a"\n'
        '    commentaire: "Une décision"\n'
        "    consultee_le: 2026-09-20\n"
    )
    seed.write_text("sources:\n" + ligne * 2, encoding="utf-8")
    with pytest.raises(ValidationError, match="en double"):
        load_sources(seed)
