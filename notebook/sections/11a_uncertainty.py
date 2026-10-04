# ---
# jupyter:
#   jupytext:
#     formats: py:percent
# ---

# %% [markdown]
# ## 11a. Incertitude d'échantillonnage (bootstrap par unité)
#
# **Objectif :** mesurer de combien la hausse du modèle retenu changerait si l'échantillon d'unités observé avait été
# légèrement différent.
#
# **Entrée :** `tables` (baux, rabais, loyers affichés), `external`, `cfg` (graine et nombre de tirages dans
# `config/core.yaml`, section `uncertainty`) et le modèle retenu en section 9. **Opération :** à chaque tirage, on retire des
# **unités** avec remise, chacune avec son historique complet de baux (jamais des baux isolés, car les baux successifs d'une
# même unité sont liés) ; une unité tirée plusieurs fois devient plusieurs unités distinctes. Le modèle retenu, choisi une
# seule fois sur les données d'origine, est relancé sur chaque tirage avec le même pipeline que la hausse annoncée.
# **Pourquoi :** une hausse issue d'un échantillon d'unités a une marge d'erreur d'échantillonnage que la valeur centrale ne montre
# pas. **Vérification :** la graine est fixe (résultat reproductible), l'intervalle doit contenir la valeur centrale et le
# nombre de tirages en échec est affiché.
#
# **Limite déclarée :** cet intervalle ne mesure que l'incertitude d'échantillonnage. Il ne couvre ni le choix du modèle ni les
# hypothèses (bornes, winsorisation, règle d'information, concessions, régime de the Ontario new-build) : ces dimensions sont traitées par les
# scénarios et les sensibilités de la section 11b. Les trois lectures se complètent ; aucune n'est un intervalle de prévision.

# %%
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from leaselens.contracts import COLOR_CONTRACT, COLOR_NET
from leaselens.evaluate.backtest import champion_forecast, champion_pipeline
from leaselens.evaluate.uncertainty import bootstrap_interval, unit_bootstrap
from leaselens.market.registry import load_external

if external is None:
    external = load_external(Path(cfg["_root"]) / cfg["data"]["public_dir"] / cfg["external"]["sources_file"])
if "champion" not in globals():
    champion = champion_pipeline(tables, external, cfg)["champion"]
target_year = cfg["forecast_years"]["target_year"]
n_draws = cfg["uncertainty"]["bootstrap_draws"]

# %% [markdown]
# ### 11a.1 Tirages
#
# **Opération :** les tirages sont indépendants et reproductibles : le tirage de rang donné ne dépend pas du nombre total de
# tirages demandés. Seuls des agrégats sont conservés (jamais un identifiant d'unité).

# %%
point = champion_forecast(tables, external, cfg)
draws = unit_bootstrap(tables, external, cfg, n_draws, champion=champion)
interval = bootstrap_interval(draws, cfg)
low_q, high_q = interval["quantiles"]
net, contract = interval["net_pct"], interval["contract_pct"]
inside = net["lower"] <= point.headline_net_pct <= net["upper"]
display(Markdown(
    f"Modèle retenu : **{champion}**. **{interval['n_ok']}** tirages réussis sur **{interval['n_draws']}** "
    f"({interval['n_failed']} en échec), graine **{cfg['random_seed']}**, unités rééchantillonnées avec remise."))
display(Markdown(
    f"Hausse {target_year} du modèle retenu : **{point.headline_net_pct:.2f} %** net (intervalle d'échantillonnage "
    f"{low_q:.0%}–{high_q:.0%} : **{net['lower']:.2f} % à {net['upper']:.2f} %**) ; **{point.headline_contract_pct:.2f} %** "
    f"contractuel (**{contract['lower']:.2f} % à {contract['upper']:.2f} %**). Écart-type des tirages : "
    f"**{net['sd']:.2f} pp** (net) et **{contract['sd']:.2f} pp** (contractuel). La valeur centrale est "
    f"**{'dans' if inside else 'hors de'}** l'intervalle net."))

# %% [markdown]
# ### 11a.2 Distribution des tirages
#
# **Opération :** histogramme de la hausse nette et de la hausse contractuelle sur les tirages ; trait plein : valeur centrale
# (données d'origine) ; traits pointillés : bornes de l'intervalle d'échantillonnage.

# %%
ok = draws.dropna(subset=["net_pct", "contract_pct"])
fig, axes = plt.subplots(1, 2, figsize=(9, 3.4), sharey=True)
for axis, column, color, label, central, bounds in (
        (axes[0], "net_pct", COLOR_NET, "Loyer net", point.headline_net_pct, net),
        (axes[1], "contract_pct", COLOR_CONTRACT, "Loyer contractuel", point.headline_contract_pct, contract)):
    axis.hist(ok[column], bins="auto", color=color, alpha=0.75)
    axis.axvline(central, color="black", linewidth=1.5, label="valeur centrale")
    axis.axvline(bounds["lower"], color="black", linestyle="--", linewidth=1)
    axis.axvline(bounds["upper"], color="black", linestyle="--", linewidth=1, label="bornes de l'intervalle")
    axis.set_title(label)
    axis.set_xlabel(f"Hausse {target_year} (%)")
axes[0].set_ylabel("Nombre de tirages")
axes[0].legend(fontsize=8, frameon=False)
fig.suptitle("Bootstrap par unité : incertitude d'échantillonnage seulement")
fig.tight_layout()
plt.show()

# %%
net_width = net["upper"] - net["lower"]
contract_width = contract["upper"] - contract["lower"]
wider = "nette" if net_width > contract_width else "contractuelle"
display(Markdown(
    f"**Lecture.** L'intervalle d'échantillonnage a une largeur de **{net_width:.2f} pp** pour la hausse nette et de "
    f"**{contract_width:.2f} pp** pour la hausse contractuelle : l'échantillon d'unités pèse davantage sur la hausse {wider}. "
    f"Cet intervalle mesure ce que changerait un autre échantillon d'unités pour le même modèle ; il ne dit rien de l'écart "
    f"entre modèles ni du poids des hypothèses (section 11b), et il n'est pas un intervalle de prévision de la hausse "
    f"réellement observée en {target_year}."))
