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
    documents,
)
from candidatheque.pipeline.seeds import load_elections


@pytest.fixture(scope="module")
def elections_du_seed():
    return load_elections()


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


def test_un_document_orphelin_est_supprime(destination):
    """Un sujet qui cesse d'être produit ne doit pas rester dans `data`."""
    orphelin = destination / ELECTIONS_DIR / "PR-2012" / "candidatures.json"
    orphelin.write_text('{"election": "PR-2012"}', encoding="utf-8")

    ecritures = publier(destination)

    assert not orphelin.exists()
    assert [e.chemin for e in ecritures if e.statut is Statut.SUPPRIME] == [orphelin]


def test_les_documents_connus_sont_publies(elections_du_seed):
    """Le point d'extension rend au moins les métadonnées, sous un nom de fichier."""
    noms = [nom for nom, _ in documents(elections_du_seed[0])]
    assert noms == [ELECTION_FILE]


class TestSchemaCandidatures:
    """Le schéma des candidatures n'a pas encore de producteur.

    Ces tests tiennent lieu de spécification : ils fixent ce que la collecte à
    venir devra produire, et surtout ce qu'elle n'aura pas le droit de produire.
    """

    @staticmethod
    def _candidature(**remplacements):
        base = {
            "personne": "PE-0001",
            "nom": "Dupont",
            "prenom": "Camille",
            "etat": "declaree",
            "sources": [{"url": "https://exemple.fr/a", "consultee_le": "2026-09-20"}],
        }
        return base | remplacements

    @staticmethod
    def _document(*candidatures):
        return {"election": "PR-2027", "candidatures": list(candidatures)}

    @pytest.fixture(scope="class")
    @classmethod
    def valideur(cls):
        return _valideur("candidatures.schema.json")

    def test_un_document_bien_forme_est_accepte(self, valideur):
        valideur.validate(self._document(self._candidature(wikidata="Q42")))

    @pytest.mark.parametrize("etat", ["declaree", "validee", "retiree", "ecartee"])
    def test_les_quatre_etats_sont_acceptes(self, valideur, etat):
        valideur.validate(self._document(self._candidature(etat=etat)))

    def test_un_etat_hors_enumeration_est_rejete(self, valideur):
        assert not valideur.is_valid(self._document(self._candidature(etat="peut-etre")))

    def test_une_candidature_sans_source_est_rejetee(self, valideur):
        """Une candidature sans provenance ne vaut rien : elle est invérifiable."""
        assert not valideur.is_valid(self._document(self._candidature(sources=[])))

    def test_une_date_de_generation_est_rejetee(self, valideur):
        """Une date de génération ferait bouger le fichier à chaque passage."""
        assert not valideur.is_valid(
            self._document(self._candidature(publie_le="2026-09-20"))
        )

    def test_un_identifiant_d_election_mal_forme_est_rejete(self, valideur):
        document = self._document(self._candidature()) | {"election": "2027"}
        assert not valideur.is_valid(document)

    def test_une_candidature_sans_identifiant_de_personne_est_rejetee(self, valideur):
        """Sans lui, rien ne relie les candidatures successives d'une personne."""
        sans_personne = self._candidature()
        del sans_personne["personne"]
        assert not valideur.is_valid(self._document(sans_personne))

    @pytest.mark.parametrize("identifiant", ["PE-1", "0001", "PR-0001", "pe-0001"])
    def test_un_identifiant_de_personne_mal_forme_est_rejete(self, valideur, identifiant):
        assert not valideur.is_valid(self._document(self._candidature(personne=identifiant)))

    def test_une_personne_peut_changer_de_nom_entre_deux_elections(self, valideur):
        """Le nom publié est celui porté lors du scrutin, pas un nom de référence.

        Deux candidatures de la même personne sous deux noms différents ne sont
        pas une incohérence : c'est le cas qu'on veut pouvoir représenter.
        """
        valideur.validate(
            {
                "election": "PR-2012",
                "candidatures": [self._candidature(personne="PE-0001", nom="Dupont")],
            }
        )
        valideur.validate(
            {
                "election": "PR-2017",
                "candidatures": [self._candidature(personne="PE-0001", nom="Durand")],
            }
        )
