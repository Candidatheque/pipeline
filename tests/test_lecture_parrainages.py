"""La lecture des parrainages, et l'exhaustivité de ce qu'elle rend."""

from __future__ import annotations

import collections
import datetime as dt

import pytest

from candidatheque.pipeline.lecture.parrainages import _texte_jo, lire, lire_en_detail
from candidatheque.pipeline.seeds.parrainages import Etendue, load_parrainages


@pytest.fixture(scope="module")
def lectures():
    return {source.election: (source, *lire_en_detail(source)) for source in load_parrainages()}


def test_chaque_liste_tiree_au_sort_compte_ses_cinq_cents_noms(lectures):
    """L'oracle du projet : la loi en imposait 500 par candidat.

    C'est la seule vérification qui prouve qu'aucune présentation ne s'est
    perdue en route. Un chiffre en dessous, et la lecture a laissé filer une
    ligne ; au-dessus, elle a coupé une présentation en deux.
    """
    for election, (source, lus, _) in lectures.items():
        if source.etendue is not Etendue.TIRAGE_AU_SORT:
            continue
        comptes = collections.Counter(parrainage.candidat for parrainage in lus)
        assert len(comptes) == len(source.candidats), election
        assert set(comptes.values()) == {500}, (election, sorted(comptes.items()))


def test_rien_n_est_lu_hors_d_une_liste(lectures):
    """Tout parrainage appartient à un candidat déclaré dans le seed."""
    for election, (source, lus, _) in lectures.items():
        declares = {candidat.titre for candidat in source.candidats}
        assert {parrainage.candidat for parrainage in lus} <= declares, election


def test_tout_parrainage_porte_un_nom_et_un_mandat(lectures):
    for election, (_, lus, _) in lectures.items():
        assert all(p.nom and p.mandat for p in lus), election


def test_tout_parrainage_est_date(lectures):
    """La date porte la décision qui l'a rendu public."""
    for election, (source, lus, _) in lectures.items():
        assert all(p.publie_le for p in lus), election
        dates = {publication.date for publication in source.publications}
        assert {p.publie_le for p in lus} <= dates, election


def test_les_publications_progressives_sont_reparties(lectures):
    """À partir de 2017, les parrainages arrivent par vagues."""
    _, lus, _ = lectures["PR-2022"]
    assert len({parrainage.publie_le for parrainage in lus}) > 1


class TestProseDuJournalOfficiel:
    """Le lecteur de prose, sur les formes que l'impression lui inflige."""

    JOUR = dt.date(1988, 4, 12)

    def _lire(self, texte, titres=("Monsieur Raymond BARRE",)):
        return _texte_jo(texte, self.JOUR, titres)

    def test_une_presentation_simple(self):
        lus, rates = self._lire("Monsieur Raymond BARRE\nPierre DRION, conseiller général (50).\n")
        assert not rates
        assert lus[0].nom == "Pierre DRION"
        assert lus[0].mandat == "conseiller général"
        assert lus[0].departement == "50"

    def test_le_lieu_se_detache_du_mandat(self):
        lus, _ = self._lire("Monsieur Raymond BARRE\nAlain MAITRE, maire d’AMFREVILLE (50).\n")
        assert (lus[0].mandat, lus[0].territoire) == ("maire", "AMFREVILLE")

    def test_un_nom_de_commune_ne_declenche_pas_de_titre(self):
        """« LA CHAPELLE-FORAINVILLIERS » contient « VILLIERS »."""
        lus, _ = self._lire(
            "Monsieur Philippe de VILLIERS\n"
            "Jean DUPONT, maire de LA CHAPELLE-FORAINVILLIERS (28) ;\n"
            "Paul MARTIN, maire de RAI (61).\n",
            titres=("Monsieur Philippe de VILLIERS",),
        )
        assert len(lus) == 2

    def test_un_mot_coupe_en_fin_de_ligne_est_recolle(self):
        lus, _ = self._lire(
            "Monsieur Raymond BARRE\nJean DUPONT, maire de NOVY-CHEVRIE-\nRES (08).\n"
        )
        assert lus[0].territoire == "NOVY-CHEVRIERES"

    def test_le_trait_d_union_conditionnel_recolle_le_mandat(self):
        lus, rates = self._lire("Monsieur Raymond BARRE\nRené TRAVERT, séna­\nteur (50).\n")
        assert not rates
        assert lus[0].mandat == "sénateur"

    def test_le_titre_courant_ne_coupe_pas_une_presentation(self):
        lus, _ = self._lire(
            "Monsieur Raymond BARRE\n"
            "Marie-Thérèse HULMEL, maire de MAR-\n"
            "4788 JOURNAL OFFICIEL DE LA\n"
            "GUERAY (50).\n"
        )
        assert (lus[0].nom, lus[0].territoire) == ("Marie-Thérèse HULMEL", "MARGUERAY")

    def test_la_note_de_bas_de_page_ne_coupe_pas_une_presentation(self):
        """Elle tombe au milieu d'une liste et sépare le nom de son mandat."""
        lus, rates = self._lire(
            "Monsieur Raymond BARRE\n"
            "Claude LUCHE,\n"
            "(1) Chacune des neuf listes comprend 500 noms tirés au sort parmi tous\n"
            "les présentateurs de chaque candidat ; chaque présentateur y est désigné par\n"
            "son nom, son prénom et sa qualité.\n"
            "maire de BOISSEAUX (45).\n"
        )
        assert not rates
        assert (lus[0].nom, lus[0].territoire) == ("Claude LUCHE", "BOISSEAUX")

    @pytest.mark.parametrize("separateur", [" ; ", " * ", " • ", " j»1 ", " î ", ". ", ", ", " "])
    def test_les_presentations_se_separent_quel_que_soit_le_signe(self, separateur):
        """Les vieux scans rendent le point-virgule par n'importe quoi.

        Le repère sûr est le département qui ferme chaque présentation.
        """
        lus, _ = self._lire(
            "Monsieur Raymond BARRE\n"
            f"Jean DUPONT, maire de RAI (61){separateur}Paul MARTIN, maire de SERE (32).\n"
        )
        assert [p.nom for p in lus] == ["Jean DUPONT", "Paul MARTIN"]

    def test_une_parenthese_lue_comme_un_chiffre_ferme_quand_meme(self):
        """« (891 » pour « (89) » : le scan confond la parenthèse et le un."""
        lus, _ = self._lire(
            "Monsieur Raymond BARRE\n"
            "Georges LASSERRE, maire de TRUCY (891 : Gabriel ARLIGUIE, maire de PINSAC (46).\n"
        )
        assert [p.nom for p in lus] == ["Georges LASSERRE", "Gabriel ARLIGUIE"]
        assert lus[0].departement == "89"

    def test_un_mandat_abime_reste_reconnu(self):
        """« mgire », « maii’e », « jnaire » : l'impression malmène « maire »."""
        lus, rates = self._lire("Monsieur Raymond BARRE\nCélestin MANIN, mgire d’ALLEMONT (38).\n")
        assert not rates
        assert lus[0].territoire == "ALLEMONT"

    @pytest.mark.parametrize(
        "prose",
        [
            "maire d’IZIEU (01)",  # la préposition telle qu'elle doit être
            "maire dTZIEU (01)",  # « ’I » recollé en un T
            "maire dlZIEU (01)",  # « ’I » recollé en un l
            "maire dé IZIEU (01)",  # l'apostrophe lue comme un accent
            "maire dç IZIEU (01)",  # … ou comme une cédille
            "maire ds IZIEU (01)",
            "maire cle IZIEU (01)",  # « de » lu « cle »
            "maire deIZIEU (01)",  # l'espace mangée
            "maire.de IZIEU (01)",
            "maire-de IZIEU (01)",
            "maire d ’ IZIEU (01)",
            "maire DE IZIEU (01)",  # la préposition passée en capitales
            "maire IZIEU (01)",  # la préposition tout bonnement absente
        ],
    )
    def test_le_lieu_se_detache_meme_sans_preposition_lisible(self, prose):
        """Quarante ans de scans ont inventé une trentaine de « de ».

        Les énumérer serait sans fin : le repère est la casse, les communes
        étant imprimées en capitales et les mandats en minuscules.
        """
        lus, rates = self._lire(f"Monsieur Raymond BARRE\nHenri PERRET, {prose}.\n")
        assert not rates
        assert (lus[0].mandat, lus[0].territoire) == ("maire", "IZIEU")

    def test_une_commune_en_du_ne_perd_pas_ses_deux_premieres_lettres(self):
        """« DUTTLENHEIM » n'est pas « du TTLENHEIM ».

        La préposition en capitales ne s'ôte que suivie d'une espace.
        """
        lus, _ = self._lire("Monsieur Raymond BARRE\nPaul KLEIN, maire der DUTTLENHEIM (67).\n")
        assert lus[0].territoire == "DUTTLENHEIM"

    def test_un_mandat_compose_ne_se_coupe_pas_sur_une_majuscule(self):
        """« Assemblée » et « Parlement » portent une majuscule, pas deux."""
        lus, _ = self._lire(
            "Monsieur Raymond BARRE\n"
            "Anne MOREL, représentant au Parlement européen ; "
            "Luc FAURE, conseiller à l’Assemblée (75).\n"
        )
        assert [p.mandat for p in lus] == ["représentant au Parlement européen", "conseiller à l’Assemblée"]
        assert [p.territoire for p in lus] == [None, None]

    def test_le_decret_imprime_sous_la_liste_est_coupe(self):
        """La présentation est vraie ; seul ce qui suit son point final ne l'est pas.

        Claude HURIET était bien conseiller général de Meurthe-et-Moselle :
        écarter la ligne entière perdrait une présentation réelle.
        """
        lus, rates = self._lire(
            "Monsieur Raymond BARRE\n"
            "Claude HURIET, conseiller général (54). DÉCRETS, ARRÊTÉS ET CIRCULAIRES "
            "MINISTERE DES AFFAIRES ETRANGERES Décret n° 81-346 du portant publication "
            "de l’accord de coopération touristique entre le Gouvernement de la et le "
            "Gouvernement des Etats-Unis du Mexique, signé à Paris le (1).\n"
        )
        assert not rates
        assert len(lus) == 1
        assert (lus[0].nom, lus[0].mandat, lus[0].departement) == (
            "Claude HURIET",
            "conseiller général",
            "54",
        )

    def test_une_virgule_parasite_ne_coupe_pas_le_nom(self):
        lus, _ = self._lire("Monsieur Raymond BARRE\nJulien , VIDAL, maire de NEBIAN (34).\n")
        assert lus[0].nom == "Julien VIDAL"

    def test_la_mention_qui_prolonge_le_nom_y_reste(self):
        lus, _ = self._lire(
            "Monsieur Raymond BARRE\nAnne TAHI, épouse SONZOGNI, conseiller général (06).\n"
        )
        assert lus[0].nom == "Anne TAHI, épouse SONZOGNI"

    def test_la_civilite_se_detache_du_nom(self):
        lus, _ = self._lire("Monsieur Raymond BARRE\nM. Pierre BON, maire d’EGRISELLES (89).\n")
        assert (lus[0].civilite, lus[0].nom) == ("M.", "Pierre BON")

    def test_un_texte_voisin_n_est_pas_pris_pour_une_presentation(self):
        """Le Journal officiel imprime d'autres textes sur les mêmes pages."""
        lus, rates = self._lire(
            "Monsieur Raymond BARRE\n"
            "Jean DUPONT, maire de RAI (61) ;\n"
            "Considérant l’importance du tourisme pour leurs deux pays.\n"
        )
        assert [p.nom for p in lus] == ["Jean DUPONT"]
        assert len(rates) == 1

    def test_un_titre_non_declare_n_ouvre_pas_de_liste(self):
        """Une signature au bas d'un décret n'est pas un titre de candidat."""
        lus, _ = self._lire(
            "Monsieur Raymond BARRE\nJean DUPONT, maire de RAI (61) ;\nVALÉRY GISCARD D’ESTAING.\n"
        )
        assert {p.candidat for p in lus} == {"Monsieur Raymond BARRE"}

    def test_un_titre_rappele_plus_loin_ne_rouvre_pas_la_liste(self):
        lus, _ = self._lire(
            "Monsieur Raymond BARRE\n"
            "Jean DUPONT, maire de RAI (61) ;\n"
            "Monsieur Raymond BARRE\n"
            "Paul MARTIN, maire de SERE (32).\n"
        )
        assert len(lus) == 2

    def test_les_presentations_avant_le_premier_titre_sont_ignorees(self):
        lus, _ = self._lire("Jean DUPONT, maire de RAI (61).\nMonsieur Raymond BARRE\n")
        assert lus == []


class TestFormatsJson:
    def test_le_nom_est_rendu_tel_que_la_source_l_ecrit(self):
        """Le rapprochement avec le registre est le travail du seed."""
        par_election = {source.election: source for source in load_parrainages()}
        noms = {p.candidat for p in lire(par_election["PR-2022"])}
        assert "ARTHAUD Nathalie" in noms

    def test_les_champs_accentues_de_2017_sont_lus(self):
        par_election = {source.election: source for source in load_parrainages()}
        lus = lire(par_election["PR-2017"])
        assert all(p.nom for p in lus)
        assert any(p.civilite for p in lus)
