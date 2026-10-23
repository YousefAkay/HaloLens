# ---
# jupyter:
#   jupytext:
#     formats: py:percent
# ---

# %% [markdown]
# ## 5. Concessions : loyer contractuel vs loyer net
#
# **Objectif :** Établir ce que contient `sRentEffective` (loyer net de toutes les concessions), traiter `PromoPay` comme
# crédit ponctuel, vérifier l'inclusion des accessoires et expliquer la divergence entre loyer contractuel et loyer net dès 2024.
#
# **Entrée :** `tables.leases` (loyer contractuel `rent_contract`, loyer net `rent_net_all_incentives`) et `tables.concessions`
# (crédits par code de charge). **Opération :** relier chaque concession à un bail de la même unité, reconstruire le loyer net à
# partir des crédits, puis comparer à la valeur déclarée. **Pourquoi :** le loyer net est la cible de notre définition (§9.1) ;
# il faut savoir exactement ce qu'il contient. **Vérification :** taux de réconciliation, comparaison avec les hypothèses rejetées.
#
# Hypothèse de travail : `loyer net = loyer contractuel − (crédits ponctuels + crédits mensuels × mois) / durée du bail`.
# Les crédits `PromoPay` comptent **une seule fois** ; aucun montant n'est multiplié par autre chose que `sMonths` (crédits mensuels).
# Seuls des décomptes et des agrégats sont affichés : aucune ligne, aucun code d'unité.

# %%
from halolens.contracts import COLOR_CONTRACT, COLOR_NET
from halolens.incentives.linking import link_concessions
from halolens.incentives.reconcile import (divergence_by_year, hypothesis_comparison, reconciliation_by_year,
                                            reconciliation_rate, reconstruct_net_rent)
from halolens.measure.pairs import build_pairs

# %% [markdown]
# ### 5.1 Lier chaque concession à un bail
#
# **Opération :** les concessions n'ont pas d'identifiant de bail. Candidats : baux de la même unité, signés au plus tard à la date
# de début de la concession et non terminés avant elle. Un seul candidat → `unique`. Plusieurs → on essaie toutes les affectations
# conjointes de la même unité et on garde celle dont le loyer net reconstruit colle le mieux au loyer déclaré (`resolved_by_fit`) ;
# les cas indiscernables restent `unresolved`. Cette étape ne modifie aucune donnée source : elle crée la table de liens.

# %%
links = link_concessions(tables.concessions, tables.leases, cfg)
status_counts = links.groupby(["status", "rule"]).size().rename("n_concessions").reset_index()
display(status_counts)
display(Markdown(f"**{len(links)}** concessions ; **{int((links['status'] != 'unresolved').sum())}** reliées à un bail."))

# %% [markdown]
# ### 5.2 Reconstruire le loyer net et mesurer la réconciliation
#
# **Opération :** pour chaque bail, loyer net reconstruit = loyer contractuel − crédits liés / durée (en mois, calculée à partir
# des dates du bail, pas `sTermMonths`). **Vérification :** taux de baux dont l'écart est inférieur à la tolérance de
# `config/forecast.yaml` (`linking.recon_tolerance_dollars`), en général et pour les seuls baux avec rabais.

# %%
rebuilt = reconstruct_net_rent(tables.leases, tables.concessions, links)
rate_all = reconciliation_rate(rebuilt, cfg)
rate_discounted = reconciliation_rate(rebuilt, cfg, only_discounted=True)
display(Markdown(f"Taux de réconciliation : **{rate_all:.1%}** de tous les baux ({len(rebuilt)}) ; "
                 f"**{rate_discounted:.1%}** des baux avec rabais."))
display(reconciliation_by_year(rebuilt, cfg).round(3))

# %% [markdown]
# ### 5.3 PromoPay est un crédit ponctuel ; les accessoires sont inclus
#
# **Opération :** on compare trois reconstructions : (1) hypothèse retenue (ponctuel une fois, tous les codes) ; (2) hypothèse
# rejetée où `PromoPay` serait multiplié par `sMonths` ; (3) hypothèse rejetée où les accessoires (stationnement, casier,
# électroménagers) seraient exclus. **Pourquoi :** une hypothèse fausse produirait des écarts systématiques.

# %%
promo = tables.concessions[tables.concessions["credit_kind"] == "lump"]
display(promo["months"].value_counts().rename("n_credits PromoPay par valeur de sMonths").to_frame())
comparison = hypothesis_comparison(tables.leases, tables.concessions, links, cfg)
display(comparison.round(3))

# %% [markdown]
# ### 5.4 Divergence entre croissance contractuelle et nette
#
# **Opération :** par année de début de bail, part des baux avec concession, rabais moyen (1 − net/contrat) et croissance médiane
# annualisée des paires d'unités (`build_pairs`, section 4) sur le loyer contractuel et sur le loyer net. **Pourquoi :** quand les
# concessions deviennent plus fréquentes ou plus généreuses, le loyer net croît moins vite que le loyer contractuel ;
# c'est ce qui rend le choix du loyer net déterminant pour la hausse 2026.

# %%
pairs = build_pairs(tables.leases, cfg)
divergence = divergence_by_year(tables.leases, pairs)
display(divergence.round(3))

fig, ax = plt.subplots(figsize=(7, 3.5))
shown = divergence.dropna(subset=["median_contract_pct"])
ax.plot(shown["year"], shown["median_contract_pct"], marker="o", color=COLOR_CONTRACT, label="Loyer contractuel")
ax.plot(shown["year"], shown["median_net_pct"], marker="o", color=COLOR_NET, label="Loyer net")
ax.set_xlabel("Année de début du bail")
ax.set_ylabel("Croissance annualisée médiane (%)")
ax.set_title("Croissance à unité constante : contractuel vs net")
ax.legend()
plt.tight_layout()
plt.show()

# %%
latest = divergence.dropna(subset=["gap_pp"]).iloc[-1]
display(Markdown(
    f"En **{int(latest['year'])}**, **{latest['share_with_concession']:.0%}** des baux comportent une concession "
    f"(rabais moyen **{latest['mean_discount_share']:.1%}** du loyer) et l'écart médian entre croissance nette et contractuelle "
    f"est de **{latest['gap_pp']:+.1f}** point de pourcentage. Le loyer net reflète donc des concessions que le loyer "
    f"contractuel ignore ; c'est pourquoi notre définition de la hausse repose sur le loyer net de toutes les concessions."))
