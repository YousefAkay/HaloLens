# ---
# jupyter:
#   jupytext:
#     formats: py:percent
# ---

# %% [markdown]
# ## 10. Prévision de l'année cible
#
# **Objectif :** fournir `estimate_2026()` et `backtest()` avec les signatures du commanditaire, annoncer la hausse de l'année cible du
# modèle retenu, la situer parmi les autres modèles et expliquer la lecture réglementaire.
#
# **Entrée :** `tables`, `external`, `cfg`. **Opération :** le modèle retenu est celui que choisit la règle déclarée en
# section 8 (`select_champion`) ; `estimate_2026()` et `backtest()` appellent **le même** pipeline du modèle retenu, jamais une
# méthode plus facile. **Pourquoi :** la prévision de l'année cible doit avoir été validée par la procédure qui a servi au backtest.
# **Vérification :** le résultat de `estimate_2026()` est comparé au pipeline direct, et chaque pli de `backtest()` porte le
# nom du même modèle.
#
# **Définition retenue :** croissance à composition fixe, à unité constante, du loyer net de tous les incitatifs, pour
# l'année cible (affichée par le code).

# %%
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from leaselens.config import cutoff_for, external_cutoff_for
from leaselens.evaluate.backtest import (backtest_both_rules, champion_backtest, champion_forecast, champion_pipeline,
                                         french_date, french_day_month, headline_table, tables_from_leases)
from leaselens.contracts import COLOR_NAIVE, COLOR_NET
from leaselens.evaluate.metrics import TOLERANCE_PP
from leaselens.forecast.asof import snapshot_for_year
from leaselens.forecast.baselines import rate_logs_by_year, to_pct
from leaselens.market.registry import load_external

if external is None:
    external = load_external(Path(cfg["_root"]) / cfg["data"]["public_dir"] / cfg["external"]["sources_file"])
if "backtest_all" not in globals():
    backtest_all = backtest_both_rules(tables, external, cfg)
target_year = cfg["forecast_years"]["target_year"]
crm_cutoff = french_date(cutoff_for(target_year, cfg))
public_cutoff = french_date(external_cutoff_for(target_year, cfg))
crm_day = french_day_month(cutoff_for(target_year, cfg))
public_day = french_day_month(external_cutoff_for(target_year, cfg))
pipeline = champion_pipeline(tables, external, cfg, backtest_all)
champion = pipeline["champion"]

# %% [markdown]
# ### 10.1 Fonctions du commanditaire
#
# `estimate_2026(leases, asking, external=None)` renvoie la hausse de l'année cible en % (loyer net). `backtest(leases, target_year)`
# renvoie un `BacktestResult`. Les signatures ne contiennent ni les loyers affichés ni les données publiques pour
# `backtest()` : la fonction reprend ceux de la session (`tables.asking`, `external`), car le choix du modèle en a besoin.

# %%
def estimate_2026(leases, asking, external=None):
    """Hausse de l'année cible (%, loyer net) du modèle retenu par la règle déclarée ; `external` : sources publiques (facultatif)."""
    result = champion_forecast(tables_from_leases(leases, asking), external, cfg)
    return result.headline_net_pct


def backtest(leases, target_year):
    """Pli de backtest du modèle retenu (même pipeline que estimate_2026), avec la sensibilité stricte."""
    return champion_backtest(tables_from_leases(leases, tables.asking), external, target_year, cfg)


estimate = estimate_2026(tables.leases, tables.asking, external)
final = champion_forecast(tables, external, cfg, table=backtest_all)
folds = {year: backtest(tables.leases, year) for year in cfg["forecast_years"]["backtest_years"]}
display(Markdown(
    f"Modèle retenu : **{champion}**. `estimate_2026()` = **{estimate:.2f} %** (identique au pipeline direct : "
    f"**{'oui' if abs(estimate - final.headline_net_pct) < TOLERANCE_PP else 'NON'}**). Plis de `backtest()` : "
    + "; ".join(f"{year} → {fold.forecast.model_name}, erreur {fold.error_pp_net:+.2f} pp" for year, fold in folds.items())
    + "."))

# %% [markdown]
# ### 10.2 La hausse de l'année cible
#
# **Opération :** prévision du modèle retenu avec les données du CRM jusqu'à la coupure du CRM et les données publiques
# publiées au plus tard à la date de coupure publique (dates affichées ci-dessous). Les médianes sont une vérification de
# robustesse. Les valeurs sont des **prévisions** de la hausse du loyer net à unité constante, pas des mesures de
# l'occupation ni du parc locatif.

# %%
display(Markdown(
    f"Données du CRM jusqu'au **{crm_cutoff}** ; données publiques publiées au plus tard le **{public_cutoff}**."))
display(Markdown(
    f"### Hausse {target_year} (modèle {champion})\n\n"
    f"- **Loyer net de tous les incitatifs : {final.headline_net_pct:.2f} %** (médiane {final.median_net_pct:.2f} %)\n"
    f"- **Loyer contractuel : {final.headline_contract_pct:.2f} %** (médiane {final.median_contract_pct:.2f} %)\n"
    f"- Écart contractuel → net : **{final.headline_contract_pct - final.headline_net_pct:+.2f} pp** "
    f"(effet des concessions)."))

# %% [markdown]
# ### 10.3 Québec et Ontario
#
# **Opération :** même agrégation à poids fixes, restreinte aux segments de chaque province. Le Québec et
# l'Ontario (the Ontario new-build) relèvent de régimes de loyers différents (TAL et loi ontarienne) ; aucun plafond d'une province n'est
# appliqué à l'autre.

# %%
from leaselens.forecast.scenarios import headline_by_province

province_of = tables.leases.drop_duplicates("prop_code").set_index("prop_code")["province"]
split = headline_by_province(final, province_of).rename(columns={
    "province": "province", "weight_share": "part des poids", "n_segments": "segments", "net_pct": "net %",
    "contract_pct": "contractuel %"})
display(split.round(3))
if (split["province"] == "all").all():
    display(Markdown(
        f"Le modèle retenu ({champion}) prévoit seulement la hausse du portefeuille, sans prévision par segment : la répartition "
        f"entre provinces n'est pas disponible pour ce modèle ; seule la ligne « all » (le portefeuille) est donnée."))
else:
    uncovered = 1 - float(split.loc[split["province"] == "all", "part des poids"].iloc[0])
    display(Markdown(
        f"Les segments sans paire l'année dernière ({uncovered:.1%} des poids) sont exclus et les autres poids sont "
        f"renormalisés, comme dans la hausse elle-même ; c'est pourquoi les parts ne totalisent pas tout à fait 100 %."))

# %% [markdown]
# ### 10.4 Les autres modèles pour l'année cible
#
# **Opération :** la même prévision pour tous les modèles, avec la règle de coupure publique retenue et la sensibilité
# stricte. L'étendue (minimum–maximum) porte sur les modèles listés dans `config/forecast.yaml` (`headline_range`) ; les autres sont montrés à part : B2 dépend de l'IPC, B3 suppose que
# l'écart contractuel → net de l'an dernier se répète en entier.

# %%
headlines = headline_table(tables, external, cfg)
display(headlines.rename(columns={"rule": "règle", "model": "modèle", "net_pct": "net %", "contract_pct": "contractuel %",
                                  "median_net_pct": "médiane net %", "median_contract_pct": "médiane contractuelle %"}).round(2))
jan31 = headlines[headlines["rule"] == "jan31"].set_index("model")
range_models = list(cfg["headline_range"]["models"])
range_net = jan31.loc[range_models, "net_pct"].dropna()
range_codes = [name.split("_")[0] for name in range_net.index]
range_names = ", ".join(range_codes[:-1]) + " et " + range_codes[-1] if len(range_codes) > 1 else range_codes[0]
display(Markdown(
    f"**Étendue de la hausse nette {target_year} sur {range_names} : de {range_net.min():.2f} % "
    f"({range_net.idxmin()}) à {range_net.max():.2f} % ({range_net.idxmax()}).** Le modèle retenu ({champion}) donne "
    f"{final.headline_net_pct:.2f} %."))

fig, axis = plt.subplots(figsize=(7, 3.2))
shown = jan31["net_pct"].dropna()
colors = [COLOR_NET if name == champion else COLOR_NAIVE for name in shown.index]
axis.barh(shown.index[::-1], shown.values[::-1], color=colors[::-1])
axis.axvline(0, color="black", linewidth=0.8)
axis.set_xlabel(f"Hausse nette {target_year} (%)")
axis.set_title(f"Hausse nette {target_year} par modèle (public au {public_day} ; modèle retenu en orange)")
plt.tight_layout()
plt.show()

# %% [markdown]
# ### 10.5 Lecture réglementaire
#
# **Opération :** comparer la prévision du modèle retenu, qui prolonge l'historique récent, au pourcentage du TAL de l'année
# cible et à la prévision du modèle réglementé E2. **Pourquoi :** les renouvellements québécois sont encadrés par le TAL ; si le
# pourcentage baisse fortement, un modèle qui répète l'an dernier peut s'écarter de ce que le cadre réglementaire permet.

# %%
snapshot_2026 = snapshot_for_year(tables, external, target_year, cfg)
tal_rates = rate_logs_by_year(snapshot_2026.external, cfg["anchors"]["tal_metric"], cfg["anchors"]["tal_geography"])
tal_now, tal_before = to_pct(tal_rates[target_year]), to_pct(tal_rates[target_year - 1])
e2 = jan31.loc["E2_regulated"]
overshoot = "surestimer" if final.headline_contract_pct > e2["contract_pct"] else "s'écarter de"
display(Markdown(
    f"**Vue réglementaire.** Le pourcentage du TAL pour {target_year} est de **{tal_now:.1f} %** (contre **{tal_before:.1f} %** "
    f"en {target_year - 1}) ; il provient de la nouvelle méthode annoncée le {french_date(cfg['anchors']['tal_method_announced'])} "
    f"et n'est pas directement comparable aux années précédentes. Un modèle fondé sur l'an dernier peut donc {overshoot} la croissance contractuelle "
    f"{target_year} : {champion} donne **{final.headline_contract_pct:.1f} %** de croissance contractuelle, alors que le "
    f"modèle réglementé E2 donne **{e2['net_pct']:.1f} %** net et **{e2['contract_pct']:.1f} %** contractuel. "
    f"Au scénario central, the Ontario new-build est considéré exempté de la ligne directrice ontarienne (hypothèse, pas une "
    f"détermination juridique)."))
