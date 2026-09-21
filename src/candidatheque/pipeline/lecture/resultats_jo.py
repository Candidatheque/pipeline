"""Lecture des tableaux de résultats annexés aux proclamations, au Journal officiel.

Jusqu'en 1995, le Conseil constitutionnel arrête les résultats des deux tours
« conformément aux tableaux annexés » à sa proclamation : un département par
ligne, un candidat par colonne, et une ligne TOTAL. Leur texte vient de la
couche que Légifrance a océrisée, extraite par `outils/tableau_pdf_en_texte.py`
dans `raw/resultats/jo/`, et il en porte les fautes : chiffres collés
— « 299997 » —, coupés — « 1 1 126 » —, défigurés — « 4.0G4 » — ou faux, ce
qui ne se voit pas à la lecture.

Rien n'y est donc pris sur la foi d'une seule lecture. Le tableau porte ses
propres contrôles : la somme des voix d'une ligne fait ses exprimés, chaque
colonne fait la ligne TOTAL, et en 1995 un pourcentage imprimé à côté des voix
tombe juste à l'arrondi près. Ils servent deux fois :

- à la lecture d'une ligne, pour choisir entre les découpages que permettent
  les espaces de milliers ;
- ensuite, sur la grille entière, pour remplir une case illisible et corriger
  une case fausse, quand deux contrôles indépendants la désignent — la ligne
  et la colonne qui se croisent sur elle.

Ce qu'ils ne suffisent pas à établir se déclare au seed, lu à la main sur
l'image de l'édition, avec le motif qui l'établit. Rien n'est deviné.
"""

from __future__ import annotations

import re
from functools import cache
from itertools import pairwise

from candidatheque.pipeline.lecture.resultats import Departement, Tour, Voix
from candidatheque.pipeline.publication.departements import normaliser
from candidatheque.pipeline.seeds.resultats import TableauJO, VersionResultats

#: Les colonnes qui ne sont pas un candidat. « total » redit les exprimés à la
#: fin de la seconde moitié d'un tableau coupé en deux.
DECOMPTES = ("inscrits", "votants", "suffrages_exprimes", "total")
#: La clé des Français établis hors de France, qui n'ont pas de département.
ETRANGER = "etranger"
#: La clé de la ligne TOTAL.
TOTAL = "total"
#: Les départements de métropole, que chaque tableau doit porter tous. Une
#: ligne absente ne se remarquerait pas autrement : la case qu'une autre ligne
#: déduirait du total l'absorberait en silence.
METROPOLE = frozenset({f"{n:02d}" for n in range(1, 96) if n != 20} | {"2A", "2B"})

#: Un pourcentage imprimé : « 5,38% », « 57.43% ».
POURCENTAGE = re.compile(r"(\d{1,3})[,.](\d{2})\s?%")
#: Le 1 que l'impression rend par une lettre ou un signe : « I 150 », « T 68 406 »,
#: « J 64 580 », « 4] 392 ».
UN_DEFIGURE = re.compile(r"(?<![A-Za-zÀ-ÿ\d])[IlTJ|]+(?=\s?\d)|(?<=\d)\](?=\s?\d)")
#: Les lettres que l'océrisation met à la place d'un chiffre, dans un nombre à
#: points : « i.688 », « 2S.82S », « 4.0G4 ». La lecture qui en sort n'est pas
#: prise pour acquise : elle passe les mêmes contrôles de ligne et de colonne.
LETTRES_POUR_CHIFFRES = str.maketrans("iIlo OSGB", "1110 0568")
#: Le début d'une ligne : un code facultatif, puis le libellé jusqu'au premier
#: chiffre. Le code n'en est un que s'il précède un libellé : sur une ligne qui
#: ne porte que des nombres, « 39 976 944 » ne commence pas par le Jura.
#: Le libellé s'arrête avant le 1 défiguré qui ouvre parfois le premier nombre :
#: « BOUCHES-DU-RHONE l 108 944 ». Entre le code et le nom, le scan laisse des
#: signes parasites : « 73 (SAVOIE », « 80 ; SOMME ».
TETE = re.compile(
    r"^\s*[^\w]*(?:(?P<code>\d{2,3}|2[AB])\b\s*[^\w\s]*\s*(?=[A-Za-zÀ-ÿ]))?"
    r"(?P<libelle>[^\d]*?)(?=\s+[IlTJ|]+\s?\d|\d|$)"
)
#: Les lignes d'en-tête, qui portent des mots mais pas de département.
EN_TETE = re.compile(
    r"(?i)d[ée]partement|^territoires?$|^terri\s*toi\s*res$|inscrits|exprim|votants|suffrages"
    r"|journal|pr[ée]sentation"
    r"|d[ée]veloppement|^nom\b|^code\b|^ou$|mai\s+19|\bNOR\b"
)
#: Un libellé à l'ancienne mode du Journal officiel, qualificatif rejeté entre
#: parenthèses : « ALPES (HAUTES-) », « RHIN (BAS-) », « REUNION (LA) ».
RETOURNE = re.compile(r"^(?P<nom>.+?)\s*-?\s*\((?P<avant>[^)>]+?)-?\s*[)>]\s*$")


# ---------------------------------------------------------------------------
# Une ligne
# ---------------------------------------------------------------------------


def _nombres_points(texte: str) -> list[int | None]:
    """Les nombres d'une ligne à points de milliers : « 262.000 ».

    La virgule y est un point mal lu : aucun décompte n'a de décimale. Un jeton
    que l'impression a défiguré — « 4.0G4 », « 2S.82S » — reste une case, mais
    vide : la ligne garde son alignement, et la case se déduira de la grille.
    """
    # Le point de milliers lu comme un tiret — « 106-794 », « 257 -668 » —
    # redevient un point.
    texte = re.sub(r"(\d)\s?-\s?(?=\d{3}\b)", r"\1.", texte)
    # Un nombre que l'impression a coupé après son point — « 84'. 136 » — se
    # recolle : un groupe de trois chiffres ne commence jamais un nombre.
    texte = re.sub(r"(\d)[.,'’]+\s+(?=\d{3}\b)", r"\1.", texte)
    nombres: list[int | None] = []
    for jeton in texte.split():
        propre = jeton.strip("*•.,;:'’‘\"»-–—")
        if not propre:
            continue
        # Un jeton qui a la forme d'un nombre à une lettre près redevient un
        # nombre ; un mot entier, lui, reste un mot.
        if re.fullmatch(r"[\diIloOSGB]{1,3}(?:[.,][\diIloOSGB]{3})*", propre) and re.search(r"\d", propre):
            propre = propre.translate(LETTRES_POUR_CHIFFRES)
        if re.fullmatch(r"\d{1,3}(?:[.,]\d{3})*", propre):
            nombres.append(int(re.sub(r"[.,]", "", propre)))
        else:
            nombres.append(None)
    return nombres


def _recolle(texte: str) -> str:
    """Rend au chiffre que l'océrisation a détaché sa place dans son nombre.

    « 363 1 14 » est 363 114, « 1 1 2 406 » est 112 406, « 35 8 648 » est
    358 648. Une suite d'au moins deux petits groupes se recolle quand elle
    forme un groupe de trois chiffres, ou quand elle précède un tel groupe et en
    devient la tête. Les pourcentages restent à l'écart : leurs chiffres ne
    sont pas des voix. La lecture qui en sort passe ensuite les mêmes contrôles
    que les autres : pourcentages, sommes, totaux.
    """
    morceaux = POURCENTAGE.split(texte)
    # POURCENTAGE a deux groupes : le texte hors pourcentages est aux rangs
    # multiples de trois, les pourcentages se reconstituent des deux suivants.
    sortie = []
    for rang in range(0, len(morceaux), 3):
        sortie.append(_recolle_hors_pourcentage(morceaux[rang]))
        if rang + 2 < len(morceaux):
            sortie.append(f"{morceaux[rang + 1]},{morceaux[rang + 2]}%")
    return "".join(sortie)


def _recolle_hors_pourcentage(texte: str) -> str:
    morceaux = re.split(r"(\d+)", texte)
    # Les nombres sont aux rangs impairs, les séparateurs aux rangs pairs.
    i = 1
    while i < len(morceaux):
        j = i
        suite = []
        # La suite des petits groupes qui ne sont séparés que par une espace.
        while j < len(morceaux) and len(morceaux[j]) <= 2 and (j == i or morceaux[j - 1] == " "):
            suite.append(morceaux[j])
            j += 2
        colle = "".join(suite)
        suivant = morceaux[j] if j < len(morceaux) and morceaux[j - 1] == " " else ""
        if len(suite) >= 2 and (len(colle) == 3 or (len(colle) <= 3 and len(suivant) == 3)):
            morceaux[i : j - 1] = [colle]
        i += 2
    return "".join(morceaux)


def _chiffres(texte: str) -> tuple[str, ...]:
    """Les groupes de chiffres d'une ligne à espaces de milliers."""
    return tuple(re.findall(r"\d+", texte))


@cache
def _decoupages(jetons: tuple[str, ...], combien: int) -> tuple[tuple[int, ...], ...]:
    """Toutes les façons de regrouper des groupes de chiffres en `combien` nombres.

    Un nombre commence par un groupe quelconque et se prolonge par des groupes
    de trois chiffres — ou de six, quand l'impression en a collé deux.
    """
    if combien == 0:
        return ((),) if not jetons else ()
    resultats = []
    for fin in range(1, len(jetons) + 1):
        if any(len(j) % 3 for j in jetons[1:fin]):
            break
        valeur = int("".join(jetons[:fin]))
        for reste in _decoupages(jetons[fin:], combien - 1):
            resultats.append((valeur, *reste))
    return tuple(resultats)


def _candidats(tableau: TableauJO) -> list[str]:
    return [c for c in tableau.colonnes if c not in DECOMPTES]


def _ordonnee(valeurs: dict[str, int]) -> bool:
    """Des inscrits aux votants, des votants aux exprimés, jamais plus."""
    suite = [valeurs.get(c) for c in ("inscrits", "votants", "suffrages_exprimes", "total")]
    presents = [v for v in suite if v is not None]
    return all(a >= b for a, b in pairwise(presents))


def _pourcentage_juste(voix: int, base: int, pourcentage: float) -> bool:
    """Le pourcentage imprimé tombe-t-il sur ces voix, à l'arrondi près ?"""
    return base > 0 and abs(100 * voix / base - pourcentage) <= 0.0051


def _lire_ligne(texte: str, tableau: TableauJO, complet: bool) -> dict[str, int]:
    """Les cases d'une ligne. Une case que la lecture ne tranche pas est omise.

    `complet` dit si le tableau porte à lui seul les exprimés et tous les
    candidats, et peut donc contrôler la somme d'une ligne.
    """
    texte = UN_DEFIGURE.sub(lambda m: "1" * len(m.group()), texte)
    colonnes = list(tableau.colonnes)
    candidats = _candidats(tableau)

    def juste(valeurs: dict[str, int]) -> bool:
        if not _ordonnee(valeurs):
            return False
        return not complet or sum(valeurs[c] for c in candidats) == valeurs["suffrages_exprimes"]

    if tableau.milliers == "point":
        nombres = _nombres_points(POURCENTAGE.sub(" ", texte))
        if len(nombres) != len(colonnes):
            return {}
        return {c: n for c, n in zip(colonnes, nombres, strict=True) if n is not None}

    texte = _recolle(re.sub(r"(\d)[,.](\d) (\d)\s?%", r"\1,\2\3%", texte))
    if not tableau.pourcentages:
        solutions = [
            dict(zip(colonnes, d, strict=True))
            for d in _decoupages(_chiffres(texte), len(colonnes))
        ]
        solutions = [s for s in solutions if juste(s)]
        return solutions[0] if len(solutions) == 1 else {}

    # Avec les pourcentages, les voix d'un candidat sont le nombre qui précède
    # le sien : le texte se coupe à chaque pourcentage. Seul le premier morceau
    # reste ambigu — les décomptes et le premier candidat s'y suivent —, et le
    # pourcentage de ce candidat le départage.
    pourcentages = [float(f"{m.group(1)}.{m.group(2)}") for m in POURCENTAGE.finditer(texte)]
    morceaux = [_chiffres(m) for m in POURCENTAGE.split(texte)[::3]]
    if len(pourcentages) != len(candidats) or len(morceaux) != len(candidats) + 1:
        return {}
    avant = colonnes[: colonnes.index(candidats[0])]
    apres = colonnes[colonnes.index(candidats[-1]) + 1 :]
    milieu = [_decoupages(m, 1) for m in morceaux[1:-1]]
    queue = _decoupages(morceaux[-1], len(apres))
    if any(len(m) != 1 for m in milieu) or len(queue) != 1:
        return {}

    solutions = []
    for tete in _decoupages(morceaux[0], len(avant) + 1):
        valeurs = dict(zip([*avant, candidats[0]], tete, strict=True))
        valeurs.update({c: m[0][0] for c, m in zip(candidats[1:], milieu, strict=True)})
        valeurs.update(zip(apres, queue[0], strict=True))
        base = valeurs.get("suffrages_exprimes", valeurs.get("total"))
        if base is None or not all(
            _pourcentage_juste(valeurs[c], base, p)
            for c, p in zip(candidats, pourcentages, strict=True)
        ):
            continue
        if juste(valeurs):
            solutions.append(valeurs)
    return solutions[0] if len(solutions) == 1 else {}


# ---------------------------------------------------------------------------
# Une page
# ---------------------------------------------------------------------------


def _libelle(brut: str) -> str:
    """Le libellé, sans points de conduite ni signes parasites du scan."""
    propre = re.sub(r"[.…•*■»,;:'’\[\]|!_]{2,}.*$", "", brut)
    return propre.strip(" \t.…•*■»,;:'’\"[]|!_-")


def est_total(libelle: str) -> bool:
    return re.search(r"(?i)\btota(?:l|ux)\b", libelle) is not None


def _lignes(page: str) -> list[tuple[str, str | None, str]]:
    """Les lignes d'une page : libellé, code imprimé, texte des nombres.

    Un libellé peut déborder sur deux lignes — « FRANÇAIS ETABLIS HORS DE /
    FRANCE » — ou laisser ses nombres à la ligne suivante, comme la ligne
    TOTAL de 1995 : un libellé sans nombres attend la ligne qui les porte.
    """
    lues: list[tuple[str, str | None, str]] = []
    attente: tuple[str, str | None] | None = None
    #: Des nombres imprimés au-dessus de leur libellé, quand la ligne du
    #: tableau a été coupée en deux par la mise en page.
    orphelins = ""
    for ligne in page.splitlines():
        # Le folio et la date, en haut ou en bas de page, ne sont pas une
        # ligne du tableau : « 14 mai 1995 JOURNAL OFFICIEL […] 8159 ».
        if re.search(r"(?i)journal\s+officiel", ligne):
            continue
        # « 1'ETRANGER » : l'apostrophe de « l' » lue comme un 1, qui couperait
        # le libellé en son milieu.
        ligne = re.sub(r"\b1['’](?=[A-Za-zÀ-ÿ])", "l'", ligne)
        # « L0IRE-ATLANT1QUE », « L01RET » : des chiffres entre deux lettres
        # sont des lettres, et couperaient le libellé.
        ligne = re.sub(
            r"(?<=[A-Za-zÀ-ÿ])[01]+(?=[A-Za-zÀ-ÿ])",
            lambda m: m.group().replace("0", "O").replace("1", "I"),
            ligne,
        )
        # « 1 1 AUDE » : le code du département coupé par l'océrisation.
        ligne = re.sub(r"^(\s*)(\d) (\d)(?=\s+[A-Za-zÀ-ÿ])", r"\1\2\3", ligne)
        m = TETE.match(ligne)
        libelle = _libelle(m.group("libelle"))
        reste = ligne[m.end() :]
        # Une ligne de données porte au moins deux nombres ; un folio de page,
        # « 8157 », n'en porte qu'un.
        if len(re.findall(r"\d", reste)) < 4 or len(re.findall(r"\d+(?:[ .,]\d{3})*", reste)) < 2:
            # Un libellé qui attend ses nombres a au moins quatre lettres : le
            # « 14maM995 » d'un haut de page n'en a que trois, et ferait du
            # Calvados le département de la ligne suivante.
            if len(re.findall(r"[A-Za-zÀ-ÿ]", libelle)) >= 4 and not EN_TETE.search(libelle):
                attente = (
                    (libelle, m.group("code"))
                    if attente is None
                    else (f"{attente[0]} {libelle}", attente[1])
                )
            continue
        if libelle and EN_TETE.search(libelle):
            continue
        code = m.group("code")
        if attente is not None and (not libelle or est_total(libelle)):
            libelle = f"{attente[0]} {libelle}".strip() if libelle else attente[0]
            code = code or attente[1]
        attente = None
        if not libelle:
            # Seule une ligne faite de plusieurs nombres est la moitié d'une
            # ligne du tableau ; le folio « 7039 », seul ou suivi de « JOURNAL
            # OFFICIEL », ne l'est pas.
            colonnes_imprimees = re.split(r"\s{2,}", reste.strip())
            if not re.search(r"[A-Za-zÀ-ÿ]{3}", reste) and len(colonnes_imprimees) >= 3:
                orphelins = reste
            continue
        lues.append((libelle, code, f"{orphelins} {reste}" if orphelins else reste))
        orphelins = ""
    return lues


def _remis_a_l_endroit(libelle: str) -> str:
    """« ALPES (HAUTES-) » en « HAUTES-ALPES », « REUNION (LA) » en « LA REUNION »."""
    m = RETOURNE.match(libelle)
    if m is None:
        return libelle
    avant = m.group("avant").strip()
    separateur = " " if avant.lower() in ("la", "le", "les") else "-"
    return f"{avant}{separateur}{m.group('nom').strip()}"


def _cle(libelle: str, code: str | None, version: VersionResultats, annee: int) -> str | None:
    """La clé d'une ligne : code du département, « etranger » ou « total »."""
    if est_total(libelle):
        return TOTAL
    if libelle in version.libelles:
        return version.libelles[libelle]
    # « FRANÇAIS ETABLIS HORS DE FRANCE », « Français-de l'étranger », et le
    # « FRANÇAIS de » de 1981 dont la fin a glissé sur la ligne suivante.
    if re.match(r"(?i)fran[çc]ais\b", libelle):
        return ETRANGER
    if code and normaliser(code, annee):
        return normaliser(code, annee)
    return normaliser(libelle, annee) or normaliser(_remis_a_l_endroit(libelle), annee)


# ---------------------------------------------------------------------------
# La grille
# ---------------------------------------------------------------------------

def _resoudre(
    grille: dict[str, dict[str, int]],
    total: dict[str, int],
    colonnes: list[str],
    candidats: list[str],
) -> list[str]:
    """Complète et corrige la grille par ses deux contrôles, et rend ce qui reste.

    Chaque ligne doit faire la somme de ses voix dans ses exprimés, chaque
    colonne la valeur de la ligne TOTAL. Trois règles s'appliquent jusqu'à ce
    que plus rien ne bouge :

    - une ligne à une seule case vide la déduit de sa somme ;
    - une ligne fausse d'un écart δ, quand une seule colonne est fausse du même
      écart et qu'aucune autre ligne ne l'est de δ, a sa faute à leur
      croisement : la case y est corrigée de δ ;
    - en dernier, une colonne à une seule case vide la déduit de son total.
      Plus tôt, la case déduite absorberait les fautes que les autres lignes
      de sa colonne portent encore.

    Aucune de ces corrections n'est tenue pour acquise : la grille entière
    doit ensuite tomber juste, ligne par ligne et colonne par colonne.
    """
    lignees = ["suffrages_exprimes", *candidats]

    def ecart_ligne(valeurs: dict[str, int]) -> int | None:
        if not all(c in valeurs for c in lignees):
            return None
        return sum(valeurs[c] for c in candidats) - valeurs["suffrages_exprimes"]

    def ecart_colonne(colonne: str) -> int | None:
        if not all(colonne in v for v in grille.values()):
            return None
        return sum(v[colonne] for v in grille.values()) - total[colonne]

    def une_passe(par_colonne: bool) -> bool:
        avance = False
        for valeurs in grille.values():
            vides = [c for c in lignees if c not in valeurs]
            if len(vides) == 1:
                somme = sum(valeurs[c] for c in candidats if c in valeurs)
                if vides[0] == "suffrages_exprimes":
                    valeurs[vides[0]] = somme
                else:
                    valeurs[vides[0]] = valeurs["suffrages_exprimes"] - somme
                avance = True
        for valeurs in grille.values():
            delta = ecart_ligne(valeurs)
            if not delta:
                continue
            # Une ligne et une colonne fausses du même écart se croisent sur la
            # case fautive.
            fautives = [c for c in candidats if ecart_colonne(c) == delta]
            if ecart_colonne("suffrages_exprimes") == -delta:
                fautives.append("suffrages_exprimes")
            au_meme_ecart = [v for v in grille.values() if ecart_ligne(v) == delta]
            if len(fautives) == 1 and len(au_meme_ecart) == 1:
                fautive = fautives[0]
                valeurs[fautive] += delta if fautive == "suffrages_exprimes" else -delta
                avance = True
        if par_colonne:
            # En dernier seulement : une case déduite du total absorberait les
            # fautes des autres lignes de sa colonne, si elles en avaient encore.
            for colonne in colonnes:
                vides = [cle for cle, v in grille.items() if colonne not in v]
                if len(vides) == 1:
                    autres = sum(v[colonne] for cle, v in grille.items() if cle != vides[0])
                    grille[vides[0]][colonne] = total[colonne] - autres
                    avance = True
        return avance

    while une_passe(par_colonne=False) or une_passe(par_colonne=True):
        pass

    restes = []
    for cle, valeurs in grille.items():
        manque = [c for c in colonnes if c not in valeurs]
        if manque:
            restes.append(f"ligne {cle} : cases illisibles {manque}")
        elif ecart_ligne(valeurs):
            restes.append(f"ligne {cle} : les voix font {ecart_ligne(valeurs):+} sur les exprimés")
        elif not _ordonnee(valeurs):
            restes.append(f"ligne {cle} : inscrits, votants et exprimés en désordre")
    for colonne in colonnes:
        ecart = ecart_colonne(colonne)
        if ecart:
            restes.append(f"colonne {colonne} : {ecart:+} sur le total")
    return restes


def lire(version: VersionResultats, racine=None) -> tuple[Tour, list[str]]:
    """Les résultats d'un tour selon les tableaux du JO, et ce qui n'a pu être lu.

    Rend le tour et les problèmes qui restent : libellés inconnus, cases que ni
    la lecture, ni la grille, ni une correction déclarée n'ont établies. Un
    appelant exige que la liste soit vide.
    """
    annee = version.date.year
    pages = version.chemin(racine).read_text(encoding="utf-8").split("\f")
    candidats = [c for t in version.tableaux for c in _candidats(t)]
    colonnes = ["inscrits", "votants", "suffrages_exprimes", *candidats]
    # Un tableau complet contrôle la somme de chaque ligne ; les deux moitiés
    # d'un tableau coupé ne le peuvent qu'une fois réunies, dans la grille.
    complet = len(version.tableaux) == 1
    grille: dict[str, dict[str, int]] = {}
    libelles: dict[str, str] = {}
    problemes: list[str] = []

    for tableau in version.tableaux:
        for numero in tableau.pages:
            for libelle, code, reste in _lignes(pages[numero - 1]):
                cle = _cle(libelle, code, version, annee)
                if cle is None:
                    problemes.append(f"libellé inconnu : « {libelle} »")
                    continue
                libelles.setdefault(cle, libelle)
                valeurs = _lire_ligne(reste, tableau, complet)
                # La colonne « total » d'une seconde moitié redit les exprimés.
                if "total" in valeurs:
                    valeurs.setdefault("suffrages_exprimes", valeurs["total"])
                    del valeurs["total"]
                grille.setdefault(cle, {}).update(valeurs)

    for correction in version.corrections:
        grille.setdefault(correction.departement, {}).update(correction.valeurs)

    total = grille.pop(TOTAL, None)
    if total is None or not all(c in total for c in colonnes):
        return Tour(), [*problemes, "ligne TOTAL illisible"]
    for absent in sorted(METROPOLE - set(grille)):
        problemes.append(f"département {absent} absent du tableau")
    if sum(total[c] for c in candidats) != total["suffrages_exprimes"]:
        problemes.append("ligne TOTAL : les voix ne font pas les exprimés")
    problemes += _resoudre(grille, total, colonnes, candidats)

    def voix(valeurs: dict[str, int]) -> tuple[Voix, ...]:
        return tuple(
            Voix(titre=c, personne=version.personne_de(c) or "", voix=valeurs[c])
            for c in candidats
            if c in valeurs
        )

    departements = tuple(
        Departement(
            code=cle,
            libelle=libelles.get(cle, cle),
            inscrits=valeurs.get("inscrits"),
            votants=valeurs.get("votants"),
            suffrages_exprimes=valeurs.get("suffrages_exprimes"),
            voix=voix(valeurs),
        )
        for cle, valeurs in grille.items()
    )
    tour = Tour(
        inscrits=total["inscrits"],
        votants=total["votants"],
        suffrages_exprimes=total["suffrages_exprimes"],
        voix=voix(total),
        departements=departements,
    )
    return tour, problemes
