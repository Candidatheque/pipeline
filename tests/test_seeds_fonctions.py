"""Les fonctions occupées par les candidats."""

from __future__ import annotations

import datetime as dt

import pytest
from pydantic import ValidationError

from candidatheque.pipeline.seeds import coherence, load_fonctions
from candidatheque.pipeline.seeds.fonctions import Fonction, Occupation, Parcours

SYCOMORE = "assemblee-nationale:1798"


def _depute(debut="1967-04-03", fin="1967-05-07", **champs):
    return {"fonction": "depute", "ressort": "Corrèze", "debut": debut, "fin": fin,
            "sources": [SYCOMORE]} | champs


def test_le_seed_du_depot_est_valide():
    parcours = load_fonctions()
    chirac = next(p for p in parcours if p.personne == "PE-0030")
    assert len(chirac.fonctions) == 9
    assert {o.fonction for o in chirac.fonctions} == {Fonction.DEPUTE}
    assert chirac.fonctions[-1].fin == dt.date(1995, 5, 16)
    assert sum(len(p.fonctions) for p in parcours) == 257


def test_une_fonction_sans_source_est_rejetee():
    with pytest.raises(ValidationError):
        Occupation.model_validate(_depute(sources=[]))


def test_la_fin_est_facultative():
    """Une fonction en cours n'a pas encore de fin."""
    assert Occupation.model_validate(_depute(fin=None)).fin is None


def test_une_fin_avant_le_debut_est_rejetee():
    with pytest.raises(ValidationError, match="antérieure"):
        Occupation.model_validate(_depute(debut="1968-01-01", fin="1967-01-01"))


def test_un_mandat_local_ou_parlementaire_demande_un_ressort():
    with pytest.raises(ValidationError, match="ressort manquant"):
        Occupation.model_validate(_depute(ressort=None))


def test_une_fonction_nationale_n_a_pas_de_ressort():
    with pytest.raises(ValidationError, match="sans ressort"):
        Occupation.model_validate(
            {"fonction": "premier-ministre", "ressort": "Corrèze", "debut": "1974-05-27",
             "sources": ["legifrance:X"]}
        )


def test_un_ministre_porte_son_portefeuille():
    with pytest.raises(ValidationError, match="portefeuille"):
        Occupation.model_validate(
            {"fonction": "ministre", "debut": "1972-07-07", "sources": ["legifrance:X"]}
        )
    with pytest.raises(ValidationError, match="réservé"):
        Occupation.model_validate(_depute(intitule="de l'Intérieur"))


def test_fonctions_dans_le_desordre_rejetees():
    with pytest.raises(ValidationError, match="date de début"):
        Parcours.model_validate({"personne": "PE-0030", "fonctions": [
            _depute("1968-07-11", "1968-08-12"), _depute("1967-04-03", "1967-05-07")]})


def test_un_mandat_compris_dans_un_autre_est_rejete():
    with pytest.raises(ValidationError, match="compris dans le précédent"):
        Parcours.model_validate({"personne": "PE-0030", "fonctions": [
            _depute("1967-04-03", "1968-08-12"), _depute("1967-06-01", "1968-01-01")]})
    with pytest.raises(ValidationError, match="compris dans le précédent"):
        Parcours.model_validate({"personne": "PE-0030", "fonctions": [
            _depute("1967-04-03", None), _depute("1968-06-01", None)]})


def test_une_reelection_avant_la_fin_de_la_legislature_est_admise():
    """Mitterrand, réélu le 17 juin 1951 : Sycomore arrête le mandat précédent au 4 juillet."""
    Parcours.model_validate({"personne": "PE-0005", "fonctions": [
        _depute("1946-11-10", "1951-07-04"), _depute("1951-06-17", "1955-12-01")]})


def test_mandats_bout_a_bout_acceptes():
    """Sycomore coupe à chaque législature : la fin et le début se touchent."""
    Parcours.model_validate({"personne": "PE-0030", "fonctions": [
        _depute("1976-11-14", "1978-04-02"), _depute("1978-04-03", "1981-05-22")]})


def test_personnes_dans_le_desordre_rejetees(tmp_path):
    seed = tmp_path / "fonctions.yaml"
    seed.write_text(
        "parcours:\n"
        "  - personne: PE-0031\n    fonctions:\n"
        f"      - {{fonction: depute, ressort: X, debut: 1967-01-01, sources: [{SYCOMORE}]}}\n"
        "  - personne: PE-0030\n    fonctions:\n"
        f"      - {{fonction: depute, ressort: X, debut: 1967-01-01, sources: [{SYCOMORE}]}}\n",
        encoding="utf-8",
    )
    with pytest.raises(ValidationError, match="croissant"):
        load_fonctions(seed)


def _parcours(personne="PE-0030", **champs):
    return (Parcours.model_validate({"personne": personne, "fonctions": [_depute(**champs)]}),)


def test_personne_inconnue_signalee(monkeypatch):
    monkeypatch.setattr(coherence, "load_fonctions", lambda: _parcours("PE-9999"))
    assert any("PE-9999 : parcours" in p for p in coherence.verifier())


def test_source_inconnue_signalee(monkeypatch):
    monkeypatch.setattr(coherence, "load_fonctions",
                        lambda: _parcours(sources=["assemblee-nationale:0"]))
    assert any("source inconnue « assemblee-nationale:0 »" in p for p in coherence.verifier())


def test_wikidata_refuse_pour_un_mandat_parlementaire(monkeypatch):
    """L'Assemblée publie ses membres : citer Wikidata, ce serait citer une copie."""
    from candidatheque.pipeline.seeds.sources import Source

    wikidata = Source(id="wikidata:Q2105", url="https://www.wikidata.org/wiki/Q2105",
                      commentaire="Jacques Chirac", consultee_le="2026-09-21")
    reelles = coherence.load_sources()
    monkeypatch.setattr(coherence, "load_sources", lambda: (*reelles, wikidata))
    monkeypatch.setattr(coherence, "load_fonctions",
                        lambda: _parcours(sources=["wikidata:Q2105"]))
    assert any("réservée aux mandats locaux" in p for p in coherence.verifier())

    maire = Parcours.model_validate({"personne": "PE-0030", "fonctions": [
        {"fonction": "maire", "ressort": "Paris", "debut": "1977-03-25",
         "sources": ["wikidata:Q2105"]}]})
    monkeypatch.setattr(coherence, "load_fonctions", lambda: (maire,))
    assert not any("réservée" in p for p in coherence.verifier())
