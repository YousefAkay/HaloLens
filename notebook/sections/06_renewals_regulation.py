# ---
# jupyter:
#   jupytext:
#     formats: py:percent
# ---

# %% [markdown]
# ## 6. Renouvellements vs relocations, règles QC et ON
#
# **Entrée :** les paires admissibles (section 4, `build_pairs`) et les pourcentages publics de référence
# (`data/public/sources.csv` : pourcentage de référence du TAL pour le Québec, ligne directrice pour l'Ontario,
# chacun avec sa date de publication).
# **Opération :** séparer, par année et par province, la hausse des **renouvellements** (même locataire,
# `sRenewal`) de celle des **relocations** (nouveau locataire), puis comparer les renouvellements à la référence
# réglementaire de **leur propre province** ; enfin, présenter la matrice d'applicabilité des règles par immeuble.
# **Pourquoi :** les deux cas obéissent à des règles différentes. Cinq immeubles relèvent du Tribunal administratif
# du logement (Québec) et the Ontario new-build de la loi ontarienne ; une règle d'une province n'est jamais appliquée à l'autre.
# **Vérification :** les comptes de paires s'additionnent au total des paires admissibles ; seuls des agrégats sont
# affichés ; les cellules trop petites montrent leur compte sans hausse.

# %%
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
from IPython.display import Markdown, display

from leaselens.config import cutoff_for
from leaselens.contracts import COLOR_CONTRACT, COLOR_MARKET, COLOR_NET
from leaselens.market.registry import load_external
from leaselens.market.regulation import applicability_matrix, reference_lines, renewals_vs_reference
from leaselens.measure.pairs import build_pairs
from leaselens.measure.renewals import split_summary

LEASE_TYPE_FR = {"renewal": "renouvellement", "turnover": "relocation"}

# %% [markdown]
# ### 6.1 Hausse par type de bail et par province
# Étape qui transforme les données : les paires admissibles sont regroupées par année (début du bail le plus
# récent), province et type de bail. Les hausses annualisées sont écrêtées aux seuils de winsorisation appris sur
# les paires connues au 31 décembre de l'année précédente (même règle que la définition retenue). Ce sont des
# moyennes simples par cellule, pas l'indicateur à poids fixes. Une cellule de moins de
# `renewals.min_pairs_per_cell` paires n'affiche que son compte.

# %%
pairs = build_pairs(tables.leases, cfg)
split = split_summary(pairs, cfg)
display(Markdown(f"Paires admissibles réparties : **{int(split['n_pairs'].sum())}** "
                 f"(total admissible : **{int(pairs['eligible'].sum())}**)."))
split_display = split.assign(lease_type=split["lease_type"].map(LEASE_TYPE_FR))[
    ["year", "province", "lease_type", "n_pairs", "mean_contract_pct", "mean_net_pct", "median_contract_pct",
     "median_net_pct", "incentive_pp"]].rename(columns={
        "year": "année", "province": "province", "lease_type": "type de bail", "n_pairs": "paires",
        "mean_contract_pct": "moyenne contractuel (%)", "mean_net_pct": "moyenne net (%)",
        "median_contract_pct": "médiane contractuel (%)", "median_net_pct": "médiane net (%)",
        "incentive_pp": "incitatifs (pts log)"})
display(split_display.round(2))

# %% [markdown]
# ### 6.2 Renouvellements et référence réglementaire de leur province
# Étape qui transforme les données : les pourcentages publics sont rattachés à l'année à laquelle ils
# s'appliquent, puis joints aux renouvellements **sur l'année et la province**. Au Québec, le pourcentage du TAL
# (logement non chauffé, sans travaux majeurs) sert au calcul quand le Tribunal fixe le loyer : c'est un repère, pas
# un plafond. En Ontario, la ligne directrice plafonne les renouvellements des logements non exemptés. Une valeur
# publiée après la date de coupure de la prévision 2026 est marquée et n'est jamais utilisée pour prévoir.

# %%
external = load_external(Path(cfg["_root"]) / cfg["data"]["public_dir"] / cfg["external"]["sources_file"])
forecast_cutoff = cutoff_for(cfg["forecast_years"]["target_year"], cfg)
references = reference_lines(external, cfg, forecast_cutoff)
comparison = renewals_vs_reference(split, references)
display(comparison.rename(columns={
    "year": "année", "n_pairs": "paires (renouvellements)", "mean_contract_pct": "renouvellements contractuel (%)",
    "reference_pct": "référence publique (%)", "gap_pp": "écart (pts de %)", "release_date": "publiée le",
    "known_at_cutoff": "connue au 31-12-2025"}).round(2))

# %%
provinces = [province for province in ("QC", "ON") if province in set(split["province"])]
fig, axes = plt.subplots(1, len(provinces), figsize=(6 * len(provinces), 4.5), squeeze=False)
for axis, province in zip(axes[0], provinces):
    cells = split[split["province"] == province]
    for lease_type, style in (("renewal", "-"), ("turnover", "--")):
        rows = cells[cells["lease_type"] == lease_type]
        axis.plot(rows["year"], rows["mean_contract_pct"], color=COLOR_CONTRACT, linestyle=style, marker="o",
                  label=f"{LEASE_TYPE_FR[lease_type].capitalize()}, contractuel")
        axis.plot(rows["year"], rows["mean_net_pct"], color=COLOR_NET, linestyle=style, marker="o",
                  label=f"{LEASE_TYPE_FR[lease_type].capitalize()}, net des incitatifs")
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
# Une ligne par immeuble et type de bail. Les colonnes « central » et « alternatif » décrivent les scénarios
# utilisés par la prévision (section 11b) ; « contraignant » indique si la référence est un plafond légal dans ce
# scénario. Les années de premier bail sont observées dans l'extrait (agrégat par immeuble) et servent d'indice
# pour les clauses visant les immeubles récents. Cette matrice est une lecture des règles publiques pour construire
# des scénarios ; elle ne constitue jamais une détermination juridique.

# %%
matrix = applicability_matrix(cfg, tables.leases)
display(matrix.assign(lease_type=matrix["lease_type"].map(LEASE_TYPE_FR))[
    ["building", "province", "lease_type", "regime", "rule", "central", "alternative", "binding_central",
     "binding_alternative", "first_lease_year", "latest_phase_first_lease_year"]].rename(columns={
        "building": "immeuble", "province": "province", "lease_type": "type de bail", "regime": "régime",
        "rule": "règle", "central": "scénario central", "alternative": "scénario alternatif",
        "binding_central": "contraignant (central)", "binding_alternative": "contraignant (alternatif)",
        "first_lease_year": "premier bail (extrait)", "latest_phase_first_lease_year": "phase la plus récente"}))
display(Markdown(f"**Après la date de coupure :** {cfg['regulation']['post_cutoff_note']}"))

# %% [markdown]
# ### 6.4 Lecture

# %%
readable = comparison.dropna(subset=["mean_contract_pct"])
reference_name = {"QC": "le pourcentage du TAL (repère)", "ON": "la ligne directrice (plafond si non exempté)"}
lines = []
for province, rows in readable.groupby("province"):
    latest = rows.iloc[-1]
    above = int((rows["gap_pp"] > 0).sum())
    lines.append(f"- **{province}, {int(latest['year'])}** : renouvellements à **{latest['mean_contract_pct']:.1f} %** "
                 f"(contractuel, {int(latest['n_pairs'])} paires) contre **{latest['reference_pct']:.1f} %** pour "
                 f"{reference_name[province]}, écart de **{latest['gap_pp']:+.1f} points** ; les renouvellements "
                 f"dépassent la référence {above} année(s) sur {len(rows)}.")
ontario_above = readable[(readable["province"] == "ON") & (readable["gap_pp"] > 0)]
if not ontario_above.empty:
    lines.append("- En Ontario, des renouvellements au-dessus de la ligne directrice sont **cohérents** avec "
                 "l'exemption des logements occupés pour la première fois après le 15 novembre 2018 (scénario "
                 "central), sans la démontrer.")
by_type = split.pivot_table(index=["year", "province"], columns="lease_type", values="mean_contract_pct")
if {"renewal", "turnover"} <= set(by_type.columns):
    spread = (by_type["turnover"] - by_type["renewal"]).dropna().groupby(level="province").median()
    lines += [f"- **{province}** : écart relocation − renouvellement de **{value:+.1f} points** (médiane des "
              f"années observées, contractuel)." for province, value in spread.items()]
display(Markdown("\n".join(lines) if lines else "Pas assez de paires pour une lecture par province."))
display(Markdown(
    "Les relocations et les renouvellements sont donc prévus séparément (section 8), chacun avec la règle de sa "
    "province. Les parts de chaque type décrivent les transitions de baux **observées dans l'extrait**, pas le taux "
    "de roulement ni l'occupation du portefeuille, que cet extrait ne permet pas de mesurer."))
