"""Publication des parrainages, candidat par candidat.

Un parrainage se lit toujours en regard d'un candidat : il est publié dans le
répertoire de ce candidat, sous l'élection, et jamais dans un document unique
qui mélangerait les seize listes de 2002. Un consommateur qui ne s'intéresse
qu'à un candidat ne télécharge que son fichier.

Deux mentions comptent autant que les présentations elles-mêmes :

- `etendue` dit si la source publie tout ou un échantillon. Avant la réforme de
  2016, la loi n'imposait de publier que 500 noms par candidat, tirés au sort.
  Sans cette mention, compter les lignes de 2007 ferait conclure que Nicolas
  Sarkozy n'a reçu que 500 parrainages.
- `publications` donne, pour chaque date, la décision du Conseil
  constitutionnel qui l'a rendue publique. Chaque présentation porte sa date,
  et non la description entière de sa source : depuis 2017 le Conseil publie
  par vagues, et recopier la décision sur chacune des 3 635 présentations de
  François Fillon pèserait plus que les données.

Ceux qui ont reçu des présentations sans être candidats chez nous — Thomas
PESQUET et Édouard PHILIPPE en 2022 — ne disparaissent pas pour autant : ils
sont réunis dans un document à part, sous l'élection. Les perdre reviendrait à
publier un total faux.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable, Iterator, Mapping
from itertools import takewhile

from candidatheque.pipeline.lecture.parrainages import Parrainage
from candidatheque.pipeline.publication.departements import normaliser as normaliser_departement
from candidatheque.pipeline.publication.departements import ressort_partage
from candidatheque.pipeline.publication.mandats import (
    DEPARTEMENT_IMPLICITE,
    RESSORT_EST_UNE_COLLECTIVITE,
)
from candidatheque.pipeline.publication.mandats import normaliser as normaliser_mandat
from candidatheque.pipeline.seeds import Source
from candidatheque.pipeline.seeds.parrainages import SourceParrainages

#: Un département réduit à un ordinal : c'est le numéro de circonscription d'un
#: député, que le Journal officiel de 2012 a mis entre parenthèses là où il
#: écrit ailleurs le département.
NUMERO_SEUL = re.compile(r"\d{1,2}\s*(?:er|re|ère|ere|ème|eme|e)", re.IGNORECASE)

#: Répertoire des candidats, sous celui d'une élection.
CANDIDATS_DIR = "candidats"
#: Document des parrainages, dans le répertoire d'un candidat.
PARRAINAGES_FILE = "parrainages.json"
#: Document de ceux qui ont reçu des présentations sans être candidats chez
#: nous, sous le répertoire de l'élection.
SANS_CANDIDATURE_FILE = "parrainages-sans-candidature.json"

#: La civilité en tête d'un nom, que le Journal officiel écrit et que le nom
#: publié ne porte pas : elle est une qualité, pas une partie du nom.
CIVILITE_EN_TETE = re.compile(r"^(?:M\.|Mme|Mlle|Monsieur|Madame|Mademoiselle)\s+")


def _est_un_nom_de_famille(mot: str) -> bool:
    """Ce mot est-il tout en capitales, comme les sources écrivent les noms ?

    Deux lettres au moins : « M. » n'est pas un nom, et une initiale isolée ne
    se distingue pas d'une civilité.
    """
    lettres = [
        c
        for c in unicodedata.normalize("NFD", mot)
        if c.isalpha() and not unicodedata.combining(c)
    ]
    return len(lettres) >= 2 and all(c.isupper() for c in lettres)


def nom_a_l_endroit(nom: str) -> str:
    """Un nom remis dans l'ordre du registre : prénom puis nom de famille.

    Les jeux de données du Conseil constitutionnel nomment les candidats
    présentés « PESQUET Thomas », là où tout le reste des données publiées
    écrit « Thomas PESQUET ». La bascule se fait sur la casse, que les sources
    tiennent sans faute : le nom de famille est en capitales, le prénom non.
    C'est le seul repère sûr — « MARECHAL Philippe Célestin » a deux prénoms,
    « KOSCIUSKO-MORIZET Nathalie » un nom composé —, et là où il manque, parce
    que tout est en capitales ou que rien ne l'est, le nom est laissé tel quel
    plutôt que coupé au jugé.
    """
    mots = CIVILITE_EN_TETE.sub("", " ".join(nom.split())).split()
    famille = list(takewhile(_est_un_nom_de_famille, mots))
    if not famille or len(famille) == len(mots):
        return " ".join(mots)
    return " ".join(mots[len(famille) :] + famille)


def _champs_du_depute(brut: str | None, territoire: str | None) -> tuple[str | None, str | None]:
    """Redresse les présentations de députés dont les deux champs sont inversés.

    Le Journal officiel de 2012 écrit « député de la DRÔME (1re) » : la lecture
    range « 1re » dans le département, entre parenthèses, et « la DRÔME » dans
    le ressort. Les deux champs ont donc échangé leur contenu, et les prendre
    pour argent comptant perdrait à la fois le numéro et le département.
    """
    if brut and NUMERO_SEUL.fullmatch(brut.strip()):
        return territoire, brut
    return brut, None


def _presentation_publiee(parrainage: Parrainage, annee: int) -> dict:
    """Une présentation, telle qu'elle est publiée.

    Les champs absents sont omis plutôt que publiés vides. Le Journal officiel
    de 2002 désigne chaque présentateur « par son nom et sa qualité », sans
    prénom, là où celui de 1995 donne les trois : publier un prénom vide
    laisserait croire à une donnée perdue.

    Le nom est publié d'un seul tenant, « Thierry NICOLAS », quelle que soit la
    forme de la source : les jeux de données de 2017 et 2022 séparent le prénom
    du nom, le Journal officiel ne l'a jamais fait, et un consommateur qui lit
    les huit élections ne doit pas avoir à connaître cette histoire. C'est aussi
    la forme qu'ont les noms partout ailleurs dans les données publiées.

    `annee` est celle du scrutin, sans laquelle le département ne se résout
    pas : les numéros ultramarins ont changé de sens en 2007.
    """
    entree: dict = {}
    if parrainage.civilite:
        entree["civilite"] = parrainage.civilite
    entree["nom_complet"] = nom_a_l_endroit(
        f"{parrainage.prenom} {parrainage.nom}" if parrainage.prenom else parrainage.nom
    )

    brut, numero = parrainage.departement, None
    qualite = normaliser_mandat(parrainage.mandat, parrainage.territoire)
    if qualite.mandat == "depute":
        brut, numero = _champs_du_depute(parrainage.departement, parrainage.territoire)
        if numero:
            qualite = normaliser_mandat(parrainage.mandat, numero)
    # Le sénateur est élu dans un département, et c'est là que son ressort va.
    # Treize présentations de 2012 l'écrivent à côté du mandat — « sénateur de
    # PARIS » — quand les 848 autres le mettent où il faut.
    territoire = qualite.territoire
    if qualite.mandat == "senateur" and not brut and normaliser_departement(territoire, annee):
        brut, territoire = territoire, None

    if qualite.mandat:
        entree["mandat"] = qualite.mandat
    # Un ressort à cheval sur deux collectivités n'a pas de code : son nom va au
    # territoire, qui était vide, plutôt que de se perdre.
    territoire = territoire or ressort_partage(brut)
    if territoire:
        entree["territoire"] = territoire
    if qualite.circonscription is not None:
        entree["circonscription"] = qualite.circonscription
    departement = normaliser_departement(brut, annee) or DEPARTEMENT_IMPLICITE.get(qualite.mandat)
    # Un territoire qui tombe sur le même code que le département ne fait que le
    # redire, là où le ressort est une collectivité entière : « Guyane »
    # n'ajoute rien à « 973 », et 35 présentations identiques s'en passent déjà.
    if (
        departement
        and qualite.mandat in RESSORT_EST_UNE_COLLECTIVITE
        and entree.get("territoire")
        and normaliser_departement(entree["territoire"], annee) == departement
    ):
        del entree["territoire"]
    if departement:
        entree["departement"] = departement
    if parrainage.publie_le:
        entree["publie_le"] = parrainage.publie_le.isoformat()
    return entree


def _annee(source: SourceParrainages) -> int:
    """L'année du scrutin, lue dans son identifiant « PR-2012 »."""
    return int(source.election.rsplit("-", 1)[1])


def _publications_publiees(
    source: SourceParrainages, sources: Mapping[str, Source], publiee_par
) -> list[dict]:
    """Les vagues de publication, avec la décision qui a rendu chacune publique."""
    return [
        {"date": publication.date.isoformat()}
        | {"source": publiee_par(sources[publication.source])}
        for publication in source.publications
    ]


def parrainages_du_candidat(
    source: SourceParrainages,
    personne: str,
    nom_complet: str,
    presentations: Iterable[Parrainage],
    sources: Mapping[str, Source],
    publiee_par,
) -> dict:
    """Le document des parrainages d'un candidat.

    Le chemin du schéma remonte de quatre niveaux : le document est sous
    `elections/<ID>/candidats/<PE>/`.
    """
    return {
        "$schema": "../../../../schemas/parrainages.schema.json",
        "election": source.election,
        "personne": personne,
        "nom_complet": nom_complet,
        "etendue": str(source.etendue),
        "publications": _publications_publiees(source, sources, publiee_par),
        "parrainages": [_presentation_publiee(p, _annee(source)) for p in presentations],
    }


def parrainages_sans_candidature(
    source: SourceParrainages,
    beneficiaires: list[dict],
    sources: Mapping[str, Source],
    publiee_par,
) -> dict:
    """Le document de ceux qui ont reçu des présentations sans candidature.

    Le nom est celui du registre quand la personne y figure, et sinon celui de
    la source remis dans l'ordre ; `personne` n'apparaît que pour qui figure au
    registre par ailleurs. François HOLLANDE a reçu des présentations en 2017 et
    en 2022 sans se porter candidat ni l'une ni l'autre fois : il est au
    registre, et son identifiant le dit.
    """
    return {
        "$schema": "../../schemas/parrainages-sans-candidature.schema.json",
        "election": source.election,
        "etendue": str(source.etendue),
        "publications": _publications_publiees(source, sources, publiee_par),
        "beneficiaires": beneficiaires,
    }


def documents(
    source: SourceParrainages,
    lus: Iterable[Parrainage],
    candidatures: set[str],
    noms: Mapping[str, str],
    sources: Mapping[str, Source],
    publiee_par,
) -> Iterator[tuple[str, dict]]:
    """Les documents de parrainages d'une élection, chemin relatif et contenu.

    `candidatures` donne les personnes dont la candidature est connue pour
    cette élection : elles seules ont leur propre répertoire. Les autres vont
    dans le document commun, qu'elles soient au registre ou non.
    """
    par_titre: dict[str, list[Parrainage]] = {}
    for presentation in lus:
        par_titre.setdefault(presentation.candidat, []).append(presentation)

    beneficiaires = []
    for candidat in source.candidats:
        presentations = par_titre.get(candidat.titre, [])
        if candidat.personne and candidat.personne in candidatures:
            yield (
                f"{CANDIDATS_DIR}/{candidat.personne}/{PARRAINAGES_FILE}",
                parrainages_du_candidat(
                    source,
                    candidat.personne,
                    noms[candidat.personne],
                    presentations,
                    sources,
                    publiee_par,
                ),
            )
            continue
        entree: dict = {
            "nom_complet": noms[candidat.personne]
            if candidat.personne
            else nom_a_l_endroit(candidat.titre)
        }
        if candidat.personne:
            entree["personne"] = candidat.personne
        entree["parrainages"] = [_presentation_publiee(p, _annee(source)) for p in presentations]
        beneficiaires.append(entree)

    if beneficiaires:
        yield (
            SANS_CANDIDATURE_FILE,
            parrainages_sans_candidature(source, beneficiaires, sources, publiee_par),
        )
