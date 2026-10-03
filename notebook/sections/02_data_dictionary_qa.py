# ---
# jupyter:
#   jupytext:
#     formats: py:percent
# ---

# %% [markdown]
# ## 2. Dictionnaire de données et contrôle qualité
#
# **Entrée :** les quatre fichiers CSV du commanditaire, intacts (empreintes vérifiées).
# **Opération :** renommer chaque colonne selon ce qu'elle contient réellement, typer les identifiants comme
# texte (zéros initiaux) et les dates, puis exécuter des contrôles structurels.
# **Pourquoi :** la description des colonnes ne correspond pas toujours aux données (consigne du défi).
# **Vérification :** chaque contrôle affiche un décompte, jamais des lignes.

# %% [markdown]
# ### 2.1 Correspondance colonnes sources → noms canoniques
# Préfixes Yardi : `h` = identifiant (jointures), `s` = valeur stockée (affichage, regroupement).
# `sAvailable` est retirée : elle est identique à `sLeaseFrom` sur toutes les lignes (contrôle ci-dessous).

# %%
mapping = column_mapping()
display(mapping)

# %% [markdown]
# ### 2.2 Contrôles structurels
# Points clés attendus : la clé `sSite + sUnitCode` provoque des collisions (elle n'est jamais utilisée),
# `hUnit` ↔ `sPropCode + sUnitCode` est biunivoque, les codes d'unité commençant par zéro sont conservés,
# et les dates de fin contractuelles après 2025 sont légitimes (baux signés).

# %%
qa_report = run_qa(raw, tables, cfg["data"]["data_end_date"])
display(qa_report)
flagged = int((qa_report["status"] != "pass").sum())
display(Markdown(f"Contrôles signalés : **{flagged}** sur {len(qa_report)}."))
