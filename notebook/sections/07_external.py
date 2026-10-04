# ---
# jupyter:
#   jupytext:
#     formats: py:percent
# ---

# %% [markdown]
# ## 7. Données externes et dates de publication
#
# **Entrée :** `data/public/sources.csv`, un registre de séries publiques vérifiées à la main (SCHL, IPC loyer de
# Statistique Canada, pourcentages du TAL, ligne directrice de l'Ontario). Chaque ligne porte sa source (URL et
# emplacement), sa période de référence et sa **date de publication**. Il y a aussi les paires admissibles de la
# section 4.
# **Opération :** charger et valider le registre, présenter la provenance de chaque série, puis comparer la hausse à
# unité constante de l'extrait aux tendances du marché **de sa propre région** : immeubles du Québec avec la RMR de
# Montréal et l'IPC loyer du Québec, the Ontario new-build avec la RMR d'Ottawa et l'IPC loyer de l'Ontario.
# **Pourquoi :** situer la hausse interne par rapport au marché et vérifier qu'aucune donnée publique n'est utilisée
# avant sa date de publication.
# **Vérification :** le registre passe toutes les règles de validation, chaque série a une date de publication, une URL
# et un vérificateur. Seuls des agrégats sont affichés. Le taux d'inoccupation de la SCHL n'est qu'un **contexte
# régional** : cet extrait ne permet pas de mesurer l'occupation ou l'inoccupation de project.

# %%
from pathlib import Path

import matplotlib.pyplot as plt
from IPython.display import Markdown, display

from leaselens.config import external_cutoff_for
from leaselens.contracts import COLOR_CONTRACT, COLOR_MARKET, COLOR_NET
from leaselens.market.reconcile_market import provenance_table, reconcile, reconcile_summary
from leaselens.market.registry import as_of, load_external, validate_external
from leaselens.market.regulation import EXEMPTION_SCENARIO, applicability_matrix
from leaselens.measure.labels import french_date, french_month, french_month_day
from leaselens.measure.pairs import build_pairs

ROLE_FR = {"compared": "comparée (7.3)", "context_only": "contexte régional seulement",
           "reference": "référence (sections 6 et 8)"}
LEASE_TYPE_FR = {"all": "tous", "renewal": "renouvellement", "turnover": "relocation"}

# %% [markdown]
# ### 7.1 Chargement et validation du registre
# Étape qui transforme les données : le registre est lu avec des dates typées et des valeurs numériques. Il remplace
# la variable partagée `external` (jusqu'ici `None`), que les sections suivantes utilisent. Les données publiques ne
# servent à prévoir l'année *y* que si elles sont publiées au plus tard à la date d'information de *y* (règle approuvée
# par le mentor, dates affichées ci-dessous à partir de `config/core.yaml`) ; ce filtre est appliqué par `as_of` lors de
# chaque prévision et de chaque backtest.

# %%
external = load_external(Path(cfg["_root"]) / cfg["data"]["public_dir"] / cfg["external"]["sources_file"])
problems = validate_external(external, cfg)
target_year = cfg["forecast_years"]["target_year"]
info_date = external_cutoff_for(target_year, cfg)
usable = as_of(external, info_date)
info_day = french_month_day(cfg["forecast_years"]["external_cutoff_month_day"])
cutoff_day = french_month_day(cfg["forecast_years"]["cutoff_month_day"])
display(Markdown(
    f"**Date d'information :** une donnée publique sert à prévoir l'année *y* si elle est publiée au plus tard le "
    f"**{info_day} de *y***. Les baux restent coupés au **{cutoff_day} précédent** ; la version stricte (publication "
    f"au plus tard le {cutoff_day} précédent) est une sensibilité.\n\n"
    f"Registre : **{len(external)}** observations, **{external['series_id'].nunique()}** séries. "
    f"Validation : {'**aucun problème**' if not problems else '; '.join(problems)}. "
    f"Observations publiées au plus tard le {french_date(info_date)} (utilisables pour {target_year}) : "
    f"**{len(usable)}** ; publiées après : **{len(external) - len(usable)}** (exclues de la prévision)."))

# %% [markdown]
# ### 7.2 Provenance des séries
# Une ligne par série : éditeur, géographie, couverture, dernière date de publication, mode d'extraction (`manual` =
# saisie ou téléchargement officiel, `llm` = lu par un modèle sur une page publique puis vérifié à la main) et rôle
# dans l'analyse.

# %%
provenance = provenance_table(external, cfg)
display(provenance.assign(role=provenance["role"].map(ROLE_FR),
                          first_period=provenance["first_period"].dt.strftime("%Y-%m"),
                          last_period=provenance["last_period"].dt.strftime("%Y-%m"),
                          last_release_date=provenance["last_release_date"].dt.strftime("%Y-%m-%d")).rename(columns={
    "series_id": "série", "publisher": "éditeur", "geography": "géographie", "metric": "mesure", "role": "rôle",
    "n_observations": "observations", "first_period": "début", "last_period": "fin",
    "last_release_date": "dernière publication", "extracted_by": "extraction", "verified": "vérifiée",
    "url": "URL"}))

# %% [markdown]
# ### 7.3 Réconciliation : hausse interne à unité constante vs marché
# Étape qui transforme les données : pour chaque année (début du bail le plus récent) et chaque province, on calcule la
# moyenne simple de la hausse annualisée des paires admissibles. Elle est écrêtée aux seuils de winsorisation appris
# sur les paires connues à la date de coupure de l'année, comme en section 6. On la place ensuite à côté de la série
# publique de la **même région**. L'écart est en points de pourcentage (interne − marché). Ce ne sont pas des mesures
# identiques :
# - la SCHL suit un **échantillon fixe** d'immeubles locatifs de la RMR, mesuré chaque année au mois de son enquête
#   (variation d'une enquête à la suivante, mois affiché ci-dessous) ; l'extrait suit des **baux consécutifs** d'un
#   même logement, rattachés à l'année de début du bail ;
# - l'IPC loyer est une moyenne annuelle provinciale, tous types de logements locatifs confondus ;
# - le marché mesure des loyers payés ou demandés, sans concessions : la comparaison principale est donc le **loyer
#   contractuel** ; le loyer net de toutes les concessions est montré à côté.
#
# Cette comparaison est descriptive : elle ne sert pas à la prévision. Une année sans assez de paires (moins de
# `renewals.min_pairs_per_cell`) n'affiche pas de hausse interne.

# %%
pairs = build_pairs(tables.leases, cfg)
comparison = reconcile(pairs, external, cfg)
summary = reconcile_summary(comparison)
main_rows = comparison[comparison["lease_type"] == "all"].dropna(subset=["internal_contract_pct", "market_pct"])
display(main_rows[["label", "province", "geography", "year", "n_pairs", "internal_contract_pct", "internal_net_pct",
                   "market_pct", "gap_contract_pp", "gap_net_pp", "release_date"]].rename(columns={
    "label": "série publique", "province": "province", "geography": "géographie", "year": "année",
    "n_pairs": "paires", "internal_contract_pct": "interne, loyer contractuel (%)",
    "internal_net_pct": "interne, loyer net (%)", "market_pct": "marché (%)",
    "gap_contract_pp": "écart, loyer contractuel (pts)", "gap_net_pp": "écart, loyer net (pts)",
    "release_date": "publiée le"}).round(2))
cmhc_series = {series_id for comparison_cfg in cfg["reconcile_market"]["comparisons"]
               for series_id in comparison_cfg["series"].values() if series_id.startswith("cmhc")}
survey_months = sorted({french_month(date) for date in
                        external.loc[external["series_id"].isin(cmhc_series), "ref_period_start"]})
display(Markdown(f"Mois de l'enquête SCHL dans le registre : **{', '.join(survey_months) or 'aucun'}**."))

# %%
labels = {comparison_cfg["name"]: comparison_cfg["label"] for comparison_cfg in cfg["reconcile_market"]["comparisons"]}
market_styles = {"cmhc_total": "-", "rent_cpi": "--"}
provinces = [province for province in ("QC", "ON") if province in set(comparison["province"])]
fig, axes = plt.subplots(1, len(provinces), figsize=(6 * len(provinces), 4.5), squeeze=False, sharey=True)
for axis, province in zip(axes[0], provinces):
    internal = comparison[(comparison["comparison"] == "cmhc_total") & (comparison["province"] == province)]
    internal = internal.dropna(subset=["internal_contract_pct"])
    axis.plot(internal["year"], internal["internal_contract_pct"], color=COLOR_CONTRACT, marker="o",
              label="Extrait, loyer contractuel")
    axis.plot(internal["year"], internal["internal_net_pct"], color=COLOR_NET, marker="o",
              label="Extrait, loyer net de toutes les concessions")
    for name, style in market_styles.items():
        market = comparison[(comparison["comparison"] == name) & (comparison["province"] == province)]
        market = market.dropna(subset=["market_pct"])
        axis.plot(market["year"], market["market_pct"], color=COLOR_MARKET, linestyle=style, marker="s",
                  label=labels[name])
    geography = internal["geography"].dropna().iloc[0] if internal["geography"].notna().any() else province
    axis.axhline(0, color="black", linewidth=0.8)
    axis.set_title(f"{province} : extrait vs marché ({geography})")
    axis.set_xlabel("Année")
    axis.set_ylabel("Hausse annuelle (%)")
    axis.grid(axis="y", alpha=0.3)
    axis.spines[["top", "right"]].set_visible(False)
    axis.legend(frameon=False, fontsize="small")
fig.tight_layout()
plt.show()

# %% [markdown]
# ### 7.4 Renouvellements et relocations vs la répartition de la SCHL
# La SCHL publie, pour une seule taille de logement (nombre de chambres affiché ci-dessous), la hausse des logements
# **sans** changement de locataire et celle des logements **avec** changement de locataire. Étape qui transforme les
# données : on garde les paires admissibles de cette taille et on les sépare entre renouvellements et relocations.
# Les cellules ont la même règle de taille minimale.

# %%
split_beds = ", ".join(sorted({str(comparison_cfg["beds"]) for comparison_cfg in cfg["reconcile_market"]["comparisons"]
                                if comparison_cfg["lease_type"] != "all" and comparison_cfg["beds"] is not None}))
display(Markdown(f"Nombre de chambres comparé (`reconcile_market.comparisons`) : **{split_beds}**."))
split_rows = comparison[comparison["lease_type"] != "all"].dropna(subset=["internal_contract_pct", "market_pct"])
display(split_rows.assign(lease_type=split_rows["lease_type"].map(LEASE_TYPE_FR))[
    ["province", "lease_type", "year", "n_pairs", "internal_contract_pct", "internal_net_pct", "market_pct",
     "gap_contract_pp", "release_date"]].rename(columns={
        "province": "province", "lease_type": "type de bail", "year": "année", "n_pairs": f"paires ({split_beds} ch.)",
        "internal_contract_pct": "interne, loyer contractuel (%)", "internal_net_pct": "interne, loyer net (%)",
        "market_pct": "SCHL (%)", "gap_contract_pp": "écart, loyer contractuel (pts)", "release_date": "publiée le"}).round(2))

# %% [markdown]
# ### 7.5 Lecture

# %%
met_buildings = [entry["building"] for entry in cfg["regulation"]["buildings"]
                 if entry.get("scenario") == EXEMPTION_SCENARIO]
matrix = applicability_matrix(cfg, tables.leases)
met_years = matrix.loc[matrix["building"].isin(met_buildings), "first_lease_year"].dropna()
met_first_year = f"{int(met_years.min())}" if len(met_years) else "non observé"
lines = []
for row in summary.itertuples():
    direction = "plus vite" if row.mean_gap_contract_pp > 0 else "moins vite"
    lines.append(f"- **{row.province}, {row.label}** ({row.geography}, {row.n_years} année(s) comparables) : "
                 f"l'extrait progresse en moyenne **{abs(row.mean_gap_contract_pp):.1f} points {direction}** que le "
                 f"marché en loyer contractuel (écart absolu moyen {row.mean_abs_gap_contract_pp:.1f} points ; "
                 f"{row.mean_gap_net_pp:+.1f} points en loyer net de toutes les concessions).")
turnover = summary[summary["comparison"] == "cmhc_2br_turnover"]
if not turnover.empty and (turnover["mean_gap_contract_pp"] < 0).all():
    lines.append("- Les relocations de l'extrait progressent nettement moins que les logements « avec changement de "
                 "locataire » de la SCHL. Explication plausible : chez la SCHL, un changement de locataire rattrape "
                 "souvent plusieurs années de hausses encadrées pendant un long bail. Dans l'extrait, les paires "
                 f"admissibles relient des baux consécutifs séparés de moins de {cfg['pairs']['max_gap_years']} ans, "
                 "donc le rattrapage est faible.")
few_years = summary["n_years"] < len(cfg["forecast_years"]["backtest_years"])
if few_years.any():
    lines.append(f"- {int(few_years.sum())} comparaison(s) ont moins d'années communes que les années de backtest "
                 f"(premier bail de the Ontario new-build dans l'extrait : {met_first_year}) : ce sont des indications, pas des "
                 "estimations précises.")
display(Markdown("\n".join(lines) if lines else "Pas assez d'années communes pour une lecture."))
display(Markdown(
    "Le taux d'inoccupation de la SCHL figure dans le registre comme **contexte du marché régional** seulement. Ce "
    "n'est jamais un taux d'occupation ou d'inoccupation de project, que cet extrait ne permet pas de mesurer."))
