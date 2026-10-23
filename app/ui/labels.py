"""Labels of the Streamlit app in English and French, with identical keys.

Owner: FCT (redesign I-11c, on top of I-11b). Text only: no number or date is typed here; every figure and date shown is
passed in as a placeholder from the aggregates JSON.
"""

from __future__ import annotations

from typing import Any

LANGS = ("en", "fr")
DEFAULT_LANG = "fr"  # one constant: the app opens in this language (French by default); the sidebar toggle switches it
LANG_NAMES = {"en": "English", "fr": "Français"}

LABELS: dict[str, dict[str, str]] = {
    "en": {
        # masthead and navigation
        "app_title": "Halo Lens", "masthead_sub": "Residential portfolio · Québec & Ontario",
        "tab_answer": "01 · Answer", "tab_why": "02 · Why", "tab_validation": "03 · Validation",
        "tab_lab": "04 · Scenario Lab", "tab_buildings": "05 · Buildings", "tab_ask": "06 · Questions",
        "tab_sources": "07 · Sources", "badge_real": "Real data", "badge_demo": "Synthetic demo",
        "data_label": "Data", "mode_demo": "Demo", "mode_real": "Real",
        "side_how_title": "How to read this",
        "side_how_body": ("Every figure comes from a precomputed aggregates file: this app never touches the lease data. "
                          "The headline is a forecast for the target year; the lab and the sensitivities show what moves it."),
        # 01 answer
        "answer_caption": "{year} rent increase · same-unit, fixed composition · forecast as of {crm}",
        "hero_label": "Net of all incentives.",
        "hero_sentence": ("Contractual rent rises {contract} before concessions. The median unit moves {median_net} net and "
                          "{median_contract} contractual."),
        "range_caption": ("Shaded band: range across the candidate models. {model} is the chosen engine. Ranges are "
                          "scenarios, not prediction intervals."),
        "legend_net": "net", "legend_contract": "contractual", "legend_band": "model range",
        "stat_province_values": "{net} net · {contract} contractual",
        "stat_province_na": "not available for this model", "province_qc": "Québec", "province_on": "Ontario",
        "stat_coverage_title": "Coverage",
        "stat_coverage_body": "{pairs} eligible same-unit pairs · {units} units · {leases} leases · {excluded} excluded",
        "stat_info_title": "Information", "stat_info_body": "Public data to {external} · lease data to {crm}",
        "stat_info_tip": "Strict rule: public data only to {strict}",
        # 02 why
        "why_kicker": "02 · Why believe it", "why_headline": "Python computes, this page shows the evidence, Claude only explains.",
        "why_step_1": "Computation", "why_step_2": "Evidence", "why_step_3": "Explanation",
        "why_title_1": "Python pipeline", "why_title_2": "This dashboard", "why_title_3": "Claude",
        "why_body_1": "Every figure is computed by the pipeline from the lease records, with weights frozen at the cutoff.",
        "why_body_2": "This page reads only precomputed aggregates and shows them unchanged.",
        "why_body_3": "Claude words an answer. A sentence is shown only if each figure in it matches the aggregates.",
        "why_measured_title": "How the rate is measured",
        "why_measured_body": ("**Same unit:** each unit is compared with its own previous lease, so size, floor and building do "
                              "not change the result.\n\n**Fixed composition:** segment weights are frozen at the cutoff, so "
                              "the mix of leases does not move the headline.\n\n**Companions are always shown:** the "
                              "contractual rent and the medians sit beside the headline."),
        "why_limits_title": "Limits of this reading",
        "why_limits_body": ("The weights describe observed lease transitions, not occupancy or turnover.\n\nNet rent is "
                            "adjusted for concessions. It is not cash collected.\n\nFew backtest years support cautious "
                            "conclusions: scenario ranges, not prediction intervals."),
        "why_definition": "Full definition",
        # 03 validation
        "val_kicker": "03 · Does it hold up", "val_headline_less": "Engines differ less than the years do.",
        "val_headline_more": "Engines differ more than the years do.",
        "val_headline_na": "How each model did on the years we already know.",
        "val_left_title": "{model}: forecast vs actual", "val_left_caption": "Net increase, one pair of bars per year.",
        "val_forecast": "forecast", "val_actual": "actual",
        "val_right_title": "Mean absolute error by model, selection years",
        "val_right_caption": ("Bar: mean over the selection years ({selection}). Ticks: each selection year. Hollow dot: the "
                              "holdout year ({holdout}), kept apart and never used to choose. Cyan: the model the "
                              "pre-declared rule chose."),
        "val_weak": ("Statistically weak ranking: {n} selection years, {n} points per model. Differences between engines are "
                     "smaller than the swings between years."),
        "val_holdout": "holdout", "val_table": "Backtest table", "val_strict": "Strict rule: public data to {strict} (sensitivity)",
        "val_pooled": "All years pooled (descriptive only)", "val_empty": "No backtest rows for this rule.",
        "val_mismatch": "The displayed ranking picks {ranked}, but the headline comes from {headline}.",
        "val_col_model": "Model", "val_col_selection": "Selection error (pp)", "val_col_holdout": "Holdout error (pp)",
        "val_col_pooled": "Pooled error (pp, descriptive only)", "val_col_folds": "Years computed",
        # 04 lab
        "lab_kicker": "04 · What if", "lab_headline": "Move a lever and watch the forecast move.",
        "lab_incentive": "Incentives", "lab_renewal": "Renewal share", "lab_newbuild": "Lakeview Residences", "lab_rule": "Public data cutoff",
        "opt_incentive_minus": "Shallower", "opt_incentive_zero": "Baseline", "opt_incentive_plus": "Deeper",
        "opt_renewal_minus": "Fewer", "opt_renewal_zero": "Baseline", "opt_renewal_plus": "More",
        "opt_newbuild_exempt": "Exempt", "opt_newbuild_guideline": "Guideline", "opt_rule_strict": "{day} strict",
        "lab_changed": "changed", "lab_reset": "Reset to baseline", "lab_baseline": "Baseline",
        "lab_scenario": "Your scenario, net", "lab_delta": "{delta} vs baseline", "lab_envelope": "scenario envelope",
        "lab_no_row": "This combination is not in the precomputed grid.", "lab_pp": "pp",
        "lab_explain": "Explain this scenario", "lab_copilot_question": "Ask about a scenario",
        "lab_understood": "What the AI understood", "lab_use_levers": "Use the levers above for this question.",
        "tornado_title": "What moves the forecast most",
        "tornado_caption": "Each bar changes one assumption alone; effects do not add up. Sensitivities, not prediction intervals.",
        "as_information_rule": "Information rule", "as_gap_bounds": "Pair gap bounds", "as_winsorization": "Winsorization",
        "as_weight_window": "Weight window (years)", "as_newbuild_applicability": "Ontario guideline for Lakeview Residences",
        "as_incentive_intensity": "Incentive intensity", "as_renewal_mix": "Renewal share", "as_model_choice": "Model choice",
        "va_strict_dec31": "strict cutoff", "va_include_six_month_leases": "short leases included",
        "va_max_gap": "maximum gap", "va_quantiles": "quantiles", "va_years": "years", "va_ontario_newbuild_guideline_applies": "guideline applies",
        "va_incentives_deeper": "deeper incentives", "va_incentives_shallower": "lighter incentives",
        "va_more_renewals": "more renewals", "va_fewer_renewals": "fewer renewals",
        # 05 buildings
        "bd_kicker": "05 · Where", "bd_headline": "{best} leads at {best_pct}. {worst} trails at {worst_pct}.",
        "bd_headline_one": "{best} is at {best_pct}.", "bd_headline_empty": "Buildings",
        "bd_caption": "Dot: shrunk net increase, sized by the pairs behind it. Tick: raw value. E2 engine, shrunk toward the building mean.",
        "bd_cell": "{building} · {beds} br", "bd_phase": "phase {phase}", "bd_pairs": "{n} pairs",
        "bd_table": "Table", "bd_empty": "No building x bedroom cell reaches the minimum number of pairs.",
        "bd_col_cell": "Cell", "bd_col_pairs": "Pairs", "bd_col_net": "Net, shrunk (%)", "bd_col_raw": "Net, raw (%)",
        "bd_col_contract": "Contractual, shrunk (%)",
        # 06 ask
        "ask_kicker": "06 · Ask", "ask_headline": "Ask why. Every number is checked.",
        "ask_free": "Or ask your own question (sections are cited)", "ask_answer": "Answer",
        "ask_sources": "Sources: {sections}", "ask_checked": "✓ numbers matched to aggregates",
        "ask_spinner": "Checking the aggregates…", "example_occupancy": "What is the occupancy rate?",
        "ask_no_key_demo": "No API key: the levers and the validated cached demo answers remain available.",
        "ask_refused": "This extract cannot measure occupancy, vacancy or absorption, so the app does not answer on them.",
        "ask_unavailable": "The answer is unavailable right now. The levers above still work.",
        "ask_error": "The AI service did not answer (temporary problem). The levers above still work.",
        "ask_fallback": "No verified answer could be produced for this question. See the notebook sections for the figures.",
        "no_key_cache_synthetic_only": ("Cached preset answers are available only in the synthetic demo. Configure an API key to ask "
                                        "questions about real-data aggregates. The dashboard and the levers remain available "
                                        "without a key."),
        "no_key_cache_missing": "No cached demo answer is available for this question.",
        "no_key_cache_rejected": ("This cached demo answer could not be validated against the current results, so it was not "
                                  "shown."),
        "no_key_generic": "No answer is available without an API key for this question.",
        # footer
        "src_kicker": "07 · Sources", "src_headline": "The public numbers behind the forecast.",
        "foot_sources": "Sources ({n} series)", "foot_col_series": "Series", "foot_col_publisher": "Publisher",
        "foot_col_release": "Release date", "foot_col_url": "Link", "foot_trust": "How this dashboard protects the data",
        "trust_privacy": ("**Privacy wall.** The lease data never leaves the analysis machine. This app reads only aggregate "
                          "files (counts and percentages), never a lease, a unit or an address."),
        "trust_ai": "**AI explains, our pipeline computes.** Every number is produced by the pipeline; the AI only words it.",
        "trust_guard": ("**Number guard.** A sentence from the AI is shown only if each figure in it appears in the aggregates "
                        "on screen; otherwise a verified fallback text is shown."),
        "trust_tools": ("**AI tools used.** Claude Code (development of the pipeline and this app) and the Claude API "
                        "(optional wording of answers, aggregates only)."),
        "trust_font": "**Typeface.** Loaded from Google Fonts (no data sent); offline, a system font is used.",
        "foot_reload": "Reload", "foot_key_note": "Adding or changing an API key requires restarting the app.",
        # errors and misc
        "pp": "pp",
        "mode_mismatch": "The file does not match the selected data mode ({found} instead of {expected}).",
        "no_real": "No real aggregates yet: run scripts/export_aggregates.py --real (the file is gitignored).",
        "bad_file": "Aggregates file not usable: {error}. Check outputs/public or outputs/private.",
    },
    "fr": {
        "app_title": "Halo Lens", "masthead_sub": "Portefeuille résidentiel · Québec et Ontario",
        "tab_answer": "01 · Réponse", "tab_why": "02 · Pourquoi", "tab_validation": "03 · Validation",
        "tab_lab": "04 · Laboratoire de scénarios", "tab_buildings": "05 · Immeubles", "tab_ask": "06 · Questions",
        "tab_sources": "07 · Sources", "badge_real": "Données réelles", "badge_demo": "Démo synthétique",
        "data_label": "Données", "mode_demo": "Démo", "mode_real": "Réel",
        "side_how_title": "Comment lire",
        "side_how_body": ("Chaque chiffre vient d'un fichier d'agrégats précalculé : l'application ne touche jamais aux baux. "
                          "La hausse est une prévision pour l'année cible ; le laboratoire et les sensibilités montrent ce qui la déplace."),
        "answer_caption": "Hausse des loyers {year} · même unité, composition fixe · prévision au {crm}",
        "hero_label": "Nette de tous les incitatifs.",
        "hero_sentence": ("Le loyer contractuel augmente de {contract} avant les concessions. L'unité médiane évolue de "
                          "{median_net} net et de {median_contract} contractuel."),
        "range_caption": ("Bande : étendue entre les modèles candidats. {model} est le moteur retenu. Les plages sont des "
                          "scénarios, pas des intervalles de prédiction."),
        "legend_net": "net", "legend_contract": "contractuel", "legend_band": "étendue des modèles",
        "stat_province_values": "{net} net · {contract} contractuel",
        "stat_province_na": "non disponible pour ce modèle", "province_qc": "Québec", "province_on": "Ontario",
        "stat_coverage_title": "Couverture",
        "stat_coverage_body": "{pairs} paires admissibles à unité constante · {units} unités · {leases} baux · {excluded} exclues",
        "stat_info_title": "Information", "stat_info_body": "Données publiques au {external} · baux au {crm}",
        "stat_info_tip": "Règle stricte : données publiques seulement au {strict}",
        "why_kicker": "02 · Pourquoi y croire", "why_headline": "Python calcule, cette page montre la preuve, Claude explique seulement.",
        "why_step_1": "Calcul", "why_step_2": "Preuve", "why_step_3": "Explication",
        "why_title_1": "Pipeline Python", "why_title_2": "Ce tableau de bord", "why_title_3": "Claude",
        "why_body_1": "Chaque chiffre est calculé par le pipeline à partir des baux, avec des poids figés à la date de coupure.",
        "why_body_2": "Cette page lit seulement des agrégats précalculés et les affiche tels quels.",
        "why_body_3": "Claude formule une réponse. Une phrase n'est affichée que si chacun de ses chiffres correspond aux agrégats.",
        "why_measured_title": "Comment le taux est mesuré",
        "why_measured_body": ("**Même unité :** chaque unité est comparée à son propre bail précédent ; superficie, étage et "
                              "immeuble ne changent pas le résultat.\n\n**Composition fixe :** les poids des segments sont figés à "
                              "la date de coupure ; le mélange de baux ne déplace pas la hausse.\n\n**Les compagnons sont "
                              "toujours affichés :** le loyer contractuel et les médianes accompagnent la hausse."),
        "why_limits_title": "Limites de cette lecture",
        "why_limits_body": ("Les poids décrivent des transitions de baux observées, pas l'occupation ni le roulement.\n\nLe loyer "
                            "net tient compte des concessions. Ce n'est pas un encaissement.\n\nPeu d'années de backtest "
                            "appellent à la prudence : des plages de scénarios, pas des intervalles de prédiction."),
        "why_definition": "Définition complète",
        "val_kicker": "03 · Est-ce solide", "val_headline_less": "Les moteurs diffèrent moins que les années.",
        "val_headline_more": "Les moteurs diffèrent plus que les années.",
        "val_headline_na": "Comment chaque modèle a fait sur les années déjà connues.",
        "val_left_title": "{model} : prévu et réalisé", "val_left_caption": "Hausse nette, une paire de barres par année.",
        "val_forecast": "prévu", "val_actual": "réalisé",
        "val_right_title": "Erreur absolue moyenne par modèle, années de sélection",
        "val_right_caption": ("Barre : moyenne sur les années de sélection ({selection}). Traits : chaque année de sélection. Point "
                              "creux : l'année de validation ({holdout}), tenue à l'écart et jamais utilisée pour choisir. "
                              "Cyan : le modèle choisi par la règle déclarée à l'avance."),
        "val_weak": ("Classement statistiquement faible : {n} années de sélection, {n} points par modèle. Les écarts entre moteurs "
                     "sont plus petits que les écarts entre années."),
        "val_holdout": "validation", "val_table": "Tableau du backtest",
        "val_strict": "Règle stricte : données publiques au {strict} (sensibilité)",
        "val_pooled": "Toutes années confondues (descriptif seulement)", "val_empty": "Aucune ligne de backtest pour cette règle.",
        "val_mismatch": "Le classement affiché désigne {ranked}, mais la hausse vient de {headline}.",
        "val_col_model": "Modèle", "val_col_selection": "Erreur de sélection (pp)", "val_col_holdout": "Erreur de validation (pp)",
        "val_col_pooled": "Erreur cumulée (pp, descriptif seulement)", "val_col_folds": "Années calculées",
        "lab_kicker": "04 · Et si", "lab_headline": "Déplacez un levier et regardez la prévision bouger.",
        "lab_incentive": "Concessions", "lab_renewal": "Part des renouvellements", "lab_newbuild": "Lakeview Residences",
        "lab_rule": "Coupure des données publiques",
        "opt_incentive_minus": "Plus légères", "opt_incentive_zero": "Base", "opt_incentive_plus": "Plus profondes",
        "opt_renewal_minus": "Moins", "opt_renewal_zero": "Base", "opt_renewal_plus": "Plus",
        "opt_newbuild_exempt": "Exempté", "opt_newbuild_guideline": "Ligne directrice", "opt_rule_strict": "{day} strict",
        "lab_changed": "modifié", "lab_reset": "Revenir à la base", "lab_baseline": "Base",
        "lab_scenario": "Votre scénario, net", "lab_delta": "{delta} par rapport à la base", "lab_envelope": "enveloppe des scénarios",
        "lab_no_row": "Cette combinaison n'est pas dans la grille précalculée.", "lab_pp": "pp",
        "lab_explain": "Expliquer ce scénario", "lab_copilot_question": "Poser une question sur un scénario",
        "lab_understood": "Ce que l'IA a compris", "lab_use_levers": "Utilisez les leviers ci-dessus pour cette question.",
        "tornado_title": "Ce qui déplace le plus la prévision",
        "tornado_caption": ("Chaque barre change une seule hypothèse ; les effets ne s'additionnent pas. Des sensibilités, pas des "
                            "intervalles de prédiction."),
        "as_information_rule": "Règle d'information", "as_gap_bounds": "Bornes de l'écart entre baux",
        "as_winsorization": "Winsorisation", "as_weight_window": "Fenêtre des poids (années)",
        "as_newbuild_applicability": "Ligne directrice ontarienne à Lakeview Residences", "as_incentive_intensity": "Intensité des concessions",
        "as_renewal_mix": "Part des renouvellements", "as_model_choice": "Choix du modèle",
        "va_strict_dec31": "coupure stricte", "va_include_six_month_leases": "baux courts inclus",
        "va_max_gap": "écart maximal", "va_quantiles": "quantiles", "va_years": "années", "va_ontario_newbuild_guideline_applies": "ligne directrice applicable",
        "va_incentives_deeper": "concessions plus profondes", "va_incentives_shallower": "concessions plus légères",
        "va_more_renewals": "plus de renouvellements", "va_fewer_renewals": "moins de renouvellements",
        "bd_kicker": "05 · Où", "bd_headline": "{best} mène à {best_pct}. {worst} ferme la marche à {worst_pct}.",
        "bd_headline_one": "{best} est à {best_pct}.", "bd_headline_empty": "Immeubles",
        "bd_caption": ("Point : hausse nette ramenée, de taille proportionnelle aux paires. Trait : valeur brute. Moteur E2, ramené "
                       "vers la moyenne de l'immeuble."),
        "bd_cell": "{building} · {beds} ch.", "bd_phase": "phase {phase}", "bd_pairs": "{n} paires",
        "bd_table": "Tableau", "bd_empty": "Aucune cellule immeuble × chambres n'atteint le nombre minimal de paires.",
        "bd_col_cell": "Cellule", "bd_col_pairs": "Paires", "bd_col_net": "Net, ramené (%)", "bd_col_raw": "Net, brut (%)",
        "bd_col_contract": "Contractuel, ramené (%)",
        "ask_kicker": "06 · Questions", "ask_headline": "Demandez pourquoi. Chaque chiffre est vérifié.",
        "ask_free": "Ou posez votre question (les sections sont citées)", "ask_answer": "Répondre",
        "ask_sources": "Sources : {sections}", "ask_checked": "✓ chiffres rapprochés des agrégats",
        "ask_spinner": "Vérification des agrégats…", "example_occupancy": "Quel est le taux d'occupation ?",
        "ask_no_key_demo": "Pas de clé API : les leviers et les réponses de démonstration validées restent disponibles.",
        "ask_refused": "Cet extrait ne permet pas de mesurer l'occupation, la vacance ni l'absorption : l'application n'y répond pas.",
        "ask_unavailable": "La réponse n'est pas disponible pour le moment. Les leviers ci-dessus fonctionnent toujours.",
        "ask_error": "Le service d'IA n'a pas répondu (problème temporaire). Les leviers ci-dessus fonctionnent toujours.",
        "ask_fallback": "Aucune réponse vérifiée n'a pu être produite pour cette question. Voir les sections du carnet pour les chiffres.",
        "no_key_cache_synthetic_only": ("Les réponses prédéfinies en cache sont disponibles seulement dans la démo synthétique. "
                                        "Configurez une clé API pour interroger les agrégats réels. Le tableau de bord et les "
                                        "leviers restent disponibles sans clé."),
        "no_key_cache_missing": "Aucune réponse de démonstration en cache pour cette question.",
        "no_key_cache_rejected": ("Cette réponse de démonstration n'a pas pu être validée avec les résultats actuels : elle n'est "
                                  "donc pas affichée."),
        "no_key_generic": "Aucune réponse n'est disponible sans clé API pour cette question.",
        "src_kicker": "07 · Sources", "src_headline": "Les chiffres publics derrière la prévision.",
        "foot_sources": "Sources ({n} séries)", "foot_col_series": "Série", "foot_col_publisher": "Éditeur",
        "foot_col_release": "Date de publication", "foot_col_url": "Lien", "foot_trust": "Comment ce tableau de bord protège les données",
        "trust_privacy": ("**Mur de confidentialité.** Les baux ne quittent jamais la machine d'analyse. Cette application ne lit "
                          "que des fichiers d'agrégats (comptes et pourcentages), jamais un bail, une unité ni une adresse."),
        "trust_ai": "**L'IA explique, notre pipeline calcule.** Chaque chiffre est produit par le pipeline ; l'IA ne fait que le formuler.",
        "trust_guard": ("**Garde-fou des nombres.** Une phrase de l'IA n'est affichée que si chacun de ses chiffres figure dans les "
                        "agrégats à l'écran ; sinon un texte de repli vérifié est affiché."),
        "trust_tools": ("**Outils d'IA utilisés.** Claude Code (développement du pipeline et de cette application) et l'API Claude "
                        "(formulation facultative des réponses, agrégats seulement)."),
        "trust_font": "**Police.** Police chargée depuis Google Fonts (aucune donnée envoyée) ; hors ligne, une police système est utilisée.",
        "foot_reload": "Recharger", "foot_key_note": "Ajouter ou changer une clé API exige de redémarrer l'application.",
        "pp": "pp",
        "mode_mismatch": "Le fichier ne correspond pas au mode de données choisi ({found} au lieu de {expected}).",
        "no_real": "Pas encore d'agrégats réels : lancez scripts/export_aggregates.py --real (le fichier est ignoré par git).",
        "bad_file": "Fichier d'agrégats inutilisable : {error}. Vérifiez outputs/public ou outputs/private.",
    },
}


def t(key: str, lang: str = DEFAULT_LANG, **values: Any) -> str:
    """A label in the given language, with `{placeholders}` filled from `values`."""
    text = LABELS[lang][key]
    return text.format(**values) if values else text
