"""Le département, ramené au code INSEE d'aujourd'hui.

Les sources l'écrivent de trois façons selon l'année : un numéro jusqu'en 2007,
un nom en capitales en 2012, un nom en casse normale depuis 2017. Publier les
trois obligerait chaque consommateur à refaire ce rapprochement.

Les noms se comparent sur une forme aplatie, sans accent, sans trait d'union et
sans espace. Ce n'est pas une commodité : c'est ce qui rattrape les césures du
Journal officiel, où l'impression mange le trait d'union — « HAUTS-DESEINE »,
« MAINEET-LOIRE », « SAÔNEET-LOIRE », « VALD'OISE ». Aplaties, ces formes
tombent exactement sur le nom de référence.

Ce qui ne se résout pas reste sans code plutôt que d'être deviné. « OS » vaut
« 08 » si le S est un 8 mal imprimé, « 05 » s'il est un 5 : une substitution
appliquée sans regarder le territoire se tromperait une fois sur deux. Un champ
absent se voit ; un département faux, non.

Quand le territoire tranche, la forme est déclarée dans `corrections` au seed,
avec le motif qui l'établit — la commune nommée dans la même présentation. Six
présentations sur 60 723 en relèvent, dont deux seulement sont établissables :
c'est écrit à la main parce que cela se relit, non parce que cela se devine.
"""

from __future__ import annotations

import re
import unicodedata
from functools import cache

from candidatheque.pipeline.seeds.departements import load_corrections, load_departements

#: Les codes que les sources emploient sans désigner de département : « 97A » et
#: « 98 » pour les Français de l'étranger, « 99 » pour les représentants au
#: Parlement européen, que le Journal officiel dit « de nationalité française et
#: élus en France ». Le mandat les distingue déjà.
HORS_DEPARTEMENT = frozenset({"97A", "97B", "98", "99"})
#: Les ressorts qui couvrent deux collectivités, et qu'aucun code unique ne
#: désigne. Saint-Barthélemy et Saint-Martin, codes 977 et 978, partagent une
#: circonscription législative, et le Conseil constitutionnel écrit les deux
#: noms dans le champ du département — « Saint-Martin/Saint-Barthélemy ». Y
#: choisir un code affirmerait une précision qu'il ne donne pas ; le nom passe
#: donc au territoire, où il se lit sans ambiguïté.
RESSORTS_PARTAGES = {
    "saintmartinsaintbarthelemy": "Saint-Barthélemy et Saint-Martin",
    "saintbarthelemysaintmartin": "Saint-Barthélemy et Saint-Martin",
}

#: Les mêmes, écrits en toutes lettres par les jeux de 2017 et 2022, qui ont
#: abandonné les numéros. 386 présentations, toutes sans département réel.
HORS_DEPARTEMENT_EN_TOUTES_LETTRES = frozenset(
    {"francaisdeletranger", "francaisetablishorsdefrance", "parlementeuropeen"}
)
#: Les articles que le Journal officiel met devant le département : « député de
#: la CÔTE-D'OR », « de l'ALLIER ». Aplatis, « la » et « l » ne se distinguent
#: plus — « lallier » — et chaque découpe est donc essayée, la bonne étant celle
#: qui tombe sur un nom du registre. Aucun n'est retiré en premier essai, « La
#: Réunion » portant le sien dans son nom.
ARTICLES = ("l", "la", "le", "les")
#: Le département et le numéro de circonscription soudés — « VAL-DE-MARNE-1re ».
DEPARTEMENT_ET_NUMERO = re.compile(r"^(?P<nom>.+?)[\s-]+\d{1,2}\s*(?:er|re|ère|ere|ème|eme|e)$", re.IGNORECASE)

#: Ce que l'impression laisse autour d'un numéro : « ►59 », « *13 », « 68i »,
#: « 42Ï », et le trait d'union qui coupe « 97-1 ».
AUTOUR_DU_NUMERO = re.compile(r"[^0-9A-Za-z]")


def _plat(texte: str) -> str:
    """Un nom réduit à ses lettres : sans accent, sans trait d'union, sans espace.

    C'est cette réduction qui fait tomber « HAUTS-DESEINE » sur
    « Hauts-de-Seine » : la césure mangée par l'impression ne se voit plus.
    """
    sans = unicodedata.normalize("NFD", texte.lower())
    sans = re.sub(r"[̀-ͯ]", "", sans)
    return re.sub(r"[^a-z0-9]", "", sans)


@cache
def _tables() -> tuple[dict[str, str], dict[str, str], dict[str, tuple[str, int]], dict[str, str]]:
    """Les index du registre : par nom, par code courant, par code ancien, corrigés."""
    par_nom: dict[str, str] = {}
    par_code: dict[str, str] = {}
    anciens: dict[str, tuple[str, int]] = {}
    for departement in load_departements():
        par_nom[_plat(departement.nom)] = departement.code
        for ancien_nom in departement.noms_anciens:
            par_nom[_plat(ancien_nom)] = departement.code
        par_code[departement.code] = departement.code
        for ancien in departement.codes_anciens:
            anciens[ancien.code] = (departement.code, ancien.jusqu_en)
    corriges = {_plat(c.brut): c.code for c in load_corrections()}
    return par_nom, par_code, anciens, corriges


def ressort_partage(brut: str | None) -> str | None:
    """Le nom du ressort quand il couvre deux collectivités, sinon None."""
    return RESSORTS_PARTAGES.get(_plat(brut)) if brut else None


def normaliser(brut: str | None, annee: int) -> str | None:
    """Le code INSEE, ou None quand la source ne donne pas de département.

    `annee` est celle du scrutin, et elle est indispensable : avant que
    Saint-Barthélemy et Saint-Martin ne reçoivent 977 et 978 en 2007, ces
    numéros désignaient Wallis-et-Futuna et la Nouvelle-Calédonie. Un
    parrainage wallisien de 1995 publié à Saint-Barthélemy serait faux, et rien
    dans la donnée ne le signalerait.
    """
    if not brut:
        return None
    par_nom, par_code, anciens, corriges = _tables()

    # Les formes corrigées à la main passent avant tout : elles n'existent que
    # parce qu'aucune règle ne les résout, et le seed porte leur justification.
    if (corrige := corriges.get(_plat(brut))) is not None:
        return corrige

    nu = AUTOUR_DU_NUMERO.sub("", brut).upper()
    if nu in HORS_DEPARTEMENT:
        return None
    if nu in anciens:
        code, jusqu_en = anciens[nu]
        return code if annee < jusqu_en else par_code.get(nu)
    if nu in par_code:
        return nu
    # Un numéro sur deux chiffres écrit sans son zéro : « 5 » pour « 05 ».
    if nu.isdigit() and len(nu) == 1 and f"0{nu}" in par_code:
        return f"0{nu}"
    # La parenthèse fermante lue comme une lettre — « (68i » pour « (68) » —,
    # travers que le lecteur du Journal officiel connaît déjà. La lettre ne
    # tombe que si ce qui précède est un code : « 97A » n'y passe pas.
    if len(nu) > 1 and nu[-1].isalpha() and nu[:-1] in par_code:
        return nu[:-1]

    plat = _plat(brut)
    if plat in HORS_DEPARTEMENT_EN_TOUTES_LETTRES:
        return None
    if plat in par_nom:
        return par_nom[plat]
    # « VAL-DE-MARNE-1re » : le numéro de circonscription soudé au département.
    soude = DEPARTEMENT_ET_NUMERO.match(brut.strip())
    if soude and _plat(soude.group("nom")) in par_nom:
        return par_nom[_plat(soude.group("nom"))]
    # L'article en dernier recours, « La Réunion » le portant dans son nom.
    for article in ARTICLES:
        if plat.startswith(article) and (code := par_nom.get(plat[len(article) :])):
            return code
    return None
