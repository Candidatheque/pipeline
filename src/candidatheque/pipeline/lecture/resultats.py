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
from dataclasses import dataclass, field

from candidatheque.pipeline.seeds.resultats import TourResultats

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
    #: Le numéro du bureau de vote, quand la portée est le bureau.
    bureau: int | None = None
    #: Les suffrages exprimés dans ce bureau, quand la décision les donne. Les
    #: décisions d'avant 1995 ne les donnent pas.
    suffrages_exprimes: int | None = None


@dataclass(frozen=True)
class Tour:
    """Un tour de scrutin, tel que la décision le donne."""

    numero: int
    inscrits: int | None = None
    votants: int | None = None
    bulletins_blancs: int | None = None
    bulletins_nuls: int | None = None
    suffrages_exprimes: int | None = None
    majorite_absolue: int | None = None
    voix: tuple[Voix, ...] = ()
    annulations: tuple[Annulation, ...] = ()
    #: Le code de nomenclature de chaque considérant, quand la décision porte
    #: des abstracts : « 8.2.5.4.1 ». C'est le classement du Conseil.
    nomenclature: dict[int, str] = field(default_factory=dict)


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


def _voix(lignes: list[str], source: TourResultats) -> list[Voix]:
    """Les voix de chaque candidat déclaré.

    Le nom doit fermer sa ligne sur un nombre : « Proclame Charles de Gaulle
    élu Président de la République » le porte aussi, mais ne dit pas ses voix.
    """
    trouvees = []
    for candidat in source.candidats:
        motif = re.compile(
            rf"{re.escape(candidat.titre)}\s*:?\s*(?P<voix>{NOMBRE.pattern})(?:\s*voix)?\s*[.,;]?$"
        )
        for ligne in lignes:
            m = motif.search(ligne)
            if m is None:
                continue
            trouvees.append(
                Voix(titre=candidat.titre, personne=candidat.personne, voix=_nombre(m.group("voix")))
            )
            break
    return trouvees


def lire(source: TourResultats, racine=None) -> Tour:
    """Un tour, lu dans le texte de la décision qui le proclame."""
    lignes = _lignes(source.chemin(racine).read_text(encoding="utf-8"))
    return Tour(
        numero=source.numero,
        voix=tuple(_voix(lignes, source)),
        **_decomptes(lignes),
    )
