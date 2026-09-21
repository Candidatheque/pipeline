"""Le département, ramené au code INSEE, sur ce que les sources écrivent."""

import pytest

from candidatheque.pipeline.publication.departements import normaliser
from candidatheque.pipeline.seeds.departements import load_departements


class TestFormes:
    """Un numéro jusqu'en 2007, un nom ensuite, et les accidents d'impression."""

    @pytest.mark.parametrize(
        "brut", ["59", "NORD", "Nord", "nord", "  Nord  "]
    )
    def test_le_meme_departement_quelle_que_soit_la_graphie(self, brut):
        assert normaliser(brut, 2017) == "59"

    @pytest.mark.parametrize(
        "brut, code",
        [
            ("HAUTS-DESEINE", "92"),
            ("MAINEET-LOIRE", "49"),
            ("SAÔNEET-LOIRE", "71"),
            ("LOTET-GARONNE", "47"),
            ("VALD’OISE", "95"),
            ("CORSE-DUSUD", "2A"),
        ],
    )
    def test_une_cesure_mangee_par_l_impression_se_recolle(self, brut, code):
        """Le nom aplati ignore le trait d'union, donc aussi son absence."""
        assert normaliser(brut, 2012) == code

    @pytest.mark.parametrize(
        "brut, code",
        [("►59", "59"), ("*13", "13"), ("8*4", "84"), ("97-1", "971"), ("2 A", "2A"), ("2-B", "2B")],
    )
    def test_les_signes_autour_du_numero_tombent(self, brut, code):
        assert normaliser(brut, 1981) == code

    def test_une_parenthese_lue_comme_une_lettre_tombe(self):
        """« (68i » pour « (68) », travers connu du lecteur de prose."""
        assert normaliser("68i", 1981) == "68"


class TestCodesDates:
    """Les numéros ultramarins ont changé de sens en 2007.

    Avant que Saint-Barthélemy et Saint-Martin ne reçoivent 977 et 978, ces
    numéros désignaient Wallis-et-Futuna et la Nouvelle-Calédonie. Un
    parrainage wallisien de 1995 publié à Saint-Barthélemy serait faux, et rien
    dans la donnée ne le signalerait.
    """

    @pytest.mark.parametrize(
        "brut, annee, code",
        [
            ("977", 1995, "986"),
            ("977", 2022, "977"),
            ("978", 1988, "988"),
            ("978", 2022, "978"),
            ("979", 1995, "987"),
        ],
    )
    def test_le_code_se_resout_avec_l_annee(self, brut, annee, code):
        assert normaliser(brut, annee) == code


class TestHorsDepartement:
    @pytest.mark.parametrize("brut", ["97A", "98", "99"])
    def test_un_code_qui_ne_designe_pas_un_departement_ne_donne_rien(self, brut):
        """Les Français de l'étranger et le Parlement européen n'en ont pas.

        Le mandat les distingue déjà ; un code inventé serait pire qu'un champ
        absent.
        """
        assert normaliser(brut, 2002) is None

    @pytest.mark.parametrize("brut", ["OU", "97", "Saint-Martin/Saint-Barthélemy", None, "", "   "])
    def test_ce_qui_ne_se_resout_pas_reste_sans_code(self, brut):
        """Rien n'est deviné quand rien ne l'établit.

        « OU » et « 97 » figurent en 1981 sur des présentations sans territoire,
        qui seul aurait pu trancher. « Saint-Martin/Saint-Barthélemy » est le
        cas où c'est la source qui ne tranche pas : les deux collectivités
        partagent une circonscription législative et n'ont pas de code commun.
        """
        assert normaliser(brut, 1981) is None


class TestCorrections:
    """Les formes qu'aucune règle ne résout, déclarées au seed.

    Elles n'y entrent que lorsque le territoire lu dans la même présentation
    établit le code : c'est écrit à la main parce que cela se relit, non parce
    que cela se devine.
    """

    @pytest.mark.parametrize("brut, code", [("OS", "08"), ("II", "11")])
    def test_une_forme_corrigee_donne_son_code(self, brut, code):
        assert normaliser(brut, 1981) == code

    def test_chaque_correction_porte_son_motif(self):
        """Le motif se relit en revue ; le code seul ne se vérifierait pas."""
        from candidatheque.pipeline.seeds.departements import load_corrections

        for correction in load_corrections():
            assert len(correction.motif) >= 20, correction


class TestRegistre:
    def test_chaque_departement_a_un_code_et_un_nom_uniques(self):
        registre = load_departements()
        assert len({d.code for d in registre}) == len(registre)
        assert len({d.nom for d in registre}) == len(registre)

    def test_les_cent_un_departements_sont_la(self):
        """96 métropolitains, Corse comptée en 2A et 2B, et 5 d'outre-mer.

        Plus la Corse d'avant 1976, sous son code d'époque.
        """
        registre = load_departements()
        metropole = [d for d in registre if not d.code.startswith("9") or d.code < "96"]
        assert len(metropole) == 97
        assert "20" in {d.code for d in metropole}
        assert {"971", "972", "973", "974", "976"} <= {d.code for d in registre}


class TestNomsAnciens:
    """Un département renommé garde son ancien nom dans les sources d'avant."""

    def test_les_cotes_du_nord_sont_les_cotes_d_armor(self):
        """La proclamation de 1988 écrit « (Côtes-du-Nord) », nom d'avant 1990."""
        assert normaliser("Côtes-du-Nord", 1988) == "22"

    def test_la_corse_d_avant_la_partition_garde_son_code_d_epoque(self):
        """Un seul département en 1974, deux aujourd'hui : choisir serait deviner.

        Le code 20 dit ce que la source écrit, sans trancher entre 2A et 2B.
        """
        assert normaliser("Corse", 1974) == "20"
