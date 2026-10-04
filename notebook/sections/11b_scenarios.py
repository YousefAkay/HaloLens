# ---
# jupyter:
#   jupytext:
#     formats: py:percent
# ---

# %% [markdown]
# ## 11b. Scénarios 2026
#
# **Objectif :** montrer comment la hausse nette 2026 varie quand on déplace, un à la fois puis ensemble, trois leviers
# incertains : l'intensité des concessions, la part des renouvellements et l'application de la ligne directrice ontarienne à
# the Ontario new-build.
#
# **Entrée :** `tables`, `external`, `cfg`. **Opération :** le moteur réglementé E2 (renouvellements québécois ancrés sur le TAL)
# est recalculé pour 2026 ; chaque levier est appliqué aux prévisions par segment, puis les segments sont agrégés avec les
# mêmes poids fixes. **Pourquoi :** la hausse retenue est une valeur centrale ; les scénarios montrent ce qui la ferait bouger.
# **Important :** ce sont des **scénarios**, pas des intervalles de prédiction : trois années de backtest ne permettent pas
# de calibrer une probabilité.

# %%
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from leaselens.evaluate.backtest import headline_table
from leaselens.forecast.asof import snapshot_for_year
from leaselens.forecast.combine import forecast_regulated
from leaselens.forecast.scenarios import scenario_table
from leaselens.market.registry import load_external

if external is None:
    external = load_external(Path(cfg["_root"]) / cfg["data"]["public_dir"] / cfg["external"]["sources_file"])
target_year = cfg["forecast_years"]["target_year"]
levers = cfg["scenarios"]

# %% [markdown]
# ### 11b.1 Les leviers
#
# - **Intensité des concessions** : on déplace de ± `incentive_intensity_shift_pp` point la part de rabais prévue de chaque
#   segment (les concessions ont gagné 2 à 3 points de loyer par an ces deux dernières années).
# - **Part des renouvellements** : on déplace de ± `renewal_share_shift_pp` point la part des renouvellements dans les poids
#   fixes (ordre de grandeur des variations annuelles observées).
# - **the Ontario new-build** : au scénario central, l'exemption des premières occupations après le 15 novembre 2018 est jugée plausible
#   (immeuble loué pour la première fois en 2023) ; au scénario alternatif, la ligne directrice ontarienne s'applique.
#   Ce n'est pas une détermination juridique.

# %%
display(Markdown(
    f"Leviers retenus : concessions ± **{levers['incentive_intensity_shift_pp']:.1f} pp**, part des renouvellements ± "
    f"**{levers['renewal_share_shift_pp']:.1f} pp**, the Ontario new-build : ligne directrice {'et exemption' if len(levers['met_guideline_applies']) > 1 else ''} "
    f"(valeurs de `config/forecast.yaml`)."))

# %% [markdown]
# ### 11b.2 Tableau des scénarios
#
# **Opération :** scénario central, chaque levier seul, puis **bas** et **haut** = minimum et maximum de la hausse nette sur
# toutes les combinaisons de leviers. `delta` est l'écart au scénario central.

# %%
snapshot_2026 = snapshot_for_year(tables, external, target_year, cfg)
e2_result = forecast_regulated(snapshot_2026, cfg)
scenarios = scenario_table(e2_result, cfg)
labels = {"central": "central", "incentives_deeper": "concessions plus profondes",
          "incentives_shallower": "concessions plus légères", "more_renewals": "plus de renouvellements",
          "fewer_renewals": "moins de renouvellements", "met_guideline_applies": "ligne directrice à the Ontario new-build",
          "low": "bas (minimum)", "high": "haut (maximum)"}
display(scenarios.assign(scenario=scenarios["scenario"].map(labels)).rename(columns={
    "scenario": "scénario", "incentive_shift_pp": "concessions (pp)", "renewal_share_shift_pp": "renouvellements (pp)",
    "met_guideline_applies": "ligne directrice à the Ontario new-build", "headline_net_pct": "net %",
    "headline_contract_pct": "contractuel %", "delta_net_pp": "écart au central (pp)"}).round(2))
by_name = scenarios.set_index("scenario")
single_levers = ["incentives_deeper", "incentives_shallower", "more_renewals", "fewer_renewals", "met_guideline_applies"]
effects = by_name.loc[single_levers, "delta_net_pp"].dropna().abs()
strongest = effects.idxmax()
display(Markdown(
    f"Scénario central E2 : **{by_name.loc['central', 'headline_net_pct']:.2f} %** net "
    f"({by_name.loc['central', 'headline_contract_pct']:.2f} % contractuel). Scénario bas : "
    f"**{by_name.loc['low', 'headline_net_pct']:.2f} %** ; scénario haut : **{by_name.loc['high', 'headline_net_pct']:.2f} %**. "
    f"Si la ligne directrice ontarienne s'applique à the Ontario new-build : **{by_name.loc['met_guideline_applies', 'delta_net_pp']:+.2f} pp** "
    f"sur la hausse nette. Le levier qui déplace le plus la hausse nette est « {labels[strongest]} » "
    f"(**{by_name.loc[strongest, 'delta_net_pp']:+.2f} pp**) ; les concessions plus profondes ou plus légères donnent "
    f"**{by_name.loc['incentives_deeper', 'delta_net_pp']:+.2f} pp** et **{by_name.loc['incentives_shallower', 'delta_net_pp']:+.2f} pp**."))

# %% [markdown]
# ### 11b.3 Cas de stress : B3
#
# **Opération :** B3 fixe la croissance contractuelle sur le pourcentage du TAL puis soustrait **en entier** l'écart
# contractuel → net observé l'an dernier. C'est un cas de stress : il suppose que l'ampleur des concessions de l'an dernier se
# répète telle quelle. Il n'est pas un scénario probable ; il montre la sensibilité du résultat à cette hypothèse.

# %%
headlines = headline_table(tables, external, cfg)
b3 = headlines[(headlines["rule"] == "jan31") & (headlines["model"] == "B3_tal_anchor")].iloc[0]
if b3["note"] == "":
    display(Markdown(
        f"Cas de stress B3 : **{b3['net_pct']:.2f} %** net pour {target_year} ({b3['contract_pct']:.2f} % contractuel), "
        f"soit **{b3['net_pct'] - by_name.loc['central', 'headline_net_pct']:+.2f} pp** par rapport au scénario central E2."))
else:
    display(Markdown(f"Cas de stress B3 indisponible : {b3['note']}"))

# %%
fig, axis = plt.subplots(figsize=(7, 3.6))
order = ["low", "incentives_deeper", "more_renewals", "met_guideline_applies", "central", "fewer_renewals",
         "incentives_shallower", "high"]
shown = by_name.loc[[name for name in order if name in by_name.index]]["headline_net_pct"].dropna()
colors = ["#0072B2" if name == "central" else "#999999" for name in shown.index]
axis.barh([labels[name] for name in shown.index][::-1], shown.values[::-1], color=colors[::-1])
if b3["note"] == "":
    axis.axvline(b3["net_pct"], color="#D55E00", linestyle="--", label="cas de stress B3")
    axis.legend(fontsize=8, frameon=False)
axis.axvline(0, color="black", linewidth=0.8)
axis.set_xlabel(f"Hausse nette {target_year} (%)")
axis.set_title("Scénarios E2 (pas des intervalles de prédiction)")
plt.tight_layout()
plt.show()
