"""Lecture des parrainages, quel que soit le format du fichier source.

Le seed déclare le format ; ce module sait le lire. Tous rendent la même chose,
une suite de `Parrainage`, ce qui laisse le reste de la pipeline indifférent à
la forme du document d'origine.

Le nom du candidat est rendu tel que la source l'écrit — « ARTHAUD Nathalie »
en 2022, « Mme Eva Joly » en 2012. Le rapprocher d'une personne du registre est
le travail de la publication, pas celui de la lecture.
"""

from __future__ import annotations

import datetime as dt
import difflib
import json
import re
import unicodedata
from dataclasses import dataclass

from candidatheque.pipeline.seeds.parrainages import Format, SourceParrainages


@dataclass(frozen=True)
class Parrainage:
    """Une présentation de candidat par un élu habilité."""

    #: Le candidat présenté, tel que la source le nomme.
    candidat: str
    nom: str
    prenom: str | None = None
    civilite: str | None = None
    #: Le mandat qui rend l'élu habilité : maire, conseiller départemental…
    mandat: str | None = None
    #: La commune, le département ou la circonscription de ce mandat.
    circonscription: str | None = None
    departement: str | None = None
    #: La date à laquelle le Conseil l'a rendu public. Absente des formats
    #: antérieurs à 2017, qui ne publiaient qu'une fois.
    publie_le: dt.date | None = None


def _texte(valeur: object) -> str | None:
    """Une valeur de source, vidée de ses blancs, ou None si elle est vide."""
    if valeur is None:
        return None
    propre = str(valeur).strip()
    return propre or None


def _json_plat(contenu: list[dict], defaut: dt.date | None) -> list[Parrainage]:
    """Un tableau, une entrée par parrainage. Forme de 2022."""
    out = []
    for entree in contenu:
        jour = _texte(entree.get("DatePublication"))
        out.append(
            Parrainage(
                candidat=_texte(entree.get("Candidat")) or "",
                nom=_texte(entree.get("Nom")) or "",
                prenom=_texte(entree.get("Prenom")),
                civilite=_texte(entree.get("Civilite")),
                mandat=_texte(entree.get("Mandat")),
                circonscription=_texte(entree.get("Circonscription")),
                departement=_texte(entree.get("Departement")),
                publie_le=dt.date.fromisoformat(jour[:10]) if jour else defaut,
            )
        )
    return out


def _jour_francais(valeur: str | None) -> dt.date | None:
    """« 01/03/2017 » en date. Le format de 2017, contrairement à celui de 2022."""
    if not valeur:
        return None
    jour, mois, annee = valeur.split("/")
    return dt.date(int(annee), int(mois), int(jour))


def _json_par_candidat(contenu: list[dict], defaut: dt.date | None) -> list[Parrainage]:
    """Un tableau de candidats portant chacun ses parrainages. Forme de 2017."""
    out = []
    for bloc in contenu:
        candidat = _texte(bloc.get("Candidat-e parrainé-e")) or ""
        for entree in bloc.get("Parrainages", []):
            out.append(
                Parrainage(
                    candidat=candidat,
                    nom=_texte(entree.get("Nom")) or "",
                    prenom=_texte(entree.get("Prénom")),
                    civilite=_texte(entree.get("Civilité")),
                    mandat=_texte(entree.get("Mandat")),
                    circonscription=_texte(entree.get("Circonscription")),
                    departement=_texte(entree.get("Département")),
                    publie_le=_jour_francais(_texte(entree.get("Date de publication"))) or defaut,
                )
            )
    return out


#: Les lignes de mise en page du Journal officiel, à écarter : en-têtes, numéros
#: de page, mentions d'édition.
BRUIT = re.compile(
    r"^\s*(?:\d{1,5}\s*)?(?:JOURNAL\s+OFFICI|Texte\s+\d+\s+sur|NOR\s*:|ÉLECTION DU PRÉSIDENT"
    r"|Conseil constitutionnel|\d{1,2}\s+\w+\s+\d{4}|\.|\s)*$",
    re.IGNORECASE,
)
#: La note de bas de page du Journal officiel, qui n'est pas une présentation :
#: « chaque présentateur y est désigné par ses nom et qualité ».
NOTE = re.compile(r"pr[ée]sentateur|par ses nom et qualit|tir[ée]s? au sort", re.IGNORECASE)
#: Elle s'ouvre sur son appel de note et court jusqu'à sa dernière phrase.
OUVERTURE_DE_NOTE = re.compile(r"^\s*\(\d\)\s")
FIN_DE_NOTE = re.compile(r"[.»]\s*$")
#: Un nom peut porter une mention entre deux virgules — « TAHI, épouse
#: SONZOGNI, conseiller… » — qu'il faut rattacher au nom et non au mandat.
SUITE_DE_NOM = re.compile(r"^(?:épouse|epouse|née|nee|veuve)\b", re.IGNORECASE)
#: Le département, quand il est donné : un numéro avant 2012, un nom ensuite.
DEPARTEMENT = re.compile(r"[(<]\s*([^)>]{1,45}?)\s*[)>]?\s*$")
#: Le lieu d'exercice, introduit par « de », « du », « des » ou « d' ».
LIEU = re.compile(r"^(?P<mandat>.+?)\s+(?:de\s+|d[’']|des\s+|du\s+)(?P<lieu>[^,]{2,70})$")

#: Le titre courant du Journal officiel, et le « Texte n sur n » de son
#: édition électronique. Il tombe au milieu d'une colonne et
#: coupe donc une présentation en deux — « Elie / JOURNAL OFFICIEL DE LA /
#: PROCUREUR, maire… » —, si bien qu'il faut l'ôter du texte plutôt que la
#: ligne qui le porte.
TITRE_COURANT = re.compile(
    r"\s*\d{0,5}\s*(?:JOURNAL\s+OFFICIEL\s+DE\s+LA\s*|R[ÉE]PUBLIQUE\s+FRAN[ÇC]AISE\s*"
    r"|\d{1,2}\s+(?:janvier|f[ée]vrier|mars|avril|mai|juin|juillet|ao[ûu]t|septembre"
    r"|octobre|novembre|d[ée]cembre)(?:\s+\d{4})?\s*|Texte\s+\d+\s+sur\s+\d+\s*"
    r"|Texte\s+\d+\s+sur\s*)+\d{0,5}\s*",
    re.IGNORECASE,
)


def _sans_cesure(lignes: list[str]) -> str:
    """Recolle un mot coupé en fin de ligne, puis joint le reste par une espace.

    Le Journal officiel coupe les noms de communes — « NOVY-CHEVRIE- / RES » —
    et les recoller est indispensable : sans quoi le département se retrouve
    rattaché à un lieu tronqué. Il coupe aussi les mandats, au trait d'union
    conditionnel : « conseil\xadler général ».
    """
    # Le titre courant s'ôte avant de recoller les mots coupés : il s'intercale
    # entre les deux moitiés, et le recollage se refermerait sur lui.
    nettes = [TITRE_COURANT.sub(" ", ligne) for ligne in lignes]
    texte = "\n".join(ligne for ligne in nettes if ligne.strip())
    # Les deux césures du Journal officiel : le trait d'union conditionnel
    # — « conseil\xadler », « séna\xadteur » — et le trait d'union en fin de
    # ligne, qui coupe les noms de communes.
    texte = re.sub(r"\u00ad\s*", "", texte)
    texte = re.sub(r"(?<=\w)-\n\s*", "", texte)
    # « (55; ; » : la parenthèse fermante lue comme un point-virgule. Sans
    # cette reprise, le département part avec elle et un morceau vide s'ouvre.
    texte = re.sub(r"\((\d{2,3}\s?[AB]?)\s*;", r"(\1)", texte)
    # « d’I » recollé en une lettre par l'impression : « dTZIEU », « dlNJOUX ».
    texte = APOSTROPHE_RECOLLEE.sub("d’I", texte)
    return " ".join(texte.split())


def _decouper(morceau: str) -> tuple[str, str | None, str | None, str | None, str | None]:
    """Un morceau de prose en (nom, civilité, mandat, lieu, département).

    Le découpage se fait sur la première virgule, sauf quand ce qui suit
    prolonge le nom — « TAHI, épouse SONZOGNI, conseiller… ». Le lieu et le
    département sont facultatifs : un sénateur de Paris n'a ni l'un ni l'autre.
    """
    parts = [p.strip() for p in morceau.split(",")]
    nom = parts.pop(0)
    # Le nom court jusqu'au mandat : une mention peut le prolonger — « TAHI,
    # épouse SONZOGNI, conseiller… » — et une virgule parasite le couper en
    # deux — « Julien , VIDAL, maire… ».
    while parts and (SUITE_DE_NOM.match(parts[0]) or not _mandat_plausible(parts[0])):
        suite = parts.pop(0)
        nom += (", " if SUITE_DE_NOM.match(suite) else " ") + suite
        if not parts:
            nom = morceau.strip()
            break

    if not parts:
        # Sans virgule, le mandat est soit entre parenthèses — « M. Gil BRIAL
        # (Membre d'une assemblée de province) » —, soit collé au nom, le
        # Journal officiel ayant omis la virgule : « Jacky LUDI maire de
        # MILLERY (21) ».
        m = re.match(r"^(?P<nom>.+?)\s*\(\s*(?P<mandat>[^)]{4,90})\s*\)\s*$", nom)
        if m and not m.group("mandat").strip().rstrip(".").isdigit():
            return _civilite(m.group("nom")) + (m.group("mandat").strip(), None, None)
        m = re.match(
            r"^(?P<nom>.+?)[^\w\s]*\s*(?P<mandat>maire|conseill\S*|s[ée]nateur|d[ée]put\S*)\b(?P<reste>.*)$",
            nom,
            re.IGNORECASE,
        )
        if m:
            parts = [m.group("mandat") + m.group("reste")]
            nom = m.group("nom")
        else:
            return nom, None, None, None, None

    reste = ", ".join(parts)
    departement = None
    m = DEPARTEMENT.search(reste)
    if m:
        departement = m.group(1)
        reste = reste[: m.start()].strip()

    lieu = None
    m = LIEU.match(reste)
    if m:
        reste, lieu = m.group("mandat").strip(), m.group("lieu").strip()
    else:
        reste, lieu = _lieu_en_capitales(reste)

    return _civilite(nom) + (_sans_scories(reste) or None, lieu, departement)


#: L'apostrophe de « d’ » suivie d'un I, que l'impression recolle en une seule
#: lettre : « maire dTZIEU » pour « maire d’IZIEU », « dlNJOUX-GENISSIAT »
#: pour « d’INJOUX-GENISSIAT ». Le nom de la commune se vérifie à chaque fois.
APOSTROPHE_RECOLLEE = re.compile(r"\bd[Tl1](?=[A-ZÉÈÀÂÎÔÛ])")
#: Le lieu quand la préposition qui l'introduit est sortie abîmée de
#: l'impression — « maire dé BARONVILLE », « mairede SAINTE-NATHALENE »,
#: « maire cle DOMEVRE-EN-HAYE » — ou qu'elle manque : « maire FASSIONS ».
#: Le repère sûr n'est alors plus la préposition, dont chaque scan invente une
#: variante, mais la casse : le Journal officiel imprime les communes tout en
#: capitales et les mandats en minuscules.
DEBUT_DE_LIEU = re.compile(r"[A-ZÉÈÀÂÎÔÛÇ]{2}")
#: Ce qu'il reste de la préposition du côté du mandat, une fois la coupure
#: faite : « maire dé », « mairede », « maire.de ».
#: Collée au mandat — « mairede » —, détachée — « maire dé » —, ou réduite à sa
#: première lettre suivie d'une apostrophe égardée : « maire d ’ ».
RESTE_DE_PREPOSITION = re.compile(
    r"(?:[\s.,'’\-]+\S{1,3}|(?<=[a-zé])(?:de|du|des)|\bd)\s*$", re.IGNORECASE
)
#: La préposition passée du côté du lieu, quand elle aussi était en capitales :
#: « maire DU BOULVÉ ». L'espace est exigée : sans elle, « DUTTLENHEIM »
#: perdrait ses deux premières lettres.
PREPOSITION_EN_CAPITALES = re.compile(r"^(?:DE|DU|DES|D\s*[’']?)\s+")


def _lieu_en_capitales(reste: str) -> tuple[str, str | None]:
    """Sépare le mandat du lieu sur la casse, quand la préposition a été perdue.

    C'est le repli de `LIEU`, qui demande une préposition lisible. Quarante ans
    de scans en ont inventé une trentaine de graphies — « dé », « dç », « ds »,
    « der », « d5 », « cle », « deLA » — et les énumérer serait sans fin.
    """
    m = DEBUT_DE_LIEU.search(reste)
    if not m:
        return reste, None
    mandat, lieu = reste[: m.start()], reste[m.start() :].strip()
    lieu = PREPOSITION_EN_CAPITALES.sub("", lieu).strip(" .,;:")
    # Un lieu plus long qu'un nom de commune n'en est pas un : c'est un texte
    # voisin que la mise en page a laissé traaîner. Mieux vaut ne rien couper et
    # laisser l'appelant compter la présentation comme non lue.
    if not lieu or len(lieu) > 70:
        return reste, None
    # Une préposition peut laisser plusieurs bribes derrière elle — « maire d ’ »
    # en laisse deux —, d'où le retrait jusqu'à ce qu'il n'en reste plus.
    while (court := RESTE_DE_PREPOSITION.sub("", mandat)) != mandat:
        mandat = court
    return mandat.strip(" .,;:-'’"), lieu


def _civilite(nom: str) -> tuple[str, str | None]:
    """Détache la civilité du nom, quand il y en a une."""
    m = re.match(r"^(M\.|M,|Mme|Mlle)\s+", nom.strip())
    if m:
        return nom.strip()[m.end() :].strip(), m.group(1).replace(",", ".")
    return nom.strip(), None


#: Ce qui trahit une présentation plutôt qu'un titre de candidat.
MANDAT_PRESENT = re.compile(
    r",\s*(?:maire|conseill|s[ée]nateur|d[ée]put|repr[ée]sentant)", re.IGNORECASE
)
#: Un mandat en tête de morceau : le point-virgule qui le précède tient la
#: place d'une virgule — « Jean LAFFORGUE; maire de BATSERE (65) ».
#: Ce qui sépare deux présentations : un point-virgule, ou l'astérisque que
#: l'impression du Journal officiel met parfois à sa place.
SEPARATEUR = re.compile(r"\s*;\s*")
#: La fin d'une présentation : son département, puis quoi que l'impression ait
#: laissé à la place du point-virgule — « (76)*. André BOYER », « (80) Roger
#: THONON » —, avant le prénom de la suivante.
FIN_DE_PRESENTATION = re.compile(
    # Le département, dont la parenthèse fermante se lit parfois « 1 » ou « l ».
    # Un code à trois chiffres est ultramarin — 971 à 988 ; partout ailleurs le
    # troisième chiffre est cette parenthèse, et « (891 » vaut « (89) ».
    r"\(\s*(9[78]\d|\d{2}\s?[AB]?)\s*[)\]}|1lI]?"
    # Puis ce que l'impression a laissé à la place du point-virgule : des
    # signes, ou une ou deux bribes de lettres — « (51) j»1 Louis GAYT ».
    r"(?:\s*(?:[^\w\s]+|\b\w{1,2}\b)){0,3}\s*"
    # Puis le prénom et le nom de la présentation suivante.
    r"(?=[A-ZÉÈÀÂÎÔÛ][\w’\'\-]+\s+[A-ZÉÈÀÂÎÔÛ])"
)
MANDAT_EN_TETE = re.compile(
    r"^(?:maire|conseill|s[ée]nateur|d[ée]put|repr[ée]sentant|membre|pr[ée]sident"
    r"|vice-pr[ée]sident|adjoint)",
    re.IGNORECASE,
)


#: Le texte voisin qui a suivi la fin d'une liste : le point final que ferme le
#: département — « … conseiller général (54). » — est le dernier mot du Conseil
#: constitutionnel, et ce qui vient ensuite appartient au décret imprimé en
#: dessous. La présentation, elle, est vraie : on la garde et on coupe la suite.
TEXTE_ETRANGER = re.compile(
    r"^(?P<presentation>.*?\(\s*\d{2,3}\s?[AB]?\s*\))\s*\.\s+\S.{40,}$", re.DOTALL
)

#: Au-delà, et une fois le texte voisin coupé, le morceau n'est plus une
#: présentation. La plus longue lue en tient 105.
LONGUEUR_MAX = 200

#: Le point final qui ferme la liste d'un candidat, après son dernier
#: département : « … maire de POUILLENAY (21). »
FIN_DE_LISTE = re.compile(r"\)\s*\.\s*$")


#: Les mandats qui habilitent à présenter un candidat, en clé.
MANDATS = (
    "maire",
    "conseiller",
    "senateur",
    "depute",
    "membre",
    "president",
    "vicepresident",
    "adjoint",
    "representant",
    "assemblee",
)


def _sans_scories(mandat: str) -> str:
    """Le mandat débarrassé de ce que l'impression a laissé devant lui.

    « ,* maire de BERMONT », « , k k k maire de CHAINAZ » : le Journal officiel
    charrie des signes et des lettres isolées entre le nom et le mandat.
    """
    mots = mandat.split()
    while mots and len(_lettres(mots[0])) < 3:
        mots.pop(0)
    return " ".join(mots)


def _mandat_plausible(mandat: str) -> bool:
    """Le premier mot désigne-t-il bien un mandat électif ?

    C'est ce qui distingue une présentation d'un fragment d'un autre texte que
    la page voisine a laissé traîner. L'océrisation malmène jusqu'à « maire »
    — « jnaire », « maii\u2019e », « mgire » —, d'où la comparaison approchée.
    """
    mot = _lettres(_sans_scories(mandat).split()[0] or "") if _sans_scories(mandat) else ""
    if not mot:
        return False
    if any(mot.startswith(m[:5]) for m in MANDATS):
        return True
    return any(
        difflib.SequenceMatcher(None, mot, m).ratio() >= 0.65
        for m in MANDATS
        if abs(len(mot) - len(m)) <= 2
    )


def _texte_jo(
    contenu: str, defaut: dt.date | None, titres: tuple[str, ...] = ()
) -> tuple[list[Parrainage], list[str]]:
    """La prose du Journal officiel, en listes par candidat.

    Un titre de candidat ouvre une liste ; les présentations qui suivent lui
    sont rattachées jusqu'au titre suivant. `titres` donne ces titres tels que
    le seed les déclare, à la lettre : l'impression en abîme — « M. Michel
    DE3RE. », « Madame ArU 3 LAGUILLER » —, et les reconnaître de loin
    reviendrait à parier sur une ressemblance. Un titre déclaré se relit.

    Rend aussi les morceaux qu'elle n'a pas su lire, pour qu'un appelant puisse
    exiger l'exhaustivité au lieu de la supposer.
    """
    attendus = {" ".join(titre.split()): titre for titre in titres}
    candidat, tampon, out, rates = None, [], [], []
    #: Chaque titre n'ouvre sa liste qu'une fois : un rappel du même nom plus
    #: loin — une signature au bas d'un autre texte — n'est pas un titre.
    ouverts: set[str] = set()

    def vider() -> None:
        if not candidat:
            return
        for morceau in _separer(_sans_cesure(tampon)):
            morceau = TEXTE_ETRANGER.sub(r"\g<presentation>", morceau).strip(" .")
            if len(morceau) < 8 or NOTE.search(morceau):
                continue
            if len(morceau) > LONGUEUR_MAX:
                rates.append(morceau)
                continue
            nom, civilite, mandat, lieu, departement = _decouper(morceau)
            # Un nom d'élu tient en quelques mots : au-delà, le morceau vient
            # d'un texte voisin que la mise en page a laissé traîner.
            if not nom or len(nom.split()) > 8 or not mandat or not _mandat_plausible(mandat):
                rates.append(morceau)
                continue
            out.append(
                Parrainage(
                    candidat=candidat,
                    nom=nom,
                    civilite=civilite,
                    mandat=mandat,
                    circonscription=lieu,
                    departement=departement,
                    publie_le=defaut,
                )
            )

    lignes = [l for l in _sans_note(contenu.splitlines()) if not BRUIT.match(l)]
    for ligne in lignes:
        # Le titre occupe sa ligne entière : le chercher à l'intérieur d'une
        # ligne ferait passer « LA CHAPELLE-FORAINVILLIERS » pour un titre de
        # Philippe de Villiers, coupant sa liste en deux.
        trouve = attendus.get(" ".join(ligne.split()))
        if trouve in ouverts:
            trouve = None
        if trouve:
            ouverts.add(trouve)
            vider()
            candidat, tampon = trouve, []
            continue
        tampon.append(ligne)
    vider()
    return out, rates


def _separer(prose: str) -> list[str]:
    """La prose en morceaux, un par présentation.

    Le point-virgule sépare les présentations, mais les scans anciens le
    rendent par n'importe quel signe, quand ils ne l'effacent pas. Le repère
    sûr est le département qui ferme chaque présentation : ce qui le suit et
    ressemble à un prénom suivi d'un nom ouvre la suivante.

    Le Journal officiel pose aussi parfois un point-virgule là où va une
    virgule, entre le nom et le mandat ; un morceau ouvert par un mandat est
    donc recollé au précédent.
    """
    morceaux: list[str] = []
    for morceau in SEPARATEUR.split(FIN_DE_PRESENTATION.sub(r"(\1) ; ", prose)):
        morceau = morceau.strip(" .,:")
        if morceaux and MANDAT_EN_TETE.match(morceau) and "," not in morceaux[-1]:
            morceaux[-1] += ", " + morceau
        else:
            morceaux.append(morceau)
    return morceaux


def _sans_note(lignes: list[str]) -> list[str]:
    """Les lignes, débarrassées de la note de bas de page.

    Le Journal officiel imprime en pied de page la règle du tirage au sort, ou
    l'article de loi qui l'impose — les deux rédactions existent, d'où le
    repère pris sur l'appel de note plutôt que sur le texte. Elle tombe au
    milieu d'une présentation et
    la coupe en deux — « Claude LUCHE, » d'un côté, « maire de BOISSEAUX (45) »
    de l'autre —, d'où l'ôter plutôt que l'écarter à la lecture : la
    présentation se recolle alors d'elle-même.
    """
    gardees, dans_la_note = [], False
    for ligne in lignes:
        if dans_la_note:
            dans_la_note = not FIN_DE_NOTE.search(ligne)
            continue
        if OUVERTURE_DE_NOTE.match(ligne):
            dans_la_note = not FIN_DE_NOTE.search(ligne)
            continue
        gardees.append(ligne)
    return gardees


def _lettres(mot: str) -> str:
    """Un mot réduit à ses lettres minuscules, sans accent ni ponctuation."""
    sans = unicodedata.normalize("NFD", mot.lower())
    return re.sub(r"[^a-z]", "", re.sub(r"[\u0300-\u036f]", "", sans))


def lire(source: SourceParrainages, racine=None) -> list[Parrainage]:
    """Les parrainages d'une élection, lus selon le format que le seed déclare."""
    chemin = source.chemin(racine)
    #: Les formats antérieurs à 2017 ne publiaient qu'une fois : la date est
    #: celle de l'unique publication déclarée.
    defaut = source.publications[0].date if len(source.publications) == 1 else None

    if source.format is Format.JSON_PLAT:
        return _json_plat(json.loads(chemin.read_text(encoding="utf-8")), defaut)
    if source.format is Format.JSON_PAR_CANDIDAT:
        return _json_par_candidat(json.loads(chemin.read_text(encoding="utf-8")), defaut)
    # Le texte du Journal officiel. Sa prose n'a pas changé de forme en
    # quarante ans ; seule la qualité de l'impression varie.
    titres = tuple(candidat.titre for candidat in source.candidats)
    lus, _ = _texte_jo(chemin.read_text(encoding="utf-8"), defaut, titres)
    return lus


def lire_en_detail(
    source: SourceParrainages, racine=None
) -> tuple[list[Parrainage], list[str]]:
    """Comme `lire`, mais rend aussi ce que la lecture n'a pas su interpréter.

    Sert à exiger l'exhaustivité : un morceau non lu est une donnée perdue, et
    il vaut mieux le compter que le découvrir plus tard.
    """
    if not source.format.value.startswith("texte"):
        return lire(source, racine), []
    defaut = source.publications[0].date if len(source.publications) == 1 else None
    titres = tuple(candidat.titre for candidat in source.candidats)
    return _texte_jo(source.chemin(racine).read_text(encoding="utf-8"), defaut, titres)
