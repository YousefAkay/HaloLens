# ---
# jupyter:
#   jupytext:
#     formats: py:percent
# ---

# %% [markdown]
# ## 3. Effet de composition (mix)
#
# **Entrée :** `tables.leases` (baux renommés et typés, section 2).
# **Opération :** comparer, année par année, la hausse « naïve » (médiane des loyers des baux qui débutent dans
# l'année, comparée à celle de l'année précédente) avec la hausse à unité constante et à composition fixe
# (définition retenue, section 1), puis décomposer l'écart.
# **Pourquoi :** la médiane annuelle mélange l'évolution des prix avec le changement du mix de baux observés
# (immeubles, nombre de chambres, renouvellements vs relocations). Un immeuble neuf qui loue beaucoup une année
# suffit à déplacer la médiane sans qu'aucun loyer n'ait changé.
# **Vérification :** les parties s'additionnent exactement en points de log ; seuls des agrégats sont affichés.

# %%
import matplotlib.pyplot as plt
import pandas as pd
from IPython.display import Markdown, display

from leaselens.contracts import COLOR_CONTRACT, COLOR_NAIVE, COLOR_NET
from leaselens.measure.composition import mix_by_year, rent_bridge
from leaselens.measure.pairs import build_pairs

# %% [markdown]
# ### 3.1 Le mix des baux observés change d'une année à l'autre
# Étape qui transforme les données : les baux sont comptés par année de début, puis par immeuble et par type de bail
# (renouvellement ou relocation) ; on affiche les parts de chaque année.
# Ces parts décrivent les baux **observés dans l'extrait**, pas l'occupation ni le taux de roulement du
# portefeuille (que cet extrait ne permet pas de mesurer).

# %%
mix_building = mix_by_year(tables.leases, "building", cfg)
mix_renewal = mix_by_year(tables.leases, "is_renewal", cfg).rename(
    columns={True: "renouvellement", False: "relocation"})
display((mix_building * 100).round(1).rename_axis(columns="part des baux (%) par immeuble"))
display((mix_renewal * 100).round(1).rename_axis(columns="part des baux (%)"))

# %% [markdown]
# ### 3.2 Construction des paires et pont naïf → unité constante → net
# Étape qui transforme les données : les baux consécutifs d'une même unité (`sPropCode + sUnitCode`) sont
# appariés (détails et audit en section 4). Pour chaque année *y*, la hausse à unité constante utilise les poids de
# segment (`code de propriété × chambres × renouvellement`) gelés à la date de coupure de *y* (fin de l'année
# précédente, `forecast_years.cutoff_month_day`) et des seuils de winsorisation appris sur les paires connues à cette
# date, exactement comme les backtests.
#
# En points de log annuels :
# - **naïf = unité constante (contractuel) + composition et autres effets** (le résidu : mix, écarts entre baux) ;
# - **unité constante (net) = unité constante (contractuel) + effet des concessions** (pont loyer contractuel → loyer net de toutes les concessions).

# %%
pairs = build_pairs(tables.leases, cfg)
bridge = rent_bridge(tables.leases, pairs, cfg)
bridge_display = bridge[["year", "n_leases", "n_pairs", "naive_contract_pct", "same_unit_contract_pct",
                         "same_unit_net_pct", "composition_pp", "incentive_pp", "weight_coverage", "note"]].rename(
    columns={"year": "année", "n_leases": "baux", "n_pairs": "paires admissibles",
             "naive_contract_pct": "naïf, loyer contractuel (%)",
             "same_unit_contract_pct": "unité constante, loyer contractuel (%)",
             "same_unit_net_pct": "unité constante, loyer net (%)", "composition_pp": "composition (pts log)",
             "incentive_pp": "concessions (pts log)", "weight_coverage": "couverture des poids", "note": "note"})
display(bridge_display.round(2))

# %%
fig, (ax_levels, ax_parts) = plt.subplots(1, 2, figsize=(12, 4.5))
ax_levels.plot(bridge["year"], bridge["naive_contract_pct"], color=COLOR_NAIVE, linewidth=2, marker="o",
               label="Naïf (médiane annuelle, loyer contractuel)")
ax_levels.plot(bridge["year"], bridge["same_unit_contract_pct"], color=COLOR_CONTRACT, linewidth=2, marker="o",
               label="Unité constante, loyer contractuel")
ax_levels.plot(bridge["year"], bridge["same_unit_net_pct"], color=COLOR_NET, linewidth=2, marker="o",
               label="Unité constante, loyer net de toutes les concessions")
ax_levels.axhline(0, color="black", linewidth=0.8)
ax_levels.set_title("Hausse annuelle selon la mesure")
ax_levels.set_xlabel("Année (début du bail)")
ax_levels.set_ylabel("Hausse annualisée (%)")
ax_levels.legend(frameon=False)

bar_width = 0.4
ax_parts.bar(bridge["year"] - bar_width / 2, bridge["composition_pp"], width=bar_width, color=COLOR_NAIVE,
             label="Composition et autres (naïf − unité constante)")
ax_parts.bar(bridge["year"] + bar_width / 2, bridge["incentive_pp"], width=bar_width, color=COLOR_NET,
             label="Concessions (net − contractuel)")
ax_parts.axhline(0, color="black", linewidth=0.8)
ax_parts.set_title("Décomposition de l'écart")
ax_parts.set_xlabel("Année (début du bail)")
ax_parts.set_ylabel("Points de log annuels (×100)")
ax_parts.legend(frameon=False)
for axis in (ax_levels, ax_parts):
    axis.grid(axis="y", alpha=0.3)
    axis.spines[["top", "right"]].set_visible(False)
fig.tight_layout()
plt.show()

# %% [markdown]
# ### 3.3 Lecture

# %%
complete = bridge.dropna(subset=["naive_contract_pct", "same_unit_contract_pct"])
if complete.empty:
    display(Markdown("Aucune année ne permet la comparaison complète."))
else:
    latest = complete.iloc[-1]
    largest = complete.loc[complete["composition_pp"].abs().idxmax()]
    display(Markdown(
        f"En **{int(latest['year'])}**, la médiane naïve donne **{latest['naive_contract_pct']:.1f} %**, la hausse "
        f"contractuelle à unité constante **{latest['same_unit_contract_pct']:.1f} %** et la hausse nette de "
        f"toutes les concessions **{latest['same_unit_net_pct']:.1f} %**. L'effet de composition le plus fort de la période "
        f"est observé en **{int(largest['year'])}** ({largest['composition_pp']:+.1f} points de log) : la médiane "
        f"annuelle mesure alors surtout le changement de mix, pas la hausse des loyers. "
        f"C'est pourquoi la définition retenue compare chaque unité à elle-même, à poids de segment fixes."))
