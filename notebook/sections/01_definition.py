# ---
# jupyter:
#   jupytext:
#     formats: py:percent
# ---

# %% [markdown]
# ## 1. Définition de la hausse mesurée
#
# **Entrée :** les baux consécutifs de chaque unité (paires, AGENTS.md §9.2) et la configuration commune (section 00).
# **Opération :** énoncer la mesure retenue avant tout calcul de résultat : ce qui est mesuré, sur quelle population, sur quel horizon, avec quelle pondération et avec quels compagnons.
# **Pourquoi :** une hausse « moyenne » ne se lit pas sans définition : le même chiffre peut venir d'un changement de loyer ou d'un changement de logements loués. La définition est fixée d'avance (AGENTS.md §9.1) pour que tous les résultats suivants lui soient comparables.
# **Vérification :** les paramètres affichés ci-dessous sont lus dans `config/`. Cette section ne calcule aucun résultat et n'affiche aucun chiffre de données.

# %% [markdown]
# ### 1.1 Énoncé et calcul
# Les paramètres (années, quantiles, écarts, fenêtres) sont lus dans la configuration. Les valeurs ci-dessous sont donc celles du fichier `config/`, et non des saisies manuelles.

# %%
from IPython.display import Markdown, display

from leaselens.config import cutoff_for

target_year = cfg["forecast_years"]["target_year"]
cutoff = cutoff_for(target_year, cfg).date().isoformat()
lower_pct = cfg["winsorize"]["lower_quantile"] * 100
upper_pct = cfg["winsorize"]["upper_quantile"] * 100
weight_years = cfg["headline"]["weight_window_years"]
segment_text = " × ".join(cfg["headline"]["segment_keys"])

display(Markdown(f"""
**Hausse mesurée :** croissance **à composition fixe** et **à unité constante** du loyer **net de toutes concessions** (`{cfg['headline']['price_column']}`), pour l'année **{target_year}**.

1. **Paires :** pour chaque paire éligible (deux baux consécutifs d'une même unité), croissance logarithmique annualisée : `ln(P_i / P_(i−1)) / durée en années`, où P est le loyer net.
2. **Écrêtage :** les croissances sont écrêtées aux quantiles {lower_pct:g} % et {upper_pct:g} %. Les seuils sont appris sur les données d'entraînement seulement.
3. **Segments :** `{segment_text}`. Pour chaque segment s, on calcule la moyenne `mean_s` des croissances.
4. **Agrégation :** hausse en % = `100 × (exp(Σ w_s × mean_s) − 1)`, où `w_s` est la part du segment dans les paires éligibles des **{weight_years} années** précédant la coupure. Les poids sont figés à la date de coupure.
"""))

# %% [markdown]
# ### 1.2 Population, horizon et coupure
# **Entrée :** les baux de la section 00 et les publications externes. **Opération :** fixer qui est compté, à quelle année chaque observation appartient, et quelle information est permise à la date de coupure.
# **Pourquoi :** une prévision faite à la coupure ne doit utiliser que ce qui était connu à cette date (AGENTS.md §9.3). **Vérification :** le tableau des paramètres ci-dessous confirme les valeurs lues.

# %%
display(Markdown(f"""
**Population :** paires éligibles.
- Même unité, identifiée par la clé `{' + '.join(cfg['pairs']['unit_key'])}` (jamais `sSite + sUnitCode`), avec contrôle croisé par `{cfg['pairs']['cross_check_key']}`.
- Baux consécutifs par date de début ; écart entre **{cfg['pairs']['min_gap_years']}** et **{cfg['pairs']['max_gap_years']}** ans ; loyers positifs. Chaque exclusion garde son motif.
- Une paire appartient à l'année de la date de début du bail le plus récent.

**Horizon :** année cible **{target_year}**, date de coupure **{cutoff}**. L'entraînement n'utilise que les baux dont la signature **et** le début sont antérieurs ou égaux à la coupure. Les publications externes sont retenues seulement si leur date de publication est antérieure ou égale à la coupure.
"""))

# %% [markdown]
# ### 1.3 Compagnons, pourquoi cette mesure, limites
# **Entrée :** la définition ci-dessus. **Opération :** rappeler les compagnons obligatoires, la justification de la moyenne logarithmique et les limites d'interprétation.
# **Pourquoi :** une hausse isolée peut être mal lue ; les compagnons et les limites la situent. **Vérification :** les noms de colonnes et les paramètres sont lus dans la configuration.

# %%
companion = cfg["headline"]["companion_price_column"]
display(Markdown(f"""
**Compagnons (toujours présentés à côté) :** le même calcul sur le loyer contractuel (`{companion}`), et les médianes des deux loyers. La médiane est un contrôle de robustesse, pas la mesure principale.

**Pourquoi la moyenne logarithmique :** les prévisions par segment s'agrègent exactement, et le pont de composition (contractuel vers net) est exactement additif. Pourquoi l'unité constante : une médiane annuelle des loyers signés mélange un changement de loyer et un changement de logements loués ; comparer la même unité avant et après isole le premier.

**Limites d'interprétation :**
- Les poids décrivent le mélange des transitions de baux observées. Ils ne mesurent ni l'occupation, ni la vacance, ni la rotation du portefeuille.
- Le loyer net est ajusté des concessions. Ce n'est pas un montant encaissé.
- Trois années de backtest soutiennent des conclusions prudentes : les plages de scénarios sont des scénarios, et non des intervalles de prédiction.
"""))

# %%
params = [
    ("Année cible", target_year),
    ("Date de coupure", cutoff),
    ("Années de backtest", ", ".join(str(year) for year in cfg["forecast_years"]["backtest_years"])),
    ("Écart minimal entre baux (ans)", cfg["pairs"]["min_gap_years"]),
    ("Écart maximal entre baux (ans)", cfg["pairs"]["max_gap_years"]),
    ("Quantiles d'écrêtage (bas / haut)", f"{cfg['winsorize']['lower_quantile']} / {cfg['winsorize']['upper_quantile']}"),
    ("Fenêtre des poids (ans)", weight_years),
    ("Colonne de loyer (mesure)", cfg["headline"]["price_column"]),
    ("Colonne de loyer (compagnon)", companion),
    ("Clés de segment", segment_text),
    ("Clé d'appariement", " + ".join(cfg["pairs"]["unit_key"])),
    ("Graine aléatoire", cfg["random_seed"]),
]
table_rows = "\n".join(f"| {label} | {value} |" for label, value in params)
display(Markdown("| Paramètre | Valeur |\n|---|---|\n" + table_rows))
