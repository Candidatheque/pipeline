"""Emplacements des répertoires du dépôt, et du dépôt de destination.

Deux régimes :

- ``seeds/`` est saisi à la main et relu en revue ;
- ``schemas/`` est écrit à la main lui aussi, puis recopié tel quel dans le
  dépôt de destination.

Les données produites ne sont pas dans ce dépôt : la pipeline les écrit dans
``data``, cloné à côté de celui-ci.
"""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]

SEEDS_DIR = REPO_ROOT / "seeds"
SCHEMAS_DIR = REPO_ROOT / "schemas"

ELECTIONS_SEED = SEEDS_DIR / "elections.yaml"
PERSONNES_SEED = SEEDS_DIR / "personnes.yaml"

# Dépôt distinct, cloné à côté de celui-ci. `publier --destination` vise ailleurs.
DATA_REPO = REPO_ROOT.parent / "data"
