"""Contrôles entre seeds.

Chaque fichier se valide seul, mais les références d'un fichier à l'autre ne se
vérifient qu'ici : une candidature cite une personne, une élection, un tour et
des sources, tous définis ailleurs. Une référence pendante ne casse rien à la
publication, elle produit silencieusement des données fausses — d'où ces
contrôles, lancés par `candidatheque valider`.
"""

from __future__ import annotations

from candidatheque.pipeline.seeds.candidatures import load_candidatures
from candidatheque.pipeline.seeds.elections import load_elections
from candidatheque.pipeline.seeds.personnes import load_personnes
from candidatheque.pipeline.seeds.sources import load_sources


def verifier() -> list[str]:
    """Rend la liste des incohérences trouvées, vide si tout se tient."""
    elections = {election.id: election for election in load_elections()}
    registre = {personne.id: personne for personne in load_personnes()}
    personnes = set(registre)
    sources = {source.id for source in load_sources()}
    candidatures = load_candidatures()

    problemes: list[str] = []
    personnes_citees: set[str] = set()
    sources_citees: set[str] = set()

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
            if personne is not None and (candidat.nom, candidat.prenom) == (
                personne.nom,
                personne.prenom,
            ):
                problemes.append(
                    f"{ou} : nom saisi alors qu'il est identique au registre, à retirer"
                )

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
    for orpheline in sorted(sources - sources_citees):
        problemes.append(f"{orpheline} : source du registre citée par aucune donnée")

    return problemes
