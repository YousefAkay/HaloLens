"""Labels (French and English), cards, header and trust panel of the Streamlit app.

Owner: FCT (task I-11b, delegated by INT). Presentation only: no number is computed here, every figure shown comes from the
aggregates JSON that the caller passes in. Colours come from leaselens.contracts.
"""

from __future__ import annotations

from typing import Any

import streamlit as st

from leaselens.contracts import COLOR_CONTRACT, COLOR_MARKET, COLOR_NAIVE, COLOR_NET

LANGS = ("en", "fr")
DEFAULT_LANG = "en"  # one constant: the app opens in this language; the sidebar toggle switches it
LANG_NAMES = {"en": "English", "fr": "Français"}
MISSING_KEY = "not_available"  # label shown where the aggregates hold null
CARD_BORDER_RADIUS_PX = 10  # CSS values live here, named, not scattered in the markup
BADGE_RADIUS_PX = 12

LABELS: dict[str, dict[str, str]] = {
    "en": {
        # header and badges
        "app_title": "LeaseLens",
        "definition_line": "Fixed-composition same-unit growth in rent net of all incentives, for the target year.",
        "as_of": "Target year {year} · CRM cutoff {crm} · public data by {external} (sensitivity: {strict})",
        "badge_real": "Real data", "badge_demo": "Synthetic demo",
        # sidebar
        "sidebar_language": "Language", "sidebar_data": "Data", "sidebar_reload": "Reload",
        "sidebar_how_title": "How to read this",
        "sidebar_how_body": ("Every figure comes from a precomputed aggregates file: this app never touches the lease data. "
                             "The headline is a forecast for the target year; scenarios and sensitivities show what moves it."),
        "sidebar_key_note": "Adding or changing an API key requires restarting the app.",
        # tabs
        "tab_overview": "Overview", "tab_validation": "Validation", "tab_scenarios": "Scenarios",
        "tab_building": "By building", "tab_ask": "Ask the analysis", "tab_trust": "Trust",
        # overview
        "kpi_net": "Headline, net of incentives", "kpi_contract": "Headline, contractual",
        "kpi_effect": "Incentive effect", "kpi_champion": "Champion model",
        "kpi_net_caption": "Forecast, same units, fixed mix", "kpi_contract_caption": "Before concessions",
        "kpi_effect_caption": "Contractual minus net, in percentage points",
        "kpi_champion_caption": "Chosen by the rule declared in advance ({rule})",
        "medians_line": "Medians: {net} net · {contract} contractual",
        "overview_answer": "From contractual rent to the net headline",
        "overview_provinces": "Québec and Ontario",
        "province_qc": "Québec", "province_on": "Ontario", "province_card": "{net} net · {contract} contractual",
        "province_unavailable": "not available for this model",
        "reading_title": "Reading",
        "reading": ("The {model} model ({rule}) forecasts {net} net of incentives and {contract} contractual for {year}: "
                    "concessions take {effect} pp. Scenarios range from {low} to {high} net."),
        "reading_no_range": "The {model} model ({rule}) forecasts {net} net of incentives and {contract} contractual for {year}.",
        "coverage_title": "Coverage",
        "coverage_line": ("Leases: {leases} · units: {units} · eligible pairs: {eligible} · excluded pairs: {excluded} · "
                          "segments: {segments}"),
        "definition_title": "Definition",
        # answer chart
        "chart_contract": "Contractual headline", "chart_effect": "Incentive effect", "chart_net": "Net headline",
        "chart_band": "Scenario range (low to high)", "chart_e2": "E2 central scenario", "chart_axis_pct": "Increase (%)",
        # validation
        "val_selection_title": "Selection ranking (the rule that chose the champion)",
        "val_selection_caption": ("Mean absolute net error over the selection years, Jan-31 rule. Lowest wins. "
                                  "The champion is highlighted."),
        "val_weak": "Statistically weak ranking: very few selection years. The holdout year is kept apart.",
        "val_holdout_title": "Holdout year (not used to choose)", "val_strict_title": "Strict Dec-31 rule (sensitivity only)",
        "val_pooled_title": "All years pooled", "val_pooled_note": "descriptive only",
        "val_rule_toggle": "Information rule for the chart", "val_rule_jan31": "Public data by Jan 31 (agreed rule)",
        "val_rule_dec31_strict": "Public data by Dec 31 (strict sensitivity)",
        "val_col_model": "Model", "val_col_selection": "Selection error (pp)", "val_col_holdout": "Holdout error (pp)",
        "val_col_pooled": "Pooled error (pp)", "val_col_folds": "Years computed",
        "val_mismatch": "The displayed ranking picks {ranked}, but the headline comes from {headline}.",
        "val_chart_title": "Net forecast error by model and year (pp)", "val_chart_champion": "champion",
        "val_empty": "No backtest rows for this rule.",
        # scenarios
        "sc_title": "Scenario range, net", "sc_low": "Low", "sc_central": "Central", "sc_high": "High",
        "sc_caption": "Scenarios, not prediction intervals.", "sc_tornado": "Sensitivity to one assumption at a time",
        "sc_tornado_caption": "Each bar changes one assumption alone; effects do not add up.",
        "sc_axis_delta": "Change in the net headline (pp)", "sc_bootstrap": "Sampling uncertainty (unit bootstrap)",
        "sc_bootstrap_caption": "Sampling uncertainty only; it does not cover the model or the assumptions.",
        # sensitivity labels
        "as_information_rule": "Information rule", "as_gap_bounds": "Pair gap bounds", "as_winsorization": "Winsorization",
        "as_weight_window": "Weight window (years)", "as_met_applicability": "Ontario guideline for the Ontario new-build",
        "as_incentive_intensity": "Incentive intensity", "as_renewal_mix": "Renewal share", "as_model_choice": "Model choice",
        "va_strict_dec31": "strict cutoff", "va_include_six_month_leases": "short leases included",
        "va_max_gap": "maximum gap", "va_quantiles": "quantiles", "va_years": "years", "va_met_guideline_applies": "guideline applies",
        "va_incentives_deeper": "deeper incentives", "va_incentives_shallower": "lighter incentives",
        "va_more_renewals": "more renewals", "va_fewer_renewals": "fewer renewals",
        # building
        "bd_title": "By building and bedroom count", "bd_caption": "E2 engine, shrunk toward the building mean.",
        "bd_empty": "No building x bedroom cell reaches the minimum number of pairs.", "bd_cell": "{building} · {beds} bd",
        "bd_phase": "phase {phase}", "bd_col_cell": "Cell", "bd_col_pairs": "Pairs", "bd_col_net": "Net, shrunk (%)",
        "bd_col_raw": "Net, raw (%)", "bd_col_contract": "Contractual, shrunk (%)", "bd_axis": "Net increase, shrunk (%)",
        # ask
        "ask_ai_line": "AI explains, our pipeline computes.", "ask_scenarios": "Scenarios",
        "ask_incentive": "Incentive intensity", "ask_renewal": "Renewal share", "ask_met": "the Ontario new-build", "ask_rule": "Information rule",
        "lever_minus": "minus", "lever_zero": "zero", "lever_plus": "plus", "met_exempt": "exempt", "met_guideline": "guideline",
        "rule_jan31": "Jan-31 rule", "rule_dec31_strict": "Dec-31 strict rule",
        "ask_copilot_question": "Ask about a scenario (uses the Claude API when a key is set)",
        "ask_copilot_go": "Explain this scenario", "ask_understood": "What the AI understood",
        "ask_use_dropdowns": "Use the dropdowns above for this question.",
        "ask_qa_title": "Questions and answers", "ask_preset": "Preset questions",
        "ask_free": "Or ask your own question (sections are cited)", "ask_answer": "Answer",
        "ask_examples": "Examples", "example_occupancy": "What is the occupancy rate?",
        "ask_no_key_demo": "No API key: scenario dropdowns and validated cached demo answers remain available.",
        "ask_refused": "This extract cannot measure occupancy, vacancy or absorption, so the app does not answer on them.",
        "ask_unavailable": "The answer is unavailable right now. The dropdowns above still work.",
        "ask_error": "The AI service did not answer (temporary problem). The dropdowns above still work.",
        "ask_fallback": "No verified answer could be produced for this question. See the notebook sections for the figures.",
        "no_key_cache_synthetic_only": ("Cached preset answers are available only in the synthetic demo. Configure an API key to ask "
                                        "questions about real-data aggregates. The dashboard and scenario dropdowns remain "
                                        "available without a key."),
        "no_key_cache_missing": "No cached demo answer is available for this question.",
        "no_key_cache_rejected": ("This cached demo answer could not be validated against the current results, so it was not "
                                  "shown."),
        "no_key_generic": "No answer is available without an API key for this question.",
        # trust
        "trust_title": "Trust", "trust_sources": "Public sources and release dates", "trust_col_series": "Series",
        "trust_col_publisher": "Publisher", "trust_col_url": "Link", "trust_col_release": "Release date",
        "trust_panel_title": "How this app protects the data",
        "trust_privacy": ("**Privacy wall.** The lease data never leaves the analysis machine. This app reads only aggregate "
                          "files (counts and percentages), never a lease, a unit or an address."),
        "trust_ai": "**AI explains, our pipeline computes.** Every number is produced by the pipeline; the AI only words it.",
        "trust_guard": ("**Number guard.** A sentence from the AI is shown only if each figure in it appears in the aggregates "
                        "on screen; otherwise a verified fallback text is shown."),
        "trust_tools": ("**AI tools used.** Claude Code (development of the pipeline and this app) and the Claude API "
                        "(optional wording of answers, aggregates only)."),
        # errors and misc
        "not_available": "not available", "mode_mismatch": "The file does not match the selected data mode ({found} instead of {expected}).",
        "no_real": "No real aggregates yet: run scripts/export_aggregates.py --real (the file is gitignored).",
        "bad_file": "Aggregates file not usable: {error}. Check outputs/public or outputs/private.",
        "pp": "pp",
    },
    "fr": {
        "app_title": "LeaseLens",
        "definition_line": "Croissance à composition fixe, à unité constante, du loyer net de tous les incitatifs, pour l'année cible.",
        "as_of": "Année cible {year} · coupure du CRM {crm} · données publiques au {external} (sensibilité : {strict})",
        "badge_real": "Données réelles", "badge_demo": "Démo synthétique",
        "sidebar_language": "Langue", "sidebar_data": "Données", "sidebar_reload": "Recharger",
        "sidebar_how_title": "Comment lire",
        "sidebar_how_body": ("Chaque chiffre vient d'un fichier d'agrégats précalculé : l'application ne touche jamais aux baux. "
                             "La hausse est une prévision pour l'année cible ; les scénarios et sensibilités montrent ce qui la déplace."),
        "sidebar_key_note": "Ajouter ou changer une clé API exige de redémarrer l'application.",
        "tab_overview": "Vue d'ensemble", "tab_validation": "Validation", "tab_scenarios": "Scénarios",
        "tab_building": "Par immeuble", "tab_ask": "Interroger l'analyse", "tab_trust": "Confiance",
        "kpi_net": "Hausse nette des incitatifs", "kpi_contract": "Hausse contractuelle",
        "kpi_effect": "Effet des concessions", "kpi_champion": "Modèle retenu",
        "kpi_net_caption": "Prévision, mêmes unités, composition fixe", "kpi_contract_caption": "Avant les concessions",
        "kpi_effect_caption": "Contractuel moins net, en points de pourcentage",
        "kpi_champion_caption": "Choisi par la règle déclarée à l'avance ({rule})",
        "medians_line": "Médianes : {net} net · {contract} contractuel",
        "overview_answer": "Du loyer contractuel à la hausse nette",
        "overview_provinces": "Québec et Ontario",
        "province_qc": "Québec", "province_on": "Ontario", "province_card": "{net} net · {contract} contractuel",
        "province_unavailable": "non disponible pour ce modèle",
        "reading_title": "Lecture",
        "reading": ("Le modèle {model} ({rule}) prévoit {net} net des incitatifs et {contract} contractuel pour {year} : "
                    "les concessions retirent {effect} pp. Les scénarios vont de {low} à {high} net."),
        "reading_no_range": "Le modèle {model} ({rule}) prévoit {net} net des incitatifs et {contract} contractuel pour {year}.",
        "coverage_title": "Couverture",
        "coverage_line": ("Baux : {leases} · unités : {units} · paires admissibles : {eligible} · paires exclues : {excluded} · "
                          "segments : {segments}"),
        "definition_title": "Définition",
        "chart_contract": "Hausse contractuelle", "chart_effect": "Effet des concessions", "chart_net": "Hausse nette",
        "chart_band": "Plage de scénarios (bas à haut)", "chart_e2": "Scénario central E2", "chart_axis_pct": "Hausse (%)",
        "val_selection_title": "Classement de sélection (la règle qui a choisi le modèle)",
        "val_selection_caption": ("Erreur absolue moyenne du loyer net sur les années de sélection, règle du 31 janvier. "
                                  "La plus faible gagne. Le modèle retenu est surligné."),
        "val_weak": "Classement statistiquement faible : très peu d'années de sélection. L'année de validation est tenue à l'écart.",
        "val_holdout_title": "Année de validation (n'a pas servi à choisir)",
        "val_strict_title": "Règle stricte du 31 décembre (sensibilité seulement)",
        "val_pooled_title": "Toutes années confondues", "val_pooled_note": "descriptif seulement",
        "val_rule_toggle": "Règle d'information pour le graphique",
        "val_rule_jan31": "Données publiques au 31 janvier (règle retenue)",
        "val_rule_dec31_strict": "Données publiques au 31 décembre (sensibilité stricte)",
        "val_col_model": "Modèle", "val_col_selection": "Erreur de sélection (pp)", "val_col_holdout": "Erreur de validation (pp)",
        "val_col_pooled": "Erreur cumulée (pp)", "val_col_folds": "Années calculées",
        "val_mismatch": "Le classement affiché désigne {ranked}, mais la hausse vient de {headline}.",
        "val_chart_title": "Erreur de prévision nette par modèle et par année (pp)", "val_chart_champion": "modèle retenu",
        "val_empty": "Aucune ligne de backtest pour cette règle.",
        "sc_title": "Plage de scénarios, net", "sc_low": "Bas", "sc_central": "Central", "sc_high": "Haut",
        "sc_caption": "Des scénarios, pas des intervalles de prédiction.", "sc_tornado": "Sensibilité à une hypothèse à la fois",
        "sc_tornado_caption": "Chaque barre change une seule hypothèse ; les effets ne s'additionnent pas.",
        "sc_axis_delta": "Écart de la hausse nette (pp)", "sc_bootstrap": "Incertitude d'échantillonnage (bootstrap par unité)",
        "sc_bootstrap_caption": "Incertitude d'échantillonnage seulement ; elle ne couvre ni le modèle ni les hypothèses.",
        "as_information_rule": "Règle d'information", "as_gap_bounds": "Bornes de l'écart entre baux",
        "as_winsorization": "Winsorisation", "as_weight_window": "Fenêtre des poids (années)",
        "as_met_applicability": "Ligne directrice ontarienne à the Ontario new-build", "as_incentive_intensity": "Intensité des concessions",
        "as_renewal_mix": "Part des renouvellements", "as_model_choice": "Choix du modèle",
        "va_strict_dec31": "coupure stricte", "va_include_six_month_leases": "baux courts inclus",
        "va_max_gap": "écart maximal", "va_quantiles": "quantiles", "va_years": "années", "va_met_guideline_applies": "ligne directrice applicable",
        "va_incentives_deeper": "concessions plus profondes", "va_incentives_shallower": "concessions plus légères",
        "va_more_renewals": "plus de renouvellements", "va_fewer_renewals": "moins de renouvellements",
        "bd_title": "Par immeuble et nombre de chambres", "bd_caption": "Moteur E2, ramené vers la moyenne de l'immeuble.",
        "bd_empty": "Aucune cellule immeuble × chambres n'atteint le nombre minimal de paires.",
        "bd_cell": "{building} · {beds} ch.", "bd_phase": "phase {phase}", "bd_col_cell": "Cellule", "bd_col_pairs": "Paires",
        "bd_col_net": "Net, ramené (%)", "bd_col_raw": "Net, brut (%)", "bd_col_contract": "Contractuel, ramené (%)",
        "bd_axis": "Hausse nette, ramenée (%)",
        "ask_ai_line": "L'IA explique, notre pipeline calcule.", "ask_scenarios": "Scénarios",
        "ask_incentive": "Intensité des concessions", "ask_renewal": "Part des renouvellements", "ask_met": "the Ontario new-build",
        "ask_rule": "Règle d'information",
        "lever_minus": "moins", "lever_zero": "zéro", "lever_plus": "plus", "met_exempt": "exempté", "met_guideline": "ligne directrice",
        "rule_jan31": "règle du 31 janvier", "rule_dec31_strict": "règle stricte du 31 décembre",
        "ask_copilot_question": "Poser une question sur un scénario (utilise l'API Claude si une clé est configurée)",
        "ask_copilot_go": "Expliquer ce scénario", "ask_understood": "Ce que l'IA a compris",
        "ask_use_dropdowns": "Utilisez les listes ci-dessus pour cette question.",
        "ask_qa_title": "Questions et réponses", "ask_preset": "Questions prédéfinies",
        "ask_free": "Ou posez votre question (les sections sont citées)", "ask_answer": "Répondre",
        "ask_examples": "Exemples", "example_occupancy": "Quel est le taux d'occupation ?",
        "ask_no_key_demo": "Pas de clé API : les listes de scénarios et les réponses de démonstration validées restent disponibles.",
        "ask_refused": "Cet extrait ne permet pas de mesurer l'occupation, la vacance ni l'absorption : l'application n'y répond pas.",
        "ask_unavailable": "La réponse n'est pas disponible pour le moment. Les listes ci-dessus fonctionnent toujours.",
        "ask_error": "Le service d'IA n'a pas répondu (problème temporaire). Les listes ci-dessus fonctionnent toujours.",
        "ask_fallback": "Aucune réponse vérifiée n'a pu être produite pour cette question. Voir les sections du carnet pour les chiffres.",
        "no_key_cache_synthetic_only": ("Les réponses prédéfinies en cache sont disponibles seulement dans la démo synthétique. "
                                        "Configurez une clé API pour interroger les agrégats réels. Le tableau de bord et les "
                                        "listes de scénarios restent disponibles sans clé."),
        "no_key_cache_missing": "Aucune réponse de démonstration en cache pour cette question.",
        "no_key_cache_rejected": ("Cette réponse de démonstration n'a pas pu être validée avec les résultats actuels : elle n'est "
                                  "donc pas affichée."),
        "no_key_generic": "Aucune réponse n'est disponible sans clé API pour cette question.",
        "trust_title": "Confiance", "trust_sources": "Sources publiques et dates de publication", "trust_col_series": "Série",
        "trust_col_publisher": "Éditeur", "trust_col_url": "Lien", "trust_col_release": "Date de publication",
        "trust_panel_title": "Comment cette application protège les données",
        "trust_privacy": ("**Mur de confidentialité.** Les baux ne quittent jamais la machine d'analyse. Cette application ne lit "
                          "que des fichiers d'agrégats (comptes et pourcentages), jamais un bail, une unité ni une adresse."),
        "trust_ai": "**L'IA explique, notre pipeline calcule.** Chaque chiffre est produit par le pipeline ; l'IA ne fait que le formuler.",
        "trust_guard": ("**Garde-fou des nombres.** Une phrase de l'IA n'est affichée que si chacun de ses chiffres figure dans les "
                        "agrégats à l'écran ; sinon un texte de repli vérifié est affiché."),
        "trust_tools": ("**Outils d'IA utilisés.** Claude Code (développement du pipeline et de cette application) et l'API Claude "
                        "(formulation facultative des réponses, agrégats seulement)."),
        "not_available": "non disponible", "mode_mismatch": "Le fichier ne correspond pas au mode de données choisi ({found} au lieu de {expected}).",
        "no_real": "Pas encore d'agrégats réels : lancez scripts/export_aggregates.py --real (le fichier est ignoré par git).",
        "bad_file": "Fichier d'agrégats inutilisable : {error}. Vérifiez outputs/public ou outputs/private.",
        "pp": "pp",
    },
}


def t(key: str, lang: str = DEFAULT_LANG, **values: Any) -> str:
    """A label in the given language, with `{placeholders}` filled from `values`."""
    text = LABELS[lang][key]
    return text.format(**values) if values else text


def inject_css() -> None:
    """Minimal styling: bordered cards with an accent bar and a small badge. Colours come from contracts.py."""
    st.markdown(
        f"""<style>
        div[class*="st-key-kpi_"] {{ border-left: 4px solid {COLOR_NET}; border-radius: {CARD_BORDER_RADIUS_PX}px; }}
        div[class*="st-key-kpi_contract"] {{ border-left-color: {COLOR_CONTRACT}; }}
        div[class*="st-key-kpi_effect"] {{ border-left-color: {COLOR_NAIVE}; }}
        div[class*="st-key-kpi_champion"] {{ border-left-color: {COLOR_MARKET}; }}
        .ll-badge {{ display:inline-block; padding:2px 12px; border-radius:{BADGE_RADIUS_PX}px; color:white; font-size:0.85rem;
                    font-weight:600; vertical-align:middle; margin-left:0.75rem; }}
        .ll-chip {{ display:inline-block; padding:2px 10px; margin:0 6px 6px 0; border-radius:{BADGE_RADIUS_PX}px;
                   border:1px solid {COLOR_NAIVE}; font-size:0.85rem; }}
        </style>""",
        unsafe_allow_html=True)


def kpi_card(title: str, value: str, caption: str | None, key: str) -> None:
    """One headline figure in a bordered card; `key` also picks the accent colour (kpi_net, kpi_contract, ...)."""
    with st.container(border=True, key=f"kpi_{key}"):
        st.metric(title, value)
        if caption:
            st.caption(caption)


def chips(items: list[str]) -> None:
    """Small pills, used to show what the AI understood of a question."""
    st.markdown("".join(f'<span class="ll-chip">{item}</span>' for item in items), unsafe_allow_html=True)


def header(doc: dict[str, Any], lang: str) -> None:
    """Title, one-line definition, as-of dates and the real/synthetic badge."""
    real = doc["mode"] == "real"
    badge = t("badge_real" if real else "badge_demo", lang)
    color = COLOR_MARKET if real else COLOR_NET
    st.markdown(f'## {t("app_title", lang)}<span class="ll-badge" style="background:{color}">{badge}</span>',
                unsafe_allow_html=True)
    st.write(t("definition_line", lang))
    as_of = doc["as_of"]
    st.caption(t("as_of", lang, year=doc["target_year"], crm=as_of["crm_cutoff"], external=as_of["external_cutoff"],
                 strict=as_of["external_strict_cutoff"]))


def trust_panel(doc: dict[str, Any], lang: str) -> None:
    """The privacy wall, the AI role, the number guard and the AI tools used, in plain words."""
    st.subheader(t("trust_panel_title", lang))
    for key in ("trust_privacy", "trust_ai", "trust_guard", "trust_tools"):
        st.markdown(t(key, lang))
