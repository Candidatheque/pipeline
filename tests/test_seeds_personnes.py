"""Le registre n'existe que pour garantir l'unicité des identifiants.

Ces tests portent donc sur cette garantie plus que sur le contenu.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from candidatheque.pipeline.seeds import load_personnes
from candidatheque.pipeline.seeds.personnes import Personne


def _ecrire(tmp_path, corps):
    seed = tmp_path / "personnes.yaml"
    seed.write_text(corps, encoding="utf-8")
    return seed


def test_le_registre_du_depot_est_valide():
    personnes = load_personnes()
    assert len(personnes) == 75
    assert personnes[0].id == "PE-0001"
    numeros = [personne.numero for personne in personnes]
    assert numeros == sorted(set(numeros)), "numérotation unique et croissante"


def test_un_registre_vide_est_accepte(tmp_path):
    """Un dépôt neuf, ou un type de scrutin dont rien n'est encore saisi."""
    assert load_personnes(_ecrire(tmp_path, "personnes: []\n")) == ()


def test_le_numero_est_lu_depuis_l_identifiant():
    assert Personne(id="PE-0042", nom="DUPONT", prenom="Camille").numero == 42


@pytest.mark.parametrize(
    "identifiant",
    ["PE-1", "PE-00001", "0001", "PR-0001", "pe-0001", "PE-0001 "],
)
def test_identifiants_mal_formes_rejetes(identifiant):
    with pytest.raises(ValidationError):
        Personne(id=identifiant, nom="DUPONT", prenom="Camille")


@pytest.mark.parametrize("champ", ["nom", "prenom"])
def test_nom_ou_prenom_vide_rejete(champ):
    """Un registre sans nom lisible perdrait son seul intérêt en revue."""
    champs = {"id": "PE-0001", "nom": "DUPONT", "prenom": "Camille", champ: "   "}
    with pytest.raises(ValidationError, match="relecture"):
        Personne(**champs)


def test_la_meme_forme_que_dans_une_candidature():
    """Registre et candidature décrivent un nom de la même façon."""
    personne = Personne(id="PE-0001", nom="DUPONT", prenom="Camille")
    assert (personne.nom, personne.prenom) == ("DUPONT", "Camille")


def test_wikidata_mal_forme_rejete():
    with pytest.raises(ValidationError, match="Wikidata"):
        Personne(id="PE-0001", nom="DUPONT", prenom="Camille", wikidata="P42")


def test_identifiants_en_double_rejetes(tmp_path):
    seed = _ecrire(
        tmp_path,
        'personnes:\n'
        '  - id: "PE-0001"\n    nom: "UNE"\n    prenom: "A"\n'
        '  - id: "PE-0001"\n    nom: "DEUX"\n    prenom: "B"\n',
    )
    with pytest.raises(ValidationError, match="en double"):
        load_personnes(seed)


def test_numerotation_decroissante_rejetee(tmp_path):
    """L'ordre rend l'attribution lisible et les trous visibles en revue."""
    seed = _ecrire(
        tmp_path,
        'personnes:\n'
        '  - id: "PE-0002"\n    nom: "DEUX"\n    prenom: "B"\n'
        '  - id: "PE-0001"\n    nom: "UNE"\n    prenom: "A"\n',
    )
    with pytest.raises(ValidationError, match="numéro croissant"):
        load_personnes(seed)


def test_wikidata_partage_rejete(tmp_path):
    """Deux identifiants pour la même personne Wikidata : l'un des deux est de trop."""
    seed = _ecrire(
        tmp_path,
        'personnes:\n'
        '  - id: "PE-0001"\n    nom: "UNE"\n    prenom: "A"\n    wikidata: "Q1189"\n'
        '  - id: "PE-0002"\n    nom: "DEUX"\n    prenom: "B"\n    wikidata: "Q1189"\n',
    )
    with pytest.raises(ValidationError, match="partagés"):
        load_personnes(seed)


def test_champ_inconnu_rejete():
    with pytest.raises(ValidationError):
        Personne.model_validate(
            {"id": "PE-0001", "nom": "DUPONT", "prenom": "Camille", "couleur": "bleu"}
        )


def test_chaque_personne_porte_son_identifiant_wikidata():
    """Recoupé le 2026-09-20 : la propriété P726 de Wikidata donne exactement
    les candidats des décisions du Conseil constitutionnel, 114 sur 114."""
    personnes = load_personnes()
    assert all(personne.wikidata for personne in personnes)
    qids = [personne.wikidata for personne in personnes]
    assert len(set(qids)) == len(qids)


def test_quelques_identifiants_wikidata_connus():
    par_id = {personne.id: personne.wikidata for personne in load_personnes()}
    assert par_id["PE-0002"] == "Q2042", "Charles de Gaulle"
    assert par_id["PE-0030"] == "Q2105", "Jacques Chirac"
    assert par_id["PE-0066"] == "Q3052772", "Emmanuel Macron"
