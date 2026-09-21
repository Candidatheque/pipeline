"""Le vocabulaire des mandats, sur les graphies que quarante ans ont produites."""

import pytest

from candidatheque.pipeline.publication.mandats import REGLES, normaliser


def code(mandat, ressort=None):
    """Le seul code, là où le ressort ne fait pas partie de ce qu'on vérifie."""
    return normaliser(mandat, ressort)[0]


class TestGraphies:
    """Un même mandat, écrit autrement selon qui tient la plume."""

    @pytest.mark.parametrize(
        "libelle",
        ["maire", "Maire", "mgire", "maii’e", "nfaire", "mdre", "«maire", "maires"],
    )
    def test_le_maire_se_reconnait_meme_abime(self, libelle):
        """L'impression des années 1980 malmène jusqu'au plus courant des mandats."""
        assert code(libelle) == "maire"

    @pytest.mark.parametrize(
        "libelle",
        ["Conseiller/ère départemental-e", "Conseiller départemental", "Conseillère départementale"],
    )
    def test_l_ecriture_inclusive_ne_fait_pas_trois_mandats(self, libelle):
        """2017 écrit l'épicène en un mot, 2022 décline les deux genres."""
        assert code(libelle) == "conseiller-departemental"

    @pytest.mark.parametrize(
        "libelle",
        ["Sénateur/trice", "Sénateur", "Sénatrice", "sénateur", "sénateur représentant"],
    )
    def test_le_senateur_aussi(self, libelle):
        assert code(libelle) == "senateur"


class TestRenommages:
    """Un mandat renommé par la loi garde son code d'époque.

    Les confondre effacerait une réforme d'un jeu de données historique : qui
    compte les conseillers généraux en 2022 doit trouver zéro, et non le total
    des conseillers départementaux.
    """

    def test_le_conseiller_general_n_est_pas_le_departemental(self):
        assert code("conseiller général") == "conseiller-general"
        assert code("Conseiller départemental") == "conseiller-departemental"

    def test_le_conseiller_territorial_d_outre_mer_est_a_part(self):
        """Celui de Saint-Martin n'est pas celui de la réforme de 2010."""
        assert code("conseiller territorial") == "conseiller-territorial"
        assert code("Conseiller/ère territorial-e de Saint-Martin") == "conseiller-territorial-com"

    def test_les_trois_ages_des_francais_de_l_etranger(self):
        """Conseil supérieur jusqu'en 2004, Assemblée ensuite, conseillers depuis 2013."""
        assert code("membre élu", "C.S.F.E.") == "membre-csfe"
        assert code("membre élu de l’Assemblée des Français de l’étranger") == "membre-afe"
        assert code("Conseiller à l'Assemblée des Français de l'étranger") == "conseiller-afe"


class TestRessort:
    """Le libellé seul ne suffit pas toujours ; le couple, si.

    Le Journal officiel écrit « conseiller » et met « Paris » dans le ressort.
    Ces 354 présentations paraissaient tronquées : elles ne l'étaient pas.
    """

    def test_le_conseiller_de_paris_se_lit_dans_le_ressort(self):
        assert code("conseiller", "Paris") == "conseiller-paris"
        assert code("Membre du Conseil de Paris") == "conseiller-paris"

    def test_le_membre_se_lit_dans_le_ressort(self):
        assert code("membre", "congrès de la Nouvelle-Calédonie") == "membre-congres-nouvelle-caledonie"
        assert code("membre", "l’Assemblée de Corse") == "membre-assemblee-corse"


class TestOutreMer:
    """Le jeu de 2022 range les assemblées d'outre-mer sous une seule catégorie.

    2017 nommait la collectivité dans le libellé du mandat ; elle passe au
    ressort, et le code suit la catégorie officielle la plus récente sans rien
    perdre de ce que la source ancienne disait.
    """

    @pytest.mark.parametrize(
        "libelle, collectivite",
        [
            ("Membre de l'assemblée de Guyane", "Guyane"),
            ("Membre de l'assemblée de Martinique", "Martinique"),
            ("Membre de l'assemblée de la Polynésie française", "Polynésie française"),
            ("Membre d'une assemblée de province de la Nouvelle-Calédonie", "Nouvelle-Calédonie"),
            ("Membre de l'assemblée territoriale des îles Wallis et Futuna", "Wallis-et-Futuna"),
        ],
    )
    def test_la_collectivite_passe_dans_le_ressort(self, libelle, collectivite):
        assert normaliser(libelle) == ("membre-assemblee-outre-mer", collectivite)

    def test_la_corse_n_est_pas_l_outre_mer(self):
        """Collectivité à statut particulier, mais métropolitaine.

        Le jeu de 2022 lui garde aussi sa propre catégorie.
        """
        assert normaliser("Membre de l'Assemblée de Corse") == ("membre-assemblee-corse", "Corse")

    def test_le_congres_n_est_pas_une_assemblee_de_province(self):
        """Deux institutions de Nouvelle-Calédonie, et non deux noms d'une même."""
        assert code("Membre du congrès de la Nouvelle-Calédonie") == "membre-congres-nouvelle-caledonie"
        assert code("Membre d'une assemblée de province de la Nouvelle-Calédonie") == "membre-assemblee-outre-mer"

    def test_un_ressort_qui_redit_l_institution_cede_a_la_regle(self):
        """« l'Assemblée de la Polynésie » répète le mandat au lieu de le situer."""
        assert normaliser("membre", "l'Assemblée de la Polynésie") == (
            "membre-assemblee-outre-mer",
            "Polynésie française",
        )

    def test_un_ressort_qui_nomme_un_lieu_est_conserve(self):
        """La circonscription consulaire du C.S.F.E. n'est pas redite du mandat."""
        assert normaliser("membre élu", "Conseil supérieur des Français de l'étranger de TOKYO")[0] == "membre-csfe"

    def test_un_conseiller_sans_ressort_ne_devient_pas_conseiller_de_paris(self):
        """Le ressort est exigé, pas supposé."""
        assert code("conseiller") != "conseiller-paris"


class TestGardeFous:
    def test_un_mandat_absent_ne_donne_pas_de_code(self):
        assert code(None) is None
        assert code("") is None
        assert code("   ") is None

    def test_un_libelle_qui_n_est_pas_un_mandat_ne_donne_pas_de_code(self):
        """Le repli approché ne doit pas inventer un mandat par ressemblance."""
        assert code("la Constitution") is None
        assert code("Décrets, arrêtés, circulaires") is None

    def test_les_codes_sont_en_kebab_case(self):
        """Ils entrent dans une énumération de schéma : pas d'accent, pas d'espace."""
        import re

        for valeur, _, _, _ in REGLES:
            assert re.fullmatch(r"[a-z]+(-[a-z]+)*", valeur), valeur
