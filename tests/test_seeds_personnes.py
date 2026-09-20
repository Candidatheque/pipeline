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
    assert Personne(id="PE-0042", libelle="Quelqu'un").numero == 42


@pytest.mark.parametrize(
    "identifiant",
    ["PE-1", "PE-00001", "0001", "PR-0001", "pe-0001", "PE-0001 "],
)
def test_identifiants_mal_formes_rejetes(identifiant):
    with pytest.raises(ValidationError):
        Personne(id=identifiant, libelle="Quelqu'un")


def test_libelle_vide_rejete():
    """Un libellé vide ôterait au registre son seul intérêt en revue."""
    with pytest.raises(ValidationError, match="relecture"):
        Personne(id="PE-0001", libelle="   ")


def test_wikidata_mal_forme_rejete():
    with pytest.raises(ValidationError, match="Wikidata"):
        Personne(id="PE-0001", libelle="Quelqu'un", wikidata="P42")


def test_identifiants_en_double_rejetes(tmp_path):
    seed = _ecrire(
        tmp_path,
        'personnes:\n'
        '  - id: "PE-0001"\n    libelle: "Une"\n'
        '  - id: "PE-0001"\n    libelle: "Deux"\n',
    )
    with pytest.raises(ValidationError, match="en double"):
        load_personnes(seed)


def test_numerotation_decroissante_rejetee(tmp_path):
    """L'ordre rend l'attribution lisible et les trous visibles en revue."""
    seed = _ecrire(
        tmp_path,
        'personnes:\n'
        '  - id: "PE-0002"\n    libelle: "Deux"\n'
        '  - id: "PE-0001"\n    libelle: "Une"\n',
    )
    with pytest.raises(ValidationError, match="numéro croissant"):
        load_personnes(seed)


def test_wikidata_partage_rejete(tmp_path):
    """Deux identifiants pour la même personne Wikidata : l'un des deux est de trop."""
    seed = _ecrire(
        tmp_path,
        'personnes:\n'
        '  - id: "PE-0001"\n    libelle: "Une"\n    wikidata: "Q1189"\n'
        '  - id: "PE-0002"\n    libelle: "Deux"\n    wikidata: "Q1189"\n',
    )
    with pytest.raises(ValidationError, match="partagés"):
        load_personnes(seed)


def test_champ_inconnu_rejete():
    with pytest.raises(ValidationError):
        Personne.model_validate({"id": "PE-0001", "libelle": "Une", "nom": "Dupont"})
