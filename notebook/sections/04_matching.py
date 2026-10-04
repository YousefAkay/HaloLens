# ---
# jupyter:
#   jupytext:
#     formats: py:percent
# ---

# %% [markdown]
# ## 4. Appariement à unité constante
#
# **Entrée :** `raw["leases"]` (fichier source, pour la démonstration de clé) et `tables.leases`.
# **Opération :** apparier chaque bail au bail précédent de la même unité, sur la clé `sPropCode + sUnitCode`
# (jamais `sSite + sUnitCode`), recoupée avec `hUnit` ; calculer la croissance annualisée en log ; écarter les
# paires hors bornes en conservant un motif d'exclusion pour chacune.
# **Pourquoi :** comparer une unité à elle-même neutralise la taille, l'étage, l'immeuble et l'orientation.
# **Vérification :** décomptes par motif d'exclusion, couverture par année et sensibilité aux bornes d'écart.
# Aucun code d'unité ni `hUnit` n'est affiché.

# %%
import matplotlib.pyplot as plt
import pandas as pd
from IPython.display import Markdown, display

from leaselens.contracts import COLOR_CONTRACT, COLOR_NAIVE
from leaselens.measure.pairs import build_pairs, exclusion_summary, gap_sensitivity, key_comparison

# %% [markdown]
# ### 4.1 Pourquoi jamais `sSite + sUnitCode`
# Un même site regroupe plusieurs codes de propriété dont les numéros d'unité se recoupent. Avec la clé
# `sSite + sUnitCode`, des appartements différents partagent une clé et seraient « appariés » entre eux.
# Le tableau compte, pour chaque clé, les clés qui mélangent plusieurs unités (`hUnit`) et les paires
# consécutives qui compareraient deux appartements différents. C'est le seul endroit où `sSite` est lu.

# %%
keys = key_comparison(raw["leases"]).rename(columns={
    "key": "clé", "n_keys": "clés distinctes", "n_units": "unités (hUnit)",
    "n_keys_with_several_units": "clés à plusieurs unités", "n_leases_in_mixed_keys": "baux dans ces clés",
    "n_cross_unit_pairs": "paires entre deux unités différentes"})
display(keys)

# %% [markdown]
# ### 4.2 Construction des paires et audit des exclusions
# Étape qui transforme les données : baux triés par début de bail dans chaque unité, puis paire (bail précédent,
# bail courant). Règles d'admissibilité (`config/measure.yaml`) : écart entre débuts de bail strictement compris
# entre les bornes configurées, deux loyers positifs, même `hUnit` des deux côtés. Une paire appartient à l'année
# du début de son bail le plus récent. Chaque paire rejetée garde son motif ; une paire peut en cumuler plusieurs.

# %%
pairs = build_pairs(tables.leases, cfg)
n_units = tables.leases.groupby(cfg["pairs"]["unit_key"]).ngroups
display(Markdown(
    f"Baux : **{len(tables.leases)}** · unités : **{n_units}** · paires consécutives : **{len(pairs)}** "
    f"(= baux − unités) · admissibles : **{int(pairs['eligible'].sum())}** "
    f"({pairs['eligible'].mean() * 100:.1f} %)."))
display(exclusion_summary(pairs).rename(columns={"exclusion_reason": "motif", "n_pairs": "paires"}))

# %% [markdown]
# ### 4.3 Couverture par année et par province
# Part des baux débutant dans l'année qui ont un bail précédent apparié et admissible. Les premiers baux
# d'une unité (aucun précédent dans l'extrait) ne peuvent pas entrer dans la mesure à unité constante.

# %%
leases_per_year = (tables.leases.assign(year=tables.leases["lease_start"].dt.year)
                   .groupby(["year", "province"]).size().rename("baux"))
pairs_per_year = pairs.groupby(["year", "province"]).agg(
    paires=("eligible", "size"), admissibles=("eligible", "sum"))
coverage = pd.concat([leases_per_year, pairs_per_year], axis=1).fillna(0).astype(int)
coverage["couverture (%)"] = (coverage["admissibles"] / coverage["baux"] * 100).round(1)
coverage = coverage[coverage.index.get_level_values("year") >= cfg["composition"]["naive_years_start"]]
display(coverage.rename_axis(index=["année", "province"]))

# %% [markdown]
# ### 4.4 Écart entre baux consécutifs et sensibilité aux bornes
# Le graphique montre la distribution des écarts (en années) entre deux débuts de bail d'une même unité, avec
# les bornes retenues. Le tableau compare la médiane de croissance annualisée avec les bornes de base et avec
# une borne inférieure qui admet les baux de 6 mois.

# %%
min_gap, max_gap = cfg["pairs"]["min_gap_years"], cfg["pairs"]["max_gap_years"]
gaps = pairs["gap_years"].dropna()
fig, ax = plt.subplots(figsize=(8, 4))
ax.hist(gaps, bins="auto", color=COLOR_CONTRACT, edgecolor="white", linewidth=0.5)
for bound, label, align in ((min_gap, "borne inférieure", "left"), (max_gap, "borne supérieure", "right")):
    ax.axvline(bound, color=COLOR_NAIVE, linestyle="--", linewidth=1.5)
    ax.text(bound, 1, f" {label} ({bound} an) ", transform=ax.get_xaxis_transform(), va="top", ha=align,
            fontsize=9)
ax.set_title("Écart entre deux baux consécutifs d'une même unité")
ax.set_xlabel("Écart entre débuts de bail (années)")
ax.set_ylabel("Nombre de paires")
ax.spines[["top", "right"]].set_visible(False)
fig.tight_layout()
plt.show()

# %%
sensitivity = gap_sensitivity(pairs, cfg).rename(columns={
    "scenario": "scénario", "min_gap_years": "écart min (ans)", "max_gap_years": "écart max (ans)",
    "n_eligible": "paires admissibles", "median_contract_pct": "médiane contractuel (%)",
    "median_net_pct": "médiane net (%)"})
display(sensitivity.round(2))
base, wide = sensitivity.iloc[0], sensitivity.iloc[1]
shift_pp = wide["médiane net (%)"] - base["médiane net (%)"]
tolerance_pp = cfg["headline"]["change_tolerance_pp"]
display(Markdown(
    f"Admettre les baux de 6 mois ajoute **{int(wide['paires admissibles'] - base['paires admissibles'])}** paires "
    f"et déplace la médiane nette de **{shift_pp:+.2f} point(s)**, "
    f"{'sous' if abs(shift_pp) < tolerance_pp else 'au-delà de'} la tolérance de {tolerance_pp} point "
    f"fixée dans `config/core.yaml` : la mesure est {'peu' if abs(shift_pp) < tolerance_pp else 'sensiblement'} "
    f"sensible à la borne inférieure."))
