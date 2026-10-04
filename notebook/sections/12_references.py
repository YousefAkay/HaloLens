# ---
# jupyter:
#   jupytext:
#     formats: py:percent
# ---

# %% [markdown]
# ## 12. Références
#
# **Entrée :** les fichiers de références de chaque volet (`docs/references/INT.md`, `MSR.md`, `FCT.md`), tenus à jour
# par leur propriétaire, et la configuration `references` de `config/measure.yaml`.
# **Opération :** cette section se compile elle-même : au moment de la construction du notebook, elle lit les trois
# fichiers et les affiche tels quels, un sous-titre par volet. Seules les parties fixes ci-dessous (notebook de départ,
# documents du défi, outils d'IA, confidentialité) sont écrites ici.
# **Pourquoi :** chaque source publique, article ou outil cité n'est écrit qu'à un seul endroit ; un ajout dans le
# fichier d'un volet apparaît ici à la construction suivante, sans modifier cette section.
# **Vérification :** les trois fichiers sont lus et affichés ; un fichier absent ou sans entrée est signalé au lieu
# d'être ignoré. Aucune donnée du CRM n'est lue ici.
#
# ### 12.1 Notebook de départ et documents du défi
# - **Notebook de départ du commanditaire** (`template.ipynb`, project,  2026). Nous en avons repris : les
#   conventions de lecture des colonnes (champs `h` = identifiants, champs `s` = valeurs, codes de frais des
#   concessions), les cellules de chargement des quatre fichiers CSV, les pistes de méthode (comparer une unité à
#   elle-même, loyer contractuel vs loyer net, renouvellements vs relocations, bornes d'écart entre deux baux proposées au départ) et
#   les signatures `estimate_2026(leases, asking, external=None)` et `backtest(leases, target_year)`. Le code d'analyse
#   lui-même a été réécrit dans le paquet `leaselens`.
# - **Documents du défi** : l'énoncé et les instructions de project pour la the portfolio (`instructions.pdf`), la
#   présentation du défi (`presentation-project.pdf`) et les quatre extraits CSV fournis par le commanditaire, utilisés sans modification (empreintes SHA-256 vérifiées au
#   chargement, section 2). Ces fichiers ne sont pas publiés.
#
# ### 12.2 Outils d'IA
# - **Claude (clavardage, projet HALO)** : planification des tâches, rédaction des instructions de travail et revue des
#   rapports de fin de tâche.
# - **Claude Code** : implémentation du code, des tests et des sections du notebook dans le dépôt local ; chaque
#   changement a été relu par un humain avant fusion.
# - **API Claude** : (1) extraction de valeurs à partir de **pages publiques** (TAL, gouvernement de l'Ontario, SCHL),
#   chaque valeur étant ensuite vérifiée à la main contre sa page officielle avant d'entrer dans
#   `data/public/sources.csv` ; (2) récit du tableau de bord, produit à partir d'un JSON d'**agrégats** seulement et
#   contrôlé par un garde-fou qui rejette tout nombre absent de ce JSON.
#
# Les modèles exacts et les détails d'usage par volet figurent dans les fichiers de références ci-dessous.

# %%
from pathlib import Path

from IPython.display import Markdown, display

from leaselens.measure.labels import french_date, track_references_markdown

references_cfg = cfg["references"]
FIRST_TRACK_SUBSECTION = 4  # 12.1 to 12.3 are the fixed parts above
approval_label = french_date(references_cfg["sponsor_approval_date"])

# %% [markdown]
# ### 12.3 Confidentialité des données du CRM

# %%
display(Markdown(
    "**Aucune donnée du CRM n'a été envoyée à une API.** L'API Claude n'a reçu que des pages publiques (extraction "
    "des sources) et un JSON d'agrégats (récit du tableau de bord) : aucune ligne de bail, aucun code de logement, "
    "aucune valeur `hUnit`. Les sessions Claude Code ont travaillé sur les fichiers réels dans le dépôt local, avec "
    f"l'approbation du commanditaire et du mentor ({approval_label}), en n'affichant que des comptes et des agrégats. "
    "Les fichiers du CRM restent dans `data/private/` (exclu de Git) et ne font partie d'aucun livrable."))

# %% [markdown]
# ### Sources, articles et outils par volet
# Étape qui lit des fichiers (sans transformer de données) : chaque fichier `docs/references/<VOLET>.md` est lu et
# affiché dans l'ordre fixé par la configuration. Son titre et la consigne d'édition en tête de fichier sont retirés,
# ses intertitres sont décalés sous le sous-titre du volet ; le texte des entrées est affiché tel qu'écrit par le volet
# (souvent en anglais, avec les URL et les dates de publication d'origine).

# %%
references_dir = Path(cfg["_root"]) / references_cfg["dir"]
for number, (track, title) in enumerate(references_cfg["tracks"].items(), start=FIRST_TRACK_SUBSECTION):
    path = references_dir / f"{track}.md"
    if not path.exists():
        body = f"_Fichier `{path.name}` introuvable : aucune référence affichée pour ce volet._"
    else:
        body = track_references_markdown(path.read_text(encoding="utf-8"), references_cfg["boilerplate"],
                                         references_cfg["heading_shift"])
        body = body or "_Aucune entrée pour l'instant._"
    display(Markdown(f"### 12.{number} {title} ({track})\n\n{body}"))
