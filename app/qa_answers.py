"""Fact sheets, deterministic composer and optional LLM polish for the Questions tab.

Owner: INT. Task Q-02.

Pipeline: `qa_topics.route` picks a topic -> `fact_sheet` reads the aggregates JSON and returns plain-label facts, rounded to
at most one decimal -> `compose` fills a template (one short answer sentence, two to four bullets, a "Read more" line) ->
`answer_question` optionally lets a model rewrite the wording (kept only if every number is in the fact sheet, the text is
complete and in the question's language). Every number in an answer comes from the fact sheet; internal model codes and
section tokens never appear. Without an API key everything still works. Only aggregates reach an API.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from app import narrative, qa_topics
from app.number_guard import extract_numbers, ungrounded_numbers

DECIMALS = 1  # most decimals written in an answer
MINUS = "−"
MODEL_CODE = re.compile(r"\b[A-Z]\d_[a-z_]+\b")
SECTION_TOKEN = re.compile(r"§")
MAX_BULLETS = 4
MIN_BULLETS = 2
SMALL_COUNT_WORDS = {
    "en": ("zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten"),
    "fr": ("zéro", "un", "deux", "trois", "quatre", "cinq", "six", "sept", "huit", "neuf", "dix"),
}
MODEL_NAMES = {  # model code -> readable name (English, French): the only place codes appear
    "B0_last_year": ("last year's growth carried forward", "la croissance de l'an dernier reconduite"),
    "B1_trailing_mean": ("the average of recent years", "la moyenne des dernières années"),
    "B2_market_anchor": ("the market-anchored estimate", "l'estimation ancrée sur le marché"),
    "B3_tal_anchor": ("the tribunal-guideline estimate", "l'estimation ancrée sur le pourcentage du TAL"),
    "E1_engine_blend": ("the three-engine blend", "le mélange des trois moteurs"),
    "E2_regulated": ("the regulation-aware blend", "le mélange tenant compte de la réglementation"),
}
ASSUMPTION_NAMES = {  # sensitivity assumption key -> readable label (English, French)
    "model_choice": ("the choice of forecasting model", "le choix du modèle de prévision"),
    "incentive_intensity": ("the depth of incentives", "l'ampleur des incitatifs"),
    "information_rule": ("the cut-off date for public data", "la date de coupure des données publiques"),
    "newbuild_applicability": ("the Ontario new-build guideline", "la ligne directrice ontarienne pour les nouveaux immeubles"),
    "weight_window": ("the history window used for weights", "la fenêtre d'historique des poids"),
    "winsorization": ("the trimming of extreme leases", "le retrait des baux extrêmes"),
    "gap_bounds": ("the allowed gap between two leases", "l'écart permis entre deux baux"),
    "renewal_mix": ("the share of renewals", "la part de renouvellements"),
}
SECTION_TITLES_EN = {
    "01": "Definition of the measured increase", "02": "Data dictionary and quality control", "03": "Composition effect",
    "04": "Same-unit matching", "05": "Concessions: contractual vs net rent", "06": "Renewals vs turnovers, Québec and Ontario rules",
    "07": "External data and release dates", "08": "Forecast method", "09": "Backtest 2023-2025",
    "10": "Forecast 2026 and the champion rule", "11a": "Uncertainty", "11b": "Scenarios 2026", "12": "References",
}
SECTION_TITLES_FR = dict(narrative.SECTION_MAP)
READ_MORE = {  # topic -> notebook section numbers (titles come from the tables above)
    "headline": ("01", "10"), "definition": ("01", "04", "05"), "scenarios_levers": ("11b", "05"),
    "regulation": ("06", "07"), "validation_backtest": ("09", "10"), "incentives": ("05", "11b"),
    "uncertainty": ("11a", "11b"), "buildings_segments": ("04", "03"), "data_quality": ("02", "07"),
}
MONTHS = {"en": ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
                 "November", "December"),
          "fr": ("janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre",
                 "novembre", "décembre")}
CAPTION = {
    "synthetic": {"en": "Computed from the synthetic demo aggregates.", "fr": "Calculé à partir des agrégats de la démo synthétique."},
    "real": {"en": "Computed from your data aggregates.", "fr": "Calculé à partir des agrégats de vos données."},
}
REFUSAL = {
    "en": ("This extract cannot measure occupancy, vacancy, absorption or the total rent roll, so I give no figure on them.",
           ("A lease extract only lists leases, not which units are empty or what the whole portfolio collects.",
            "I can tell you how much rents for the same unit rise from one lease to the next, which is what this analysis measures.",
            "Try asking about the 2026 increase, the scenarios, the Québec and Ontario rules or how well past forecasts did.")),
    "fr": ("Cet extrait ne permet pas de mesurer l'occupation, la vacance, l'absorption ni le rent roll total : je ne donne donc aucun chiffre à ce sujet.",
           ("Un extrait de baux liste des baux, pas les unités vides ni ce que le portefeuille encaisse au total.",
            "Je peux en revanche dire de combien le loyer d'une même unité monte d'un bail au suivant, ce que mesure cette analyse.",
            "Essayez de poser une question sur la hausse 2026, les scénarios, les règles du Québec et de l'Ontario ou la qualité des prévisions passées.")),
}
OUT_OF_SCOPE = {
    "en": ("That question is outside what this analysis covers, so I will not guess.",
           ("I can explain the 2026 rent increase and how it is defined.", "I can show what changes under other scenarios and how the Québec and Ontario rules apply.",
            "I can say how well past forecasts did, how much uncertainty remains, how buildings differ and how good the data is.")),
    "fr": ("Cette question dépasse ce que couvre l'analyse : je préfère ne pas deviner.",
           ("Je peux expliquer la hausse 2026 et la façon dont elle est définie.", "Je peux montrer ce qui change selon les scénarios et comment les règles du Québec et de l'Ontario s'appliquent.",
            "Je peux dire quelle a été la qualité des prévisions passées, quelle incertitude demeure, comment les immeubles diffèrent et quelle est la qualité des données.")),
}


# ---------------------------------------------------------------------------- formatting
def percent(value: float | None, lang: str) -> str:
    """'3.5 %' / '3,5 %' with at most one decimal; 'n/a' for a missing value."""
    if value is None:
        return "n/a"
    rounded = round(float(value), DECIMALS)
    text = f"{abs(rounded):.{DECIMALS}f}"
    text = text.replace(".", ",") if lang == "fr" else text
    return f"{MINUS if rounded < 0 else ''}{text} %"


def points(value: float | None, lang: str, signed: bool = False) -> str:
    """A change in percentage points: its magnitude, or with `signed` its sign too (a signed value matches the JSON's sign)."""
    if value is None:
        return "n/a"
    rounded = round(float(value), DECIMALS)
    text = f"{abs(rounded):.{DECIMALS}f}"
    text = text.replace(".", ",") if lang == "fr" else text
    sign = (MINUS if rounded < 0 else "+") if signed and rounded != 0 else ""
    return f"{sign}{text} points"


def count(value: int | None, lang: str) -> str:
    """Whole counts: words up to ten, digits above."""
    if value is None:
        return "n/a"
    return SMALL_COUNT_WORDS[lang][value] if 0 <= value <= 10 else f"{value}"


def long_date(iso: str, lang: str) -> str:
    year, month, day = (int(part) for part in iso.split("-"))
    name = MONTHS[lang][month - 1]
    return f"{day} {name} {year}" if lang == "en" else f"{day}{'er' if day == 1 else ''} {name} {year}"


def model_label(code: str | None, lang: str) -> str:
    if code is None:
        return "n/a"
    return MODEL_NAMES.get(code, (code.replace("_", " "), code.replace("_", " ")))[0 if lang == "en" else 1]


# ---------------------------------------------------------------------------- fact sheets
@dataclass(frozen=True)
class Fact:
    """One plain-label fact: the label shown to a reader and the value already formatted for the language."""

    label: str
    text: str


@dataclass
class FactSheet:
    """Facts for one topic and language, read from the aggregates; `numbers` lists every number the facts contain."""

    topic: str
    lang: str
    facts: dict[str, Fact] = field(default_factory=dict)

    def add(self, key: str, label_en: str, label_fr: str, text: str) -> None:
        self.facts[key] = Fact(label_en if self.lang == "en" else label_fr, text)

    def text(self, key: str, default: str = "n/a") -> str:
        return self.facts[key].text if key in self.facts else default

    def has(self, *keys: str) -> bool:
        return all(key in self.facts and "n/a" not in self.facts[key].text for key in keys)

    @property
    def numbers(self) -> list[float]:
        return [number.value for fact in self.facts.values() for number in extract_numbers(fact.text)]

    def as_payload(self) -> list[dict[str, str]]:
        return [{"label": fact.label, "value": fact.text} for fact in self.facts.values()]


def _get(node: Any, *path: str) -> Any:
    for key in path:
        node = node.get(key) if isinstance(node, dict) else None
    return node


def _sensitivity(doc: dict[str, Any], variant: str, model: str | None = None) -> dict[str, Any] | None:
    for row in doc.get("sensitivity", []):
        if row.get("variant") == variant and (model is None or row.get("model") == model):
            return row
    return None


def _backtest_rows(doc: dict[str, Any]) -> list[dict[str, Any]]:
    model, rule = _get(doc, "headline", "model"), _get(doc, "headline", "information_rule")
    rows = [row for row in doc.get("backtest", []) if row.get("model") == model and row.get("information_rule") == rule]
    return sorted(rows, key=lambda row: row["year"])


def _top_assumptions(doc: dict[str, Any], limit: int = 3) -> list[dict[str, Any]]:
    """The largest one-at-a-time swing of each assumption, strongest first."""
    best: dict[str, dict[str, Any]] = {}
    for row in doc.get("sensitivity", []):
        if row.get("delta_pp") is None:
            continue
        key = row["assumption"]
        if key not in best or abs(row["delta_pp"]) > abs(best[key]["delta_pp"]):
            best[key] = row
    return sorted(best.values(), key=lambda row: -abs(row["delta_pp"]))[:limit]


def _cells(doc: dict[str, Any]) -> list[dict[str, Any]]:
    return [row for row in doc.get("building_beds", []) if row.get("net_pct_shrunk") is not None]


def fact_sheet(topic: str, doc: dict[str, Any], lang: str) -> FactSheet:
    """Plain-label facts for `topic`, formatted in `lang`. Never contains internal keys or model codes."""
    sheet = FactSheet(topic, lang)
    p = lambda value: percent(value, lang)  # noqa: E731
    headline, companions, coverage = doc.get("headline", {}), doc.get("companions", {}), doc.get("coverage", {})
    year = doc.get("target_year")
    if topic in ("headline", "definition", "incentives", "regulation"):
        sheet.add("year", "Target year", "Année cible", str(year) if year else "n/a")
        sheet.add("net", f"Net increase {year}", f"Hausse nette {year}", p(headline.get("net_pct")))
        sheet.add("contract", "Contractual increase", "Hausse contractuelle", p(headline.get("contract_pct")))
    if topic == "headline":
        sheet.add("median_net", "Median net increase", "Hausse nette médiane", p(companions.get("median_net_pct")))
        sheet.add("median_contract", "Median contractual increase", "Hausse contractuelle médiane", p(companions.get("median_contract_pct")))
        for code, name_en, name_fr in (("QC", "Québec", "Québec"), ("ON", "Ontario", "Ontario")):
            province = _get(headline, "provinces", code) or {}
            sheet.add(f"{code.lower()}_net", f"{name_en} net increase", f"Hausse nette {name_fr}", p(province.get("net_pct")))
        sheet.add("low", "Lowest model estimate", "Estimation la plus basse des modèles", p(_get(headline, "model_range", "low_net_pct")))
        sheet.add("high", "Highest model estimate", "Estimation la plus haute des modèles", p(_get(headline, "model_range", "high_net_pct")))
        sheet.add("model", "Model used", "Modèle retenu", model_label(headline.get("model"), lang))
        sheet.add("crm_cutoff", "Lease data up to", "Baux connus jusqu'au", long_date(doc["as_of"]["crm_cutoff"], lang))
        sheet.add("external_cutoff", "Public data published by", "Données publiques parues au plus tard le", long_date(doc["as_of"]["external_cutoff"], lang))
    elif topic == "definition":
        sheet.add("pairs", "Same-unit lease pairs", "Paires de baux d'une même unité", count(coverage.get("eligible_pairs"), lang))
        sheet.add("units", "Units", "Unités", count(coverage.get("units"), lang))
        sheet.add("median_net", "Median net increase", "Hausse nette médiane", p(companions.get("median_net_pct")))
    elif topic == "scenarios_levers":
        scenarios = doc.get("scenarios", {})
        sheet.add("low", "Low scenario", "Scénario bas", p(scenarios.get("low_net_pct")))
        sheet.add("central", "Central scenario", "Scénario central", p(scenarios.get("central_net_pct")))
        sheet.add("high", "High scenario", "Scénario haut", p(scenarios.get("high_net_pct")))
        for key, variant, label_en, label_fr in (("deeper", "incentives_deeper", "Deeper incentives", "Incitatifs plus profonds"),
                                                 ("shallower", "incentives_shallower", "Shallower incentives", "Incitatifs moins profonds")):
            row = _sensitivity(doc, variant)
            sheet.add(key, label_en, label_fr, p(row["headline_net_pct"]) if row else "n/a")
            sheet.add(f"{key}_shift", f"{label_en}: change", f"{label_fr} : écart", points(row["delta_pp"], lang) if row else "n/a")
            sheet.add(f"{key}_setting", f"{label_en}: size", f"{label_fr} : ampleur", points(float(row["setting"]), lang) if row else "n/a")
        row = _sensitivity(doc, "ontario_newbuild_guideline_applies")
        sheet.add("guideline", "Ontario new-build guideline applies", "Ligne directrice ontarienne applicable", p(row["headline_net_pct"]) if row else "n/a")
        sheet.add("guideline_shift", "Ontario guideline: change", "Ligne directrice ontarienne : écart", points(row["delta_pp"], lang) if row else "n/a")
    elif topic == "regulation":
        for code, name in (("QC", "Québec"), ("ON", "Ontario")):
            province = _get(headline, "provinces", code) or {}
            sheet.add(f"{code.lower()}_net", f"{name} net increase", f"Hausse nette {name}", p(province.get("net_pct")))
            sheet.add(f"{code.lower()}_contract", f"{name} contractual increase", f"Hausse contractuelle {name}", p(province.get("contract_pct")))
        row = _sensitivity(doc, "ontario_newbuild_guideline_applies")
        sheet.add("guideline", "Ontario new-build guideline applies", "Ligne directrice ontarienne applicable", p(row["headline_net_pct"]) if row else "n/a")
        sheet.add("guideline_shift", "Ontario guideline: change", "Ligne directrice ontarienne : écart", points(row["delta_pp"], lang) if row else "n/a")
        sheet.add("external_cutoff", "Public data published by", "Données publiques parues au plus tard le", long_date(doc["as_of"]["external_cutoff"], lang))
    elif topic == "validation_backtest":
        rows = _backtest_rows(doc)
        sheet.add("model", "Model used", "Modèle retenu", model_label(headline.get("model"), lang))
        sheet.add("years", "Backtest years", "Années du backtest", count(len(rows), lang) if rows else "n/a")
        if rows:
            over, under = max(rows, key=lambda r: r["error_pp_net"]), min(rows, key=lambda r: r["error_pp_net"])
            sheet.add("over_year", "Year of the largest overshoot", "Année du plus grand excès", str(over["year"]))
            sheet.add("over", "Largest overshoot", "Plus grand excès", points(over["error_pp_net"], lang, signed=True))
            sheet.add("under_year", "Year of the largest shortfall", "Année du plus grand manque", str(under["year"]))
            sheet.add("under", "Largest shortfall", "Plus grand manque", points(under["error_pp_net"], lang, signed=True))
            last = rows[-1]
            sheet.add("last_year", "Latest backtest year", "Dernière année du backtest", str(last["year"]))
            sheet.add("last_forecast", "Latest year: forecast", "Dernière année : prévision", p(last["forecast_net_pct"]))
            sheet.add("last_actual", "Latest year: actual", "Dernière année : observé", p(last["actual_net_pct"]))
    elif topic == "incentives":
        sheet.add("concessions", "Concessions matched", "Concessions rapprochées", count(coverage.get("concessions"), lang))
        for key, variant, label_en, label_fr in (("deeper", "incentives_deeper", "Deeper incentives", "Incitatifs plus profonds"),
                                                 ("shallower", "incentives_shallower", "Shallower incentives", "Incitatifs moins profonds")):
            row = _sensitivity(doc, variant)
            sheet.add(key, label_en, label_fr, p(row["headline_net_pct"]) if row else "n/a")
            sheet.add(f"{key}_shift", f"{label_en}: change", f"{label_fr} : écart", points(row["delta_pp"], lang) if row else "n/a")
        row = _sensitivity(doc, "incentives_deeper")
        sheet.add("setting", "Size of the incentive change", "Ampleur du changement d'incitatifs", points(float(row["setting"]), lang) if row else "n/a")
    elif topic == "uncertainty":
        scenarios = doc.get("scenarios", {})
        sheet.add("low", "Low scenario", "Scénario bas", p(scenarios.get("low_net_pct")))
        sheet.add("central", "Central scenario", "Scénario central", p(scenarios.get("central_net_pct")))
        sheet.add("high", "High scenario", "Scénario haut", p(scenarios.get("high_net_pct")))
        for index, row in enumerate(_top_assumptions(doc), start=1):
            names = ASSUMPTION_NAMES.get(row["assumption"], (row["assumption"].replace("_", " "),) * 2)
            sheet.add(f"top{index}", f"Assumption {index}", f"Hypothèse {index}", names[0 if lang == "en" else 1])
            sheet.add(f"top{index}_shift", f"Assumption {index}: swing", f"Hypothèse {index} : écart", points(row["delta_pp"], lang))
    elif topic == "buildings_segments":
        cells = sorted(_cells(doc), key=lambda row: row["net_pct_shrunk"])
        buildings = {row["building"] for row in cells}
        sheet.add("buildings", "Buildings", "Immeubles", count(len(buildings), lang) if buildings else "n/a")
        if cells:
            low, high = cells[0], cells[-1]
            for key, row, label_en, label_fr in (("high", high, "Highest", "Plus haute"), ("low", low, "Lowest", "Plus basse")):
                sheet.add(f"{key}_name", f"{label_en} segment", f"{label_fr} cellule", f"{row['building']}, {row['beds']}-bedroom" if lang == "en"
                          else f"{row['building']}, {row['beds']} chambre{'s' if row['beds'] > 1 else ''}")
                sheet.add(f"{key}_net", f"{label_en} segment: net increase", f"{label_fr} cellule : hausse nette", p(row["net_pct_shrunk"]))
                sheet.add(f"{key}_pairs", f"{label_en} segment: lease pairs", f"{label_fr} cellule : paires de baux", count(row["n_pairs"], lang))
    elif topic == "data_quality":
        for key, label_en, label_fr in (("leases", "Leases", "Baux"), ("units", "Units", "Unités"),
                                        ("eligible_pairs", "Usable same-unit pairs", "Paires d'une même unité utilisables"),
                                        ("excluded_pairs", "Pairs excluded", "Paires exclues"), ("segments", "Segments", "Segments"),
                                        ("concessions", "Concessions", "Concessions"), ("asking_rows", "Asking-rent observations", "Observations de loyers affichés"),
                                        ("external_rows", "Public-data observations", "Observations de données publiques")):
            sheet.add(key, label_en, label_fr, count(coverage.get(key), lang))
    return sheet


# ---------------------------------------------------------------------------- composer
@dataclass
class Answer:
    """A structured answer: one short sentence, two to four bullets, a read-more line and a caption."""

    topic: str
    lang: str
    lead: str
    bullets: list[str]
    read_more: str
    caption: str
    source: str = "deterministic"  # or "polished"

    @property
    def text(self) -> str:
        return "\n".join(line for line in [self.lead, *[f"- {bullet}" for bullet in self.bullets], self.read_more] if line)


def read_more_line(topic: str, lang: str) -> str:
    """'Read more in the notebook: <title> · <title>' with readable section titles."""
    titles = SECTION_TITLES_EN if lang == "en" else SECTION_TITLES_FR
    names = " · ".join(titles[number] for number in READ_MORE.get(topic, ()))
    return (f"Read more in the notebook: {names}." if lang == "en" else f"Pour approfondir, dans le carnet : {names}.") if names else ""


def _compose_body(topic: str, f: FactSheet) -> tuple[str, list[str]]:
    """Lead sentence and bullets for one topic, from the fact sheet only."""
    en = f.lang == "en"
    t = f.text
    if topic == "headline":
        lead = (f"Net of all concessions, the {t('year')} rent increase is {t('net')} (contractual rent: {t('contract')})." if en else
                f"Nette de toutes les concessions, la hausse des loyers {t('year')} est de {t('net')} (loyer contractuel : {t('contract')}).")
        bullets = [
            (f"The median lease pair gives {t('median_net')} net and {t('median_contract')} contractual." if en else
             f"La paire de baux médiane donne {t('median_net')} nette et {t('median_contract')} contractuelle."),
            (f"By province, the net increase is {t('qc_net')} in Québec and {t('on_net')} in Ontario." if en else
             f"Par province, la hausse nette est de {t('qc_net')} au Québec et de {t('on_net')} en Ontario."),
            (f"The models compared give estimates from {t('low')} to {t('high')}; the figure above comes from {t('model')}." if en else
             f"Les modèles comparés donnent des estimations de {t('low')} à {t('high')} ; le chiffre ci-dessus vient de {t('model')}."),
            (f"It uses leases known by {t('crm_cutoff')} and public data published by {t('external_cutoff')}." if en else
             f"Elle utilise les baux connus au {t('crm_cutoff')} et les données publiques parues au plus tard le {t('external_cutoff')}."),
        ]
    elif topic == "definition":
        lead = ("The increase is how much the rent of the same unit grows from one lease to the next, net of every concession." if en else
                "La hausse est la croissance du loyer d'une même unité d'un bail au suivant, nette de toutes les concessions.")
        bullets = [
            (f"Each unit is compared with itself, using {t('pairs')} lease pairs across {t('units')} units, so a new, pricier building does not look like a price rise." if en else
             f"Chaque unité est comparée à elle-même, avec {t('pairs')} paires de baux sur {t('units')} unités : un nouvel immeuble plus cher ne ressemble donc pas à une hausse de prix."),
            ("Growth is annualised, then averaged over segments (building, bedrooms, renewal or turnover) with weights frozen at the forecast date." if en else
             "La croissance est annualisée puis moyennée par segment (immeuble, chambres, renouvellement ou relocation) avec des poids figés à la date de prévision."),
            (f"The contractual version and the median are shown beside it: {t('contract')} contractual and {t('median_net')} median net for {t('year')}, against {t('net')} net." if en else
             f"La version contractuelle et la médiane sont présentées à côté : {t('contract')} contractuelle et {t('median_net')} nette médiane pour {t('year')}, contre {t('net')} nette."),
        ]
    elif topic == "scenarios_levers":
        lead = (f"If incentives become deeper by {t('deeper_setting')}, the net increase falls to {t('deeper')}; if they become shallower, it rises to {t('shallower')}." if en else
                f"Si les incitatifs deviennent plus profonds de {t('deeper_setting')}, la hausse nette tombe à {t('deeper')} ; s'ils le sont moins, elle monte à {t('shallower')}.")
        bullets = [
            (f"That is a swing of {t('deeper_shift')} either way around the central scenario of {t('central')}." if en else
             f"C'est un écart de {t('deeper_shift')} de part et d'autre du scénario central de {t('central')}."),
            (f"The scenario range runs from {t('low')} to {t('high')}; scenarios use the regulation-aware blend, so its central case can differ from the headline." if en else
             f"La fourchette des scénarios va de {t('low')} à {t('high')} ; les scénarios utilisent le mélange tenant compte de la réglementation, dont le cas central peut différer du chiffre principal."),
            (f"A different share of renewals barely moves it; applying the Ontario new-build guideline gives {t('guideline')}, a change of {t('guideline_shift')}." if en else
             f"Une autre part de renouvellements ne le déplace presque pas ; appliquer la ligne directrice ontarienne aux nouveaux immeubles donne {t('guideline')}, un écart de {t('guideline_shift')}."),
        ]
    elif topic == "regulation":
        lead = (f"Renewals follow each province's own rules: the net increase is {t('qc_net')} in Québec and {t('on_net')} in Ontario." if en else
                f"Les renouvellements suivent les règles de chaque province : la hausse nette est de {t('qc_net')} au Québec et de {t('on_net')} en Ontario.")
        bullets = [
            (f"In Québec the housing tribunal's percentage guides rent fixing when an increase is refused; it is a benchmark, not a cap. The contractual increase there is {t('qc_contract')}." if en else
             f"Au Québec, le pourcentage du Tribunal administratif du logement guide la fixation du loyer en cas de refus ; c'est un repère, pas un plafond. La hausse contractuelle y est de {t('qc_contract')}."),
            (f"In Ontario the yearly guideline caps renewals of non-exempt units (contractual increase {t('on_contract')}); newer buildings are exempt, and applying the guideline to them gives {t('guideline')}." if en else
             f"En Ontario, la ligne directrice annuelle plafonne les renouvellements des unités non exemptées (hausse contractuelle {t('on_contract')}) ; les immeubles plus récents sont exemptés, et lui appliquer la ligne directrice donne {t('guideline')}."),
            (f"Public rates are used only if published by {t('external_cutoff')}, the same rule as in the backtests." if en else
             f"Les taux publics ne sont utilisés que s'ils sont parus au plus tard le {t('external_cutoff')}, la même règle que dans les backtests."),
        ]
    elif topic == "validation_backtest":
        lead = (f"The ranking is weak because it rests on only {t('years')} yearly results, and one year can reverse the order." if en else
                f"Le classement est fragile parce qu'il repose sur seulement {t('years')} résultats annuels, et une seule année peut inverser l'ordre.")
        bullets = [
            (f"The model behind the headline misses widely in both directions: its forecast error (forecast minus observed) was {t('over')} in {t('over_year')} and {t('under')} in {t('under_year')}." if en else
             f"Le modèle derrière le chiffre principal se trompe largement dans les deux sens : son erreur de prévision (prévu moins observé) était de {t('over')} en {t('over_year')} et de {t('under')} en {t('under_year')}."),
            (f"In {t('last_year')} it forecast {t('last_forecast')} and the observed figure was {t('last_actual')}." if en else
             f"En {t('last_year')}, il prévoyait {t('last_forecast')} et le chiffre observé était de {t('last_actual')}."),
            ("Every model is tested with the same code as the real forecast and only with information known at each cutoff, but a few years cannot separate close models." if en else
             "Chaque modèle est testé avec le même code que la vraie prévision et seulement avec l'information connue à chaque coupure, mais quelques années ne départagent pas des modèles proches."),
        ]
    elif topic == "incentives":
        lead = (f"Incentives such as free months lower the net increase ({t('net')}) below the contractual one ({t('contract')})." if en else
                f"Les incitatifs, comme les mois gratuits, abaissent la hausse nette ({t('net')}) sous la hausse contractuelle ({t('contract')}).")
        bullets = [
            (f"Each concession is matched to the lease it belongs to ({t('concessions')} are in the data); one-off credits are not treated as monthly discounts." if en else
             f"Chaque concession est rapprochée du bail auquel elle appartient ({t('concessions')} dans les données) ; les crédits ponctuels ne sont pas traités comme des rabais mensuels."),
            (f"If incentives deepen by {t('setting')}, the net increase falls by {t('deeper_shift')} to {t('deeper')}." if en else
             f"Si les incitatifs s'approfondissent de {t('setting')}, la hausse nette baisse de {t('deeper_shift')} et passe à {t('deeper')}."),
            (f"If they shrink by the same amount, it rises by {t('shallower_shift')} to {t('shallower')}." if en else
             f"S'ils rétrécissent d'autant, elle monte de {t('shallower_shift')} et passe à {t('shallower')}."),
        ]
    elif topic == "uncertainty":
        lead = (f"The scenarios put the net increase between {t('low')} and {t('high')}, with {t('central')} as the central case." if en else
                f"Les scénarios situent la hausse nette entre {t('low')} et {t('high')}, avec {t('central')} comme cas central.")
        bullets = [
            (f"Moving one assumption at a time, the strongest are {t('top1')} ({t('top1_shift')}), {t('top2')} ({t('top2_shift')}) and {t('top3')} ({t('top3_shift')})." if en else
             f"En déplaçant une hypothèse à la fois, les plus fortes sont {t('top1')} ({t('top1_shift')}), {t('top2')} ({t('top2_shift')}) et {t('top3')} ({t('top3_shift')})."),
            ("These ranges show what changes if an assumption changes; they are not prediction intervals." if en else
             "Ces fourchettes montrent ce qui change si une hypothèse change ; ce ne sont pas des intervalles de prévision."),
            ("A unit-level bootstrap in the notebook adds a statistical view of the same question." if en else
             "Un bootstrap par unité dans le carnet ajoute un regard statistique sur la même question."),
        ]
    elif topic == "buildings_segments":
        lead = (f"Across {t('buildings')} buildings, the highest net increase is {t('high_net')} ({t('high_name')}) and the lowest is {t('low_net')} ({t('low_name')})." if en else
                f"Dans {t('buildings')} immeubles, la hausse nette la plus haute est de {t('high_net')} ({t('high_name')}) et la plus basse de {t('low_net')} ({t('low_name')}).")
        bullets = [
            (f"The highest rests on {t('high_pairs')} lease pairs and the lowest on {t('low_pairs')}." if en else
             f"La plus haute repose sur {t('high_pairs')} paires de baux et la plus basse sur {t('low_pairs')}."),
            ("Small segments are pulled toward the portfolio average, so a single building should not be read as a trend." if en else
             "Les petits segments sont ramenés vers la moyenne du portefeuille : un seul immeuble ne se lit donc pas comme une tendance."),
        ]
    elif topic == "data_quality":
        lead = (f"The analysis uses {t('leases')} leases in {t('units')} units, which give {t('eligible_pairs')} usable same-unit pairs." if en else
                f"L'analyse utilise {t('leases')} baux dans {t('units')} unités, ce qui donne {t('eligible_pairs')} paires d'une même unité utilisables.")
        bullets = [
            (f"{t('excluded_pairs')} pairs were excluded, each with a recorded reason; nothing is dropped silently." if en else
             f"{t('excluded_pairs')} paires ont été exclues, chacune avec une raison consignée ; rien n'est écarté en silence.")
            if f.has("excluded_pairs") else
            ("Every excluded pair is counted and reported with a reason." if en else "Chaque paire exclue est comptée et déclarée avec une raison."),
            (f"The estimate also draws on {t('concessions')} concessions, {t('asking_rows')} asking-rent observations and {t('external_rows')} public-data observations." if en else
             f"L'estimation s'appuie aussi sur {t('concessions')} concessions, {t('asking_rows')} observations de loyers affichés et {t('external_rows')} observations de données publiques."),
            ("Public figures come from CMHC, Statistics Canada, the Government of Ontario and Québec's housing tribunal, each with its release date." if en else
             "Les chiffres publics viennent de la SCHL, de Statistique Canada, du gouvernement de l'Ontario et du Tribunal administratif du logement, chacun avec sa date de parution."),
        ]
    else:
        raise ValueError(f"no template for topic {topic!r}")
    return lead, [bullet[0].upper() + bullet[1:] for bullet in bullets[:MAX_BULLETS]]


def compose(topic: str, doc: dict[str, Any], lang: str) -> tuple[Answer, FactSheet]:
    """The deterministic answer and the fact sheet it was written from."""
    caption = CAPTION["synthetic" if doc.get("mode") == "synthetic" else "real"][lang]
    if topic in (qa_topics.FORBIDDEN, qa_topics.OUT_OF_SCOPE):
        lead, bullets = (REFUSAL if topic == qa_topics.FORBIDDEN else OUT_OF_SCOPE)[lang]
        return Answer(topic, lang, lead, list(bullets), "", caption), FactSheet(topic, lang)
    sheet = fact_sheet(topic, doc, lang)
    lead, bullets = _compose_body(topic, sheet)
    return Answer(topic, lang, lead, bullets, read_more_line(topic, lang), caption), sheet


# ---------------------------------------------------------------------------- optional polish
POLISH_SYSTEM = {
    "en": ("Rewrite the draft answer in natural, plain English. Keep every number exactly as written in the draft and add no "
           "other number. Output one short first sentence, then 2 to 4 lines starting with '- '. No headings, no model codes, "
           "no section symbols."),
    "fr": ("Réécris la réponse en français naturel et simple. Garde chaque nombre exactement comme dans le brouillon et "
           "n'en ajoute aucun autre. Écris une première phrase courte, puis 2 à 4 lignes commençant par « - ». Pas de titres, "
           "pas de codes de modèles, pas de symboles de section."),
}


def parse_polished(text: str) -> tuple[str, list[str]] | None:
    """Lead and bullets of a rewritten answer, or None when the shape is wrong."""
    lines = [line.strip() for line in text.strip().splitlines() if line.strip()]
    if not lines or lines[0].startswith(("-", "*")):
        return None
    lead = re.sub(r"\*\*", "", lines[0])
    bullets = [re.sub(r"^[-*•]\s*", "", line) for line in lines[1:] if re.match(r"^[-*•]\s", line)]
    if len(bullets) != len(lines) - 1 or not MIN_BULLETS <= len(bullets) <= MAX_BULLETS:
        return None
    return lead, bullets


def accept_polished(text: str, sheet: FactSheet, lang: str) -> tuple[str, list[str]] | None:
    """The parsed rewrite when it is complete, grounded in the fact sheet, clean and in `lang`; otherwise None."""
    parsed = parse_polished(text)
    if parsed is None:
        return None
    joined = " ".join([parsed[0], *parsed[1]])
    if ungrounded_numbers(joined, {"facts": sheet.numbers}) or MODEL_CODE.search(joined) or SECTION_TOKEN.search(joined):
        return None
    if qa_topics.detect_language(joined, default=lang) != lang:
        return None
    return parsed


def polish(answer: Answer, sheet: FactSheet, question: str, client: Any) -> Answer:
    """Ask the model for a more natural wording; any failure returns the deterministic answer unchanged."""
    payload = {"question": question, "facts": sheet.as_payload(), "draft": answer.text}
    try:
        narrative.assert_privacy_payload(payload)
        response = narrative._call(client, POLISH_SYSTEM[answer.lang], json.dumps(payload, ensure_ascii=False))
        text = narrative._text(response)  # "" when stopped at max_tokens
    except Exception:  # noqa: BLE001 - the user never sees an error: the deterministic answer stands
        return answer
    parsed = accept_polished(text, sheet, answer.lang) if text else None
    if parsed is None:
        return answer
    return Answer(answer.topic, answer.lang, parsed[0], parsed[1], answer.read_more, answer.caption, source="polished")


def answer_question(question: str, doc: dict[str, Any], client: Any | None = None, default_lang: str = "fr") -> Answer:
    """Route, compose and (with a client) polish. Always returns a complete answer; never raises for a bad question."""
    route = qa_topics.route_with_client(question, client, narrative._call, default_lang) if client is not None \
        else qa_topics.route(question, default_lang)
    answer, sheet = compose(route.topic, doc, route.lang)
    if client is not None and route.topic in qa_topics.TOPICS:
        return polish(answer, sheet, question, client)
    return answer
