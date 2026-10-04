# ---
# jupyter:
#   jupytext:
#     formats: py:percent
# ---

# %% [markdown]
# ## 8. Méthode de prévision
#
# **Objectif :** définir la cible, fixer ce qui est connu à la date de coupure, présenter les modèles de référence et les
# moteurs, et annoncer à l'avance la règle qui choisira le modèle retenu.
#
# **Entrée :** `tables` (baux, rabais, loyers affichés), `external` (sources publiques vérifiées) et `cfg` (paramètres de
# `config/*.yaml`). **Opération :** construire un instantané de ce qui était connu à chaque date de coupure, puis appliquer
# chaque modèle à cet instantané. **Pourquoi :** une prévision n'est honnête que si rien de postérieur à sa date de
# coupure n'y entre ; c'est pourquoi tous les modèles lisent leurs données par une seule fonction (`snapshot_for_year`).
# **Vérification :** des tests automatiques ajoutent de fausses lignes futures et vérifient que rien ne change.
#
# **Cible.** Croissance à composition fixe, à unité constante, du loyer net de tous les incitatifs : pour chaque paire de
# baux consécutifs d'une même unité, log-croissance annualisée du loyer net ; moyenne par segment
# (code de propriété × chambres × renouvellement ou relocation), winsorisée avec des seuils appris sur les données d'entraînement
# seulement ; agrégation avec des poids fixes (parts de chaque segment parmi les paires admissibles de la fenêtre qui
# précède la coupure). Ces poids décrivent la composition des transitions de baux observées, **pas** un taux d'occupation.

# %%
from pathlib import Path

import pandas as pd

from leaselens.config import cutoff_for, external_cutoff_for
from leaselens.evaluate.backtest import all_models, french_day_month
from leaselens.forecast.asof import snapshot_for_year
from leaselens.forecast.baselines import frozen_weights, training_pairs
from leaselens.market.registry import load_external

if external is None:
    external = load_external(Path(cfg["_root"]) / cfg["data"]["public_dir"] / cfg["external"]["sources_file"])

# %% [markdown]
# ### 8.1 Ce qui est connu à la date de coupure
#
# **Opération :** les données du CRM (baux, rabais, loyers affichés) sont coupées à la fin de l'année précédant la
# prévision. Les données publiques (TAL, IPC, SCHL, ligne directrice ontarienne) sont coupées un peu plus tard, règle
# approuvée par le mentor : le pourcentage du TAL et l'IPC annuel sont publiés tôt dans l'année cible. La version stricte
# (même date que le CRM) est conservée comme sensibilité. Les dates exactes sont affichées ci-dessous, lues de la
# configuration. Un bail compte comme connu seulement si sa **signature et son début** précèdent la coupure.

# %%
target_year = cfg["forecast_years"]["target_year"]
snapshot_jan31 = snapshot_for_year(tables, external, target_year, cfg)
snapshot_strict = snapshot_for_year(tables, external, target_year, cfg, strict=True)
crm_day = french_day_month(cutoff_for(target_year, cfg))
public_day = french_day_month(external_cutoff_for(target_year, cfg))
display(Markdown(
    f"Prévision **{target_year}** : coupure du CRM au **{crm_day} {target_year - 1}** ; données publiques au "
    f"**{public_day} {target_year}** (règle retenue, {len(snapshot_jan31.external)} observations) ou au "
    f"**{crm_day} {target_year - 1}** (sensibilité stricte, {len(snapshot_strict.external)} observations)."))
display(pd.DataFrame({
    "table": ["baux", "rabais (concessions)", "loyers affichés"],
    "lignes dans les données": [len(tables.leases), len(tables.concessions), len(tables.asking)],
    "lignes connues à la coupure": [len(snapshot_jan31.leases), len(snapshot_jan31.concessions), len(snapshot_jan31.asking)]}))

# %% [markdown]
# ### 8.2 Les modèles
#
# **Opération :** des modèles de référence simples et des moteurs sont comparés avec exactement le même protocole.
# Les modèles de référence servent d'étalon : un moteur qui ne les bat pas ne mérite pas sa complexité.
#
# | Modèle | Idée | Données publiques |
# |---|---|---|
# | **B0** année précédente | répète la croissance de l'année précédente (même définition) | non |
# | **B1** moyenne mobile | moyenne des années de la fenêtre qui précède la coupure | non |
# | **B2** ancrage marché | dernière croissance de l'IPC loyer + écart historique interne − marché | oui (IPC) |
# | **B3** ancrage TAL | pourcentage du TAL + écart historique ; net = contractuel − écart contractuel→net de l'an dernier | oui (TAL) |
# | **E1** moteur combiné | renouvellements : historique du segment + niveau du nowcast ; relocations : + signal des loyers affichés ; rabais prévus par segment | non |
# | **E2** moteur réglementé | E1, mais les renouvellements québécois sont ancrés sur le TAL ; the Ontario new-build (Ontario) reste exempté au scénario central | oui (TAL, ligne directrice) |
#
# **Note de transparence.** B3 et E2 ont été ajoutés après le premier backtest réel, à cause de la structure
# réglementaire TAL / Ontario ; B0, B1, B2 et E1 existaient avant. Cet ajout ne change pas la règle de choix, qui reste celle
# déclarée au départ.

# %%
models = pd.DataFrame({"modèle": list(all_models())})
weights = cfg["combine"]
display(models)
display(Markdown(
    f"Poids de départ du moteur E1 (non optimisés, à examiner seulement sur les années de sélection) : "
    f"renouvellements — historique {weights['renewal_history_weight']:.0%}, nowcast {weights['renewal_nowcast_weight']:.0%} ; "
    f"relocations — historique {weights['turnover_history_weight']:.0%}, loyers affichés {weights['turnover_signal_weight']:.0%}, "
    f"nowcast {weights['turnover_nowcast_weight']:.0%}. Fenêtre d'historique : {weights['history_window_years']} ans ; "
    f"fenêtre de l'écart réglementaire : {cfg['anchors']['gap_window_years']} ans."))

# %% [markdown]
# ### 8.3 Composition des poids à la date de coupure
#
# **Opération :** les poids fixes sont les parts de chaque segment parmi les paires admissibles des
# `weight_window_years` dernières années. **Vérification :** nombre de paires, de segments et part des renouvellements
# (comptes et agrégats seulement).

# %%
pairs_now = training_pairs(snapshot_jan31, cfg)
weights_now = frozen_weights(pairs_now, snapshot_jan31.cutoff, cfg)
renewal_share = float(weights_now.loc[weights_now["is_renewal"].astype(bool), "weight"].sum())
display(Markdown(
    f"À la coupure {snapshot_jan31.cutoff:%Y-%m-%d} : **{len(pairs_now)}** paires admissibles, **{len(weights_now)}** segments "
    f"pondérés ; les renouvellements pèsent **{renewal_share:.1%}** des poids (fenêtre de "
    f"{cfg['headline']['weight_window_years']} ans)."))

# %% [markdown]
# ### 8.4 Règle de choix, déclarée avant les résultats
#
# **Le modèle retenu est celui dont l'erreur absolue moyenne sur le loyer net est la plus faible sur les années de sélection,
# avec la règle de coupure des données publiques décrite ci-dessus.** L'année de validation est conservée pour la fin : elle
# est rapportée mais ne sert jamais à choisir. Un modèle n'est admissible que s'il produit une prévision pour chaque année
# de sélection ; en cas d'égalité, le modèle le plus simple (premier dans la liste) l'emporte. La section 9 applique cette
# règle ; les années exactes sont affichées ci-dessous, lues de la configuration.

# %%
selection_years = cfg["forecast_years"]["selection_years"]
display(Markdown(
    f"Années de sélection : **{', '.join(map(str, selection_years))}** ; année de validation : "
    f"**{cfg['forecast_years']['holdout_year']}** ; règle de coupure des données publiques : **{public_day}** de l'année "
    f"cible ; mesure : **{cfg['selection']['metric']}**."))
