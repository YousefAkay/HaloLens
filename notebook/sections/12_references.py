# ---
# jupyter:
#   jupytext:
#     formats: py:percent
# ---

# %% [markdown]
# ## 12. Références
#
# **Entrée :** le fichier `docs/references.md` et la configuration `references` de `config/measure.yaml`.
# **Opération :** cette section se compile elle-même : au moment de la construction du notebook, elle lit le fichier
# et l'affiche tel quel. Seules les parties fixes ci-dessous (outils d'IA, confidentialité) sont écrites ici.
# **Pourquoi :** chaque source publique, article ou outil cité n'est écrit qu'à un seul endroit ; un ajout dans le
# fichier apparaît ici à la construction suivante, sans modifier cette section.
# **Vérification :** le fichier est lu et affiché ; un fichier absent est signalé au lieu d'être ignoré. Aucune donnée
# de baux n'est lue ici.
#
# ### 12.1 Outils d'IA
# - **Claude (clavardage)** : planification des tâches et revue des résultats.
# - **Claude Code** : implémentation du code, des tests et des sections du notebook ; chaque changement a été relu par
#   un humain avant fusion.
# - **API Claude** : (1) extraction de valeurs à partir de **pages publiques**, chaque valeur étant ensuite contrôlée
#   contre sa page officielle par Claude, puis un humain a vérifié un échantillon nommé (toutes les valeurs n'ont pas
#   été vérifiées à la main) avant leur entrée dans `data/public/sources.csv` ; (2) veille des sources
#   (`scripts/extract_sources.py --watch`, pages publiques seulement) : les nouvelles valeurs détectées attendent une
#   vérification humaine et n'entrent jamais seules dans la prévision ; (3) copilote de scénarios et
#   questions-réponses du tableau de bord, à partir des **résultats agrégés** seulement et contrôlés par un garde-fou
#   qui rejette tout nombre absent de ces résultats.

# %% [markdown]
# ### 12.2 Confidentialité des données

# %%
from pathlib import Path

from IPython.display import Markdown, display

from halolens.measure.labels import track_references_markdown

references_cfg = cfg["references"]
display(Markdown(
    "**Aucune ligne de bail n'a été envoyée à une API.** L'API Claude n'a reçu que des pages publiques (extraction "
    "et veille des sources) et des résultats agrégés (copilote et questions-réponses du tableau de bord) : aucune ligne "
    "de bail, aucun code de logement, aucun identifiant d'unité. Les données privées restent dans `data/private/` "
    "(exclu de Git) et ne font partie d'aucun livrable."))

# %% [markdown]
# ### 12.3 Sources, articles et outils
# Étape qui lit un fichier (sans transformer de données) : `docs/references.md` est lu et affiché. Son titre est
# retiré et ses intertitres sont décalés sous ce sous-titre ; le texte des entrées est affiché tel qu'écrit (en
# anglais, avec les URL d'origine).

# %%
references_path = Path(cfg["_root"]) / references_cfg["file"]
if not references_path.exists():
    body = f"_Fichier `{references_path.name}` introuvable : aucune référence affichée._"
else:
    body = track_references_markdown(references_path.read_text(encoding="utf-8"), references_cfg["boilerplate"],
                                     references_cfg["heading_shift"])
    body = body or "_Aucune entrée pour l'instant._"
display(Markdown(body))
