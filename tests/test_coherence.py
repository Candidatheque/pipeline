"""Les références d'un seed à l'autre ne se vérifient que là.

Une référence pendante ne casse rien à la publication : elle produit
silencieusement des données fausses.
"""

from __future__ import annotations

import pytest

from candidatheque.pipeline.seeds import coherence


def test_les_seeds_du_depot_sont_coherents():
    assert coherence.verifier() == []


@pytest.fixture
def seeds_bricoles(monkeypatch):
    """Permet de remplacer un seed par un contenu forgé, les autres inchangés."""
    def remplacer(nom, valeur):
        monkeypatch.setattr(coherence, nom, lambda: valeur)
    return remplacer


def _candidature(**champs):
    from candidatheque.pipeline.seeds.candidatures import CandidaturesElection
    base = {
        "election": "PR-1965",
        "candidats": [{
            "personne": "PE-0001", "nom": "BARBU", "prenom": "Marcel", "etat": "validee",
            "tours": [{"numero": 1, "sources": ["conseil-constitutionnel:65-3-PDR"]}],
        }],
    }
    candidat = base["candidats"][0] | champs.pop("candidat", {})
    return (CandidaturesElection.model_validate({**base, **champs, "candidats": [candidat]}),)


def test_personne_inconnue_signalee(seeds_bricoles):
    seeds_bricoles("load_candidatures", _candidature(candidat={"personne": "PE-9999"}))
    problemes = coherence.verifier()
    assert any("PE-9999 : personne absente du registre" in p for p in problemes)


def test_election_inconnue_signalee(seeds_bricoles):
    seeds_bricoles("load_candidatures", _candidature(election="PR-1900"))
    assert any("élection inconnue" in p for p in coherence.verifier())


def test_tour_inexistant_signale(seeds_bricoles):
    seeds_bricoles(
        "load_candidatures",
        _candidature(candidat={"tours": [{"numero": 3, "sources": ["conseil-constitutionnel:65-3-PDR"]}]}),
    )
    assert any("tour 3 inexistant" in p for p in coherence.verifier())


def test_source_inconnue_signalee(seeds_bricoles):
    seeds_bricoles(
        "load_candidatures",
        _candidature(candidat={"tours": [{"numero": 1, "sources": ["presse:inventee"]}]}),
    )
    assert any("source inconnue" in p for p in coherence.verifier())


def test_personne_orpheline_signalee(seeds_bricoles):
    """Une entrée que plus rien ne cite finira par induire en erreur."""
    seeds_bricoles("load_candidatures", _candidature())
    problemes = coherence.verifier()
    assert any("citée par aucune candidature" in p for p in problemes)
    assert any("citée par aucune donnée" in p for p in problemes)
