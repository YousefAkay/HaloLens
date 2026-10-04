# ---
# jupyter:
#   jupytext:
#     formats: py:percent
# ---

# %% [markdown]
# ## 6. Renouvellements vs relocations, règles QC et ON
#
# **Entrée :** les paires admissibles (section 4, `build_pairs`) et les pourcentages publics de référence
# (`data/public/sources.csv` : pourcentage du TAL pour le Québec, ligne directrice pour l'Ontario, chacun avec sa date
# de publication).
# **Opération :** séparer, par année et par province, la hausse des **renouvellements** (même locataire, `sRenewal`)
# de celle des **relocations** (nouveau locataire) ; comparer les renouvellements à la référence réglementaire de
# **leur propre province** ; présenter la matrice d'applicabilité des règles par immeuble.
# **Pourquoi :** les deux cas obéissent à des règles différentes. Les immeubles du Québec relèvent du Tribunal
# administratif du logement (TAL), the Ontario new-build de la loi ontarienne ; la règle d'une province n'est jamais appliquée à
# l'autre.
# **Vérification :** les comptes de paires s'additionnent au total des paires admissibles ; seuls des agrégats sont
# affichés ; une cellule trop petite montre son compte sans hausse.

# %%
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
from IPython.display import Markdown, display

from leaselens.config import cutoff_for, external_cutoff_for
from leaselens.contracts import COLOR_CONTRACT, COLOR_MARKET, COLOR_NET
from leaselens.forecast.asof import make_snapshot
from leaselens.forecast.combine import forecast_regulated
from leaselens.forecast.scenarios import CENTRAL, scenario_table
from leaselens.market.registry import load_external
from leaselens.market.regulation import (EXEMPTION_SCENARIO, applicability_matrix, exemption_evidence,
                                         reference_lines, renewals_vs_reference)
from leaselens.measure.labels import french_date, french_month_day, french_month_year
from leaselens.measure.pairs import build_pairs
from leaselens.measure.renewals import split_summary

LEASE_TYPE_FR = {"renewal": "renouvellement", "turnover": "relocation"}
MET_SCENARIO_ROW = "met_guideline_applies"
target_year = cfg["forecast_years"]["target_year"]
strict_label = f"{french_month_day(cfg['forecast_years']['cutoff_month_day'])} de l'année précédente"
info_label = f"{french_month_day(cfg['forecast_years']['external_cutoff_month_day'])} de l'année visée"
exemption_cutoff = french_date(cfg["regulation"]["ontario_post_2018_exemption_cutoff"])

# %% [markdown]
# ### 6.1 Hausse par type de bail et par province
# Étape qui transforme les données : les paires admissibles sont regroupées par année (début du bail le plus récent),
# province et type de bail. Les hausses annualisées sont écrêtées aux seuils de winsorisation appris sur les paires
# connues à la date de coupure de l'année (même règle que la définition retenue). Ce sont des moyennes simples par
# cellule, pas l'indicateur à poids fixes. Une cellule de moins de `renewals.min_pairs_per_cell` paires n'affiche que
# son compte.

# %%
pairs = build_pairs(tables.leases, cfg)
split = split_summary(pairs, cfg)
display(Markdown(f"Date de coupure des baux pour l'année *y* : **{strict_label}**. Paires admissibles réparties : "
                 f"**{int(split['n_pairs'].sum())}** (total admissible : **{int(pairs['eligible'].sum())}**)."))
split_display = split.assign(lease_type=split["lease_type"].map(LEASE_TYPE_FR))[
    ["year", "province", "lease_type", "n_pairs", "mean_contract_pct", "mean_net_pct", "median_contract_pct",
     "median_net_pct", "incentive_pp"]].rename(columns={
        "year": "année", "province": "province", "lease_type": "type de bail", "n_pairs": "paires",
        "mean_contract_pct": "moyenne loyer contractuel (%)", "mean_net_pct": "moyenne loyer net (%)",
        "median_contract_pct": "médiane loyer contractuel (%)", "median_net_pct": "médiane loyer net (%)",
        "incentive_pp": "concessions (pts log)"})
display(split_display.round(2))

# %% [markdown]
# ### 6.2 Renouvellements et référence réglementaire de leur province
# Étape qui transforme les données : les pourcentages publics sont rattachés à l'année à laquelle ils s'appliquent,
# puis joints aux renouvellements **sur l'année et la province**. Au Québec, le pourcentage du TAL (logement non
# chauffé, sans travaux majeurs) sert au calcul quand le Tribunal fixe le loyer : c'est un repère, pas un plafond.
# En Ontario, la ligne directrice plafonne les renouvellements des logements non exemptés.

# %%
display(Markdown(
    f"**Date d'information :** une donnée publique est utilisable pour l'année *y* si elle est publiée au plus tard le "
    f"**{info_label}** (règle approuvée par le mentor, appliquée de la même façon aux backtests ; les baux restent "
    f"coupés au {strict_label}). La version stricte (publication au plus tard le {strict_label}) est montrée comme "
    f"sensibilité."))

# %% [markdown]
# **Entrée :** le registre public `data/public/sources.csv` (pourcentages du TAL et lignes directrices de l'Ontario,
# avec leur date de publication) et le tableau des renouvellements de la section 6.1.
# **Opération :** charger le registre, en tirer une ligne de référence par année et par province (TAL pour le Québec,
# ligne directrice pour l'Ontario), puis la joindre aux renouvellements sur l'année et la province. Chaque référence
# est marquée selon qu'elle était publiée ou non à la date d'information (et à la date stricte, en sensibilité).
# **Pourquoi :** comparer la hausse des renouvellements au repère réglementaire de **sa propre** province, sans
# jamais appliquer la règle d'une province à l'autre.
# **Vérification :** la jointure se fait sur l'année **et** la province ; seules les années de renouvellement qui ont
# une référence publiée dans leur province sont comparées (les autres restent dans le tableau 6.1) ; seuls des
# agrégats sont affichés.

# %%
external = load_external(Path(cfg["_root"]) / cfg["data"]["public_dir"] / cfg["external"]["sources_file"])
references = reference_lines(external, cfg)
comparison = renewals_vs_reference(split, references)
strict_sensitivity = cfg["forecast_years"]["external_cutoff_strict_sensitivity"]
known_columns = {"known_by_info_date": f"publiée au plus tard le {info_label}"}
if strict_sensitivity:
    known_columns["known_by_strict_cutoff"] = f"sensibilité : publiée au plus tard le {strict_label}"
display(comparison.drop(columns=[] if strict_sensitivity else ["known_by_strict_cutoff"]).rename(columns={
    "year": "année", "n_pairs": "paires (renouvellements)", "mean_contract_pct": "renouvellements, loyer contractuel (%)",
    "reference_pct": "référence publique (%)", "gap_pp": "écart (pts de %)", "release_date": "publiée le",
    **known_columns}).round(2))

info_date = external_cutoff_for(target_year, cfg)
strict_date = cutoff_for(target_year, cfg)
target_lines = references[references["year"] == target_year]
target_text = "; ".join(
    f"{row.province} {row.reference_pct:.1f} % (publié le {french_date(row.release_date)}, "
    f"{'connu' if row.known_by_info_date else 'inconnu'} au {french_date(info_date)}"
    + (f", {'connu' if row.known_by_strict_cutoff else 'inconnu'} au {french_date(strict_date)}" if strict_sensitivity
       else "") + ")"
    for row in target_lines.itertuples())
quebec_target = target_lines[target_lines["province"] == "QC"]
note = ""
if not quebec_target.empty:
    tal = quebec_target.iloc[0]
    note = cfg["regulation"]["post_cutoff_note"].format(
        target_year=target_year, tal_release=french_date(tal["release_date"]), info_date=french_date(info_date),
        method_change=french_date(cfg["regulation"]["quebec_method_change_date"]),
        strict_cutoff=french_date(strict_date),
        strict_known="serait aussi connu" if tal["known_by_strict_cutoff"] else "ne serait pas connu")
display(Markdown(f"**Références pour {target_year} :** {target_text or 'aucune'}.\n\n{note}"))

# %%
provinces = [province for province in ("QC", "ON") if province in set(split["province"])]
fig, axes = plt.subplots(1, len(provinces), figsize=(6 * len(provinces), 4.5), squeeze=False)
for axis, province in zip(axes[0], provinces):
    cells = split[split["province"] == province]
    for lease_type, style in (("renewal", "-"), ("turnover", "--")):
        rows = cells[cells["lease_type"] == lease_type]
        axis.plot(rows["year"], rows["mean_contract_pct"], color=COLOR_CONTRACT, linestyle=style, marker="o",
                  label=f"{LEASE_TYPE_FR[lease_type].capitalize()}, loyer contractuel")
        axis.plot(rows["year"], rows["mean_net_pct"], color=COLOR_NET, linestyle=style, marker="o",
                  label=f"{LEASE_TYPE_FR[lease_type].capitalize()}, loyer net de toutes les concessions")
    line = references[(references["province"] == province) & references["year"].between(
        cells["year"].min(), cells["year"].max())]
    label = "Pourcentage du TAL (repère)" if province == "QC" else "Ligne directrice de l'Ontario"
    axis.step(line["year"], line["reference_pct"], where="mid", color=COLOR_MARKET, linewidth=2, label=label)
    axis.axhline(0, color="black", linewidth=0.8)
    axis.set_title(f"{province} : renouvellements vs relocations")
    axis.set_xlabel("Année (début du bail)")
    axis.set_ylabel("Hausse annualisée moyenne (%)")
    axis.grid(axis="y", alpha=0.3)
    axis.spines[["top", "right"]].set_visible(False)
    axis.legend(frameon=False, fontsize="small")
fig.tight_layout()
plt.show()

# %% [markdown]
# ### 6.3 Matrice d'applicabilité des règles (scénarios, pas un avis juridique)
# Une ligne par immeuble et type de bail. Les colonnes « central » et « alternatif » décrivent les scénarios utilisés
# par la prévision (section 11b) ; « contraignant » indique si la référence est un plafond légal dans ce scénario. Les
# années de premier bail sont observées dans l'extrait (agrégat par immeuble) et servent d'indice pour les clauses
# visant les immeubles récents. Cette matrice est une lecture des règles publiques pour construire des scénarios ;
# elle ne constitue jamais une détermination juridique.

# %%
matrix = applicability_matrix(cfg, tables.leases)
regime_counts = pd.Series([entry["province"] for entry in cfg["regulation"]["buildings"]]).value_counts()
display(Markdown(", ".join(f"**{count}** immeuble(s) en {province}" for province, count in regime_counts.items())
                 + " ; chaque immeuble suit uniquement la règle de sa province."))
display(matrix.assign(lease_type=matrix["lease_type"].map(LEASE_TYPE_FR))[
    ["building", "province", "lease_type", "regime", "rule", "central", "alternative", "binding_central",
     "binding_alternative", "first_lease_year", "latest_phase_first_lease_year"]].rename(columns={
        "building": "immeuble", "province": "province", "lease_type": "type de bail", "regime": "régime",
        "rule": "règle", "central": "scénario central", "alternative": "scénario alternatif",
        "binding_central": "contraignant (central)", "binding_alternative": "contraignant (alternatif)",
        "first_lease_year": "premier bail (extrait)", "latest_phase_first_lease_year": "phase la plus récente"}))

# %% [markdown]
# ### 6.4 the Ontario new-build : pourquoi le scénario central retient l'exemption
# Le scénario central suppose que les renouvellements de the Ontario new-build ne sont pas plafonnés par la ligne directrice. Les
# preuves ci-dessous viennent de sources indépendantes : la loi, un fait public sur l'immeuble (presse spécialisée) et
# ce que montrent les baux de l'extrait (agrégats seulement). Étape qui transforme les données : pour chaque
# renouvellement admissible de the Ontario new-build, la hausse du loyer contractuel non annualisée (loyer / loyer précédent − 1) est
# comparée à la ligne directrice de son année ; un renouvellement est « au-dessus » s'il la dépasse de plus de
# `regulation.exemption_evidence.above_reference_tolerance_pp` point (arrondi au cent).

# %%
evidence_settings = cfg["regulation"]["exemption_evidence"]
evidence_years = list(cfg["forecast_years"]["backtest_years"])
met_entries = [entry for entry in cfg["regulation"]["buildings"] if entry.get("scenario") == EXEMPTION_SCENARIO]
met_buildings = [entry["building"] for entry in met_entries]
met_evidence = exemption_evidence(pairs, references, cfg, evidence_years)
met_first_year = matrix.loc[matrix["building"].isin(met_buildings), "first_lease_year"].dropna()
display(met_evidence.rename(columns={
    "year": "année", "n_renewals": "renouvellements admissibles", "n_above_reference": "au-dessus de la ligne directrice",
    "share_above_reference": "part au-dessus", "reference_pct": "ligne directrice (%)"}).round(2))

share_text = ", ".join(
    f"{int(row.year)} : {row.n_above_reference}/{row.n_renewals} ({row.share_above_reference:.0%})" if row.n_renewals
    else f"{int(row.year)} : aucun renouvellement admissible" for row in met_evidence.itertuples())
first_text = f"{int(met_first_year.min())}" if len(met_first_year) else "non observée (données synthétiques)"
occupancy_fact = (
    f"the Ontario new-build ({evidence_settings['building_address']}), projet locatif de {evidence_settings['building_units']} "
    f"logements, a commencé à être occupée en {french_month_year(evidence_settings['occupancy_start_month'])} "
    f"({evidence_settings['occupancy_source_label']}, {french_date(evidence_settings['occupancy_source_date'])}), "
    f"soit après le {exemption_cutoff}.")
display(Markdown(
    f"1. **Loi** — {evidence_settings['law_citation']}, résumée par le gouvernement de l'Ontario "
    f"([ontario.ca]({evidence_settings['law_url']})) : les nouveaux immeubles occupés pour la première fois à des fins "
    f"résidentielles après le {exemption_cutoff} sont exemptés du contrôle des loyers.\n"
    f"2. **Fait public** — {occupancy_fact} ([source]({evidence_settings['occupancy_url']})) "
    f"Aucune source officielle datée (Ville d'Ottawa, propriétaire) n'a été trouvée.\n"
    f"3. **Extrait interne** — premier bail de the Ontario new-build dans l'extrait : **{first_text}**.\n"
    f"4. **Comportement observé** — renouvellements au-dessus de la ligne directrice, par année : {share_text}.\n\n"
    f"**Conclusion :** scénario central = **exemption** (la ligne directrice ne plafonne pas les renouvellements de "
    f"the Ontario new-build) ; scénario alternatif = **la ligne directrice s'applique**. Ce choix repose sur des preuves publiques "
    f"et internes concordantes ; ce n'est pas une détermination juridique."))

# %% [markdown]
# #### Effet du scénario the Ontario new-build sur la prévision
# Étape qui transforme les données : on prend la prévision réglementée de FCT pour l'année visée (`forecast_regulated`,
# baux coupés à la date de coupure, données publiques à la date d'information) et son tableau de scénarios
# (`scenario_table`, section 11b). On lit l'écart entre le scénario central (exemption) et le scénario où la ligne
# directrice s'applique aux renouvellements de the Ontario new-build. Les poids décrivent le mix des transitions de baux observées,
# pas l'occupation du portefeuille.

# %%
met_snapshot = make_snapshot(tables, external, cutoff_for(target_year, cfg), external_cutoff_for(target_year, cfg))
met_result = forecast_regulated(met_snapshot, cfg)
met_scenarios = scenario_table(met_result, cfg).set_index("scenario")
met_provinces = {entry["province"] for entry in met_entries}
met_segments = met_result.segments
met_renewal_weight = float(met_segments.loc[met_segments["province"].isin(met_provinces)
                                            & met_segments["is_renewal"].astype(bool), "weight"].sum())
if MET_SCENARIO_ROW in met_scenarios.index and pd.notna(met_scenarios.loc[MET_SCENARIO_ROW, "headline_net_pct"]):
    central_pct = met_scenarios.loc[CENTRAL, "headline_net_pct"]
    alternative_pct = met_scenarios.loc[MET_SCENARIO_ROW, "headline_net_pct"]
    delta_pp = met_scenarios.loc[MET_SCENARIO_ROW, "delta_net_pp"]
    display(Markdown(
        f"Appliquer la ligne directrice aux renouvellements de the Ontario new-build change la hausse {target_year} (loyer net de "
        f"toutes les concessions) de **{delta_pp:+.2f} point** ({central_pct:.2f} % → {alternative_pct:.2f} %), car "
        f"ces renouvellements ne pèsent que **{met_renewal_weight:.1%}** des poids fixes."))
else:
    display(Markdown("Le scénario « ligne directrice appliquée à the Ontario new-build » ne peut pas être calculé avec ces données."))

# %% [markdown]
# ### 6.5 Lecture

# %%
readable = comparison.dropna(subset=["mean_contract_pct"])
reference_name = {"QC": "le pourcentage du TAL (repère)", "ON": "la ligne directrice (plafond si non exempté)"}
lines = []
for province, rows in readable.groupby("province"):
    latest = rows.iloc[-1]
    above = int((rows["gap_pp"] > 0).sum())
    lines.append(f"- **{province}, {int(latest['year'])}** : renouvellements à **{latest['mean_contract_pct']:.1f} %** "
                 f"(loyer contractuel, {int(latest['n_pairs'])} paires) contre **{latest['reference_pct']:.1f} %** "
                 f"pour {reference_name[province]}, écart de **{latest['gap_pp']:+.1f} points** ; les renouvellements "
                 f"dépassent la référence {above} année(s) sur {len(rows)}.")
ontario_above = readable[(readable["province"] == "ON") & (readable["gap_pp"] > 0)]
if not ontario_above.empty:
    lines.append("- En Ontario, des renouvellements au-dessus de la ligne directrice sont **cohérents** avec "
                 f"l'exemption des logements occupés pour la première fois après le {exemption_cutoff} (scénario "
                 "central), sans la démontrer.")
by_type = split.pivot_table(index=["year", "province"], columns="lease_type", values="mean_contract_pct")
if {"renewal", "turnover"} <= set(by_type.columns):
    spread = (by_type["turnover"] - by_type["renewal"]).dropna().groupby(level="province").median()
    lines += [f"- **{province}** : écart relocation − renouvellement de **{value:+.1f} points** (médiane des "
              f"années observées, loyer contractuel)." for province, value in spread.items()]
display(Markdown("\n".join(lines) if lines else "Pas assez de paires pour une lecture par province."))
display(Markdown(
    "Les relocations et les renouvellements sont donc prévus séparément (section 8), chacun avec la règle de sa "
    "province. Les parts de chaque type décrivent les transitions de baux **observées dans l'extrait**, pas le taux "
    "de roulement ni l'occupation du portefeuille, que cet extrait ne permet pas de mesurer."))
