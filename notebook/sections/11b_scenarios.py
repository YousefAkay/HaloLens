# ---
# jupyter:
#   jupytext:
#     formats: py:percent
# ---

# %% [markdown]
# ## 11b. Scénarios de l'année cible
#
# **Objectif :** montrer comment la hausse nette de l'année cible varie quand on déplace, un à la fois puis ensemble, des leviers
# incertains : l'intensité des concessions, la part des renouvellements et l'application de la ligne directrice ontarienne à
# the Ontario new-build.
#
# **Entrée :** `tables`, `external`, `cfg`. **Opération :** le moteur réglementé E2 (renouvellements québécois ancrés sur le TAL)
# est recalculé pour l'année cible ; chaque levier est appliqué aux prévisions par segment, puis les segments sont agrégés avec les
# mêmes poids fixes. **Pourquoi :** la hausse retenue est une valeur centrale ; les scénarios montrent ce qui la ferait bouger.
# **Important :** ce sont des **scénarios**, pas des intervalles de prédiction : un petit nombre d'années de backtest ne permet pas
# de calibrer une probabilité.

# %%
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from leaselens.config import cutoff_for
from leaselens.evaluate.backtest import french_date, headline_table
from leaselens.forecast.asof import snapshot_for_year
from leaselens.forecast.combine import forecast_regulated
from leaselens.forecast.scenarios import scenario_table
from leaselens.incentives.engine import discount_share
from leaselens.market.registry import load_external
from leaselens.market.regulation import applicability_matrix
from leaselens.measure.pairs import build_pairs

if external is None:
    external = load_external(Path(cfg["_root"]) / cfg["data"]["public_dir"] / cfg["external"]["sources_file"])
target_year = cfg["forecast_years"]["target_year"]
levers = cfg["scenarios"]

# %% [markdown]
# ### 11b.1 Les leviers
#
# - **Intensité des concessions** : on déplace de ± `incentive_intensity_shift_pp` point la part de rabais prévue de chaque
#   segment ; l'ordre de grandeur vient de l'évolution récente de la part de rabais moyenne (chiffrée ci-dessous).
# - **Part des renouvellements** : on déplace de ± `renewal_share_shift_pp` point la part des renouvellements dans les poids
#   fixes ; l'ordre de grandeur vient des variations annuelles observées (chiffrées ci-dessous).
# - **the Ontario new-build** : au scénario central, l'exemption des premières occupations résidentielles postérieures à la date prévue par
#   la loi est jugée plausible ; au scénario alternatif, la ligne directrice ontarienne s'applique. Ce n'est pas une
#   détermination juridique (date et première année de bail affichées ci-dessous).

# %%
cutoff = cutoff_for(target_year, cfg)
known_leases = tables.leases[tables.leases["lease_start"] <= cutoff]
yearly_discount = (known_leases.assign(year=known_leases["lease_start"].dt.year, discount=discount_share(known_leases))
                   .dropna(subset=["discount"]).groupby("year")["discount"].mean())
discount_changes_pp = 100 * yearly_discount.diff().dropna().tail(2)
pairs_all = build_pairs(tables.leases, cfg)
renewal_share = pairs_all[pairs_all["eligible"]].groupby("year")["is_renewal"].mean()
renewal_swing_pp = 100 * renewal_share.diff().abs().dropna()

met_entries = [entry for entry in cfg["regulation"]["buildings"] if entry.get("scenario") == "ontario_post_2018_exemption"]
met_names = [entry["building"] for entry in met_entries]
matrix = applicability_matrix(cfg, tables.leases)
met_first_years = matrix.loc[matrix["building"].isin(met_names), "first_lease_year"].dropna()
met_first_year = f"**{int(met_first_years.min())}**" if len(met_first_years) else "non disponible dans ces données"
exemption_date = french_date(cfg["regulation"]["ontario_post_2018_exemption_cutoff"])

display(Markdown(
    f"Leviers retenus (valeurs de `config/forecast.yaml`) : concessions ± **{levers['incentive_intensity_shift_pp']:.1f} pp**, "
    f"part des renouvellements ± **{levers['renewal_share_shift_pp']:.1f} pp**."))
display(Markdown(
    "- **Concessions** : la part de rabais moyenne des baux a varié de "
    + " puis de ".join(f"**{change:+.1f} pp** en {year}" for year, change in discount_changes_pp.items())
    + " (baux connus à la coupure du CRM).\n"
    f"- **Renouvellements** : la part des renouvellements parmi les paires admissibles varie en moyenne de "
    f"**{renewal_swing_pp.mean():.1f} pp** par an (maximum **{renewal_swing_pp.max():.1f} pp**).\n"
    f"- **{', '.join(met_names)}** : premier bail de l'extrait : {met_first_year} ; exemption plausible pour les "
    f"premières occupations résidentielles postérieures au **{exemption_date}** (scénario central), ligne directrice "
    f"ontarienne appliquée (scénario alternatif)."))

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
