"""La déclaration des sources de parrainages."""

from __future__ import annotations

import datetime as dt

import pytest
from pydantic import ValidationError

from candidatheque.pipeline.seeds import load_elections, load_sources
from candidatheque.pipeline.seeds.parrainages import (
    Etendue,
    Format,
    SourceParrainages,
    load_parrainages,
)


def _source(**champs) -> dict:
    return {
        "election": "PR-2022",
        "fichier": "parrainages/2022.json",
        "origine": "data-gouv:parrainages-2022",
        "format": "json-plat",
        "etendue": "integrale",
        "publications": [{"date": "2022-02-01", "source": "a:b"}],
    } | champs


def test_le_depot_declare_une_source_par_election_couverte():
    sources = load_parrainages()
    assert len(sources) == 8
    elections = {election.id for election in load_elections()}
    assert {source.election for source in sources} <= elections


def test_le_fichier_source_est_dans_le_depot():
    """La pipeline ne télécharge rien : le fichier déclaré doit être là."""
    for source in load_parrainages():
        assert source.chemin().is_file(), source.fichier


def test_chaque_fichier_declare_le_document_dont_il_est_tire():
    """L'origine se distingue des décisions de publication.

    La décision est l'acte qui rend les présentations publiques ; l'origine est
    le document qui les porte, et dont la conversion se rejoue.
    """
    sources = {source.id for source in load_sources()}
    for source in load_parrainages():
        assert source.origine in sources, source.election
        assert source.origine not in {p.source for p in source.publications}


def test_l_etendue_distingue_le_tirage_au_sort_de_la_publication_integrale():
    """Avant 2017, la loi n'imposait de publier que 500 noms par candidat.

    Sans ce champ, compter les lignes ferait conclure que Nicolas Sarkozy n'a
    eu que 500 parrainages en 2007.
    """
    par_election = {source.election: source for source in load_parrainages()}
    assert par_election["PR-2007"].etendue is Etendue.TIRAGE_AU_SORT
    assert par_election["PR-2017"].etendue is Etendue.INTEGRALE


def test_les_publications_progressives_sont_toutes_datees():
    """À partir de 2017, le Conseil publie par vagues pendant la campagne."""
    par_election = {source.election: source for source in load_parrainages()}
    assert len(par_election["PR-2022"].publications) > 1
    assert len(par_election["PR-1981"].publications) == 1


def test_chaque_publication_cite_la_decision_qui_l_a_rendue_publique():
    for source in load_parrainages():
        assert all(publication.source for publication in source.publications)


def test_la_source_d_un_jour_est_la_decision_de_ce_jour():
    source = SourceParrainages.model_validate(
        _source(
            publications=[
                {"date": "2022-02-01", "source": "cc:une"},
                {"date": "2022-02-08", "source": "cc:deux"},
            ]
        )
    )
    assert source.source_du(dt.date(2022, 2, 8)) == "cc:deux"
    assert source.source_du(dt.date(2022, 3, 1)) is None


def test_format_inconnu_rejete():
    """Le code ne connaît que des formats : un format inédit demande du code."""
    with pytest.raises(ValidationError):
        SourceParrainages.model_validate(_source(format="csv"))


def test_publications_dans_le_desordre_rejetees():
    with pytest.raises(ValidationError, match="date croissante"):
        SourceParrainages.model_validate(
            _source(
                publications=[
                    {"date": "2022-02-08", "source": "cc:deux"},
                    {"date": "2022-02-01", "source": "cc:une"},
                ]
            )
        )


def test_sans_publication_rejete():
    with pytest.raises(ValidationError):
        SourceParrainages.model_validate(_source(publications=[]))


def test_deux_entrees_pour_la_meme_election_rejetees(tmp_path):
    seed = tmp_path / "parrainages.yaml"
    seed.write_text(
        "parrainages:\n"
        + 2
        * (
            '  - election: "PR-2022"\n'
            '    fichier: "parrainages/2022.json"\n'
            '    origine: "data-gouv:parrainages-2022"\n'
            '    format: "json-plat"\n'
            '    etendue: "integrale"\n'
            "    publications:\n"
            '      - date: 2022-02-01\n        source: "a:b"\n'
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValidationError, match="deux entrées"):
        load_parrainages(seed)


def test_tous_les_formats_declares_sont_utilises():
    """Un format que rien n'emploie est du code mort."""
    employes = {source.format for source in load_parrainages()}
    assert employes == set(Format)
