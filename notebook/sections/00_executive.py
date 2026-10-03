# ---
# jupyter:
#   jupytext:
#     formats: py:percent
# ---

# %% [markdown]
# # Hausse de loyer 2026 — the portfolio
#
# _Résumé exécutif complété à la fin (I-13) à partir des résultats calculés : hausse 2026, définition,
# compagnons (loyer contractuel, médianes), plage de scénarios et erreurs de backtest._
#
# Ce notebook est dérivé du notebook de départ fourni par project (`template.ipynb`).

# %% [markdown]
# ### Configuration commune
# Toutes les sections suivantes utilisent les objets créés ici : `cfg` (configuration), `raw` (tables sources,
# noms originaux), `tables` (tables renommées et typées) et `external` (données publiques).
# Le mode (`synthetic` ou `real`) est fixé dans `config/core.yaml`.

# %%
import warnings

import matplotlib.pyplot as plt
import pandas as pd
from IPython.display import Markdown, display

from leaselens.config import data_dir, load_config
from leaselens.io import canonicalize, column_mapping, load_raw, run_qa

warnings.filterwarnings("ignore", category=FutureWarning)
pd.set_option("display.width", 160)

cfg = load_config()
raw = load_raw(data_dir(cfg))        # vérifie les empreintes SHA-256 du manifeste avant de lire
tables = canonicalize(raw)
external = None                      # chargé en section 7 (MSR) via market.registry.load_external
display(Markdown(f"Mode des données : **{cfg['data']['mode']}**"))
