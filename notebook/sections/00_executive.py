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

# %% [markdown]
# ### Résumé exécutif : calcul unique des résultats
# **Entrée :** `tables`, `cfg` (configuration commune ci-dessus) et les sources publiques de `data/public/sources.csv`,
# chargées ici sans modifier `external`, qui reste `None` pour les sections suivantes.
# **Opération :** calculer une seule fois l'agrégat complet (`build_aggregates`), c'est-à-dire le même chemin que
# `estimate_2026()` (modèle champion, règle de l'information du 31 janvier), puis lire le classement de la règle déclarée
# et quelques repères réglementaires. Le résultat est exposé sous le nom `summary` pour réutilisation.
# **Pourquoi :** tous les chiffres du résumé viennent de ce calcul ; rien n'est saisi à la main.
# **Vérification :** la hausse 2026 affichée ici doit être égale à celle de la section 10 (estimate_2026).

# %%
from leaselens.config import repo_root
from leaselens.evaluate.backtest import champion_pipeline, headline_table
from leaselens.export.aggregates import build_aggregates
from leaselens.forecast.asof import snapshot_for_year
from leaselens.forecast.baselines import rate_logs_by_year, to_pct
from leaselens.forecast.combine import REGULATED_MODEL_NAME
from leaselens.market.registry import load_external
from leaselens.measure.labels import french_date

PCT_DECIMALS = 2   # two decimals, the same display as section 10's estimate
PP_DECIMALS = 2    # backtest errors and ranking gaps, in percentage points
TARGET_YEAR = cfg["forecast_years"]["target_year"]

summary_external = load_external(repo_root() / cfg["data"]["public_dir"] / cfg["external"]["sources_file"])
summary = build_aggregates(tables, summary_external, cfg)          # résultats calculés une fois
champion_info = champion_pipeline(tables, summary_external, cfg)   # classement de la règle déclarée
snapshot_target = snapshot_for_year(tables, summary_external, TARGET_YEAR, cfg)
tal_rates = rate_logs_by_year(snapshot_target.external, cfg["anchors"]["tal_metric"], cfg["anchors"]["tal_geography"])
tal_now, tal_before = to_pct(tal_rates[TARGET_YEAR]), to_pct(tal_rates[TARGET_YEAR - 1])
headlines = headline_table(tables, summary_external, cfg)
e2_net = float(headlines[(headlines["rule"] == "jan31") & (headlines["model"] == REGULATED_MODEL_NAME)]["net_pct"].iloc[0])

eligible_ranking = champion_info["ranking"][champion_info["ranking"]["eligible"]]
ranking_gap_pp = (float(eligible_ranking["mae_selection_pp"].iloc[1] - eligible_ranking["mae_selection_pp"].iloc[0])
                  if len(eligible_ranking) > 1 else float("nan"))
champion_row = champion_info["ranking"][champion_info["ranking"]["model"] == champion_info["champion"]].iloc[0]

# %% [markdown]
# ### Réponse
# **Entrée :** `summary` (calcul ci-dessus). **Opération :** lire la hausse 2026, ses compagnons et les dates de référence.
# **Pourquoi :** la réponse doit tenir en quelques lignes, avec ses dates. **Vérification :** les dates viennent de la configuration.

# %%
def pct(value) -> str:
    return "n/a" if value is None else f"{value:.{PCT_DECIMALS}f} %"


def pp(value) -> str:
    return "n/a" if value is None or value != value else f"{value:.{PP_DECIMALS}f} pp"


headline, companions, as_of = summary["headline"], summary["companions"], summary["as_of"]
display(Markdown(
    f"**Hausse 2026, nette de toutes les concessions : {pct(headline['net_pct'])}** "
    f"(loyer contractuel : {pct(headline['contract_pct'])}).\n\n"
    f"Médianes : nette {pct(companions['median_net_pct'])}, contractuelle {pct(companions['median_contract_pct'])}. "
    f"Modèle retenu par la règle déclarée : **{headline['model']}**.\n\n"
    f"Dates de référence : coupure des données de baux au **{french_date(as_of['crm_cutoff'])}** ; données publiques "
    f"retenues jusqu'au **{french_date(as_of['external_cutoff'])}** (sensibilité stricte : au "
    f"{french_date(as_of['external_strict_cutoff'])})."))

# %% [markdown]
# ### Graphique-réponse
# **Entrée :** `summary` (prévision contractuelle, hausse nette, plage de scénarios) et la ligne E2 de `headline_table`.
# **Opération :** tracer la prévision contractuelle, l'effet des incitatifs (contractuel − net) et la hausse nette ; la
# plage bas-haut des scénarios est une barre d'erreur autour du scénario central ; E2 est un repère séparé.
# **Pourquoi :** une seule figure donne la réponse, son ajustement par les incitatifs et son incertitude.
# **Vérification :** toutes les valeurs viennent de `summary` et du calcul E2 ci-dessus.

# %%
from leaselens.contracts import COLOR_CONTRACT, COLOR_MARKET, COLOR_NAIVE, COLOR_NET

BAR_WIDTH = 0.5
contract_value, net_value = headline["contract_pct"], headline["net_pct"]
incentive_value = net_value - contract_value
scenario_values = summary["scenarios"]
low, central, high = scenario_values["low_net_pct"], scenario_values["central_net_pct"], scenario_values["high_net_pct"]

fig, ax = plt.subplots(figsize=(7.5, 4.8))
ax.bar(0, contract_value, width=BAR_WIDTH, color=COLOR_CONTRACT, label="Prévision contractuelle")
ax.bar(1, abs(incentive_value), width=BAR_WIDTH, bottom=min(contract_value, net_value), color=COLOR_NAIVE,
       hatch="//", label="Effet des incitatifs")
ax.bar(2, net_value, width=BAR_WIDTH, color=COLOR_NET, label="Hausse nette")
ax.errorbar(2, central, yerr=[[central - low], [high - central]], fmt="o", color="black", capsize=8, zorder=3,
            label="Plage des scénarios (bas-haut, central)")
ax.scatter(2, e2_net, marker="D", s=60, color=COLOR_MARKET, zorder=4, label="E2 : vue réglementaire")
ax.axhline(0, color="black", linewidth=0.8)
ax.set_xticks([0, 1, 2], ["Prévision\ncontractuelle", "Effet des\nincitatifs", "Hausse\nnette"])
ax.set_ylabel("Hausse annualisée 2026 (%)")
ax.set_title(f"Hausse {TARGET_YEAR} : contractuelle, incitatifs, nette")
ax.legend(frameon=False, fontsize=8, loc="upper right")
ax.grid(axis="y", alpha=0.3)
ax.spines[["top", "right"]].set_visible(False)
fig.tight_layout()
plt.show()

# %% [markdown]
# ### Définition, pourquoi cette mesure, validation
# **Entrée :** `summary` et la configuration des années. **Opération :** énoncer la définition, la raison de la mesure et
# la validation sur les années de backtest. **Pourquoi :** un chiffre sans définition ni validation ne se lit pas.
# **Vérification :** le classement vient du calcul de la règle déclarée ; aucune année de validation n'a servi à choisir.

# %%
backtest_years = ", ".join(str(year) for year in cfg["forecast_years"]["backtest_years"])
selection_years = ", ".join(str(year) for year in cfg["forecast_years"]["selection_years"])
holdout_year = cfg["forecast_years"]["holdout_year"]
display(Markdown(
    f"**Définition :** {summary['definition']}\n\n"
    f"**Pourquoi cette mesure :** la médiane annuelle des loyers signés mélange l'évolution des loyers et le changement "
    f"de logements loués (effet de composition). Comparer chaque unité à son propre bail précédent isole la hausse ; les "
    f"poids figés à la coupure empêchent le mix de déplacer le résultat. Les incitatifs sont isolés en comparant le loyer "
    f"net au loyer contractuel.\n\n"
    f"**Validation :** backtest sur {backtest_years}. Le modèle est choisi sur {selection_years} par une règle déclarée "
    f"avant les résultats ; {holdout_year} sert de validation et n'a pas servi au choix. Le modèle retenu, "
    f"**{champion_info['champion']}**, a une erreur absolue moyenne de {pp(champion_row['mae_selection_pp'])} sur les années "
    f"de sélection et de {pp(champion_row['mae_holdout_pp'])} sur {holdout_year}.\n\n"
    f"**Réserve :** l'écart entre les deux premiers modèles sur les années de sélection n'est que de "
    f"{pp(ranking_gap_pp)} : le classement est statistiquement faible, avec si peu d'années."))

# %% [markdown]
# ### Fourchette, réglementation, scénarios, provinces, limites
# **Entrée :** `summary`, les taux du TAL (`tal_rates`) et la ligne E2 de `headline_table`. **Opération :** lire la
# fourchette des modèles, la vue réglementaire, les scénarios, la répartition par province et les limites.
# **Pourquoi :** une hausse isolée se lit avec sa fourchette, ses règles et ses limites. **Vérification :** chaque
# valeur est lue dans les résultats ou la configuration.

# %%
model_range, provinces, scenarios = headline["model_range"], headline["provinces"], summary["scenarios"]
regulation = cfg["regulation"]["scenarios"]["ontario_post_2018_exemption"]
display(Markdown(
    f"**Fourchette 2026 entre les modèles candidats (B0, B1, E1, E2) :** de {pct(model_range['low_net_pct'])} à "
    f"{pct(model_range['high_net_pct'])} (net).\n\n"
    f"**Vue réglementaire :** le pourcentage du TAL pour {TARGET_YEAR} est de {pct(tal_now)}, contre {pct(tal_before)} "
    f"pour {TARGET_YEAR - 1}. Il suit la nouvelle méthode annoncée le "
    f"{french_date(cfg['anchors']['tal_method_announced'])}, à comparer avec les années antérieures. Le modèle E2 "
    f"(renouvellements québécois ancrés sur le TAL) donne {pct(e2_net)} net.\n\n"
    f"**Scénarios (net) :** bas {pct(scenarios['low_net_pct'])}, central {pct(scenarios['central_net_pct'])}, haut "
    f"{pct(scenarios['high_net_pct'])}. Ce sont des scénarios, pas des intervalles de prédiction.\n\n"
    f"**Québec :** {pct(provinces['QC']['net_pct'])} net ({pct(provinces['QC']['contract_pct'])} contractuel), sous "
    f"les règles du TAL. **Ontario :** {pct(provinces['ON']['net_pct'])} net ({pct(provinces['ON']['contract_pct'])} "
    f"contractuel), sous les règles ontariennes. Aucune règle n'est appliquée à l'autre province.\n\n"
    f"**the Ontario new-build (Ontario) :** scénario central : {regulation['central']} Scénario alternatif : "
    f"{regulation['alternative']} Ce ne sont pas des déterminations juridiques.\n\n"
    f"**Limites :** cet extrait ne permet de mesurer ni l'occupation, ni la vacance, ni l'absorption, ni le rent roll "
    f"total. Les poids décrivent les transitions de baux observées, pas l'occupation du portefeuille. Le loyer net est "
    f"ajusté des concessions : ce n'est pas un montant encaissé."))

# %%
plan_lines = []
for path in sorted((repo_root() / "notebook" / "sections").glob("*.py")):
    if path.name.startswith("00_"):
        continue
    heading = next((line[len("# ## "):] for line in path.read_text(encoding="utf-8").splitlines()
                    if line.startswith("# ## ")), path.stem)
    plan_lines.append(f"- **{path.name.split('_')[0]}** — {heading}")
display(Markdown("**Plan du notebook :**\n" + "\n".join(plan_lines)))
