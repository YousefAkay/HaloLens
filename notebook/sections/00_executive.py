# ---
# jupyter:
#   jupytext:
#     formats: py:percent
# ---

# %% [markdown]
# # Halo Lens — Hausse de loyer 2026
#
# Ce notebook est dérivé du notebook de départ fourni avec le défi.

# %% [markdown]
# **Abstract (English).** Halo Lens estimates the rent increase of a residential portfolio for the target year, for residential
# buildings in Québec and Ontario, from lease history up to the data cutoff and from public market data. The increase is
# defined as same-unit growth in rent net of all incentives, at fixed composition, and the method is backtested on the three
# previous years. Every number in this notebook is computed by code from the data and the configuration. The notebook text
# is in French, and the starter notebook is credited in section 12.

# %% [markdown]
# ### Configuration commune
# Toutes les sections suivantes utilisent les objets créés ici : `cfg` (configuration), `raw` (tables sources,
# noms originaux), `tables` (tables renommées et typées) et `external` (données publiques).
# Le mode (`synthetic` ou `real`) est fixé dans `config/core.yaml`.

# %%
# %matplotlib inline
import os
import sys
import warnings
from pathlib import Path

# ---- Données / Data ----------------------------------------------------------------------------------------------
# Mettez ici le dossier qui contient les 4 fichiers CSV sources et manifest.json.
# Put here the folder that holds the 4 source CSV files and manifest.json. None = data/private
# (or the environment variable LEASELENS_DATA_DIR, if set).
DATA_DIR = None  # mettez le chemin de vos fichiers CSV sources ici / put your source CSV folder path here


def _stop(message_fr: str, message_en: str) -> None:
    """Print a clear bilingual message and end the run without a traceback."""
    print(message_fr)
    print(message_en)
    raise SystemExit(message_fr)


def _find_root(start: Path):
    """The repository root is the folder that contains config/core.yaml (searched upward from `start`)."""
    return next((folder for folder in [start, *start.parents] if (folder / "config" / "core.yaml").exists()), None)


ROOT = _find_root(Path.cwd())
if ROOT is None:
    _stop("Ouvrez le notebook depuis le dossier du dépôt Halo Lens (celui qui contient config/core.yaml).",
          "Open the notebook from the Halo Lens repository folder (the one that contains config/core.yaml).")
try:
    import leaselens  # noqa: F401
except ImportError:
    sys.path.insert(0, str(ROOT / "src"))  # no install needed: use the copy of the code next to this notebook

REQUIRED_PACKAGES = ("pandas", "numpy", "matplotlib", "yaml", "jsonschema", "IPython", "nbformat")
missing_packages = []
for _name in REQUIRED_PACKAGES:
    try:
        __import__(_name)
    except ImportError:
        missing_packages.append(_name)
if missing_packages:
    _stop(f"Paquets manquants : {', '.join(missing_packages)}. Dans le dossier du dépôt, exécutez : "
          "pip install -r requirements.txt",
          f"Missing packages: {', '.join(missing_packages)}. In the repository folder, run: pip install -r requirements.txt")

import matplotlib.pyplot as plt
import pandas as pd
from IPython.display import Markdown, display

from leaselens.config import data_dir, load_config
from leaselens.contracts import SOURCE_FILES
from leaselens.io import canonicalize, column_mapping, load_raw, run_qa

warnings.filterwarnings("ignore", category=FutureWarning)
pd.set_option("display.width", 160)

cfg = load_config()
FOLDER = Path(DATA_DIR or os.environ.get("LEASELENS_DATA_DIR") or data_dir(cfg))
EXPECTED_FILES = [*SOURCE_FILES.values(), "manifest.json"]
missing_files = [name for name in EXPECTED_FILES if not (FOLDER / name).is_file()]
if missing_files:
    _stop(f"Fichiers introuvables dans « {FOLDER} » : {', '.join(missing_files)}. Attendus : "
          f"{', '.join(EXPECTED_FILES)}. Réglez DATA_DIR (en haut de cette cellule) ou la variable LEASELENS_DATA_DIR.",
          f"Files not found in « {FOLDER} »: {', '.join(missing_files)}. Expected: {', '.join(EXPECTED_FILES)}. "
          "Set DATA_DIR (top of this cell) or the LEASELENS_DATA_DIR variable.")
try:
    raw = load_raw(FOLDER)           # vérifie les empreintes SHA-256 du manifeste avant de lire
except ValueError as error:
    _stop(f"Contrôle des empreintes SHA-256 échoué : {error}. Vérifiez que les fichiers correspondent au manifeste.",
          f"SHA-256 check failed: {error}. Check that the files match manifest.json.")
tables = canonicalize(raw)
external = None                      # chargé en section 7 via market.registry.load_external
display(Markdown(f"Mode des données : **{cfg['data']['mode']}**"))

# %% [markdown]
# ### Résumé exécutif : calcul unique des résultats
# **Entrée :** `tables`, `cfg` (configuration commune ci-dessus) et les sources publiques de `data/public/sources.csv`,
# chargées ici sans modifier `external`, qui reste `None` pour les sections suivantes.
# **Opération :** calculer une seule fois l'agrégat complet (`build_aggregates`), c'est-à-dire le même chemin que
# `estimate_2026()` (modèle champion, avec la date d'information des données publiques), puis lire le classement de la règle déclarée
# et quelques repères réglementaires. Le résultat est exposé sous le nom `results` pour réutilisation.
# **Pourquoi :** tous les chiffres du résumé viennent de ce calcul ; rien n'est saisi à la main.
# **Vérification :** la hausse 2026 affichée ici doit être égale à celle de la section 10 (estimate_2026).

# %%
from leaselens.config import repo_root
from leaselens.evaluate.backtest import champion_pipeline, headline_table
from leaselens.export.aggregates import MODEL_RANGE_NAMES, build_aggregates
from leaselens.forecast.asof import snapshot_for_year
from leaselens.forecast.baselines import rate_logs_by_year, to_pct
from leaselens.forecast.combine import REGULATED_MODEL_NAME
from leaselens.market.registry import load_external
from leaselens.measure.labels import french_date

PCT_DECIMALS = 2   # two decimals, the same display as section 10's estimate
PP_DECIMALS = 2    # backtest errors and ranking gaps, in percentage points
TARGET_YEAR = cfg["forecast_years"]["target_year"]

results_external = load_external(repo_root() / cfg["data"]["public_dir"] / cfg["external"]["sources_file"])
results = build_aggregates(tables, results_external, cfg)          # résultats calculés une fois
champion_info = champion_pipeline(tables, results_external, cfg)   # classement de la règle déclarée
snapshot_target = snapshot_for_year(tables, results_external, TARGET_YEAR, cfg)
tal_rates = rate_logs_by_year(snapshot_target.external, cfg["anchors"]["tal_metric"], cfg["anchors"]["tal_geography"])
tal_now, tal_before = to_pct(tal_rates[TARGET_YEAR]), to_pct(tal_rates[TARGET_YEAR - 1])
headlines = headline_table(tables, results_external, cfg)
e2_net = float(headlines[(headlines["rule"] == "jan31") & (headlines["model"] == REGULATED_MODEL_NAME)]["net_pct"].iloc[0])

eligible_ranking = champion_info["ranking"][champion_info["ranking"]["eligible"]]
ranking_gap_pp = (float(eligible_ranking["mae_selection_pp"].iloc[1] - eligible_ranking["mae_selection_pp"].iloc[0])
                  if len(eligible_ranking) > 1 else float("nan"))
champion_row = champion_info["ranking"][champion_info["ranking"]["model"] == champion_info["champion"]].iloc[0]

# %% [markdown]
# ### Réponse
# **Entrée :** `results` (calcul ci-dessus). **Opération :** lire la hausse 2026, ses compagnons et les dates de référence.
# **Pourquoi :** la réponse doit tenir en quelques lignes, avec ses dates. **Vérification :** les dates viennent de la configuration.

# %%
def pct(value) -> str:
    return "n/a" if value is None else f"{value:.{PCT_DECIMALS}f} %"


def pp(value) -> str:
    return "n/a" if value is None or value != value else f"{value:.{PP_DECIMALS}f} pp"


headline, companions, as_of = results["headline"], results["companions"], results["as_of"]
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
# **Entrée :** `results` (prévision contractuelle, hausse nette, plage de scénarios) et la ligne E2 de `headline_table`.
# **Opération :** tracer, pour le modèle retenu, la prévision contractuelle, l'effet des incitatifs (contractuel − net) et la
# hausse nette ; puis, à part, la vue réglementaire du modèle E2 : sa hausse nette et la plage bas–central–haut de ses
# scénarios, qui sont des quantités de E2 et non du modèle retenu.
# **Pourquoi :** une seule figure donne la réponse, son ajustement par les incitatifs et son incertitude.
# **Vérification :** toutes les valeurs viennent de `results` et du calcul E2 ci-dessus ; les couleurs viennent de `leaselens.contracts`.

# %%
from leaselens.contracts import COLOR_CONTRACT, COLOR_MARKET, COLOR_NAIVE, COLOR_NET

BAR_WIDTH = 0.5
E2_POSITION = 3  # le modèle E2 est tracé à part, après les trois barres du modèle retenu
contract_value, net_value = headline["contract_pct"], headline["net_pct"]
incentive_value = net_value - contract_value
scenario_values = results["scenarios"]
low, central, high = scenario_values["low_net_pct"], scenario_values["central_net_pct"], scenario_values["high_net_pct"]

fig, ax = plt.subplots(figsize=(7.5, 4.8))
ax.bar(0, contract_value, width=BAR_WIDTH, color=COLOR_CONTRACT, label="Prévision contractuelle")
ax.bar(1, abs(incentive_value), width=BAR_WIDTH, bottom=min(contract_value, net_value), color=COLOR_NAIVE,
       hatch="//", label="Effet des incitatifs")
ax.bar(2, net_value, width=BAR_WIDTH, color=COLOR_NET, label="Hausse nette")
ax.errorbar(E2_POSITION, central, yerr=[[central - low], [high - central]], fmt="_", markersize=14, color=COLOR_MARKET,
            capsize=8, zorder=3, label="Scénarios E2 (bas–central–haut)")
ax.scatter(E2_POSITION, e2_net, marker="D", s=60, color=COLOR_MARKET, zorder=4, label="E2 : hausse nette")
ax.axhline(0, color=COLOR_NAIVE, linewidth=0.8)
ax.set_xticks([0, 1, 2, E2_POSITION], ["Prévision\ncontractuelle", "Effet des\nincitatifs", "Hausse\nnette", "Vue réglementaire\nE2"])
ax.set_ylabel("Hausse annualisée 2026 (%)")
ax.set_title(f"Hausse {TARGET_YEAR} : modèle retenu (barres) et vue réglementaire E2")
ax.legend(frameon=False, fontsize=8, loc="upper center", bbox_to_anchor=(0.5, -0.2), ncol=2)  # sous le graphique
ax.grid(axis="y", alpha=0.3)
ax.spines[["top", "right"]].set_visible(False)
fig.tight_layout()
plt.show()

# %% [markdown]
# ### Définition, pourquoi cette mesure, validation
# **Entrée :** `results` et la configuration des années. **Opération :** énoncer la définition, la raison de la mesure et
# la validation sur les années de backtest. **Pourquoi :** un chiffre sans définition ni validation ne se lit pas.
# **Vérification :** le classement vient du calcul de la règle déclarée ; aucune année de validation n'a servi à choisir.

# %%
backtest_years = ", ".join(str(year) for year in cfg["forecast_years"]["backtest_years"])
selection_years = ", ".join(str(year) for year in cfg["forecast_years"]["selection_years"])
holdout_year = cfg["forecast_years"]["holdout_year"]
display(Markdown(
    f"**Définition :** {results['definition']}\n\n"
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
# **Entrée :** `results`, les taux du TAL (`tal_rates`) et la ligne E2 de `headline_table`. **Opération :** lire la
# fourchette des modèles, la vue réglementaire, les scénarios, la répartition par province et les limites.
# **Pourquoi :** une hausse isolée se lit avec sa fourchette, ses règles et ses limites. **Vérification :** chaque
# valeur est lue dans les résultats ou la configuration.

# %%
model_range, provinces, scenarios = headline["model_range"], headline["provinces"], results["scenarios"]
model_names = ", ".join(name.split("_")[0] for name in MODEL_RANGE_NAMES)
ranking = champion_info["ranking"]
best_holdout = ranking.dropna(subset=["mae_holdout_pp"]).sort_values("mae_holdout_pp").iloc[0]
tal_direction = "la baisse" if tal_now < tal_before else "la hausse" if tal_now > tal_before else "la stabilité"
champion_name = headline["model"]
holdout_clause = (f"{best_holdout['model']} a la meilleure erreur sur {holdout_year} ({pp(best_holdout['mae_holdout_pp'])}) ; "
                  f"passer à ce modèle reviendrait à choisir sur l'année de validation"
                  if best_holdout["model"] != champion_name else
                  f"le modèle retenu est aussi le meilleur sur {holdout_year} ({pp(best_holdout['mae_holdout_pp'])}), "
                  f"mais ce n'est pas ce qui a décidé le choix")
gap_to_e2_pp = headline["net_pct"] - e2_net
regulation = cfg["regulation"]["scenarios"]["ontario_post_2018_exemption"]
display(Markdown(
    f"**Fourchette {TARGET_YEAR} entre les modèles candidats ({model_names}) :** de {pct(model_range['low_net_pct'])} à "
    f"{pct(model_range['high_net_pct'])} (net).\n\n"
    f"**Vue réglementaire :** le pourcentage du TAL pour {TARGET_YEAR} est de {pct(tal_now)}, contre {pct(tal_before)} "
    f"pour {TARGET_YEAR - 1}. Il provient de la nouvelle méthode annoncée le "
    f"{french_date(cfg['anchors']['tal_method_announced'])} et n'est pas directement comparable aux années précédentes. Le modèle E2 "
    f"(renouvellements québécois ancrés sur le TAL) donne {pct(e2_net)} net.\n\n"
    f"**Pourquoi garder {champion_name} malgré {tal_direction} du TAL ?** "
    f"(a) La règle de choix a été déclarée avant tout résultat ; {holdout_clause}. "
    f"(b) L'avance de {champion_name} sur le deuxième modèle, sur les années de sélection, n'est que de "
    f"{pp(ranking_gap_pp)} : le classement est faible, et nous le disons. "
    f"(c) E2 est montré à côté comme vue réglementaire : {pct(e2_net)} net, avec une plage de scénarios de "
    f"{pct(scenarios['low_net_pct'])} à {pct(scenarios['high_net_pct'])}. "
    f"(d) L'écart {champion_name} − E2 est de {gap_to_e2_pp:+.{PP_DECIMALS}f} pp.\n\n"
    f"**Scénarios (net) :** bas {pct(scenarios['low_net_pct'])}, central {pct(scenarios['central_net_pct'])}, haut "
    f"{pct(scenarios['high_net_pct'])}. Ce sont des scénarios, pas des intervalles de prédiction.\n\n"
    f"**Québec :** {pct(provinces['QC']['net_pct'])} net ({pct(provinces['QC']['contract_pct'])} contractuel), sous "
    f"les règles du TAL. **Ontario :** {pct(provinces['ON']['net_pct'])} net ({pct(provinces['ON']['contract_pct'])} "
    f"contractuel), sous les règles ontariennes. Aucune règle n'est appliquée à l'autre province.\n\n"
    f"**Projet ontarien neuf (Ontario) :** scénario central : {regulation['central']} Scénario alternatif : "
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
