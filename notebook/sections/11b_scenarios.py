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

# %% [markdown]
# ### 11b.4 Sensibilité à chaque hypothèse (diagramme en tornade)
#
# **Entrée :** `tables`, `external`, `cfg` et le modèle retenu en section 9 ; les tailles des variantes viennent de
# `config/forecast.yaml` (`sensitivity`, `scenarios`) et de `config/measure.yaml`. **Opération :** on relance le modèle retenu
# en changeant **une seule** hypothèse à la fois : règle d'information des données publiques, bornes de l'écart entre baux
# (y compris les baux courts), seuils de winsorisation, fenêtre des poids ; on relance E2 pour les leviers
# réglementaires (the Ontario new-build, concessions, part des renouvellements) et on compare les modèles entre eux. Rien n'est combiné.
# **Pourquoi :** montrer quelles hypothèses déplacent vraiment la hausse et lesquelles n'ont aucun effet. **Vérification :** chaque
# écart est la hausse de la variante moins celle du même modèle dans le cas de base ; une variante impossible reste visible avec sa
# raison. Ce sont des **sensibilités**, pas des intervalles de prédiction : les effets ne s'additionnent pas.

# %%
import numpy as np

from leaselens.evaluate.backtest import champion_pipeline
from leaselens.forecast.scenarios import sensitivity_table

if "champion" not in globals():
    champion = champion_pipeline(tables, external, cfg)["champion"]
sensitivities = sensitivity_table(tables, external, cfg, champion=champion)

assumption_fr = {
    "information_rule": "Règle d'information (données publiques)", "gap_bounds": "Bornes de l'écart entre baux",
    "winsorization": "Winsorisation", "weight_window": "Fenêtre des poids",
    "met_applicability": "Ligne directrice à the Ontario new-build", "incentive_intensity": "Intensité des concessions",
    "renewal_mix": "Part des renouvellements", "model_choice": "Choix du modèle"}


def variant_fr(row):
    setting = row["setting"]
    labels = {
        "strict_dec31": "coupure stricte (même date que le CRM)",
        "include_six_month_leases": f"baux courts inclus (borne basse {setting} an)",
        "max_gap": f"écart maximal {setting} ans", "quantiles": f"quantiles {setting}",
        "years": f"{setting} ans", "met_guideline_applies": "ligne directrice applicable",
        "incentives_deeper": f"concessions plus profondes ({float(setting):+.1f} pp)" if row["variant"] == "incentives_deeper" else "",
        "incentives_shallower": f"concessions plus légères ({float(setting):+.1f} pp)" if row["variant"] == "incentives_shallower" else "",
        "more_renewals": f"plus de renouvellements ({float(setting):+.1f} pp)" if row["variant"] == "more_renewals" else "",
        "fewer_renewals": f"moins de renouvellements ({float(setting):+.1f} pp)" if row["variant"] == "fewer_renewals" else ""}
    return labels.get(row["variant"], row["variant"])


sensitivities["libellé"] = [
    f"{assumption_fr[row.assumption]} : {variant_fr(row._asdict())}" + ("" if row.assumption == "model_choice" else f" [{row.model}]")
    for row in sensitivities.itertuples()]
display(sensitivities[["libellé", "headline_net_pct", "base_net_pct", "delta_pp", "note"]].rename(columns={
    "headline_net_pct": "net variante %", "base_net_pct": "net base %", "delta_pp": "écart pp", "note": "raison si impossible"
}).round(2))

# %%
ran = sensitivities.dropna(subset=["delta_pp"])
fig, axis = plt.subplots(figsize=(8, max(3.5, 0.32 * len(ran))))
palette_models = {champion: "#0072B2", "E2_regulated": "#E69F00"}
ordered = ran.iloc[::-1]
axis.barh(ordered["libellé"], ordered["delta_pp"], color=[palette_models.get(model, "#999999") for model in ordered["model"]])
axis.axvline(0, color="black", linewidth=0.8)
axis.set_xlabel("Écart de la hausse nette par rapport au cas de base du même modèle (pp)")
axis.set_title("Sensibilités, une hypothèse à la fois (pas des intervalles de prédiction)")
for model, color in palette_models.items():
    axis.barh([], [], color=color, label=f"modèle {model}")
axis.barh([], [], color="#999999", label="autre modèle (choix du modèle)")
axis.legend(fontsize=8, frameon=False, loc="lower right")
plt.tight_layout()
plt.show()

# %%
champion_rows = ran[(ran["model"] == champion) & (ran["assumption"] != "model_choice")]
unchanged = int((champion_rows["abs_delta_pp"] < 1e-9).sum())
largest = ran.iloc[0]
largest_champion = champion_rows.iloc[0] if len(champion_rows) else None
rule_rows = sensitivities[sensitivities["assumption"] == "information_rule"].set_index("model")
unavailable = int(sensitivities["delta_pp"].isna().sum())
text = (f"**Lecture des sensibilités.** L'hypothèse qui déplace le plus la hausse nette est « {largest['libellé']} » "
        f"(**{largest['delta_pp']:+.2f} pp**). ")
if largest_champion is not None:
    text += (f"Pour le modèle retenu ({champion}), le plus grand effet d'un choix de données ou de règle est "
             f"« {largest_champion['libellé']} » (**{largest_champion['delta_pp']:+.2f} pp**) ; "
             f"**{unchanged}** de ces variantes laissent la hausse inchangée. ")
if champion in rule_rows.index and np.isfinite(rule_rows.loc[champion, "delta_pp"]):
    text += (f"La règle d'information des données publiques déplace le modèle retenu de "
             f"**{rule_rows.loc[champion, 'delta_pp']:+.2f} pp**")
    if "E2_regulated" in rule_rows.index and np.isfinite(rule_rows.loc["E2_regulated", "delta_pp"]):
        text += f", mais E2, qui lit le pourcentage du TAL, de **{rule_rows.loc['E2_regulated', 'delta_pp']:+.2f} pp**"
    text += ". "
if unavailable:
    text += f"**{unavailable}** variante(s) n'ont pas pu être calculées (raison dans le tableau). "
text += ("Ce sont des **sensibilités**, pas des intervalles de prédiction : chaque ligne modifie une seule hypothèse et les "
         "effets ne s'additionnent pas.")
display(Markdown(text))
