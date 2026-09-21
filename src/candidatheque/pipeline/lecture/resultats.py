"""Lecture d'une décision de résultats du Conseil constitutionnel.

Le texte de la décision est commité dans `raw/resultats/` ; ce module le lit et
rend un `Tour` : les décomptes, les voix de chaque candidat, et les annulations
de suffrages que la décision prononce.

Quarante ans de rédactions et de transcriptions, et une seule chose ne bouge
pas : le vocabulaire des décomptes. « Électeurs inscrits », « Votants »,
« Suffrages exprimés », « Majorité absolue » se retrouvent de 1965 à 2022, et
c'est sur eux que la lecture s'appuie plutôt que sur une mise en page qui, elle,
change à chaque scrutin — deux-points ou rien, lignes de points de conduite,
nombres séparés par des points en 1965 et par des espaces ensuite.

Le reste se déclare : les noms des candidats viennent du seed, qui les écrit
tels que la décision les porte. La lecture n'a donc jamais à décider si
« Ariette LAGUILLER » désigne Arlette.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace

from candidatheque.pipeline.seeds.resultats import VersionResultats

#: Un considérant : son numéro en tête de ligne, puis son texte. La rédaction
#: « Considérant que… » s'arrête en 2016, le numéro demeure.
CONSIDERANT = re.compile(r"^(?P<numero>\d{1,2})\.\s+(?P<texte>.+)$")

#: La section des abstracts, qui suit la décision dans le fichier. Elle porte le
#: classement que le Conseil fait de ses propres motifs.
SEPARATEUR_ABSTRACTS = "\nABSTRACTS"

#: Un nombre tel que les décisions l'écrivent : par tranches séparées d'espaces
#: depuis 1969, de points en 1965, parfois pas du tout quand la transcription a
#: mangé l'espace — « 36 398762 ». Le « l » est un 1 que l'impression a raté :
#: « l 260 208 » pour les 1 260 208 voix de Jean-Louis Tixier-Vignancour.
NOMBRE = re.compile(r"[\dlI][\dlI. ]*")

#: Les décomptes, et la graphie de leur intitulé. L'accent d'« Électeurs » n'est
#: pas constant, ni le pluriel de « Bulletins ».
DECOMPTES = {
    "inscrits": r"[ÉE]lecteurs\s+inscrits",
    "votants": r"Votants",
    "bulletins_blancs": r"Bulletins\s+blancs",
    "bulletins_nuls": r"Bulletins\s+nuls",
    "suffrages_exprimes": r"Suffrages\s+exprim[ée]s",
    "majorite_absolue": r"Majorit[ée]\s+absolue",
}

#: Ce qui sépare deux décomptes quand la transcription a perdu le saut de ligne,
#: comme dans la proclamation de 2002 : « 41 191 169Votants : 32 832 295 ».
#: Un chiffre suivi d'une capitale n'est jamais un nombre, c'est une couture.
COUTURE = re.compile(r"(?<=\d)(?=[A-ZÉÈ])")


@dataclass(frozen=True)
class Voix:
    """Les voix d'un candidat à ce tour."""

    #: Le nom tel que la décision l'écrit, celui que le seed déclare.
    titre: str
    personne: str
    voix: int


@dataclass(frozen=True)
class Annulation:
    """Des suffrages annulés par un considérant de la décision.

    L'unité est le bureau de vote, ou la commune entière quand le Conseil
    annule sans distinguer ses bureaux. Un même considérant en prononce souvent
    plusieurs, pour un motif commun : il en sort alors autant d'annulations,
    qui portent toutes son numéro.
    """

    #: Le numéro du considérant, qui est la citation officielle du motif :
    #: « 2022-197 PDR, cons. 3 ».
    considerant: int
    #: « commune » ou « bureau-de-vote ». L'absence de numéro de bureau ne
    #: suffirait pas à le dire : elle voudrait aussi bien dire que la décision
    #: ne le donne pas.
    portee: str
    #: Le nom du lieu, tel que la décision l'écrit.
    commune: str
    #: Le département, tel que la décision l'écrit, entre parenthèses. La
    #: publication le ramène à son code.
    departement: str | None = None
    #: Les numéros des bureaux, quand la portée est le bureau. Plusieurs
    #: quand la décision ne donne qu'un nombre de suffrages pour l'ensemble :
    #: « les bureaux de vote n° 3 et 4 […], dans lesquels 817 suffrages ont été
    #: exprimés ». Les séparer perdrait ce nombre.
    bureaux: tuple[int, ...] = ()
    #: Les suffrages exprimés dans ces bureaux ou cette commune, quand la
    #: décision les donne. Celles d'avant 1995 ne les donnent pas.
    suffrages_exprimes: int | None = None
    #: Le texte du considérant, tel que la décision l'écrit.
    motif: str = ""
    #: Les rubriques sous lesquelles le Conseil classe ce considérant dans ses
    #: abstracts, de la plus générale à la plus précise pour chacune : code et
    #: intitulé. Vide quand la décision n'en porte pas pour ce considérant.
    nomenclature: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class Tour:
    """Les résultats d'un tour, tels qu'une version les donne."""

    inscrits: int | None = None
    votants: int | None = None
    bulletins_blancs: int | None = None
    bulletins_nuls: int | None = None
    suffrages_exprimes: int | None = None
    majorite_absolue: int | None = None
    voix: tuple[Voix, ...] = ()
    annulations: tuple[Annulation, ...] = ()


def _nombre(brut: str) -> int:
    """Un nombre de la décision en entier.

    Les séparateurs de tranches sautent, quels qu'ils soient, et le « l » de
    l'impression redevient le 1 qu'il n'aurait pas dû cesser d'être.
    """
    return int(re.sub(r"[ .]", "", brut).replace("l", "1").replace("I", "1"))


def _lignes(texte: str) -> list[str]:
    """Le texte de la décision, une ligne par paragraphe, coutures défaites."""
    decision = texte.split(SEPARATEUR_ABSTRACTS)[0]
    return [ligne.strip() for ligne in COUTURE.sub("\n", decision).splitlines() if ligne.strip()]


def _decomptes(lignes: list[str]) -> dict[str, int]:
    """Les décomptes du tour, lus sur l'intitulé qui les précède.

    Seul le premier de chaque espèce est retenu. La proclamation de 1995
    rappelle les résultats du premier tour avant de donner ceux du second ; les
    intitulés sont les mêmes, et c'est l'ordre du texte qui les distingue.
    """
    trouves: dict[str, int] = {}
    for ligne in lignes:
        for champ, intitule in DECOMPTES.items():
            if champ in trouves:
                continue
            # Le nombre suit son intitulé immédiatement : rien entre les deux
            # que des séparateurs, dont les points de conduite de 2002
            # — « Votants .................... 29 495 733 ». C'est ce qui
            # distingue le décompte de la prose qui emploie les mêmes mots :
            # « n'a recueilli la majorité absolue des suffrages exprimés ».
            m = re.search(rf"{intitule}[\s.:,]*(?P<nombre>\d[\dlI. ]*)", ligne, re.IGNORECASE)
            if m is not None:
                trouves[champ] = _nombre(m.group("nombre"))
    return trouves


def _voix(lignes: list[str], source: VersionResultats) -> list[Voix]:
    """Les voix de chaque candidat déclaré, dans l'ordre de la décision.

    Le nom doit fermer sa ligne sur un nombre : « Proclame Charles de Gaulle
    élu Président de la République » le porte aussi, mais ne dit pas ses voix.
    L'ordre est celui des lignes, non celui du seed : c'est la décision qui le
    fixe.
    """
    trouvees: list[tuple[int, Voix]] = []
    for candidat in source.candidats:
        motif = re.compile(
            rf"{re.escape(candidat.titre)}\s*:?\s*(?P<voix>{NOMBRE.pattern})(?:\s*voix)?\s*[.,;]?$"
        )
        for rang, ligne in enumerate(lignes):
            m = motif.search(ligne)
            if m is None:
                continue
            voix = Voix(titre=candidat.titre, personne=candidat.personne, voix=_nombre(m.group("voix")))
            trouvees.append((rang, voix))
            break
    return [voix for _, voix in sorted(trouvees, key=lambda paire: paire[0])]


# ---------------------------------------------------------------------------
# Les annulations
# ---------------------------------------------------------------------------

#: La formule par laquelle le Conseil annule des suffrages. Elle a varié —
#: « il y a lieu d'annuler », « il y a lieu, par suite, […] d'annuler », « il y a
#: lieu pour le Conseil constitutionnel d'annuler », « d'en annuler les
#: résultats », « les résultats du scrutin doivent être annulés », « doit
#: entraîner l'annulation de l'ensemble des suffrages » — mais porte toujours la
#: décision d'annuler, et non son simple rappel : « compte tenu des
#: rectifications et annulations opérées » n'annule rien.
ANNULE = re.compile(
    r"(?:lieu|décidé)\b[^;]{0,160}?d['’](?:en\s+)?annuler|doivent\s+être\s+annulés"
    r"|lieu\s+de\s+les\s+annuler|entraîner\s+l['’]annulation",
    re.IGNORECASE,
)
#: Les considérants qui parlent d'annulation sans en prononcer : le redressement
#: d'une commission de recensement qui avait retranché des voix à tort, que le
#: Conseil rétablit — « il y a lieu de rectifier […] et de majorer ».
REDRESSEMENT = re.compile(r"\b(?:rectifier|majorer)\b", re.IGNORECASE)
#: L'annulation des seuls votes par correspondance, qui n'est pas celle des
#: suffrages d'un bureau : 1974, à Bastia et à Albertacce. Le nombre de votes
#: concernés n'est pas donné, et la ranger parmi les autres ferait croire qu'un
#: bureau entier a été annulé.
PARTIELLE = re.compile(r"votes\s+par\s+correspondance", re.IGNORECASE)

#: Les ordinaux écrits en toutes lettres, pour les bureaux de 1974 — « les
#: premier, troisième […] et treizième bureaux de vote de la ville de Bastia » —
#: et les arrondissements de Paris.
ORDINAUX = {
    mot: rang
    for rang, mot in enumerate(
        ["premier", "deuxième", "troisième", "quatrième", "cinquième", "sixième", "septième", "huitième", "neuvième", "dixième", "onzième", "douzième", "treizième", "quatorzième", "quinzième", "seizième", "dix-septième", "dix-huitième", "dix-neuvième", "vingtième"],
        start=1,
    )
}

#: Un nom de lieu : une capitale, puis des mots liés par des traits d'union ou
#: des particules — « Saint-Martin-de-Brômes », « Le Valdécie », « La
#: Chapelle-Saint-Laurent », « Hodenc-l'Évêque ».
NOM_DE_LIEU = (
    r"[A-ZÉÈÀÂÎÔÛÇ][\wÉÈÀÂÎÔÛéèàâîôûçœ'’\-]*"
    r"(?:\s+(?:[A-ZÉÈÀÂÎÔÛÇ][\wéèàâîôûçœ'’\-]*))*"
)
#: Le département ou la collectivité, entre parenthèses après le lieu.
DEPARTEMENT = r"\(\s*(?P<departement>[^)]{2,45}?)\s*\)"

#: Ce qui annonce une ou plusieurs communes : « la commune de », « la ville
#: de », « les communes de », « les trois communes de », et la reprise « dans
#: celle de Poix-du-Nord ». La préposition manque une fois, en 2017 : « la
#: commune Les Abymes ».
ANCRE_COMMUNE = re.compile(
    r"\b(?:communes?|ville|(?<=dans )celle)\s+(?=de\s|du\s|des\s|d['’]|[A-ZÉÈ])"
)
#: Un lieu d'une énumération, avec son département quand la décision le donne
#: à chacun — « les communes de Talus-Saint-Prix (Marne) et de Rémelfang
#: (Moselle) » — ou une seule fois pour tous : « les communes de Canteleux et
#: de Guinecourt (Pas-de-Calais) ». La virgule manque parfois entre deux lieux :
#: « de Saint-Sulpice (Nièvre) de Montrevel (Isère) ».
LIEU = re.compile(
    r"(?P<prep>de\s+|du\s+|des\s+|d['’])?"
    rf"(?P<nom>{NOM_DE_LIEU})(?:\s*{DEPARTEMENT})?"
)
SEPARATEUR_DE_LIEUX = re.compile(r"(?:\s*,\s*|\s+et\s+|\s+)(?=de\s|du\s|des\s|d['’]|[A-ZÉÈ])")
#: Une commune que la décision nomme sans dire « commune » : « les bureaux de
#: vote n° 1 […] et 11 de Papeete (Polynésie Française) », « le 4e bureau de
#: vote de Yaté ».
SANS_LE_MOT = re.compile(
    rf"bureaux?\s+(?:de\s+vote\s+)?(?:[^;]{{0,80}}?\s)?(?:de\s+l['’]Île\s+de\s+|de\s+|d['’])(?P<liste>{NOM_DE_LIEU})"
    rf"(?:\s*{DEPARTEMENT})?"
)
#: Un arrondissement de Paris, où les bureaux sont numérotés par arrondissement :
#: « le bureau de vote n° 27 du treizième arrondissement de Paris ».
ARRONDISSEMENT = re.compile(
    r"du\s+(?P<ordinal>[a-zè\-]+)\s+arrondissement\s+de\s+(?P<liste>Paris)"
)

#: Ce qui désigne les bureaux, dans le texte qui précède la commune. Le mot
#: « bureau » peut manquer quand il est déjà dit : « dans les bureaux n° 1 de la
#: commune de Furiani et n° 15 de la commune de Bastia ».
BUREAUX_NUMERO_APRES = re.compile(
    r"(?:bureaux?\s+(?:de\s+vote\s+)?)?\bn[o°s]{1,2}\s*"
    r"(?P<numeros>\d{1,4}(?:\s*(?:,|et)\s*(?:n[o°s]{1,2}\s*)?\d{1,4})*)",
    re.IGNORECASE,
)
#: « le 23e bureau », « les 26 ° et 27 ° bureaux », « le 1 er bureau », et les
#: blessures de la transcription : « le l bureau » pour le premier, « le 2"
#: bureau » pour le deuxième.
BUREAUX_NUMERO_AVANT = re.compile(
    r"(?P<numeros>\b[\dl]{1,3}\s*(?:er|re|ère|ème|eme|e|°|\")?"
    r"(?:\s*(?:,|et)\s*\d{1,3}\s*(?:er|re|ère|ème|eme|e|°|\")?)*)\s+bureaux?\b",
)
BUREAUX_EN_LETTRES = re.compile(
    r"\b(?P<numeros>(?:(?:" + "|".join(ORDINAUX) + r")(?:,\s*|\s+et\s+)?)+)\s*bureaux?\b"
)
#: Tous les bureaux de la commune, ou son unique bureau : la portée est alors la
#: commune entière.
TOUS_LES_BUREAUX = re.compile(
    r"l['’]unique\s+bureau|bureau\s+de\s+vote\s+unique|l['’]ensemble\s+des\s+bureaux"
    r"|les\s+(?:deux|trois|quatre|cinq|six|sept|huit|neuf|dix)\s+bureaux"
    r"|le\s+bureau\s+de\s+vote\s+(?:de|du|d['’])",
    re.IGNORECASE,
)

#: Les suffrages exprimés dans le lieu annulé, dans toutes leurs tournures :
#: « dans lequel 291 suffrages ont été exprimés », « où 1 117 suffrages », « dans
#: lesquels 666 et 573 suffrages ont été respectivement exprimés », « dans
#: lesquels ont été respectivement exprimés 769 et 765 suffrages », « dans
#: lesquelles respectivement 8 et 12 suffrages », « dans lesquels,
#: respectivement, 755, 708 […] suffrages », et, une fois, « seuls 30 suffrages
#: ont été exprimés ».
SUFFRAGES = re.compile(
    r"(?:(?:dans\s+(?:lequel|laquelle|lesquels|lesquelles)|où),?\s+"
    r"(?:ont\s+été\s+(?:respectivement\s+)?exprimés\s+|respectivement,?\s+|ont\s+été\s+exprimés\s+)?"
    r"|seuls\s+)"
    r"(?P<nombres>\d[\d ]*(?:\s*(?:,|et)\s*\d[\d ]*)*?)\s+suffrages",
    re.IGNORECASE,
)
#: Une section qui situe les considérants qui la suivent, quand eux ne le
#: disent pas : « SUR LE DEROULEMENT DES OPERATIONS ELECTORALES DANS LE
#: TERRITOIRE DE NOUVELLE-CALEDONIE ».
SECTION_TERRITOIRE = re.compile(r"DANS\s+LE\s+TERRITOIRE\s+DE\s+(?P<territoire>.+?)\s*:?\s*$")
#: « dans le département du Val-de-Marne, dans le 23e bureau de… » : le
#: département donné en tête vaut pour les communes qui suivent.
DEPARTEMENT_EN_TETE = re.compile(
    r"dans\s+le\s+département\s+(?:du\s+|de\s+la\s+|de\s+l['’]|des\s+|de\s+)(?P<departement>[A-ZÉ][\w'’\- ]+?)\s*,"
)


@dataclass(frozen=True)
class _Mention:
    """Un lieu nommé dans un considérant, avant qu'on sache ses suffrages."""

    commune: str
    departement: str | None
    #: None quand rien ne désigne de bureau, () quand la décision vise tous
    #: les bureaux de la commune ou son unique bureau.
    bureaux: tuple[int, ...] | None
    fin: int


def _numeros(brut: str) -> tuple[int, ...]:
    """« 1, 2 et 4 », « 26 ° et 27 ° », « premier, troisième et dixième »."""
    mots = re.findall(r"[a-zè\-]+|[\dl]{1,4}", brut)
    numeros = []
    for mot in mots:
        if mot in ORDINAUX:
            numeros.append(ORDINAUX[mot])
        elif re.fullmatch(r"[\dl]{1,4}", mot):
            numeros.append(int(mot.replace("l", "1")))
    return tuple(numeros)


def _bureaux(avant: str, numerotes_seulement: bool = False) -> tuple[int, ...] | None:
    """Les bureaux que désigne un fragment du considérant.

    `numerotes_seulement` écarte « le bureau de vote » sans numéro, qui dans la
    suite d'un considérant désigne le bureau dont on parle, pas tous ceux de la
    commune.
    """
    for motif in (BUREAUX_NUMERO_APRES, BUREAUX_NUMERO_AVANT, BUREAUX_EN_LETTRES):
        trouve = None
        for trouve in motif.finditer(avant):
            pass
        if trouve is not None:
            return _numeros(trouve.group("numeros"))
    if not numerotes_seulement and TOUS_LES_BUREAUX.search(avant):
        return ()
    return None


def _avec_article(preposition: str, nom: str) -> str:
    """Rend à la commune l'article que la préposition avait absorbé.

    « la commune du Blanc-Mesnil » est Le Blanc-Mesnil, « la commune des
    Riceys » Les Riceys. La contraction est une règle de la langue, pas une
    supposition : la défaire rend le nom que porte la commune.
    """
    if preposition == "du":
        return f"Le {nom}"
    if preposition == "des":
        return f"Les {nom}"
    return nom


def _lieux(tete: str, position: int) -> tuple[list[tuple[str, str | None]], int]:
    """Les lieux énumérés à partir de `position`, et où l'énumération s'arrête.

    Un lieu après le premier doit être introduit par sa préposition — « et de
    Guinecourt », « , d'Asquins » — ou par une capitale après une virgule :
    « Besneville, Catteville et Le Valdécie ». Sans cette exigence, la phrase
    qui suit l'énumération serait lue comme un lieu de plus.
    """
    lieux: list[tuple[str, str | None]] = []
    while True:
        m = LIEU.match(tete, position)
        if m is None:
            break
        nom = _avec_article((m.group("prep") or "").strip(), m.group("nom"))
        lieux.append((nom, m.group("departement")))
        position = m.end()
        suite = SEPARATEUR_DE_LIEUX.match(tete, position)
        if suite is None:
            break
        prochain = LIEU.match(tete, suite.end())
        if prochain is None or not (prochain.group("prep") or "," in suite.group() or " et " in suite.group()):
            break
        position = suite.end()
    return lieux, position


def _mentions(tete: str) -> list[_Mention]:
    """Les lieux que nomme un considérant, dans l'ordre du texte."""
    trouves: list[tuple[int, int, list[tuple[str, str | None]], str]] = []
    for m in ARRONDISSEMENT.finditer(tete):
        rang = ORDINAUX.get(m.group("ordinal"))
        nom = f"Paris {rang}e arrondissement" if rang else "Paris"
        trouves.append((m.start(), m.end(), [(nom, "Paris")], ""))
    if not trouves:
        for m in ANCRE_COMMUNE.finditer(tete):
            lieux, bout = _lieux(tete, m.end())
            if lieux:
                trouves.append((m.start(), bout, lieux, ""))
    if not trouves:
        for m in SANS_LE_MOT.finditer(tete):
            nom = _avec_article("", m.group("liste"))
            trouves.append((m.start(), m.end(), [(nom, m.group("departement"))], ""))

    mentions: list[_Mention] = []
    deja: set[tuple[str, tuple[int, ...] | None]] = set()
    fin = 0
    for i, (debut, bout, lieux, designation) in enumerate(trouves):
        # La désignation des bureaux précède la commune — « le 23e bureau de la
        # commune d'Aulnay-sous-Bois » — ou la suit sans la quitter : « les 2e et
        # 5e bureaux de vote de l'Île de Maré ». Elle se lit donc de la fin du
        # lieu précédent à la fin de celui-ci.
        bureaux = _bureaux(designation or tete[fin:bout])
        if bureaux is None:
            # Elle peut aussi venir après, dans la phrase qui décrit le lieu :
            # « Dans la commune de Nice (Alpes-Maritimes), la composition du
            # bureau de vote n° 208 », « soixante électeurs du 5e bureau de
            # cette ville ».
            suivant = trouves[i + 1][0] if i + 1 < len(trouves) else len(tete)
            bureaux = _bureaux(tete[bout:suivant], numerotes_seulement=True)
        for nom, departement in lieux:
            # Un considérant peut nommer deux fois le même lieu — « dans cette
            # commune de Lourdios-Ichère » — sans l'annuler deux fois.
            if (nom, bureaux) in deja or (bureaux is None and any(n == nom for n, _ in deja)):
                continue
            deja.add((nom, bureaux))
            mentions.append(_Mention(nom, departement, bureaux, bout))
        fin = bout
    return mentions


def _suffrages(texte: str) -> list[int]:
    """Les nombres d'une tournure « dans lesquels 666 et 573 suffrages »."""
    return [int(n.replace(" ", "")) for n in re.split(r"\s*(?:,|et)\s*", texte) if n.strip()]


def _annulations_du_considerant(
    numero: int, texte: str, defaut: str | None
) -> tuple[list[Annulation], bool]:
    """Les annulations d'un considérant, et s'il a été lu en entier.

    Seul compte le texte qui précède la formule d'annulation : c'est là que la
    décision nomme les lieux, avant d'en exposer le motif. Un lieu cité dans le
    motif — la préfecture, un bureau voisin — n'est pas un lieu annulé.
    """
    formule = ANNULE.search(texte)
    tete, suite = texte[: formule.start()], texte[formule.start() :]
    # Quand rien ne désigne de bureau, la formule d'annulation dit la portée :
    # « d'annuler les suffrages exprimés dans ce bureau » à Chenevelles, où la
    # commune avait ouvert un second bureau sans en avoir le droit. Une formule
    # qui vise à la fois « ce bureau et cette commune » ne tranche pas, et le
    # lieu nommé comme commune le reste.
    vise_un_bureau = bool(re.search(r"\b(?:ce|ces)\s+bureaux?\b", suite)) and not re.search(
        r"\b(?:cette|ces)\s+communes?\b", suite
    )
    en_tete = DEPARTEMENT_EN_TETE.search(tete)
    defaut = en_tete.group("departement") if en_tete else defaut
    mentions = _mentions(tete)
    if not mentions:
        return [], False

    # Les suffrages suivent le groupe de lieux qu'ils décrivent : chaque
    # tournure vaut pour les lieux nommés depuis la précédente.
    groupes: list[tuple[list[_Mention], list[int] | None]] = []
    en_cours: list[_Mention] = []
    comptes = list(SUFFRAGES.finditer(tete))
    for mention in mentions:
        while comptes and comptes[0].start() < mention.fin and en_cours:
            groupes.append((en_cours, _suffrages(comptes.pop(0).group("nombres"))))
            en_cours = []
        en_cours.append(mention)
        # Une tournure qui suit immédiatement ce lieu, avant le suivant.
    if en_cours:
        groupes.append((en_cours, _suffrages(comptes.pop(0).group("nombres")) if comptes else None))

    # Le département d'une énumération n'est écrit qu'une fois, après son
    # dernier lieu : « dans les bureaux n° 1 de la commune de Furiani et n° 15
    # de la commune de Bastia (Haute Corse) ».
    departements = [m.departement for m in mentions]
    suivant = defaut
    for i in range(len(departements) - 1, -1, -1):
        if departements[i]:
            suivant = departements[i]
        else:
            departements[i] = suivant
    par_mention = dict(zip(map(id, mentions), departements, strict=True))

    annulations: list[Annulation] = []
    lu_en_entier = True
    for lieux, nombres in groupes:
        unites: list[tuple[_Mention, tuple[int, ...] | None]] = []
        if nombres and len(nombres) > 1 and len(lieux) == 1 and lieux[0].bureaux and len(
            lieux[0].bureaux
        ) == len(nombres):
            # « les bureaux n° 1 et 2 […], dans lesquels 666 et 573 suffrages
            # ont été respectivement exprimés » : un nombre par bureau.
            unites = [(lieux[0], (bureau,)) for bureau in lieux[0].bureaux]
        else:
            unites = [(lieu, lieu.bureaux) for lieu in lieux]
        if nombres and len(nombres) not in (1, len(unites)):
            lu_en_entier = False
            nombres = None
        if nombres and len(nombres) == 1 and len(unites) > 1:
            # Un seul nombre pour plusieurs lieux : il ne se répartit pas.
            lu_en_entier = False
            nombres = None
        for i, (lieu, bureaux) in enumerate(unites):
            annulations.append(
                Annulation(
                    considerant=numero,
                    portee=(
                        "bureau-de-vote"
                        if bureaux or (bureaux is None and vise_un_bureau)
                        else "commune"
                    ),
                    commune=lieu.commune,
                    departement=par_mention[id(lieu)],
                    bureaux=bureaux or (),
                    suffrages_exprimes=nombres[i] if nombres else None,
                    motif=texte,
                )
            )
    return annulations, lu_en_entier


#: Une rubrique de la nomenclature du Conseil : « 8.2.5.4.1. Procédure de
#: dépouillement ».
RUBRIQUE = re.compile(r"^(?P<code>\d+(?:\.\d+)+)\.\s+(?P<intitule>.+)$")
#: La citation qui ferme un abstract et dit quel considérant il résume :
#: « ( 2022-197 PDR , 27 avril 2022, cons. 17 , JORF […]) ».
CITATION = re.compile(r"\bcons\.\s*(?P<numero>\d+)")


def _nomenclature(texte: str) -> dict[int, tuple[tuple[str, str], ...]]:
    """Les rubriques des abstracts, par numéro de considérant.

    Chaque abstract descend l'arbre de la nomenclature, de « 8. ÉLECTIONS » à
    sa rubrique la plus précise, puis résume un considérant. Seule cette
    dernière rubrique est retenue : les autres ne sont que son chemin. Un
    considérant en a souvent plusieurs, quand son motif relève de deux
    principes à la fois.
    """
    if SEPARATEUR_ABSTRACTS not in texte:
        return {}
    rubriques: dict[int, list[tuple[str, str]]] = {}
    derniere = None
    for ligne in texte.split(SEPARATEUR_ABSTRACTS, 1)[1].splitlines():
        rubrique = RUBRIQUE.match(ligne.strip())
        if rubrique:
            derniere = (rubrique.group("code"), rubrique.group("intitule").strip())
            continue
        citation = CITATION.search(ligne)
        if citation and derniere:
            deja = rubriques.setdefault(int(citation.group("numero")), [])
            if derniere not in deja:
                deja.append(derniere)
    return {numero: tuple(liste) for numero, liste in rubriques.items()}


def _annulations(lignes: list[str]) -> tuple[list[Annulation], list[int], list[int]]:
    """Les annulations d'une décision, et les considérants lus de travers.

    Rend trois listes : les annulations, les considérants qui annulent mais
    dont aucun lieu n'a été reconnu, et ceux dont les lieux ont été lus sans
    que leurs suffrages aient pu leur être attribués. Un appelant exige ainsi
    l'exhaustivité au lieu de la supposer.
    """
    annulations, sans_lieu, sans_suffrages = [], [], []
    territoire = None
    for ligne in lignes:
        section = SECTION_TERRITOIRE.search(ligne)
        if section:
            territoire = section.group("territoire")
            continue
        m = CONSIDERANT.match(ligne)
        if m is None:
            continue
        numero, texte = int(m.group("numero")), m.group("texte")
        if not ANNULE.search(texte) or REDRESSEMENT.search(texte) or PARTIELLE.search(texte):
            continue
        lues, entier = _annulations_du_considerant(numero, texte, territoire)
        if not lues:
            sans_lieu.append(numero)
        elif not entier:
            sans_suffrages.append(numero)
        annulations.extend(lues)
    return annulations, sans_lieu, sans_suffrages


def lire_en_detail(source: VersionResultats, racine=None) -> tuple[Tour, list[int], list[int]]:
    """Comme `lire`, mais rend aussi les considérants lus de travers.

    Les deux listes sont celles de `_annulations` : considérants qui annulent
    sans qu'un lieu ait été reconnu, et ceux dont les suffrages n'ont pu être
    attribués. Elles servent à exiger l'exhaustivité.
    """
    texte = source.chemin(racine).read_text(encoding="utf-8")
    lignes = _lignes(texte)
    annulations, sans_lieu, sans_suffrages = _annulations(lignes)
    rubriques = _nomenclature(texte)
    annulations = [
        replace(annulation, nomenclature=rubriques.get(annulation.considerant, ()))
        for annulation in annulations
    ]
    tour = Tour(
        voix=tuple(_voix(lignes, source)),
        annulations=tuple(annulations),
        **_decomptes(lignes),
    )
    return tour, sans_lieu, sans_suffrages


def lire(source: VersionResultats, racine=None) -> Tour:
    """Les résultats d'un tour, lus dans le texte de la décision qui les proclame."""
    return lire_en_detail(source, racine)[0]
