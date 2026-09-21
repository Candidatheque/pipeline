"""Contrôles entre seeds.

Chaque fichier se valide seul, mais les références d'un fichier à l'autre ne se
vérifient qu'ici : une candidature cite une personne, une élection, un tour, un
parti et des sources, tous définis ailleurs. Une référence pendante ne casse rien à la
publication, elle produit silencieusement des données fausses — d'où ces
contrôles, lancés par `candidatheque valider`.
"""

from __future__ import annotations

from candidatheque.pipeline.lecture.parrainages import lire
from candidatheque.pipeline.seeds.autorites import load_autorites
from candidatheque.pipeline.seeds.candidatures import load_candidatures
from candidatheque.pipeline.seeds.elections import load_elections
from candidatheque.pipeline.seeds.parrainages import load_parrainages
from candidatheque.pipeline.seeds.partis import load_partis
from candidatheque.pipeline.seeds.personnes import load_personnes
from candidatheque.pipeline.seeds.resultats import load_resultats
from candidatheque.pipeline.seeds.sources import load_sources


def verifier() -> list[str]:
    """Rend la liste des incohérences trouvées, vide si tout se tient."""
    elections = {election.id: election for election in load_elections()}
    registre = {personne.id: personne for personne in load_personnes()}
    personnes = set(registre)
    sources = {source.id: source for source in load_sources()}
    autorites = {autorite.id: autorite for autorite in load_autorites()}
    partis = {parti.id for parti in load_partis()}
    candidatures = load_candidatures()
    sources_parrainages = load_parrainages()
    sources_resultats = load_resultats()

    problemes: list[str] = []

    # Une source ne peut relever que d'une autorité listée, et son URL doit
    # être servie par un de ses domaines. Sans ce second contrôle, une source
    # pourrait se réclamer d'une autorité en pointant ailleurs.
    for source in sources.values():
        autorite = autorites.get(source.autorite)
        if autorite is None:
            problemes.append(
                f"{source.id} : autorité « {source.autorite} » absente de la liste de confiance"
            )
        elif not autorite.sert(source.url):
            problemes.append(
                f"{source.id} : l'URL n'est pas servie par {autorite.nom} ({source.url})"
            )

    personnes_citees: set[str] = set()
    sources_citees: set[str] = set()
    partis_cites: set[str] = set()

    for entree in candidatures:
        election = elections.get(entree.election)
        if election is None:
            problemes.append(f"{entree.election} : élection inconnue du seed des élections")
            continue

        tours_connus = {tour.numero for tour in election.tours}
        for candidat in entree.candidats:
            ou = f"{entree.election}/{candidat.personne}"
            if candidat.personne not in personnes:
                problemes.append(f"{ou} : personne absente du registre")
            personnes_citees.add(candidat.personne)

            # Le nom ne se saisit que s'il diffère de celui du registre. Le
            # saisir à l'identique noie l'exception — une personne qui a
            # réellement changé de nom — dans des répétitions.
            personne = registre.get(candidat.personne)
            if personne is not None and candidat.nom_complet == personne.nom_complet:
                problemes.append(
                    f"{ou} : nom saisi alors qu'il est identique au registre, à retirer"
                )

            for changement in candidat.etats:
                for identifiant in changement.sources:
                    if identifiant not in sources:
                        problemes.append(
                            f"{ou}/{changement.etat} : source inconnue « {identifiant} »"
                        )
                    sources_citees.add(identifiant)

            for affiliation in candidat.partis:
                if affiliation.parti not in partis:
                    problemes.append(
                        f"{ou} : parti « {affiliation.parti} » absent du registre"
                    )
                partis_cites.add(affiliation.parti)
                for identifiant in affiliation.sources:
                    if identifiant not in sources:
                        problemes.append(
                            f"{ou}/{affiliation.parti} : source inconnue « {identifiant} »"
                        )
                    sources_citees.add(identifiant)

            for participation in candidat.tours:
                if participation.numero not in tours_connus:
                    problemes.append(
                        f"{ou} : tour {participation.numero} inexistant pour cette élection "
                        f"(tours connus : {sorted(tours_connus)})"
                    )
                for identifiant in participation.sources:
                    if identifiant not in sources:
                        problemes.append(
                            f"{ou}/T{participation.numero} : source inconnue « {identifiant} »"
                        )
                    sources_citees.add(identifiant)

    # Une entrée que plus rien ne cite est du bruit qui finira par induire en
    # erreur : mieux vaut la retirer ou comprendre pourquoi elle est orpheline.
    for orpheline in sorted(personnes - personnes_citees):
        problemes.append(f"{orpheline} : personne du registre citée par aucune candidature")
    # Les parrainages citent leurs sources depuis leur propre seed, et leur
    # fichier doit exister : une déclaration qui pointe vers rien produirait une
    # publication muette, sans erreur.
    for entree in sources_parrainages:
        if entree.election not in elections:
            problemes.append(f"{entree.election} : élection inconnue du seed des élections")
        if not entree.chemin().is_file():
            problemes.append(f"{entree.election} : fichier absent, {entree.fichier}")
        if entree.origine not in sources:
            problemes.append(f"{entree.election} : origine inconnue « {entree.origine} »")
        sources_citees.add(entree.origine)
        for publication in entree.publications:
            if publication.source not in sources:
                problemes.append(
                    f"{entree.election}/{publication.date} : "
                    f"source inconnue « {publication.source} »"
                )
            sources_citees.add(publication.source)
        for candidat in entree.candidats:
            if candidat.personne is not None and candidat.personne not in personnes:
                problemes.append(
                    f"{entree.election} : « {candidat.titre} » renvoie à "
                    f"{candidat.personne}, absent du registre des personnes"
                )
        # Le seed doit nommer exactement les candidats que porte le fichier.
        # Un titre oublié, c'est une liste entière qui disparaît sans bruit ;
        # un titre en trop, une déclaration qui ne correspond plus à la source.
        if entree.chemin().is_file():
            portes = {parrainage.candidat for parrainage in lire(entree)}
            declares = {candidat.titre for candidat in entree.candidats}
            for absent in sorted(portes - declares):
                problemes.append(f"{entree.election} : « {absent} » porté par la source, non déclaré")
            for surnumeraire in sorted(declares - portes):
                problemes.append(
                    f"{entree.election} : « {surnumeraire} » déclaré, absent de la source"
                )

    # Les résultats d'un tour citent la décision qui les proclame, et les
    # candidats que cette décision nomme. Ceux-ci doivent être exactement les
    # participants déclarés au tour : un candidat oublié ici, ce sont ses voix
    # qui manqueraient au total sans que rien ne le signale.
    participants = {
        (entree.election, participation.numero): {
            candidat.personne
            for candidat in entree.candidats
            for participation_ in candidat.tours
            if participation_.numero == participation.numero
        }
        for entree in candidatures
        for candidat in entree.candidats
        for participation in candidat.tours
    }
    for entree in sources_resultats:
        election = elections.get(entree.election)
        if election is None:
            problemes.append(f"{entree.election} : élection inconnue du seed des élections")
            continue
        tours_connus = {tour.numero for tour in election.tours}
        for tour in entree.tours:
            ou = f"{entree.election}/T{tour.numero}"
            if tour.numero not in tours_connus:
                problemes.append(
                    f"{ou} : tour inexistant pour cette élection "
                    f"(tours connus : {sorted(tours_connus)})"
                )
            if not tour.chemin().is_file():
                problemes.append(f"{ou} : fichier absent, {tour.fichier}")
            if tour.origine not in sources:
                problemes.append(f"{ou} : origine inconnue « {tour.origine} »")
            sources_citees.add(tour.origine)

            declares = {candidat.personne for candidat in tour.candidats}
            for inconnue in sorted(declares - personnes):
                problemes.append(f"{ou} : {inconnue} absent du registre des personnes")
            attendus = participants.get((entree.election, tour.numero), set())
            for absent in sorted(attendus - declares):
                problemes.append(f"{ou} : {absent} a participé au tour, sans ligne de voix")
            for surnumeraire in sorted(declares - attendus - (declares - personnes)):
                problemes.append(
                    f"{ou} : {surnumeraire} porte des voix, sans candidature à ce tour"
                )

    for orpheline in sorted(partis - partis_cites):
        problemes.append(f"{orpheline} : parti du registre cité par aucune candidature")
    for orpheline in sorted(set(sources) - sources_citees):
        problemes.append(f"{orpheline} : source du registre citée par aucune donnée")

    return problemes
