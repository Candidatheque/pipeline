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
| `seeds/` | Saisi à la main. La pipeline itère dessus pour savoir quoi publier. |
| `schemas/` | Les JSON Schema qui décrivent les données publiées. Écrits à la main, recopiés tels quels dans `data`. |
| `src/` | Le code de la pipeline. |

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

## Données publiées

```
elections.json                     index : une entrée { id, annee } par élection
elections/PR-2012/election.json    métadonnées de l'élection
schemas/*.schema.json              copie des schémas de ce dépôt
```

L'index porte de quoi énumérer les élections et atteindre leur répertoire, rien
de plus. Ce qui s'ajoutera ensuite, tours, candidats, résultats, ira dans le
document de l'élection.

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

Seules les présidentielles sont couvertes, de 1965 à 2027, et seuls l'identifiant
et l'année sont publiés.

Rien ne relance la publication quand une source externe change : le workflow ne
se déclenche que sur un commit de ce dépôt. Quand la collecte arrivera, il lui
faudra un `schedule`.
