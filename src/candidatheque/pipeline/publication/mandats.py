"""Le mandat qui habilite un élu à présenter un candidat, en vocabulaire fixe.

Quarante ans de sources écrivent le même mandat de dix façons. « maire » et
« Maire » selon que le Journal officiel ou le Conseil constitutionnel tient la
plume ; « Conseiller/ère départemental-e » en 2017, « Conseiller départemental »
et « Conseillère départementale » en 2022 ; « conseiller général » avant que la
loi NOTRe ne le renomme en 2015. Publier ces libellés tels quels obligerait
chaque consommateur à refaire ce travail, et il le referait moins bien.

Deux principes tiennent ce module :

- **Un renommage n'est pas une variante de graphie.** Le conseiller général et
  le conseiller départemental sont le même siège sous deux noms, mais la
  bascule a une date, et les confondre effacerait une réforme d'un jeu de
  données historique. Ils gardent deux codes, comme le Conseil supérieur des
  Français de l'étranger, devenu Assemblée en 2004, puis ses membres devenus
  conseillers en 2013.
- **Le mandat se lit avec son ressort.** Le Journal officiel écrit « conseiller »
  tout court et met « Paris » dans le ressort ; « membre élu » et « C.S.F.E. ».
  Le libellé seul ne dit pas de quel conseiller il s'agit, le couple le dit. Les
  354 présentations qui paraissaient tronquées se rangent ainsi toutes.
"""

from __future__ import annotations

import difflib
import re
import unicodedata

#: L'écriture inclusive, réduite au masculin qui sert de forme de citation.
#: 2017 écrit « Conseiller/ère départemental-e », 2022 « Conseiller
#: départemental » et « Conseillère départementale » : trois graphies, un
#: mandat. Réduire avant de comparer évite de tripler chaque règle.
INCLUSIF = (
    re.compile(r"/\s*(?:ere|ère|trice|e)\b", re.IGNORECASE),
    re.compile(r"(?<=[a-z])-e\b", re.IGNORECASE),
)


def _plat(texte: str | None) -> str:
    """Un libellé réduit à ce qui le distingue : minuscules, sans accent."""
    if not texte:
        return ""
    for motif in INCLUSIF:
        texte = motif.sub("", texte)
    sans = unicodedata.normalize("NFD", texte.lower())
    sans = re.sub(r"[̀-ͯ]", "", sans)
    return " ".join(re.sub(r"[^a-z0-9]", " ", sans).split())


#: Les règles, dans l'ordre : le premier motif qui reconnaît le couple
#: (mandat, ressort) donne le code. L'ordre compte — « maire délégué » se
#: teste avant « maire », qui reconnaîtrait les deux.
#:
#: Un motif de ressort vide ne regarde que le mandat. Un motif de ressort
#: présent sert les libellés que la source laisse incomplets.
#:
#: Le quatrième élément est le ressort que la règle rend, pour les libellés qui
#: portent le lieu au lieu de le laisser à côté : « Membre de l'assemblée de
#: Guyane » dit à la fois le mandat et où il s'exerce. Le code suit alors la
#: catégorie unique du jeu de 2022, et la collectivité passe dans le ressort,
#: où 2017 la retrouve. Il ne s'applique jamais par-dessus un ressort que la
#: source donne : « une assemblée de province de la Nouvelle-Calédonie ILES
#: LOYAUTE » en dit plus que « Nouvelle-Calédonie ».
REGLES: tuple[tuple[str, str, str, str], ...] = (
    # Communal.
    ("maire-arrondissement", r"maire d arrondissement", "", ""),
    ("maire-delegue", r"maire\w* delegue|maire delegue", "", ""),
    ("maire", r"^m\w{0,3}ire\b|^\W*m\w{0,3}ire\b", "", ""),
    # Départemental et régional. Le renommage de 2015 garde deux codes.
    ("conseiller-departemental", r"conseill\w* departemental", "", ""),
    ("conseiller-general", r"conseill\w* gener", "", ""),
    ("conseiller-regional", r"conseill\w* region", "", ""),
    ("conseiller-metropolitain-lyon", r"conseill\w* metropolitain\w* de lyon", "", ""),
    # Paris : le Journal officiel écrit « conseiller » et met « Paris » au
    # ressort, le Conseil constitutionnel écrit le mandat en entier.
    ("conseiller-paris", r"conseill\w* de paris|membre du conseil de paris", "", ""),
    ("conseiller-paris", r"^conseill\w*$", r"^paris$", ""),
    # National et européen.
    ("depute", r"^depute", "", ""),
    ("senateur", r"^senat", "", ""),
    ("representant-parlement-europeen", r"representant\w*( francais\w*)? au parlement europeen", "", ""),
    # Français de l'étranger : trois noms successifs pour un même siège, le
    # Conseil supérieur devenu Assemblée en 2004, ses membres devenus
    # conseillers en 2013.
    ("conseiller-afe", r"conseill\w* a l assemblee( des francais)?", "", ""),
    ("membre-afe", r"membre elu\w* de l assemblee des francais", "", ""),
    ("membre-afe", r"^(membre elu|assemblee)$", r"assemblee des francais|^francais de l etranger$", ""),
    ("membre-csfe", r"^membre elu$", r"c s ?f ?e|conseil superieur des francais", ""),
    ("membre-afe", r"^assemblee des francais", "", ""),
    # Intercommunal.
    ("president-epci", r"president\w* d un epci", "", ""),
    ("president-communaute", r"president\w* d (un|une) (conseil de )?communaute", "", ""),
    ("president-communaute", r"^president( de communaute.*)?$", r"communaute|communes", ""),
    ("president-metropole", r"president\w* d un conseil de metropole", "", ""),
    ("president-conseil-consulaire", r"president\w* du conseil consulaire", "", ""),
    # Outre-mer : assemblées délibérantes et exécutifs.
    # La Corse est une collectivité à statut particulier, mais métropolitaine :
    # le jeu de 2022 lui garde sa propre catégorie, et nous aussi.
    ("membre-assemblee-corse", r"assemblee de corse", "", "Corse"),
    ("membre-assemblee-corse", r"^membre$", r"assemblee de corse", "Corse"),
    ("membre-assemblee-outre-mer", r"assemblee de guyane", "", "Guyane"),
    ("membre-assemblee-outre-mer", r"assemblee de martinique", "", "Martinique"),
    ("president-conseil-executif-martinique", r"president du conseil executif de martinique", "", "Martinique"),
    ("membre-assemblee-outre-mer", r"assemblee de la polynesie", "", "Polynésie française"),
    ("membre-assemblee-outre-mer", r"^membre$", r"assemblee de la polynesie", "Polynésie française"),
    ("president-polynesie", r"president de la polynesie", "", "Polynésie française"),
    ("membre-assemblee-outre-mer", r"assemblee de province", "", "Nouvelle-Calédonie"),
    ("membre-assemblee-outre-mer", r"^membre$", r"assemblee de (la )?province", "Nouvelle-Calédonie"),
    # Le congrès n'est pas une assemblée de province : deux institutions, et non
    # deux noms d'une même. Il garde son code.
    ("membre-congres-nouvelle-caledonie", r"membre du congres", "", "Nouvelle-Calédonie"),
    ("membre-congres-nouvelle-caledonie", r"^membre$", r"congres de (la )?nouvelle", "Nouvelle-Calédonie"),
    ("president-gouvernement-nouvelle-caledonie", r"president du gouvernement de la nouvelle", "", "Nouvelle-Calédonie"),
    ("membre-assemblee-outre-mer", r"assemblee territoriale des iles wallis", "", "Wallis-et-Futuna"),
    ("membre-assemblee-outre-mer", r"^membre$", r"assemblee de wallis", "Wallis-et-Futuna"),
    # Les collectivités d'outre-mer à statut particulier. Leur conseiller
    # territorial n'est pas celui de la réforme de 2010, resté sans élection.
    ("conseiller-territorial-com", r"conseill\w* territorial\w* de (saint|mayotte)", "", ""),
    ("conseiller-territorial", r"conseill\w* territorial", "", ""),
    ("membre-assemblee-outre-mer", r"assemblee d une collectivite territoriale d outre mer", "", ""),
)

_COMPILEES = tuple(
    (code, re.compile(mandat), re.compile(motif) if motif else None, rendu)
    for code, mandat, motif, rendu in REGLES
)

#: Les mots-clés sur lesquels l'océrisation est rattrapée de loin. « maii’e »,
#: « cnaire », « conseiller généi-al » : l'impression des années 1980 malmène
#: les mandats, et une trentaine de présentations ne se reconnaissent qu'à la
#: ressemblance.
APPROCHES: tuple[tuple[str, str], ...] = (
    ("maire", "maire"),
    ("conseiller-general", "conseiller general"),
    ("conseiller-regional", "conseiller regional"),
    ("senateur", "senateur"),
    ("depute", "depute"),
)
#: Un ressort qui nomme l'assemblée plutôt que le lieu où elle siège. Le Journal
#: officiel écrit « membre » et met « l’Assemblée de Corse » à côté : le champ
#: redit alors le mandat au lieu de le compléter.
REDIT_L_INSTITUTION = re.compile(r"\b(assemblee|congres|conseil)\b")

#: En deçà, la ressemblance ne prouve plus rien. Le seuil est bas parce que
#: « maire » est court : une lettre fausse sur cinq coûte déjà un cinquième du
#: ratio, et « nfaire » ou « mdre » doivent encore passer. Le repli n'est
#: consulté qu'après toutes les règles, qui ont déjà reconnu 60 672 libellés.
SEUIL = 0.66


def normaliser(mandat: str | None, ressort: str | None = None) -> tuple[str | None, str | None]:
    """Le code du mandat et son ressort.

    `ressort` sert deux fois. Il départage d'abord les libellés que la source
    laisse incomplets : « conseiller » ne dit pas lequel, « conseiller » et
    « Paris » le disent. Il est ensuite rendu, éventuellement complété par la
    règle quand c'est le libellé du mandat qui portait le lieu.
    """
    plat = _plat(mandat)
    if not plat:
        return None, ressort
    plat_ressort = _plat(ressort)
    for code, motif, motif_ressort, rendu in _COMPILEES:
        if motif.search(plat) and (motif_ressort is None or motif_ressort.search(plat_ressort)):
            # Le ressort de la source l'emporte, sauf quand il ne nomme aucun
            # lieu et se contente de redire l'institution : « l’Assemblée de la
            # Polynésie » répète le mandat là où la règle nomme la collectivité.
            if rendu and (not ressort or REDIT_L_INSTITUTION.search(plat_ressort)):
                return code, rendu
            return code, ressort or None
    return _approché(plat), ressort


def _approché(plat: str) -> str | None:
    """Le code le plus ressemblant, quand l'impression a abîmé le libellé."""
    meilleur, score = None, SEUIL
    for code, reference in APPROCHES:
        ratio = difflib.SequenceMatcher(None, plat, reference).ratio()
        if ratio > score:
            meilleur, score = code, ratio
    return meilleur
