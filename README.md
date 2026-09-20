<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/Candidatheque/.github/main/assets/logo/candidatheque-logo-sombre.svg">
    <img src="https://raw.githubusercontent.com/Candidatheque/.github/main/assets/logo/candidatheque-logo-clair.svg" alt="Candidathèque" width="360">
  </picture>
</p>

<h1 align="center">Pipeline</h1>

<p align="center">La chaîne de traitement qui collecte, normalise et publie les données de la Candidathèque.</p>

## Organisation

| Répertoire | Régime |
|---|---|
| `seeds/` | Saisi à la main. `elections.yaml` dit quoi publier, `candidatures.yaml` qui s'est présenté, `personnes.yaml` et `sources.yaml` attribuent les identifiants. |
| `schemas/` | Les JSON Schema qui décrivent les données publiées. Écrits à la main, recopiés tels quels dans `data`. |
| `src/` | Le code de la pipeline. |
| `requetes/` | Requêtes SPARQL lancées à la main pour retrouver des identifiants externes. La pipeline ne les exécute pas. |

Les données produites ne sont pas dans ce dépôt : la pipeline les écrit dans le
dépôt `data`, cloné à côté de celui-ci.

## Développement

Python 3.12 ou plus récent, et [uv](https://docs.astral.sh/uv/).

```sh
uv sync --extra dev
uv run candidatheque valider   # relit les seeds
uv run candidatheque lister    # affiche les élections connues
uv run candidatheque publier   # écrit les données dans ../data
uv run pytest -q
```

`publier` vise `../data` par défaut ; `--destination` pointe ailleurs.

## Identifiants

Une élection porte un identifiant de la forme `PR-2012`. `PR` désigne une
élection présidentielle et réserve la place pour d'autres scrutins (législatives,
municipales) sans renommage ultérieur. L'identifiant sert tel quel de nom au
répertoire publié, `elections/PR-2012/`.

## Identifiants de personne

Une personne porte un identifiant de la forme `PE-0001`, attribué dans l'ordre
par `seeds/personnes.yaml` et jamais réattribué. Il est opaque exprès : comme il
ne dit rien, personne n'a jamais de raison de le corriger.

Il suit la personne d'une élection à l'autre, ce qui permet de rapprocher ses
candidatures successives. Le nom, lui, reste dans la candidature : c'est le nom
porté lors de ce scrutin. Une même personne peut donc apparaître sous deux noms
à deux élections, et les deux sont exacts à leur date — un nom d'usage change,
un mariage change un nom. L'identifiant relie, il n'uniformise pas.

Le registre n'est pas publié. Regrouper les candidatures d'une même personne ne
demande que l'identifiant, et le registre n'existe que pour garantir qu'il est
unique.

## Identifiant Wikidata

Chaque élection porte le QID de son élément Wikidata, obligatoire : les douze en
ont un, y compris celle de 2027. Il est publié dans les métadonnées de
l'élection, pas dans l'index, qui ne porte que de quoi énumérer.

La pipeline n'interroge pas Wikidata. Le QID est saisi à la main dans le seed, au
même titre que l'identifiant et l'année ; il n'y a rien à récupérer sur le
scrutin lui-même. `requetes/elections-wikidata.rq` sert à le retrouver quand une
élection s'ajoute, à lancer soi-même sur le service de requête.

Un piège si tu rejoues la requête : la classe interrogée contient aussi les
élections d'avant 1962, au suffrage indirect — 1848, 1947, 1953, 1958 — qui sont
hors périmètre, et `P585` porte une date par tour, donc une élection à deux tours
ressort deux fois sans regroupement.

## Tours

Une élection porte ses tours, numérotés à partir de 1 et dans l'ordre, chacun
avec sa date et, quand il existe, son QID Wikidata.

Il y a eu deux tours à chaque scrutin depuis 1965, mais c'est un constat et non
une règle : une majorité absolue au premier tour rendrait le second inutile. Le
modèle exige au moins un tour et n'en suppose pas le nombre. Ne pas écrire de
code qui tienne les deux tours pour acquis.

Le QID d'un tour est facultatif, et il est absent du JSON plutôt que publié à
`null` : Wikidata ne modélise les tours que pour une partie des scrutins, et
l'absence se lit mieux qu'une valeur nulle. Dix des vingt-quatre tours en ont
un, les autres non.

## Candidatures

Une candidature est à l'élection, pas au tour : on ne se porte pas candidat au
second tour, on s'y qualifie. Le Conseil constitutionnel arrête une liste, une
seule, pour le scrutin. La participation à un tour, elle, se rattache au tour et
porte la ou les sources qui l'établissent.

Le nom publié est celui porté lors de ce scrutin, et il peut différer d'une
élection à l'autre — un nom d'usage change, un mariage change un nom.

Dans le seed, il n'est pas répété : il se déduit du registre des personnes, et
ne se saisit que s'il diffère. L'exception devient ainsi visible au lieu de se
perdre parmi cent quatorze répétitions, et `candidatheque valider` signale un
nom saisi à l'identique. Aucune des candidatures actuelles n'en saisit : dans
les données de 1965 à 2022, personne n'a changé de nom entre deux scrutins.

C'est le même principe que pour les sources : le seed ne répète rien, la
publication développe tout.

L'état d'une candidature est une **trajectoire**, pas un instantané : une suite
d'états datés et sourcés, dans l'ordre. L'état courant est le dernier élément et
n'est pas publié à part — le stocker en double le laisserait diverger.

C'est ce qui permet de représenter une candidature déclarée puis abandonnée, qui
n'a pris part à aucun tour, et de garder qui avait annoncé une candidature
finalement validée. Le champ `tours` peut donc être vide.

```json
"etats": [
  { "etat": "declaree", "date": "2026-05-01", "sources": [...] },
  { "etat": "retiree",  "date": "2026-11-03", "sources": [...] }
],
"tours": []
```

Les 114 candidatures publiées viennent des vingt-deux décisions du Conseil
constitutionnel arrêtant les listes officielles, de 1965 à 2022 — celle du
premier tour, puis celle des candidats habilités au second. Leur trajectoire n'a
donc qu'un seul état, `validee` : rien n'a été collecté sur les déclarations qui
les ont précédées. Les états `declaree`, `retiree` et `ecartee` serviront pour
une élection à venir.

Ces seeds ont été constitués en une fois à partir du fonds CONSTIT, l'open data
du Conseil constitutionnel, puis relus. Chaque participation cite la décision
qui l'établit : la vérification se refait en ouvrant les vingt-deux URL de
`seeds/sources.yaml`.

Ils ont ensuite été recoupés avec Wikidata, dont la propriété `P726` associe des
candidats à une élection. Les deux sources s'accordent exactement : mêmes 75
personnes, mêmes 114 candidatures, aucun écart. Wikidata ne connaît donc aucun
candidat que le Conseil constitutionnel n'aurait pas retenu.

Chaque personne porte son QID Wikidata. C'est le QID qu'on stocke et jamais le
nom : cinq de ces éléments n'ont pas de libellé français, dont ceux de Jacques
Chirac et d'Emmanuel Macron.

## Sources

Partout où une donnée est sourcée, elle l'est de la même façon, décrite par
`schemas/source.schema.json` :

```json
{
  "id": "conseil-constitutionnel:2022-187-PDR",
  "url": "https://www.conseil-constitutionnel.fr/decision/2022/2022187PDR.htm",
  "commentaire": "Liste des candidats à l'élection présidentielle",
  "consultee_le": "2026-09-20"
}
```

L'identifiant est de la forme `<autorité>:<identifiant chez elle>`. Pour le
Conseil constitutionnel, le numéro de décision suivi de sa nature, qui est sa
citation officielle : le numéro seul ne désigne pas une décision unique, 128
numéros du fonds sont portés par plusieurs décisions de natures différentes.

Dans les seeds, une source est décrite une fois dans `sources.yaml` et citée
par son identifiant. À la publication, la pipeline la recopie en clair à côté
de chaque donnée qui s'y rattache : le seed est optimisé pour la maintenance,
les fichiers publiés pour la lecture, et un consommateur n'a jamais de
référence à résoudre.

`consultee_le` est saisie, jamais calculée au moment de publier.

## Données publiées

```
elections.json                        index : une entrée { id, annee } par élection
elections/PR-2012/election.json       métadonnées : identifiant, année, QID, tours
elections/PR-2012/candidatures.json   qui s'est présenté, et à quels tours
schemas/*.schema.json                 copie des schémas de ce dépôt
```

L'index porte de quoi énumérer les élections et atteindre leur répertoire, rien
de plus. Le reste vit dans le répertoire de l'élection, à raison d'un document
par sujet.

Le découpage suit la volatilité, pas le thème. Les résultats d'un scrutin
proclamé ne changeront plus jamais ; les candidatures à une élection à venir
changent toutes les semaines et sont fausses une partie du temps. Réunies dans
un même fichier, la donnée provisoire ferait bouger la donnée définitive à
chaque passage, et personne ne pourrait plus les mettre en cache séparément.
Deux élections n'ont donc pas les mêmes documents, selon leur stade.

Un corollaire qui contraint tout ce qui viendra : **aucun document ne porte de
date de génération**. Les dates publiées viennent des sources, jamais de
l'horloge au moment de publier. Sinon chaque passage produirait un diff et
l'idempotence ne voudrait plus rien dire. C'est la raison d'être du champ
`consultee_le`, lu dans l'archive `raw/`.

De même, rien ne publie d'état dérivé de la date du jour, du genre « élection à
venir » : il deviendrait faux sans qu'aucune source ait bougé. La date du
scrutin est un fait, le consommateur la compare à aujourd'hui.

Les schémas sont recopiés à côté des données pour qu'un commit de `data` se
valide tout seul : un consommateur qui épingle un commit obtient le contrat qui
décrit ces données-là, et non une version qui a continué d'avancer de son côté.
C'est aussi ce qui fait fonctionner les `"$schema"` relatifs des fichiers
produits.

La publication est idempotente. Un fichier au contenu inchangé n'est pas réécrit,
et les répertoires sans entrée correspondante dans le seed sont supprimés. Un
commit dans `data` signifie donc toujours que les données ont bougé.

## Publication automatique

`.github/workflows/publier.yml` publie vers `data` à chaque push sur `main` qui
touche `seeds/`, `schemas/`, `src/` ou `uv.lock`. Le workflow lance les tests,
écrit dans une copie de `data`, et ne commite que si le contenu a changé. Le
message de commit porte le SHA du commit de `pipeline` qui l'a produit : les
commits de `data` sont écrits par une machine, c'est le seul moyen de remonter à
leur cause.

Sur une pull request, le workflow ne pousse rien. Il publie dans une copie jetable
et écrit le diff dans le résumé du run, ce qui permet de relire l'effet d'un
changement de seed avant de le fusionner.

Le push demande une clé de déploiement en écriture sur `data`, attendue dans le
secret `DATA_DEPLOY_KEY` de ce dépôt. Les clés de déploiement doivent être
autorisées au niveau de l'organisation, sinon l'API répond `422 Deploy keys are
disabled for this repository`.

```sh
ssh-keygen -t ed25519 -N "" -C "pipeline vers data" -f /tmp/cle-data
gh repo deploy-key add /tmp/cle-data.pub --repo Candidatheque/data \
  --title "pipeline (publication)" --allow-write
gh secret set DATA_DEPLOY_KEY --repo Candidatheque/pipeline < /tmp/cle-data
rm /tmp/cle-data /tmp/cle-data.pub
```

La lecture de `data` ne demande rien : le dépôt est public, l'aperçu de pull
request s'en passe.

Les actions sont épinglées sur un SHA de commit, avec la version en commentaire.
Un tag `v7` se déplace, un SHA non : c'est ce qui empêche qu'un dépôt d'action
compromis se retrouve exécuté ici avec une clé d'écriture sur `data` à portée.
Pour relever une version, prendre le SHA du tag visé et corriger le commentaire
en même temps :

```sh
gh api /repos/actions/checkout/git/ref/tags/v7.0.1 --jq .object.sha
```

## Limites connues

Les schémas se référencent par chemin relatif et n'ont pas de `$id`. À reprendre
le jour où `data` sera servi sur une URL stable.

Seules les présidentielles sont couvertes, de 1965 à 2027.

`schemas/candidatures.schema.json` n'a pas encore de producteur : il fixe le
contrat que la collecte devra respecter, et les tests en tiennent lieu de
spécification. Il bougera sans doute à la rencontre des vraies sources.

Trois noms ont été corrigés par rapport à la source, qui les orthographie mal :
`LALONIDE` pour LALONDE en 1981, `Ariette` pour Arlette LAGUILLER en 1988, et les
accents absents d'`Émile MULLER` et `Édouard BALLADUR`. Les corrections sont
signalées en commentaire dans `seeds/personnes.yaml`.

Rien ne collecte : les candidatures ont été extraites en une fois et sont
maintenues à la main. Une élection à venir demandera un collecteur.

Il n'y a pas de schéma de résultats. Sa forme doit sortir des décisions du
Conseil constitutionnel, qui ne sont pas encore analysées.

Rien ne relance la publication quand une source externe change : le workflow ne
se déclenche que sur un commit de ce dépôt. Quand la collecte arrivera, il lui
faudra un `schedule`.
