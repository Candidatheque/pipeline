"""La publication est le contrat avec le dépôt de destination.

Ces tests vérifient la forme produite, sa conformité aux schémas publiés et
l'idempotence. Sans elle, chaque passage de la pipeline produirait un commit
vide dans le dépôt de destination.
"""

from __future__ import annotations

import json

import pytest
from jsonschema import Draft202012Validator

from candidatheque.pipeline.paths import SCHEMAS_DIR
from candidatheque.pipeline.publication import Statut, publier
from candidatheque.pipeline.publication.elections import (
    ELECTION_FILE,
    ELECTIONS_DIR,
    INDEX_FILE,
)


@pytest.fixture
def destination(tmp_path):
    publier(tmp_path)
    return tmp_path


def _charge(chemin):
    return json.loads(chemin.read_text(encoding="utf-8"))


def _valideur(nom):
    schema = _charge(SCHEMAS_DIR / nom)
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def test_les_schemas_sont_recopies(destination):
    noms = {chemin.name for chemin in (destination / "schemas").iterdir()}
    assert noms == {chemin.name for chemin in SCHEMAS_DIR.glob("*.schema.json")}


def test_l_index_est_conforme_a_son_schema(destination):
    _valideur("elections.schema.json").validate(_charge(destination / INDEX_FILE))


def test_l_index_liste_toutes_les_elections(destination):
    index = _charge(destination / INDEX_FILE)
    assert len(index["elections"]) == 12
    assert index["elections"][0] == {"id": "PR-1965", "annee": 1965}
    assert [e["annee"] for e in index["elections"]] == sorted(
        e["annee"] for e in index["elections"]
    )


def test_chaque_election_a_son_repertoire_et_ses_metadonnees(destination):
    valideur = _valideur("election.schema.json")
    index = _charge(destination / INDEX_FILE)

    for entree in index["elections"]:
        repertoire = destination / ELECTIONS_DIR / entree["id"]
        metadonnees = _charge(repertoire / ELECTION_FILE)
        valideur.validate(metadonnees)
        assert metadonnees["id"] == entree["id"]
        assert metadonnees["annee"] == entree["annee"]


def test_le_schema_reference_depuis_les_donnees_existe(destination):
    metadonnees = destination / ELECTIONS_DIR / "PR-2012" / ELECTION_FILE
    chemin = (metadonnees.parent / _charge(metadonnees)["$schema"]).resolve()
    assert chemin.is_file()

    index = destination / INDEX_FILE
    assert (index.parent / _charge(index)["$schema"]).resolve().is_file()


def test_une_seconde_publication_ne_reecrit_rien(destination):
    assert {e.statut for e in publier(destination)} == {Statut.INCHANGE}


def test_un_repertoire_obsolete_est_supprime(destination):
    obsolete = destination / ELECTIONS_DIR / "PR-1900"
    obsolete.mkdir()
    (obsolete / ELECTION_FILE).write_text("{}", encoding="utf-8")

    ecritures = publier(destination)

    assert not obsolete.exists()
    assert [e.chemin for e in ecritures if e.statut is Statut.SUPPRIME] == [obsolete]


def test_une_modification_est_detectee(destination):
    cible = destination / ELECTIONS_DIR / "PR-2012" / ELECTION_FILE
    cible.write_text("{}", encoding="utf-8")

    modifies = [e.chemin for e in publier(destination) if e.statut is Statut.MODIFIE]

    assert modifies == [cible]
