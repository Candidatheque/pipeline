"""La publication est le contrat avec le dépôt de destination.

Ces tests vérifient la forme produite, sa conformité aux schémas publiés et
l'idempotence. Sans elle, chaque passage de la pipeline produirait un commit
vide dans le dépôt de destination.
"""

from __future__ import annotations

import json

import pytest
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

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


@pytest.fixture(scope="module")
def destination(tmp_path_factory):
    """Un dépôt publié une fois, partagé par les tests qui ne le modifient pas.

    Publier écrit une quinzaine de mégaoctets, dont les 60 723 parrainages ; le
    refaire à chaque test faisait passer ce module de dix à quatre-vingts
    secondes.
    """
    racine = tmp_path_factory.mktemp("depot")
    publier(racine)
    return racine


@pytest.fixture
def depot_modifiable(tmp_path):
    """Un dépôt à soi, pour les tests qui y touchent avant de republier."""
    publier(tmp_path)
    return tmp_path


def _charge(chemin):
    return json.loads(chemin.read_text(encoding="utf-8"))


def _registre():
    """Les schémas se référencent entre eux : il faut les résoudre ensemble."""
    registre = Registry()
    for chemin in SCHEMAS_DIR.glob("*.schema.json"):
        registre = registre.with_resource(chemin.name, Resource.from_contents(_charge(chemin)))
    return registre


def _valideur(nom):
    schema = _charge(SCHEMAS_DIR / nom)
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, registry=_registre())


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
        assert metadonnees["wikidata"].startswith("Q")
        assert metadonnees["tours"], "chaque élection publie au moins un tour"
        assert [t["numero"] for t in metadonnees["tours"]] == list(
            range(1, len(metadonnees["tours"]) + 1)
        )


def test_le_schema_reference_depuis_les_donnees_existe(destination):
    metadonnees = destination / ELECTIONS_DIR / "PR-2012" / ELECTION_FILE
    chemin = (metadonnees.parent / _charge(metadonnees)["$schema"]).resolve()
    assert chemin.is_file()

    index = destination / INDEX_FILE
    assert (index.parent / _charge(index)["$schema"]).resolve().is_file()


def test_une_seconde_publication_ne_reecrit_rien(depot_modifiable):
    assert {e.statut for e in publier(depot_modifiable)} == {Statut.INCHANGE}


def test_un_repertoire_obsolete_est_supprime(depot_modifiable):
    obsolete = depot_modifiable / ELECTIONS_DIR / "PR-1900"
    obsolete.mkdir()
    (obsolete / ELECTION_FILE).write_text("{}", encoding="utf-8")

    ecritures = publier(depot_modifiable)

    assert not obsolete.exists()
    assert [e.chemin for e in ecritures if e.statut is Statut.SUPPRIME] == [obsolete]


def test_une_modification_est_detectee(depot_modifiable):
    cible = depot_modifiable / ELECTIONS_DIR / "PR-2012" / ELECTION_FILE
    cible.write_text("{}", encoding="utf-8")

    modifies = [e.chemin for e in publier(depot_modifiable) if e.statut is Statut.MODIFIE]

    assert modifies == [cible]


def test_un_document_orphelin_est_supprime(depot_modifiable):
    """Un sujet qui cesse d'être produit ne doit pas rester dans `data`."""
    orphelin = depot_modifiable / ELECTIONS_DIR / "PR-2012" / "parrainages.json"
    orphelin.write_text('{"election": "PR-2012"}', encoding="utf-8")

    ecritures = publier(depot_modifiable)

    assert not orphelin.exists()
    assert [e.chemin for e in ecritures if e.statut is Statut.SUPPRIME] == [orphelin]


def test_les_documents_connus_sont_publies(elections_du_seed):
    """Le point d'extension rend au moins les métadonnées, sous un nom de fichier."""
    noms = [nom for nom, _ in documents(elections_du_seed[0])]
    assert noms == [ELECTION_FILE]


def test_un_tour_sans_qid_omet_le_champ(destination):
    """Absent se lit « Wikidata ne modélise pas ce tour ».

    Publier `null` inviterait à y voir une valeur.
    """
    tours = _charge(destination / ELECTIONS_DIR / "PR-1969" / ELECTION_FILE)["tours"]
    assert all("wikidata" not in tour for tour in tours)


def test_l_index_ne_porte_pas_les_tours(destination):
    """L'index sert à énumérer ; le détail vit dans le document de l'élection."""
    for entree in _charge(destination / INDEX_FILE)["elections"]:
        assert set(entree) == {"id", "annee"}


def test_les_candidatures_sont_publiees_et_conformes(destination):
    valideur = _valideur("candidatures.schema.json")
    publies = sorted((destination / ELECTIONS_DIR).glob("*/candidatures.json"))
    assert len(publies) == 11
    for chemin in publies:
        valideur.validate(_charge(chemin))


def test_une_election_sans_candidature_ne_publie_pas_de_document_vide(destination):
    """Deux élections n'ont pas les mêmes documents, selon leur stade."""
    repertoire = destination / ELECTIONS_DIR / "PR-2027"
    assert (repertoire / ELECTION_FILE).is_file()
    assert not (repertoire / "candidatures.json").exists()


def test_les_sources_sont_recopiees_en_clair(destination):
    """Le seed cite par identifiant ; le publié se lit sans résoudre de référence."""
    doc = _charge(destination / ELECTIONS_DIR / "PR-2022" / "candidatures.json")
    avec_tour = next(c for c in doc["candidatures"] if c["tours"])
    source = avec_tour["tours"][0]["sources"][0]
    assert source["id"].startswith("conseil-constitutionnel:")
    assert source["url"].startswith("https://")
    assert source["commentaire"]
    assert source["consultee_le"] == "2026-09-20"


def test_chaque_tour_cite_correspond_a_un_tour_de_l_election(destination):
    for chemin in sorted((destination / ELECTIONS_DIR).glob("*/candidatures.json")):
        connus = {t["numero"] for t in _charge(chemin.parent / ELECTION_FILE)["tours"]}
        for candidature in _charge(chemin)["candidatures"]:
            assert {t["numero"] for t in candidature["tours"]} <= connus


def test_le_nom_publie_est_resolu_depuis_le_registre(destination):
    """Le seed ne répète pas le nom ; le document publié le porte toujours."""
    doc = _charge(destination / ELECTIONS_DIR / "PR-1965" / "candidatures.json")
    par_personne = {c["personne"]: c for c in doc["candidatures"]}
    assert par_personne["PE-0002"]["nom_complet"] == "Charles DE GAULLE"
    assert all(c["nom_complet"] for c in doc["candidatures"])


def test_la_trajectoire_est_publiee_sans_etat_courant_a_part(destination):
    """L'état courant se déduit du dernier élément ; le publier serait dérivé."""
    doc = _charge(destination / ELECTIONS_DIR / "PR-2022" / "candidatures.json")
    etats_finaux = set()
    for candidature in doc["candidatures"]:
        assert "etat" not in candidature
        assert candidature["etats"]
        assert all(changement["sources"] for changement in candidature["etats"])
        etats_finaux.add(candidature["etats"][-1]["etat"])
    assert etats_finaux == {"validee", "ecartee", "retiree"}


def test_les_partis_sont_publies_avec_leur_nom(destination):
    """Le seed cite un parti par identifiant ; le publié porte aussi son nom."""
    doc = _charge(destination / ELECTIONS_DIR / "PR-2022" / "candidatures.json")
    melenchon = next(c for c in doc["candidatures"] if c["personne"] == "PE-0061")
    assert [(p["nom_complet"], p["sigle"]) for p in melenchon["partis"]] == [
        ("La France insoumise", "LFI"),
        ("Parti de gauche", "PG"),
    ]
    assert all(p["id"].startswith("PA-") for p in melenchon["partis"])
    assert all(p["sources"] for p in melenchon["partis"])


class TestParrainages:
    """Les parrainages publiés, candidat par candidat."""

    @pytest.fixture(scope="class")
    @classmethod
    def sources_du_seed(cls):
        from candidatheque.pipeline.seeds.parrainages import load_parrainages

        return {source.election: source for source in load_parrainages()}

    def _documents(self, destination, election):
        racine = destination / ELECTIONS_DIR / election / "candidats"
        return sorted(racine.glob("*/parrainages.json"))

    def test_un_document_par_candidat(self, destination, sources_du_seed):
        """Un consommateur qui suit un candidat ne télécharge pas les autres."""
        for election, source in sources_du_seed.items():
            attendus = {candidat.personne for candidat in source.candidats if candidat.personne}
            publies = {chemin.parent.name for chemin in self._documents(destination, election)}
            assert publies <= attendus, election
            assert publies, election

    def test_les_documents_sont_conformes_a_leur_schema(self, destination):
        valideur = _valideur("parrainages.schema.json")
        racine = destination / ELECTIONS_DIR
        documents_publies = sorted(racine.glob("*/candidats/*/parrainages.json"))
        assert len(documents_publies) > 100
        for chemin in documents_publies:
            valideur.validate(_charge(chemin))

    def test_le_document_des_non_candidats_est_conforme(self, destination):
        valideur = _valideur("parrainages-sans-candidature.schema.json")
        racine = destination / ELECTIONS_DIR
        documents_publies = sorted(racine.glob("*/parrainages-sans-candidature.json"))
        assert len(documents_publies) == 2, "2017 et 2022 seules en produisent"
        for chemin in documents_publies:
            valideur.validate(_charge(chemin))

    def test_le_schema_reference_depuis_les_donnees_existe(self, destination):
        for motif in ("*/candidats/*/parrainages.json", "*/parrainages-sans-candidature.json"):
            for chemin in (destination / ELECTIONS_DIR).glob(motif):
                cible = (chemin.parent / _charge(chemin)["$schema"]).resolve()
                assert cible.is_file(), chemin

    def test_chaque_liste_tiree_au_sort_compte_ses_cinq_cents_noms(
        self, destination, sources_du_seed
    ):
        """L'exhaustivité tient jusque dans les fichiers publiés.

        La vérifier à la lecture ne suffit pas : c'est ce qui sort du dépôt qui
        engage le projet.
        """
        for election, source in sources_du_seed.items():
            if source.etendue.value != "tirage-au-sort":
                continue
            for chemin in self._documents(destination, election):
                publie = _charge(chemin)
                assert len(publie["parrainages"]) == 500, chemin

    def test_l_etendue_est_publiee(self, destination):
        """Sans elle, compter les lignes de 2007 donne un total faux."""
        for chemin in (destination / ELECTIONS_DIR).glob("*/candidats/*/parrainages.json"):
            assert _charge(chemin)["etendue"] in {"integrale", "tirage-au-sort"}

    def test_chaque_date_renvoie_a_une_publication_declaree(self, destination):
        for chemin in (destination / ELECTIONS_DIR).glob("*/candidats/*/parrainages.json"):
            publie = _charge(chemin)
            dates = {publication["date"] for publication in publie["publications"]}
            portees = {
                parrainage["publie_le"]
                for parrainage in publie["parrainages"]
                if "publie_le" in parrainage
            }
            assert portees <= dates, chemin

    def test_aucun_parrainage_n_est_perdu(self, destination, sources_du_seed):
        """Ce qui est lu est publié, dans un document ou dans l'autre."""
        from candidatheque.pipeline.lecture.parrainages import lire

        racine = destination / ELECTIONS_DIR
        for election, source in sources_du_seed.items():
            publies = sum(
                len(_charge(chemin)["parrainages"])
                for chemin in self._documents(destination, election)
            )
            hors = racine / election / "parrainages-sans-candidature.json"
            if hors.is_file():
                publies += sum(
                    len(beneficiaire["parrainages"])
                    for beneficiaire in _charge(hors)["beneficiaires"]
                )
            assert publies == len(lire(source)), election

    def test_aucune_presentation_ne_perd_son_mandat(self, destination):
        """Le vocabulaire couvre les 60 723 présentations, sans exception.

        Le champ est facultatif au schéma, parce qu'une source pourrait un jour
        ne pas donner la qualité de l'élu. Aucune ne le fait à ce jour, et une
        graphie inédite qui passerait au travers des règles doit se voir en revue
        plutôt que de vider silencieusement le champ.
        """
        for chemin in (destination / ELECTIONS_DIR).glob("*/candidats/*/parrainages.json"):
            sans = [p for p in _charge(chemin)["parrainages"] if "mandat" not in p]
            assert not sans, (chemin, sans[:3])

    def test_le_departement_publie_est_un_code_du_registre(self, destination):
        """Aucun nom, aucune césure, aucun code inventé n'arrive dans les données."""
        from candidatheque.pipeline.seeds.departements import load_departements

        connus = {d.code for d in load_departements()}
        for chemin in (destination / ELECTIONS_DIR).glob("*/candidats/*/parrainages.json"):
            publies = {p["departement"] for p in _charge(chemin)["parrainages"] if "departement" in p}
            assert publies <= connus, (chemin, sorted(publies - connus))

    def test_seuls_les_deputes_portent_une_circonscription(self, destination):
        """Le numéro n'a de sens que pour eux ; ailleurs, c'est une erreur."""
        for chemin in (destination / ELECTIONS_DIR).glob("*/candidats/*/parrainages.json"):
            autres = [
                p
                for p in _charge(chemin)["parrainages"]
                if "circonscription" in p and p.get("mandat") != "depute"
            ]
            assert not autres, (chemin, autres[:3])

    def test_le_territoire_ne_redit_pas_le_departement(self, destination):
        """« Guyane » n'ajoute rien à « 973 » quand le ressort est la collectivité.

        Le maire de MAYENNE fait exception, et c'est voulu : son territoire
        nomme la commune, non le département du même nom.
        """
        from candidatheque.pipeline.publication.departements import normaliser

        for chemin in (destination / ELECTIONS_DIR).glob("*/candidats/*/parrainages.json"):
            publie = _charge(chemin)
            annee = int(publie["election"].rsplit("-", 1)[1])
            redites = [
                p
                for p in publie["parrainages"]
                if p.get("mandat") in {"membre-assemblee-outre-mer", "conseiller-regional"}
                and "territoire" in p
                and "departement" in p
                and normaliser(p["territoire"], annee) == p["departement"]
            ]
            assert not redites, (chemin, redites[:3])

    def test_un_ressort_a_cheval_sur_deux_collectivites_n_a_pas_de_departement(
        self, destination
    ):
        """Saint-Barthélemy et Saint-Martin partagent une circonscription.

        Leurs codes sont 977 et 978 ; en choisir un affirmerait une précision
        que le Conseil constitutionnel ne donne pas, lui qui écrit les deux
        noms. Le nom va au territoire, le département reste vide.
        """
        trouves = 0
        for chemin in (destination / ELECTIONS_DIR).glob("*/candidats/*/parrainages.json"):
            for p in _charge(chemin)["parrainages"]:
                if p.get("territoire") == "Saint-Barthélemy et Saint-Martin":
                    trouves += 1
                    assert "departement" not in p, p
        assert trouves == 2

    def test_un_non_candidat_connu_du_registre_porte_son_identifiant(self, destination):
        """François HOLLANDE a reçu des présentations sans être candidat."""
        publie = _charge(
            destination / ELECTIONS_DIR / "PR-2022" / "parrainages-sans-candidature.json"
        )
        hollande = next(
            b for b in publie["beneficiaires"] if b["nom_complet"] == "François HOLLANDE"
        )
        assert hollande["personne"] == "PE-0065"

    def test_le_nom_de_l_elu_est_publie_d_un_seul_tenant(self, destination):
        """Une seule forme de nom, quelle que soit celle de la source.

        2017 et 2022 séparent le prénom du nom, le Journal officiel ne l'a
        jamais fait : un consommateur qui lit les huit élections n'a pas à
        connaître cette histoire.
        """
        for motif in ("*/candidats/*/parrainages.json", "*/parrainages-sans-candidature.json"):
            for chemin in (destination / ELECTIONS_DIR).glob(motif):
                publie = _charge(chemin)
                listes = [publie["parrainages"]] if "parrainages" in publie else [
                    b["parrainages"] for b in publie["beneficiaires"]
                ]
                for presentations in listes:
                    for presentation in presentations:
                        assert presentation["nom_complet"].strip(), (chemin, presentation)
                        assert "nom" not in presentation and "prenom" not in presentation

    def test_le_prenom_de_2022_precede_le_nom_de_famille(self, destination):
        """« NICOLAS », « Thierry » recollés dans l'ordre du registre."""
        publie = _charge(
            destination / ELECTIONS_DIR / "PR-2022" / "candidats" / "PE-0072" / "parrainages.json"
        )
        noms = {p["nom_complet"] for p in publie["parrainages"]}
        assert all(nom == " ".join(nom.split()) for nom in noms)
        assert not any(nom.split()[0].isupper() and not nom.split()[-1].isupper() for nom in noms)

    def test_un_non_candidat_absent_du_registre_n_a_pas_d_identifiant(self, destination):
        """Thomas PESQUET n'a jamais été candidat : il n'est pas au registre."""
        publie = _charge(
            destination / ELECTIONS_DIR / "PR-2022" / "parrainages-sans-candidature.json"
        )
        pesquet = next(b for b in publie["beneficiaires"] if b["nom_complet"] == "Thomas PESQUET")
        assert "personne" not in pesquet

    def test_une_election_sans_parrainages_ne_publie_pas_de_repertoire(self, destination):
        """Avant la loi organique de 1976, les listes n'étaient pas publiées."""
        for election in ("PR-1965", "PR-1969", "PR-1974"):
            assert not (destination / ELECTIONS_DIR / election / "candidats").exists()

    def test_le_repertoire_d_un_candidat_disparu_est_retire(self, tmp_path):
        """Le dépôt de destination ne garde rien des états précédents."""
        publier(tmp_path)
        intrus = tmp_path / ELECTIONS_DIR / "PR-2002" / "candidats" / "PE-9999"
        intrus.mkdir(parents=True)
        (intrus / "parrainages.json").write_text("{}", encoding="utf-8")
        publier(tmp_path)
        assert not intrus.exists()


class TestResultatsProclames:
    """Les résultats de chaque tour, tels que le Conseil constitutionnel les proclame."""

    FICHIER = "resultats-proclames.json"

    def _documents(self, destination):
        return {
            chemin.parent.name: _charge(chemin)
            for chemin in (destination / ELECTIONS_DIR).glob(f"*/{self.FICHIER}")
        }

    def test_les_documents_sont_conformes_a_leur_schema(self, destination):
        valideur = _valideur("resultats-proclames.schema.json")
        documents_publies = self._documents(destination)
        assert len(documents_publies) == 11
        for document in documents_publies.values():
            valideur.validate(document)

    def test_une_election_a_venir_n_a_pas_de_resultats(self, destination):
        """Un fichier absent dit qu'il n'y a rien, mieux qu'un fichier vide."""
        assert not (destination / ELECTIONS_DIR / "PR-2027" / self.FICHIER).exists()

    def test_la_somme_des_voix_fait_les_suffrages_exprimes(self, destination):
        for election, document in self._documents(destination).items():
            for tour in document["tours"]:
                somme = sum(v["voix"] for v in tour["voix"])
                assert somme == tour["suffrages_exprimes"], f"{election} T{tour['numero']}"

    def test_les_tours_et_les_candidats_renvoient_a_ceux_de_l_election(self, destination):
        """Même date que « election.json », mêmes personnes que les candidatures."""
        for election, document in self._documents(destination).items():
            repertoire = destination / ELECTIONS_DIR / election
            dates = {t["numero"]: t["date"] for t in _charge(repertoire / "election.json")["tours"]}
            candidatures = {
                c["personne"]: c
                for c in _charge(repertoire / "candidatures.json")["candidatures"]
            }
            for tour in document["tours"]:
                assert tour["date"] == dates[tour["numero"]], election
                for voix in tour["voix"]:
                    candidature = candidatures[voix["personne"]]
                    assert voix["nom_complet"] == candidature["nom_complet"]
                    assert tour["numero"] in {t["numero"] for t in candidature["tours"]}

    def test_le_departement_d_une_annulation_est_un_code_du_registre(self, destination):
        from candidatheque.pipeline.seeds.departements import load_departements

        connus = {d.code for d in load_departements()}
        for election, document in self._documents(destination).items():
            for tour in document["tours"]:
                publies = {a["departement"] for a in tour["annulations"] if "departement" in a}
                assert publies <= connus, (election, sorted(publies - connus))

    def test_seul_le_bureau_porte_des_numeros(self, destination):
        """Une commune entière annulée n'a pas de numéro de bureau."""
        for document in self._documents(destination).values():
            for tour in document["tours"]:
                for annulation in tour["annulations"]:
                    if annulation["portee"] == "commune":
                        assert "bureaux" not in annulation, annulation

    def test_rien_n_est_calcule(self, destination):
        """Ni pourcentage, ni abstention : les entiers de la décision, et eux seuls."""
        for document in self._documents(destination).values():
            for tour in document["tours"]:
                assert not {"abstention", "pourcentage", "blancs_et_nuls"} & set(tour)
                assert all(set(v) == {"personne", "nom_complet", "voix"} for v in tour["voix"])


class TestNomALEndroit:
    """Les noms que les sources écrivent à l'envers, remis dans l'ordre."""

    @pytest.mark.parametrize(
        ("source", "attendu"),
        [
            ("PESQUET Thomas", "Thomas PESQUET"),
            ("CAZENEUVE  Bernard", "Bernard CAZENEUVE"),
            ("MÉNARD Emmanuelle", "Emmanuelle MÉNARD"),
            ("KOSCIUSKO-MORIZET Nathalie", "Nathalie KOSCIUSKO-MORIZET"),
            ("MARECHAL Philippe Célestin", "Philippe Célestin MARECHAL"),
            ("LE GALL Gilbert", "Gilbert LE GALL"),
            # Déjà dans le bon ordre : on n'y touche pas.
            ("Christian PÉNIGUEL", "Christian PÉNIGUEL"),
            # Rien ne distingue le nom du prénom : mieux vaut ne rien couper.
            ("LARSONNEUR-MOREL", "LARSONNEUR-MOREL"),
            ("Eva Joly", "Eva Joly"),
            # La civilité est une qualité, pas une partie du nom.
            ("M. Jacques CHIRAC", "Jacques CHIRAC"),
        ],
    )
    def test_le_nom_de_famille_passe_derriere_le_prenom(self, source, attendu):
        from candidatheque.pipeline.publication.parrainages import nom_a_l_endroit

        assert nom_a_l_endroit(source) == attendu
