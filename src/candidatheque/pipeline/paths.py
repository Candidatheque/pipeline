"""Emplacements des répertoires du dépôt, et du dépôt de destination.

Deux régimes :

- ``seeds/`` est saisi à la main et relu en revue ;
- ``schemas/`` est écrit à la main lui aussi, puis recopié tel quel dans le
  dépôt de destination ;
- ``raw/`` porte les fichiers sources tels que leur éditeur les publie. Ils y
  sont commités et jamais téléchargés : ces documents sont figés, et un fichier
  suivi par git s'archive mieux qu'une copie reconstruite à chaque passage.

Les données produites ne sont pas dans ce dépôt : la pipeline les écrit dans
``data``, cloné à côté de celui-ci.
"""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]

SEEDS_DIR = REPO_ROOT / "seeds"
SCHEMAS_DIR = REPO_ROOT / "schemas"
#: Les fichiers sources, commités tels que leur éditeur les publie.
RAW_DIR = REPO_ROOT / "raw"

ELECTIONS_SEED = SEEDS_DIR / "elections.yaml"
PERSONNES_SEED = SEEDS_DIR / "personnes.yaml"
SOURCES_SEED = SEEDS_DIR / "sources.yaml"
AUTORITES_SEED = SEEDS_DIR / "autorites.yaml"
PARTIS_SEED = SEEDS_DIR / "partis.yaml"
CANDIDATURES_SEED = SEEDS_DIR / "candidatures.yaml"
PARRAINAGES_SEED = SEEDS_DIR / "parrainages.yaml"
RESULTATS_SEED = SEEDS_DIR / "resultats.yaml"
#: Table de référence, jamais publiée : elle sert à normaliser ce que les
#: sources écrivent du département.
DEPARTEMENTS_SEED = SEEDS_DIR / "departements.yaml"

# Dépôt distinct, cloné à côté de celui-ci. `publier --destination` vise ailleurs.
DATA_REPO = REPO_ROOT.parent / "data"
