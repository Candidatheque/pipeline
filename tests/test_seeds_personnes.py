"""Le registre n'existe que pour garantir l'unicité des identifiants.

Ces tests portent donc sur cette garantie plus que sur le contenu.
"""

from __future__ import annotations

import re

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
    assert len(personnes) == 239
    assert personnes[0].id == "PE-0001"
    numeros = [personne.numero for personne in personnes]
    assert numeros == sorted(set(numeros)), "numérotation unique et croissante"


def test_un_registre_vide_est_accepte(tmp_path):
    """Un dépôt neuf, ou un type de scrutin dont rien n'est encore saisi."""
    assert load_personnes(_ecrire(tmp_path, "personnes: []\n")) == ()


def test_le_numero_est_lu_depuis_l_identifiant():
    assert Personne(id="PE-0042", nom_complet="Camille DUPONT").numero == 42


@pytest.mark.parametrize(
    "identifiant",
    ["PE-1", "PE-00001", "0001", "PR-0001", "pe-0001", "PE-0001 "],
)
def test_identifiants_mal_formes_rejetes(identifiant):
    with pytest.raises(ValidationError):
        Personne(id=identifiant, nom_complet="Camille DUPONT")


def test_nom_vide_rejete():
    """Un registre sans nom lisible perdrait son seul intérêt en revue."""
    with pytest.raises(ValidationError, match="relecture"):
        Personne(id="PE-0001", nom_complet="   ")


def test_la_meme_forme_que_dans_une_candidature():
    """Registre et candidature décrivent un nom de la même façon."""
    personne = Personne(id="PE-0001", nom_complet="Camille DUPONT")
    assert personne.nom_complet == "Camille DUPONT"


def test_un_pseudonyme_tient_dans_le_champ():
    """Un nom unique n'est pas une anomalie : « Super Châtaigne » se présenta."""
    assert Personne(id="PE-0001", nom_complet="Super Châtaigne").nom_complet


#: Ceux qui se sont présentés sous un pseudonyme : pas de patronyme à
#: distinguer d'un prénom, donc pas de capitales. Énumérés plutôt que devinés.
PSEUDONYMES = {"Dieudonné", "Lucius Liber", "Super Châtaigne"}


def test_le_patronyme_est_en_capitales():
    """Convention des décisions du Conseil constitutionnel, gardée au registre."""
    for personne in load_personnes():
        if personne.nom_complet in PSEUDONYMES:
            continue
        assert re.search(r"[A-ZÀ-Þ]{2,}", personne.nom_complet), personne


def test_wikidata_mal_forme_rejete():
    with pytest.raises(ValidationError, match="Wikidata"):
        Personne(id="PE-0001", nom_complet="Camille DUPONT", wikidata="P42")


def test_identifiants_en_double_rejetes(tmp_path):
    seed = _ecrire(
        tmp_path,
        'personnes:\n'
        '  - id: "PE-0001"\n    nom_complet: "A UNE"\n'
        '  - id: "PE-0001"\n    nom_complet: "B DEUX"\n',
    )
    with pytest.raises(ValidationError, match="en double"):
        load_personnes(seed)


def test_numerotation_decroissante_rejetee(tmp_path):
    """L'ordre rend l'attribution lisible et les trous visibles en revue."""
    seed = _ecrire(
        tmp_path,
        'personnes:\n'
        '  - id: "PE-0002"\n    nom_complet: "B DEUX"\n'
        '  - id: "PE-0001"\n    nom_complet: "A UNE"\n',
    )
    with pytest.raises(ValidationError, match="numéro croissant"):
        load_personnes(seed)


def test_wikidata_partage_rejete(tmp_path):
    """Deux identifiants pour la même personne Wikidata : l'un des deux est de trop."""
    seed = _ecrire(
        tmp_path,
        'personnes:\n'
        '  - id: "PE-0001"\n    nom_complet: "A UNE"\n    wikidata: "Q1189"\n'
        '  - id: "PE-0002"\n    nom_complet: "B DEUX"\n    wikidata: "Q1189"\n',
    )
    with pytest.raises(ValidationError, match="partagés"):
        load_personnes(seed)


def test_champ_inconnu_rejete():
    with pytest.raises(ValidationError):
        Personne.model_validate(
            {"id": "PE-0001", "nom_complet": "Camille DUPONT", "couleur": "bleu"}
        )


def test_les_identifiants_wikidata_sont_uniques():
    """Facultatif : beaucoup de candidats non retenus n'ont pas d'élément."""
    qids = [p.wikidata for p in load_personnes() if p.wikidata]
    assert len(set(qids)) == len(qids)


def test_les_candidats_valides_ont_tous_un_identifiant_wikidata():
    """Recoupé le 2026-09-20 : la propriété P726 de Wikidata donne exactement
    les candidats des décisions du Conseil constitutionnel, 114 sur 114."""
    from candidatheque.pipeline.seeds import load_candidatures

    valides = {
        c.personne
        for e in load_candidatures()
        for c in e.candidats
        if c.etat == "validee"
    }
    par_id = {p.id: p for p in load_personnes()}
    assert all(par_id[pid].wikidata for pid in valides)


def test_quelques_identifiants_wikidata_connus():
    par_id = {personne.id: personne.wikidata for personne in load_personnes()}
    assert par_id["PE-0002"] == "Q2042", "Charles de Gaulle"
    assert par_id["PE-0030"] == "Q2105", "Jacques Chirac"
    assert par_id["PE-0066"] == "Q3052772", "Emmanuel Macron"


#: Un registre de personnes ne doit pas contenir d'organisation. « Parti
#: socialiste » et « Les Verts » s'y étaient glissés : l'article de 2007 liste
#: les candidats à une investiture sous la forme « Parti : Untel et Untel », et
#: une extraction avait pris le parti en tête de ligne pour le candidat.
ORGANISATION = re.compile(
    r"\b(parti|verts|mouvement|union|front|rassemblement|ligue|alliance|"
    r"fédération|comité|collectif|association|centre)\b",
    re.IGNORECASE,
)


def test_aucune_organisation_dans_le_registre():
    for personne in load_personnes():
        assert not ORGANISATION.search(personne.nom_complet), (
            f"{personne.id} ressemble à une organisation : {personne.nom_complet!r}"
        )


def test_la_numerotation_est_contigue():
    """Tant que rien n'est publié, un trou se rattrape en renumérotant.

    Après la première publication ce test devra sauter : un identifiant publié
    ne se réattribue pas, et une ligne retirée laissera un trou définitif.
    """
    numeros = [personne.numero for personne in load_personnes()]
    assert numeros == list(range(1, len(numeros) + 1))
