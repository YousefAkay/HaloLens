# ---
# jupyter:
#   jupytext:
#     formats: py:percent
# ---

# %% [markdown]
# ## 9. Backtest 2023–2025
#
# **Objectif :** valider chaque modèle en prévoyant, avec les seules informations connues à la coupure, des années dont
# on connaît le résultat, puis appliquer la règle de choix annoncée en section 8.
#
# **Entrée :** `tables`, `external`, `cfg`. **Opération :** pour chaque année cible (2023, 2024, 2025) et chaque modèle,
# un instantané coupé au 31 décembre précédent (données publiques au 31 janvier de l'année cible, ou au 31 décembre pour la
# sensibilité stricte) alimente le modèle ; la prévision est comparée au réalisé, calculé avec la même définition et les mêmes
# poids fixes. **Pourquoi :** un modèle qui ne se valide pas sur le passé n'a pas de crédibilité pour 2026.
# **Vérification :** erreur = prévision − réalisé, en points de pourcentage (pp), pour le loyer net et le loyer contractuel,
# pour **tous** les modèles, y compris ceux qui perdent.

# %%
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from leaselens.evaluate.backtest import backtest_both_rules, select_champion, summarize_models
from leaselens.market.registry import load_external

if external is None:
    external = load_external(Path(cfg["_root"]) / cfg["data"]["public_dir"] / cfg["external"]["sources_file"])

# %%
backtest_all = backtest_both_rules(tables, external, cfg)
columns = ["model", "year", "forecast_net_pct", "actual_net_pct", "error_pp_net", "forecast_contract_pct",
           "actual_contract_pct", "error_pp_contract"]
for rule, label in (("jan31", "règle retenue : données publiques au 31 janvier"),
                    ("dec31_strict", "sensibilité : données publiques au 31 décembre")):
    block = backtest_all[backtest_all["rule"] == rule]
    if block.empty:
        continue
    display(Markdown(f"**Backtest — {label}** (pourcentages ; erreurs en pp = prévision − réalisé)"))
    display(block[columns].rename(columns={
        "model": "modèle", "year": "année", "forecast_net_pct": "prévu net %", "actual_net_pct": "réalisé net %",
        "error_pp_net": "erreur net pp", "forecast_contract_pct": "prévu contrat %",
        "actual_contract_pct": "réalisé contrat %", "error_pp_contract": "erreur contrat pp"}).round(2).reset_index(drop=True))
    failed = block[block["note"] != ""][["model", "year", "note"]]
    if len(failed):
        display(Markdown("Prévisions impossibles (raison indiquée, jamais masquées) :"))
        display(failed.reset_index(drop=True))

# %% [markdown]
# ### 9.1 Erreur absolue moyenne et choix du modèle
#
# **Opération :** erreur absolue moyenne (EAM) du loyer net sur les années de sélection, sur l'année de validation et sur
# toutes les années, pour chaque règle. Le champion est choisi par la règle déclarée à l'avance : EAM la plus faible sur
# 2023–2024, règle du 31 janvier.

# %%
summary = summarize_models(backtest_all, cfg).rename(columns={
    "rule": "règle", "model": "modèle", "mae_selection_pp": "EAM sélection (2023–24) pp",
    "mae_holdout_pp": "EAM validation (2025) pp", "mae_all_pp": "EAM toutes années pp", "n_folds_run": "années calculées"})
display(summary.round(2))
chosen = select_champion(backtest_all, cfg)
champion = chosen["champion"]
display(Markdown(f"**Modèle retenu par la règle déclarée : {champion}**"))
display(chosen["ranking"].round(2).rename(columns={
    "model": "modèle", "mae_selection_pp": "EAM sélection pp", "n_selection_folds_run": "années de sélection calculées",
    "eligible": "admissible", "mae_holdout_pp": "EAM validation pp"}))

# %%
ranking = chosen["ranking"]
top_three = ranking[ranking["eligible"]].head(3)
spread_top_three = float(top_three["mae_selection_pp"].max() - top_three["mae_selection_pp"].min())
best_holdout = ranking.loc[ranking["mae_holdout_pp"].idxmin()]
selection_years = chosen["selection_years"]
display(Markdown(
    f"**Lecture honnête du classement.** La règle de choix a été déclarée **avant** de voir les résultats. B3 et E2 ont été "
    f"ajoutés **après** le premier backtest réel (tâche F-05b), à cause de la structure réglementaire du TAL et de l'Ontario ; "
    f"ils sont soumis à la même règle et ne la modifient pas. Avec seulement **{len(selection_years)} années de sélection**, "
    f"le classement des trois premiers modèles ({', '.join(top_three['model'])}) tient dans **{spread_top_three:.2f} point de "
    f"pourcentage** : il est statistiquement faible. **{best_holdout['model']}** a la meilleure erreur sur la validation "
    f"{chosen['holdout_year']} (**{best_holdout['mae_holdout_pp']:.2f} pp**), mais {chosen['holdout_year']} n'a pas servi à "
    f"choisir : le modèle retenu reste **{champion}**."))

# %% [markdown]
# ### 9.2 Erreurs du loyer net par modèle et par année
#
# **Opération :** graphique des erreurs signées (prévision − réalisé) du loyer net. Une barre au-dessus de zéro est une
# surestimation. Les deux panneaux montrent la règle retenue et la sensibilité stricte ; seuls les modèles qui utilisent des
# données publiques (B2, B3, E2) diffèrent d'un panneau à l'autre.

# %%
palette = ["#0072B2", "#E69F00", "#009E73", "#CC79A7", "#56B4E9", "#D55E00"]   # Okabe-Ito, un modèle par couleur
rules_shown = [rule for rule in ("jan31", "dec31_strict") if (backtest_all["rule"] == rule).any()]
fig, axes = plt.subplots(1, len(rules_shown), figsize=(5.5 * len(rules_shown), 3.8), sharey=True, squeeze=False)
model_names = list(dict.fromkeys(backtest_all["model"]))
years = sorted(backtest_all["year"].unique())
bar_width = 0.8 / len(model_names)
for axis, rule in zip(axes[0], rules_shown):
    block = backtest_all[backtest_all["rule"] == rule]
    for index, name in enumerate(model_names):
        values = block[block["model"] == name].set_index("year")["error_pp_net"].reindex(years)
        positions = [position + (index - (len(model_names) - 1) / 2) * bar_width for position in range(len(years))]
        # a model that could not run has no bar (never a false zero)
        axis.bar(positions, values, width=bar_width, color=palette[index % len(palette)],
                 label=name if rule == rules_shown[0] else None)
    axis.axhline(0, color="black", linewidth=0.8)
    axis.set_xticks(range(len(years)))
    axis.set_xticklabels(years)
    axis.set_title("Règle du 31 janvier (retenue)" if rule == "jan31" else "Sensibilité : 31 décembre")
    axis.set_xlabel("Année cible")
axes[0][0].set_ylabel("Erreur du loyer net (pp)")
fig.legend(loc="lower center", ncol=3, fontsize=8, frameon=False)
fig.tight_layout(rect=(0, 0.12, 1, 1))
plt.show()
