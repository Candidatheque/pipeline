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
from dataclasses import dataclass

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


#: Ce que le territoire redit du mandat et qu'il n'a donc pas à porter : le type
#: de la collectivité, que le code dit déjà. « Conseil supérieur des Français de
#: l'étranger de RABAT » ne doit laisser que « RABAT », « communauté de communes
#: du CONFOLENTAIS » que « CONFOLENTAIS », « commune associée de LECOURT » que
#: « LECOURT ». Les motifs sont explicites plutôt que génériques : un préfixe
#: « LE », « LA » ou « VILLE » appartient au nom de la commune neuf fois sur dix
#: — « LE THOUR », « VILLEDOUX » —, et le retirer mutilerait 2 800 territoires.
REDITES = (
    re.compile(
        r"^(?:la |le |l['’])?commune\s+(?:associ[ée]e|d[ée]l[ée]gu[ée]e|nouvelle)\s+"
        r"(?:de\s+|d['’]|du\s+|des\s+)?",
        re.IGNORECASE,
    ),
    re.compile(
        r"^(?:le\s+)?conseil\s+sup[ée]rieur\s+des\s+fran[çc]ais\s+de\s+l['’][ée]tranger\s+"
        r"(?:de\s+|d['’])",
        re.IGNORECASE,
    ),
    # Le type d'EPCI, parfois écrit deux fois de suite — « communauté de communes
    # COMMUNAUTÉ DE COMMUNES DE LA HAUTE SAINTONGE ».
    re.compile(
        r"^(?:(?:la |le |les )?communaut[ée]\s+(?:de\s+communes|d['’]agglom[ée]ration"
        r"|urbaine|intercommunale|de\s+m[ée]tropole)\s*"
        r"(?:de\s+la\s+|de\s+|du\s+|des\s+|d['’])?)+",
        re.IGNORECASE,
    ),
)
#: Un territoire qui ne dit plus rien une fois la redite ôtée : la source n'y
#: nommait que l'institution. « C.S.F.E. » n'est pas un lieu.
SANS_LIEU = re.compile(
    r"^(?:c\W*s\W*f\W*e\W*|(?:l['’])?assembl[ée]e\s+des\s+fran[çc]ais\s+de\s+l['’][ée]tranger)$",
    re.IGNORECASE,
)
#: Les codes qui nomment déjà la collectivité : leur territoire ne ferait que
#: la redire. « membre-assemblee-outre-mer » n'en est pas, justement : c'est la
#: catégorie unique de 2022, et seul le territoire dit s'il s'agit de la Guyane
#: ou de Wallis-et-Futuna.
TERRITOIRE_IMPLICITE = frozenset(
    {
        "conseiller-paris",
        "conseiller-metropolitain-lyon",
        "membre-assemblee-corse",
        "membre-congres-nouvelle-caledonie",
        "president-polynesie",
        "president-gouvernement-nouvelle-caledonie",
        "president-conseil-executif-martinique",
    }
)
#: Le numéro de la circonscription législative, dans les formes que les sources
#: lui donnent : « 2ème circonscription », « la 3e circonscription », « 1er »,
#: et jusqu'à « l’Hérault (7 e) », où le département s'est invité.
NUMERO_DE_CIRCONSCRIPTION = re.compile(
    r"\b(\d{1,2})\s*(?:er|re|ère|ere|ème|eme|e)\b", re.IGNORECASE
)


@dataclass(frozen=True)
class Qualite:
    """Ce qui rend un élu habilité : son mandat, et où il l'exerce."""

    #: Le code du mandat, ou None si la source n'en donne pas.
    mandat: str | None
    #: Le nom propre du lieu — commune, canton, EPCI, collectivité, ville où
    #: siège un conseil consulaire. Jamais le type, que le mandat porte déjà.
    territoire: str | None = None
    #: Le numéro de la circonscription législative, pour les seuls députés.
    circonscription: int | None = None


def normaliser(mandat: str | None, ressort: str | None = None) -> Qualite:
    """Le mandat en vocabulaire fixe, et le lieu où il s'exerce.

    `ressort` est ce que la source écrit à côté du mandat. Il sert deux fois :
    il départage d'abord les libellés que la source laisse incomplets —
    « conseiller » ne dit pas lequel, « conseiller » et « Paris » le disent —,
    puis il devient le territoire, une fois ôté ce que le mandat redit.
    """
    plat = _plat(mandat)
    if not plat:
        return Qualite(None, _territoire(None, ressort))
    plat_ressort = _plat(ressort)
    for code, motif, motif_ressort, rendu in _COMPILEES:
        if motif.search(plat) and (motif_ressort is None or motif_ressort.search(plat_ressort)):
            # Le ressort de la source l'emporte, sauf quand il ne nomme aucun
            # lieu et se contente de redire l'institution : « l’Assemblée de la
            # Polynésie » répète le mandat là où la règle nomme la collectivité.
            if rendu and (not ressort or REDIT_L_INSTITUTION.search(plat_ressort)):
                return _avec_ressort(code, rendu)
            return _avec_ressort(code, ressort)
    return _avec_ressort(_approché(plat), ressort)


def _avec_ressort(code: str | None, ressort: str | None) -> Qualite:
    """Range le ressort, en numéro pour un député, en territoire sinon.

    Tous les chemins y passent, y compris celui d'une règle qui rend
    elle-même le ressort : c'est ici, et ici seulement, que les codes nommant
    déjà leur collectivité s'en voient priver.
    """
    if code in TERRITOIRE_IMPLICITE:
        return Qualite(code)
    if code == "depute":
        # Le numéro quand la source le donne. Sinon elle a écrit le département
        # — « député de la DRÔME » —, qu'on garde faute de mieux plutôt que de
        # le jeter : c'est la seule mention du département sur ces lignes.
        numero = NUMERO_DE_CIRCONSCRIPTION.search(ressort or "")
        if numero:
            return Qualite(code, None, int(numero.group(1)))
        return Qualite(code, _territoire(code, ressort))
    return Qualite(code, _territoire(code, ressort))


def _territoire(code: str | None, ressort: str | None) -> str | None:
    """Le ressort débarrassé de ce que le mandat dit déjà."""
    if not ressort:
        return None
    propre = ressort.strip()
    for redite in REDITES:
        propre = redite.sub("", propre).strip()
    if not propre or SANS_LIEU.match(propre):
        return None
    return propre


def _approché(plat: str) -> str | None:
    """Le code le plus ressemblant, quand l'impression a abîmé le libellé."""
    meilleur, score = None, SEUIL
    for code, reference in APPROCHES:
        ratio = difflib.SequenceMatcher(None, plat, reference).ratio()
        if ratio > score:
            meilleur, score = code, ratio
    return meilleur
