"""Le registre des partis, et le rattachement d'une candidature à un parti."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from candidatheque.pipeline.seeds import load_candidatures, load_partis
from candidatheque.pipeline.seeds.partis import Parti


def test_le_registre_du_depot_est_valide():
    partis = load_partis()
    assert len(partis) == 43
    numeros = [parti.numero for parti in partis]
    assert numeros == sorted(set(numeros))
    qids = [parti.wikidata for parti in partis if parti.wikidata]
    assert len(set(qids)) == len(qids)


def test_le_sigle_est_facultatif():
    """On dit « le PCF », mais beaucoup de petits mouvements n'ont pas de sigle."""
    partis = load_partis()
    avec = [p for p in partis if p.sigle]
    assert 20 < len(avec) < len(partis)
    assert Parti(id="PA-9999", nom_complet="Un mouvement").sigle is None


def test_l_identifiant_wikidata_reste_facultatif():
    """Les 43 en ont un parce qu'ils viennent tous de Wikidata.

    C'est un artefact de la source : les partis relevés dans les tableaux de
    2007 — « France Équité », « Esperanto Liberté » — n'en auront pas.
    """
    assert Parti(id="PA-9999", nom_complet="France Équité").wikidata is None


@pytest.mark.parametrize("identifiant", ["PA-1", "0001", "PE-0001", "pa-0001", "PA-00001"])
def test_identifiants_mal_formes_rejetes(identifiant):
    with pytest.raises(ValidationError, match="PA-0001"):
        Parti(id=identifiant, nom_complet="Un parti")


def test_nom_vide_rejete():
    with pytest.raises(ValidationError):
        Parti(id="PA-0001", nom_complet="")


def test_wikidata_mal_forme_rejete():
    with pytest.raises(ValidationError, match="Wikidata"):
        Parti(id="PA-0001", nom_complet="Un parti", wikidata="P42")


def test_numerotation_decroissante_rejetee(tmp_path):
    seed = tmp_path / "partis.yaml"
    seed.write_text(
        'partis:\n  - id: "PA-0002"\n    nom_complet: "Deux"\n  - id: "PA-0001"\n    nom_complet: "Un"\n',
        encoding="utf-8",
    )
    with pytest.raises(ValidationError, match="numéro croissant"):
        load_partis(seed)


class TestAffiliations:
    @pytest.fixture(scope="class")
    @classmethod
    def par_election(cls):
        return {entree.election: entree for entree in load_candidatures()}

    def test_une_candidature_peut_avoir_plusieurs_partis(self, par_election):
        """Une coalition présente un candidat unique, l'étiquette est partagée.

        Mélenchon en 2022 : La France insoumise et le Parti de gauche.
        """
        melenchon = next(
            c for c in par_election["PR-2022"].candidats if c.personne == "PE-0061"
        )
        assert len(melenchon.partis) == 2

    def test_un_parti_cite_deux_fois_est_rejete(self):
        from candidatheque.pipeline.seeds.candidatures import Candidature

        with pytest.raises(ValidationError, match="deux fois"):
            Candidature.model_validate(
                {
                    "personne": "PE-0001",
                    "etats": [{"etat": "validee", "sources": ["a:b"]}],
                    "partis": [
                        {"parti": "PA-0001", "sources": ["a:b"]},
                        {"parti": "PA-0001", "sources": ["a:b"]},
                    ],
                }
            )

    def test_toutes_les_affiliations_sont_sourcees(self, par_election):
        for entree in par_election.values():
            for candidat in entree.candidats:
                assert all(a.sources for a in candidat.partis)

    def test_un_parti_posterieur_au_scrutin_n_est_pas_rattache(self, par_election):
        """Charles DE GAULLE n'est pas rattaché à l'UDR en 1965.

        L'UDR est fondée en 1968. Wikidata porte l'appartenance sans date, et la
        retenir aurait produit cet anachronisme : seules les appartenances
        datées sont reprises.
        """
        de_gaulle = next(
            c for c in par_election["PR-1965"].candidats if c.personne == "PE-0002"
        )
        assert de_gaulle.partis == ()
