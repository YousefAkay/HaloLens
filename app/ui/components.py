"""Pure HTML components and the data preparation behind them (hero, range bars, validation, tornado, buildings, answers).

Owner: FCT (redesign I-11c, from the design hand-off). Every function returns a string or a small structure and reads only the
aggregates document passed in: no file, no network, no computation of an authoritative figure. Every dynamic string is escaped
with `html.escape`; a null value is shown as "n/a" and its marker is left out. Bars are percent-positioned divs on a scale that
starts at the design's fixed range and widens when a value would fall outside it, so nothing is clipped.
"""

from __future__ import annotations

import html
import math
import re
from typing import Any

import pandas as pd

from app.ui.labels import DEFAULT_LANG, LABELS, t
from leaselens.evaluate.backtest import RULE_DEC31, RULE_JAN31, select_champion, summarize_models

MISSING = "n/a"
PERCENT_DECIMALS = 1  # percentages in the page
ERROR_DECIMALS = 2  # errors and deltas in percentage points
HERO_SCALE = (0.0, 8.0)  # percent scale of the hero range bar and the forecast/actual bars
MAE_SCALE_PP = 5.0  # error scale of the model comparison
TORNADO_SCALE_PP = 3.0  # half-width of the tornado
BUILDING_SCALE = (2.0, 6.0)  # percent scale of the building dots
TORNADO_ROWS = 8  # strongest sensitivities shown
DOT_BASE_PX, DOT_PER_PAIR_PX, DOT_MAX_PX = 10.0, 0.6, 30.0  # building dot diameter: base + per pair, capped to the row height
AXIS_STEP = 1.0  # tick spacing of the percent axes
MONTHS = {"en": ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"),
          "fr": ("janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc.")}
SECTION_REFERENCE = re.compile(r"§\d+[ab]?")
NUMERIC_SETTINGS = {"max_gap", "quantiles", "years"}  # sensitivity variants whose setting is shown next to the label
SHIFT_SETTINGS = {"incentives_deeper", "incentives_shallower", "more_renewals", "fewer_renewals"}  # settings in pp
MODEL_CHOICE = "model_choice"


def esc(value: Any) -> str:
    """HTML-escape any value."""
    return html.escape(str(value), quote=True)


def pct(value: float | None, decimals: int = PERCENT_DECIMALS) -> str:
    """A percentage with its sign-free number and a space before %, or "n/a"."""
    return f"{value:.{decimals}f} %" if _present(value) else MISSING


def pp(value: float | None) -> str:
    return f"{value:+.{ERROR_DECIMALS}f}" if _present(value) else MISSING


def format_date(iso: str, lang: str) -> str:
    """'31 Jan 2026' (English) or '31 janv. 2026' (French) from an ISO date."""
    year, month, day = (int(part) for part in iso.split("-"))
    return f"{day} {MONTHS[lang][month - 1]} {year}"


def format_day_month(iso: str, lang: str) -> str:
    """'31 Dec' / '31 déc.' from an ISO date."""
    _, month, day = (int(part) for part in iso.split("-"))
    return f"{day} {MONTHS[lang][month - 1]}"


def _present(value: Any) -> bool:
    return value is not None and not (isinstance(value, float) and math.isnan(value))


present = _present  # the public name, for the app's own guards on values read from the aggregates


def model_name(doc: dict[str, Any]) -> str:
    """The headline model's name, or "n/a" when the aggregates hold null."""
    return doc["headline"]["model"] if doc["headline"]["model"] is not None else MISSING


def scale_with(values: list[float | None], low: float, high: float) -> tuple[float, float]:
    """The design's scale, widened to whole units when a value would fall outside it."""
    present = [value for value in values if _present(value)]
    if not present:
        return low, high
    return min(low, math.floor(min(present))), max(high, math.ceil(max(present)))


def _pos(value: float, low: float, high: float) -> float:
    """Percent position of a value on a scale, clamped to the track."""
    return max(0.0, min(100.0, 100.0 * (value - low) / (high - low)))


def _axis(low: float, high: float, fmt: str = "{:.0f} %") -> str:
    ticks = [low + index * AXIS_STEP for index in range(int((high - low) / AXIS_STEP) + 1)]
    return '<div class="ll-axis">' + "".join(
        f'<span style="left:{_pos(tick, low, high):.2f}%">{esc(fmt.format(tick))}</span>' for tick in ticks) + "</div>"


# ---------------------------------------------------------------------------
# Masthead and sections
# ---------------------------------------------------------------------------
def masthead_title(real: bool, lang: str) -> str:
    """Title, subtitle and the real/demo badge; the badge follows the selected data mode (a mismatching file is rejected)."""
    badge = t("badge_real" if real else "badge_demo", lang)
    return (f'<p class="ll-title">{esc(t("app_title", lang))}<span class="ll-badge">{esc(badge)}</span></p>'
            f'<p class="ll-sub">{esc(t("masthead_sub", lang))}</p>')


def notice(doc: dict[str, Any]) -> str:
    """The synthetic-data line (the document's own note); empty for real data."""
    return f'<div class="ll-notice">{esc(doc["note"])}</div>' if doc["mode"] == "synthetic" else ""


def section_header(anchor: str, kicker: str, headline: str, ai: bool = False) -> str:
    cls = "ll-section"
    kicker_class = "ll-kicker ai" if ai else "ll-kicker"
    return (f'<div id="{esc(anchor)}" class="{cls}"><div class="{kicker_class}">{esc(kicker)}</div>'
            f'<h2 class="ll-h2">{esc(headline)}</h2></div>')


# ---------------------------------------------------------------------------
# 01 Answer
# ---------------------------------------------------------------------------
def range_bar(low: float, high: float, band: tuple[float, float] | None = None, markers: tuple = (), dots: tuple = (),
              band_class: str = "") -> str:
    """A track with an optional shaded band, vertical markers ((value, class)) and dots ((value, class)).

    Values that are None are skipped, so a missing figure never draws a marker.
    """
    parts = ['<div class="ll-scale"><div class="ll-track"></div>']
    if band is not None and _present(band[0]) and _present(band[1]):
        start, end = _pos(band[0], low, high), _pos(band[1], low, high)
        parts.append(f'<div class="ll-band {esc(band_class)}" style="left:{start:.2f}%;width:{max(end - start, 0):.2f}%"></div>')
    for value, kind in markers:
        if _present(value):
            parts.append(f'<div class="ll-marker {esc(kind)}" style="left:{_pos(value, low, high):.2f}%"></div>')
    for value, kind in dots:
        if _present(value):
            parts.append(f'<div class="ll-dot {esc(kind)}" style="left:{_pos(value, low, high):.2f}%"></div>')
    parts.append("</div>")
    parts.append(_axis(low, high))
    return "".join(parts)


def hero(doc: dict[str, Any], lang: str = DEFAULT_LANG) -> str:
    """Caption, the headline number, one sentence, the range bar and its legend (section 01)."""
    headline, companions = doc["headline"], doc["companions"]
    net, contract = headline["net_pct"], headline["contract_pct"]
    model_range = headline["model_range"]
    low, high = scale_with([net, contract, model_range["low_net_pct"], model_range["high_net_pct"]], *HERO_SCALE)
    number = MISSING if net is None else f"{net:.{PERCENT_DECIMALS}f}"
    sentence = t("hero_sentence", lang, contract=pct(contract), median_net=pct(companions["median_net_pct"]),
                 median_contract=pct(companions["median_contract_pct"]))
    caption = t("answer_caption", lang, year=doc["target_year"], crm=format_date(doc["as_of"]["crm_cutoff"], lang))
    bar = range_bar(low, high, band=(model_range["low_net_pct"], model_range["high_net_pct"]),
                    markers=((net, "net"), (contract, "contract")))
    legend = ('<div class="ll-legend">'
              f'<span><i class="net"></i>{esc(t("legend_net", lang))}</span>'
              f'<span><i class="contract"></i>{esc(t("legend_contract", lang))}</span>'
              f'<span><i class="band"></i>{esc(t("legend_band", lang))}</span></div>')
    return (f'<div class="ll-caption">{esc(caption)}</div>'
            f'<div class="ll-hero-row"><div class="ll-hero-number">{esc(number)}<span class="ll-hero-pct">%</span></div>'
            f'<div class="ll-hero-text"><div class="ll-hero-label">{esc(t("hero_label", lang))}</div>'
            f'<p>{esc(sentence)}</p></div></div>{bar}{legend}'
            f'<div class="ll-small">{esc(t("range_caption", lang, model=model_name(doc)))}</div>')


def stats(doc: dict[str, Any], lang: str = DEFAULT_LANG) -> str:
    """The four supporting facts: Québec, Ontario, coverage, information. No cards, no rules."""
    blocks = []
    for code in ("QC", "ON"):
        province = doc["headline"]["provinces"][code]
        name = t(f"province_{code.lower()}", lang)
        if province["net_pct"] is None and province["contract_pct"] is None:
            body = t("stat_province_na", lang)
        else:
            body = t("stat_province_values", lang, net=pct(province["net_pct"]), contract=pct(province["contract_pct"]))
        blocks.append((name, body, ""))
    coverage = doc["coverage"]
    blocks.append((t("stat_coverage_title", lang),
                   t("stat_coverage_body", lang, pairs=coverage["eligible_pairs"], units=coverage["units"],
                     leases=coverage["leases"], excluded=coverage["excluded_pairs"]), ""))
    as_of = doc["as_of"]
    blocks.append((t("stat_info_title", lang),
                   t("stat_info_body", lang, external=format_date(as_of["external_cutoff"], lang),
                     crm=format_date(as_of["crm_cutoff"], lang)),
                   t("stat_info_tip", lang, strict=format_date(as_of["external_strict_cutoff"], lang))))
    return '<div class="ll-stats">' + "".join(
        f'<div title="{esc(tip)}"><div class="ll-stat-title">{esc(title)}</div><div class="ll-stat-body">{esc(body)}</div></div>'
        for title, body, tip in blocks) + "</div>"


# ---------------------------------------------------------------------------
# 02 Why
# ---------------------------------------------------------------------------
def steps(lang: str) -> str:
    """Computation -> Evidence -> Explanation, the last in the AI colour."""
    parts = []
    for index in (1, 2, 3):
        ai = " ai" if index == 3 else ""
        parts.append(f'<div><div class="ll-step-k{ai}">{esc(t(f"why_step_{index}", lang))}</div>'
                     f'<div class="ll-step-t">{esc(t(f"why_title_{index}", lang))}</div>'
                     f'<div>{esc(t(f"why_body_{index}", lang))}</div></div>')
    return '<div class="ll-steps">' + "".join(parts) + "</div>"


# ---------------------------------------------------------------------------
# 03 Validation: data preparation (the ranking is the pipeline's own rule) and charts
# ---------------------------------------------------------------------------
def backtest_frame(doc: dict[str, Any]) -> pd.DataFrame:
    """The backtest rows in the shape select_champion and summarize_models expect (model, year, rule, abs error)."""
    rows = pd.DataFrame(doc["backtest"]).rename(columns={"information_rule": "rule"})
    for column in ("forecast_net_pct", "actual_net_pct", "error_pp_net"):
        rows[column] = pd.to_numeric(rows[column], errors="coerce")           # a null in the file is a missing value, not an error
    rows["abs_error_pp_net"] = rows["error_pp_net"].abs()
    return rows


def selection_ranking(doc: dict[str, Any], cfg: dict[str, Any]) -> dict[str, Any]:
    """The pre-declared champion rule applied to the file's backtest rows, so the displayed ranking is the pipeline's own.

    Raises ValueError when no model has a forecast for every selection year.
    """
    return select_champion(backtest_frame(doc), cfg)


def rule_summary(doc: dict[str, Any], cfg: dict[str, Any], rule: str) -> pd.DataFrame:
    """Selection, holdout and pooled mean absolute net error per model for one information rule."""
    summary = summarize_models(backtest_frame(doc), cfg)
    return summary[summary["rule"] == rule].drop(columns="rule").reset_index(drop=True)


def validation_figures(doc: dict[str, Any], cfg: dict[str, Any]) -> dict[str, Any]:
    """Everything the validation section draws, from the file's backtest rows and the selection years in the config.

    Returns: champion (the model the pre-declared rule picks, or None), models (ordered best first: model, mean over the selection
    years, per-year |error|, holdout |error|, champion flag), left (the headline model's forecast and actual per year),
    selection_years, holdout_year, model_spread and year_spread (for the generated headline).
    """
    frame = backtest_frame(doc)
    headline = doc["headline"]
    selection, holdout = cfg["forecast_years"]["selection_years"], cfg["forecast_years"]["holdout_year"]
    try:
        chosen = selection_ranking(doc, cfg)
    except ValueError:
        chosen = None
    models = []
    if chosen is not None:
        jan31 = frame[frame["rule"] == RULE_JAN31]
        for row in chosen["ranking"][chosen["ranking"]["eligible"]].itertuples():
            mine = jan31[jan31["model"] == row.model].set_index("year")["abs_error_pp_net"]
            models.append({"model": row.model, "mean": float(row.mae_selection_pp),
                           "years": {int(year): float(mine[year]) for year in selection if year in mine.index},
                           "holdout": float(mine[holdout]) if holdout in mine.index and _present(mine[holdout]) else None,
                           "champion": row.model == chosen["champion"]})
    mine = frame[(frame["model"] == headline["model"]) & (frame["rule"] == headline["information_rule"])].sort_values("year") \
        if headline["model"] is not None else frame.iloc[0:0]
    left = [{"year": int(row.year), "forecast": row.forecast_net_pct, "actual": row.actual_net_pct}
            for row in mine.itertuples() if _present(row.forecast_net_pct) and _present(row.actual_net_pct)]
    means = [model["mean"] for model in models]
    headline_years = next((list(model["years"].values()) for model in models if model["model"] == headline["model"]), [])
    return {"champion": chosen["champion"] if chosen else None, "models": models, "left": left,
            "selection_years": list(selection), "holdout_year": holdout,
            "model_spread": (max(means) - min(means)) if len(means) > 1 else None,
            "year_spread": (max(headline_years) - min(headline_years)) if len(headline_years) > 1 else None}


def validation_headline(figures: dict[str, Any], lang: str) -> str:
    """The section headline, chosen from the data: do the engines differ less than the years do?"""
    model_spread, year_spread = figures["model_spread"], figures["year_spread"]
    if model_spread is None or year_spread is None:
        return t("val_headline_na", lang)
    return t("val_headline_less" if model_spread < year_spread else "val_headline_more", lang)


def forecast_actual(left: list[dict[str, Any]], lang: str) -> str:
    """Two thin bars per year: forecast (grey) and actual (ink), with their values."""
    low, high = scale_with([value for row in left for value in (row["forecast"], row["actual"])], *HERO_SCALE)
    rows = []
    for row in left:
        pair = "".join(
            f'<div class="ll-trk"><div class="ll-fill thin {cls}" style="width:{_pos(value, low, high):.2f}%"></div></div>'
            for value, cls in ((row["forecast"], "forecast"), (row["actual"], "actual")))
        values = (f'<div class="val">{esc(t("val_forecast", lang))} {esc(pct(row["forecast"]))}<br>'
                  f'{esc(t("val_actual", lang))} {esc(pct(row["actual"]))}</div>')
        rows.append(f'<div class="ll-row" style="grid-template-columns:70px 1fr 150px"><div class="lbl ll-year">{esc(row["year"])}'
                    f'</div><div class="ll-pair">{pair}</div>{values}</div>')
    return '<div class="ll-rows">' + "".join(rows) + "</div>"


def mae_chart(models: list[dict[str, Any]], lang: str) -> str:
    """Mean |error| per model over the selection years: bar, one tick per year, hollow dot for the holdout, champion in cyan."""
    values = [model["mean"] for model in models] + [v for model in models for v in model["years"].values()] + [
        model["holdout"] for model in models]
    high = max(MAE_SCALE_PP, math.ceil(max([v for v in values if _present(v)], default=0.0)))
    rows = []
    for model in models:
        cls = "lead" if model["champion"] else ""  # the champion is the full net colour, the others its tint
        marks = "".join(f'<div class="ll-tick" style="left:{_pos(value, 0.0, high):.2f}%"></div>' for value in model["years"].values())
        hollow = (f'<div class="ll-hollow" title="{esc(t("val_holdout", lang))}" style="left:{_pos(model["holdout"], 0.0, high):.2f}%">'
                  "</div>") if model["holdout"] is not None else ""
        rows.append(f'<div class="ll-row"><div class="lbl" title="{esc(model["model"])}">{esc(model["model"])}</div>'
                    f'<div class="ll-trk"><div class="ll-fill {cls}" style="width:{_pos(model["mean"], 0.0, high):.2f}%"></div>'
                    f'{marks}{hollow}</div><div class="val">{model["mean"]:.{ERROR_DECIMALS}f}</div></div>')
    return '<div class="ll-rows">' + "".join(rows) + "</div>"


# ---------------------------------------------------------------------------
# 04 Scenario Lab: tornado
# ---------------------------------------------------------------------------
def sensitivity_label(row: dict[str, Any], lang: str) -> str:
    """Readable label of one sensitivity row from its machine keys; unknown keys fall back to the raw text."""
    labels = LABELS[lang]
    assumption = labels.get(f"as_{row['assumption']}", row["assumption"])
    variant, setting = row["variant"], row.get("setting", "")
    if row["assumption"] == MODEL_CHOICE:
        return f"{assumption}: {variant}"
    text = labels.get(f"va_{variant}", variant)
    if variant in NUMERIC_SETTINGS:
        text = f"{text} {setting}"
    elif variant in SHIFT_SETTINGS:
        text = f"{text} ({float(setting):+.1f} {labels['pp']})"
    return f"{assumption}: {text} [{row['model']}]"


def tornado_rows(doc: dict[str, Any], lang: str, limit: int = TORNADO_ROWS) -> list[dict[str, Any]]:
    """The strongest sensitivities: sorted by absolute change, zero and missing changes left out."""
    rows = [{"label": sensitivity_label(row, lang), "delta": row["delta_pp"]} for row in doc.get("sensitivity") or []
            if _present(row.get("delta_pp")) and row["delta_pp"] != 0]
    return sorted(rows, key=lambda row: abs(row["delta"]), reverse=True)[:limit]


def tornado(rows: list[dict[str, Any]]) -> str:
    """Bars from a centre line: negative in neutral, positive in cyan."""
    half = max(TORNADO_SCALE_PP, math.ceil(max([abs(row["delta"]) for row in rows], default=0.0)))
    out = []
    for row in rows:
        width = 50.0 * abs(row["delta"]) / half
        left = 50.0 if row["delta"] > 0 else 50.0 - width
        cls = "pos" if row["delta"] > 0 else "neg"
        out.append(f'<div class="ll-torn-row"><div title="{esc(row["label"])}">{esc(row["label"])}</div>'
                   f'<div class="ll-torn-trk"><div class="ll-torn-mid"></div>'
                   f'<div class="ll-torn-bar {cls}" style="left:{left:.2f}%;width:{width:.2f}%"></div></div>'
                   f'<div class="val">{esc(pp(row["delta"]))}</div></div>')
    return '<div class="ll-torn">' + "".join(out) + "</div>"


# ---------------------------------------------------------------------------
# 05 Buildings
# ---------------------------------------------------------------------------
def building_cells(doc: dict[str, Any], lang: str) -> pd.DataFrame | None:
    """The building x bedroom cells with unique public labels; None when there are none.

    The aggregates carry no property code (that would identify a building cell), so phases are INFERRED FROM THE ROW ORDER OF THE
    EXPORT: when several rows share the same building and bedroom count, the k-th such row is "phase k". Rows that are the only
    one for their building and bedroom count get no phase word, so a building with an extra property cell that has other
    bedroom counts never gets a guessed phase. The rule does not depend on how the export sorts the rows (cell first or bedroom
    count first) as long as the cells keep the same relative order inside a bedroom count, and a test checks both orders.
    The `phase` column holds k for every row (1 for a single row); no property code is shown anywhere.
    """
    cells = pd.DataFrame(doc.get("building_beds") or [])
    if cells.empty:
        return None
    cells = cells.assign(phase=cells.groupby(["building", "beds"]).cumcount() + 1)
    shared = cells.groupby(["building", "beds"])["phase"].transform("max") > 1
    cells["label"] = [
        t("bd_cell", lang, building=row.building, beds=row.beds) + (f" · {t('bd_phase', lang, phase=row.phase)}" if many else "")
        for row, many in zip(cells.itertuples(), shared)]
    return cells


def _with_net(cells: pd.DataFrame | None) -> pd.DataFrame | None:
    """The cells that have a shrunk net increase to draw (a null in the aggregates is left out of the chart and the headline)."""
    if cells is None:
        return None
    drawn = cells[cells["net_pct_shrunk"].map(_present)]
    return drawn if not drawn.empty else None


def building_headline(cells: pd.DataFrame | None, lang: str) -> str:
    """A sentence from the data: the best and the worst building by shrunk net increase."""
    drawn = _with_net(cells)
    if drawn is None:
        return t("bd_headline_empty", lang)
    ordered = drawn.sort_values("net_pct_shrunk", ascending=False, kind="stable")
    best, worst = ordered.iloc[0], ordered.iloc[-1]
    if best["building"] == worst["building"]:
        return t("bd_headline_one", lang, best=best["building"], best_pct=pct(best["net_pct_shrunk"]))
    return t("bd_headline", lang, best=best["building"], best_pct=pct(best["net_pct_shrunk"]), worst=worst["building"],
             worst_pct=pct(worst["net_pct_shrunk"]))


def building_dots(cells: pd.DataFrame, lang: str) -> str:
    """One row per labelled cell, best first: dot at the shrunk net (sized by pairs), tick at the raw value when it exists."""
    drawn = _with_net(cells)
    if drawn is None:
        return ""
    ordered = drawn.sort_values("net_pct_shrunk", ascending=False, kind="stable")
    low, high = scale_with(list(ordered["net_pct_shrunk"]) + list(ordered["net_pct_raw"]), *BUILDING_SCALE)
    rows = []
    for row in ordered.itertuples():
        diameter = min(DOT_BASE_PX + DOT_PER_PAIR_PX * (row.n_pairs if _present(row.n_pairs) else 0), DOT_MAX_PX)
        tick = (f'<div class="ll-bd-tick" style="left:{_pos(row.net_pct_raw, low, high):.2f}%"></div>'
                if _present(row.net_pct_raw) else "")
        rows.append(
            f'<div class="ll-bd-row"><div title="{esc(row.label)}">{esc(row.label)}</div>'
            f'<div class="ll-bd-trk">{tick}'
            f'<div class="ll-bd-dot" style="left:{_pos(row.net_pct_shrunk, low, high):.2f}%;width:{diameter:.1f}px;height:{diameter:.1f}px">'
            f'</div></div><div class="val" style="text-align:left">{esc(pct(row.net_pct_shrunk))} · '
            f'{esc(t("bd_pairs", lang, n=row.n_pairs if _present(row.n_pairs) else MISSING))}</div></div>')
    axis = "".join(f'<span style="left:{_pos(tick, low, high):.2f}%">{esc(f"{tick:.0f} %")}</span>'
                   for tick in [low + index * AXIS_STEP for index in range(int((high - low) / AXIS_STEP) + 1)])
    return '<div class="ll-rows">' + "".join(rows) + f'</div><div class="ll-bd-axis">{axis}</div>'


# ---------------------------------------------------------------------------
# 06 Ask: answers
# ---------------------------------------------------------------------------
def chips_html(items: list[str]) -> str:
    """Small pills, used to show what the AI understood of a question."""
    return "".join(f'<span class="ll-chip">{esc(item)}</span>' for item in items)


def answer_html(question: str, text: str, lang: str, checked: bool) -> str:
    """An answer set like a newspaper Q&A: italic question, short bold answer, bullets, sources and the match mark.

    The first line is the short answer (its ** markers are dropped); lines starting with "-" or "*" become bullets; the other
    lines are paragraphs. Section references (§05, §11a) found in the text are listed in the footer. `checked` adds the
    mark that the numbers were matched to the aggregates (only for answers that passed the number guard).
    """
    lines = [line.strip() for line in text.strip().splitlines() if line.strip()]
    lead = re.sub(r"\*\*", "", lines[0]) if lines else ""
    bullets = [re.sub(r"^[-*]\s*", "", line) for line in lines[1:] if re.match(r"^[-*]\s", line)]
    paragraphs = [re.sub(r"\*\*", "", line) for line in lines[1:] if not re.match(r"^[-*]\s", line)]
    sections = list(dict.fromkeys(SECTION_REFERENCE.findall(text)))
    foot = []
    if sections:
        foot.append(esc(t("ask_sources", lang, sections=" · ".join(sections))))
    if checked:
        foot.append(f'<span class="ok">{esc(t("ask_checked", lang))}</span>')
    return (f'<div class="ll-q">{esc(question)}</div><p class="ll-a">{esc(lead)}</p>'
            + "".join(f"<p>{esc(paragraph)}</p>" for paragraph in paragraphs)
            + (f'<ul class="ll-a-list">{"".join(f"<li>{esc(item)}</li>" for item in bullets)}</ul>' if bullets else "")
            + (f'<div class="ll-a-foot">{" ".join(foot)}</div>' if foot else ""))
