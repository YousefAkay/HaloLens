"""Altair charts for the Streamlit app, built only from the aggregates JSON.

Owner: FCT (task I-11b, delegated by INT). Every function returns None when the data it needs is absent, so a view can simply
skip it. Colours come from leaselens.contracts (net, contractual, market, plus the neutral grey).
"""

from __future__ import annotations

import math
from typing import Any

import altair as alt
import pandas as pd

from app.ui import LABELS, t
from leaselens.contracts import COLOR_CONTRACT, COLOR_MARKET, COLOR_NAIVE, COLOR_NET

FACET_COLUMNS = 3  # backtest panels per row
PANEL_SIZE_PX = 150
BAND_OPACITY = 0.25
MARKER_SIZE = 160
BAR_HEIGHT_PX = 26  # per bar, for charts whose height follows the number of rows
ANSWER_ROW_PX = 46  # per row of the answer chart, so the three labels stay readable
AXIS_ALLOWANCE_PX = 80  # Streamlit fits the whole figure, axes included, into the height: the plot needs this much extra
LABEL_LIMIT_PX = 260  # axis labels are cut after this width
MIN_CHART_HEIGHT_PX = 120
CHAMPION_STAR = "★"
NUMERIC_SETTINGS = {"max_gap", "quantiles", "years"}  # variants whose setting is shown next to the label
SHIFT_SETTINGS = {"incentives_deeper", "incentives_shallower", "more_renewals", "fewer_renewals"}  # settings in pp
MODEL_CHOICE = "model_choice"


def _present(value: Any) -> bool:
    return value is not None and not (isinstance(value, float) and math.isnan(value))


def _height(rows: int) -> int:
    return max(MIN_CHART_HEIGHT_PX, BAR_HEIGHT_PX * rows) + AXIS_ALLOWANCE_PX


# ---------------------------------------------------------------------------
# Overview: contract -> incentive effect -> net headline, scenario band and E2 marker
# ---------------------------------------------------------------------------
def answer_chart(doc: dict[str, Any], lang: str) -> alt.Chart | None:
    """Contractual headline, the incentive effect (contract minus net) and the net headline, with the scenario band and E2."""
    net, contract = doc["headline"]["net_pct"], doc["headline"]["contract_pct"]
    if not (_present(net) and _present(contract)):
        return None
    labels = {"contract": t("chart_contract", lang), "effect": t("chart_effect", lang), "net": t("chart_net", lang)}
    order = [labels["contract"], labels["effect"], labels["net"]]
    rows = pd.DataFrame([
        {"label": labels["contract"], "start": 0.0, "end": contract, "color": COLOR_CONTRACT},
        {"label": labels["effect"], "start": net, "end": contract, "color": COLOR_NAIVE},
        {"label": labels["net"], "start": 0.0, "end": net, "color": COLOR_NET}])
    y = alt.Y("label:N", sort=order, title=None, axis=alt.Axis(labelLimit=LABEL_LIMIT_PX))
    bars = alt.Chart(rows).mark_bar().encode(
        y=y, x=alt.X("start:Q", title=t("chart_axis_pct", lang)), x2="end:Q", color=alt.Color("color:N", scale=None),
        tooltip=[alt.Tooltip("label:N", title=""), alt.Tooltip("start:Q", format=".2f"), alt.Tooltip("end:Q", format=".2f")])
    layers = []
    scenarios = doc.get("scenarios") or {}
    if _present(scenarios.get("low_net_pct")) and _present(scenarios.get("high_net_pct")):
        band = pd.DataFrame([{"label": labels["net"], "low": scenarios["low_net_pct"], "high": scenarios["high_net_pct"],
                              "name": t("chart_band", lang)}])
        layers.append(alt.Chart(band).mark_rect(opacity=BAND_OPACITY, color=COLOR_MARKET).encode(
            y=y, x="low:Q", x2="high:Q", tooltip=["name:N", alt.Tooltip("low:Q", format=".2f"), alt.Tooltip("high:Q", format=".2f")]))
    layers.append(bars)  # the band sits behind the bars, so the bars keep their own colours
    if _present(scenarios.get("central_net_pct")):
        marker = pd.DataFrame([{"label": labels["net"], "central": scenarios["central_net_pct"], "name": t("chart_e2", lang)}])
        layers.append(alt.Chart(marker).mark_point(shape="diamond", size=MARKER_SIZE, filled=True, color=COLOR_MARKET).encode(
            y=y, x="central:Q", tooltip=["name:N", alt.Tooltip("central:Q", format=".2f")]))
    return alt.layer(*layers).properties(height=ANSWER_ROW_PX * len(order) + AXIS_ALLOWANCE_PX)


# ---------------------------------------------------------------------------
# Validation: net forecast error per model and year, for one information rule
# ---------------------------------------------------------------------------
def backtest_chart(doc: dict[str, Any], rule: str, lang: str) -> alt.Chart | None:
    """Net forecast error (pp) per model and year, one small panel per model; the champion's panel is starred."""
    rows = pd.DataFrame(doc.get("backtest") or [])
    if rows.empty:
        return None
    rows = rows[(rows["information_rule"] == rule) & rows["error_pp_net"].map(_present)]
    if rows.empty:
        return None
    champion = doc["headline"]["model"]
    rows = rows.assign(panel=[f"{CHAMPION_STAR} {model} ({t('val_chart_champion', lang)})" if model == champion else model
                              for model in rows["model"]])
    order = list(dict.fromkeys(rows["panel"]))
    bars = alt.Chart().mark_bar(color=COLOR_NET).encode(
        x=alt.X("year:O", title=None), y=alt.Y("error_pp_net:Q", title=t("val_chart_title", lang)),
        tooltip=["model:N", "year:O", alt.Tooltip("forecast_net_pct:Q", format=".2f"),
                 alt.Tooltip("actual_net_pct:Q", format=".2f"), alt.Tooltip("error_pp_net:Q", format=".2f")])
    zero = alt.Chart().mark_rule(color=COLOR_NAIVE).encode(y=alt.datum(0))
    return alt.layer(bars, zero, data=rows).properties(width=PANEL_SIZE_PX, height=PANEL_SIZE_PX).facet(
        facet=alt.Facet("panel:N", sort=order, title=None), columns=FACET_COLUMNS)


# ---------------------------------------------------------------------------
# Scenarios: tornado of one-at-a-time sensitivities, and the optional bootstrap band
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
    return f"{assumption}: {text} [{row['model']}]"  # the model keeps two rows with the same assumption apart


def tornado_chart(doc: dict[str, Any], lang: str) -> alt.Chart | None:
    """Change in the net headline from altering one assumption at a time, sorted by absolute change."""
    rows = pd.DataFrame(doc.get("sensitivity") or [])
    if rows.empty:
        return None
    rows = rows[rows["delta_pp"].map(_present)]
    if rows.empty:
        return None
    rows = rows.assign(label=[sensitivity_label(row, lang) for row in rows.to_dict("records")],
                       abs_delta=rows["delta_pp"].abs(),
                       color=[COLOR_MARKET if assumption == MODEL_CHOICE else COLOR_NET for assumption in rows["assumption"]])
    order = list(rows.sort_values("abs_delta", ascending=False, kind="stable")["label"])
    bars = alt.Chart(rows).mark_bar().encode(
        y=alt.Y("label:N", sort=order, title=None), x=alt.X("delta_pp:Q", title=t("sc_axis_delta", lang)),
        color=alt.Color("color:N", scale=None),
        tooltip=["label:N", "model:N", alt.Tooltip("base_net_pct:Q", format=".2f"),
                 alt.Tooltip("headline_net_pct:Q", format=".2f"), alt.Tooltip("delta_pp:Q", format="+.2f")])
    zero = alt.Chart(pd.DataFrame({"zero": [0]})).mark_rule(color=COLOR_NAIVE).encode(x="zero:Q")
    return alt.layer(bars, zero).properties(height=_height(len(rows)))


def bootstrap_band(doc: dict[str, Any], lang: str) -> alt.Chart | None:
    """Sampling-uncertainty interval of the net and contractual headline, when the aggregates carry one (F-11)."""
    boot = doc.get("bootstrap")
    if not isinstance(boot, dict):
        return None
    rows = []
    for key, label, color, headline in (("net_pct", t("chart_net", lang), COLOR_NET, doc["headline"]["net_pct"]),
                                        ("contract_pct", t("chart_contract", lang), COLOR_CONTRACT, doc["headline"]["contract_pct"])):
        interval = boot.get(key)
        if isinstance(interval, dict) and _present(interval.get("lower")) and _present(interval.get("upper")):
            rows.append({"label": label, "lower": interval["lower"], "upper": interval["upper"], "headline": headline,
                         "color": color})
    if not rows:
        return None
    frame = pd.DataFrame(rows)
    order = list(frame["label"])
    y = alt.Y("label:N", sort=order, title=None)
    interval = alt.Chart(frame).mark_rule(strokeWidth=6).encode(
        y=y, x=alt.X("lower:Q", title=t("chart_axis_pct", lang)), x2="upper:Q", color=alt.Color("color:N", scale=None),
        tooltip=["label:N", alt.Tooltip("lower:Q", format=".2f"), alt.Tooltip("upper:Q", format=".2f")])
    points = alt.Chart(frame).mark_point(shape="diamond", size=MARKER_SIZE, filled=True, color="black").encode(
        y=y, x="headline:Q", tooltip=["label:N", alt.Tooltip("headline:Q", format=".2f")])
    return alt.layer(interval, points).properties(height=_height(len(rows)))


# ---------------------------------------------------------------------------
# By building: unique public labels, one table and one chart over the same cells
# ---------------------------------------------------------------------------
def building_cells(doc: dict[str, Any], lang: str) -> pd.DataFrame | None:
    """The building x bedroom cells with unique public labels; None when there are none.

    A building with several property cells (phases) gets "phase 1", "phase 2", ... in the order the cells appear: a new phase
    starts when the bedroom count stops increasing. No property code is shown anywhere.
    """
    cells = pd.DataFrame(doc.get("building_beds") or [])
    if cells.empty:
        return None
    phases, last_beds, phase = [], {}, {}
    for building, beds in zip(cells["building"], cells["beds"]):
        if building in last_beds and beds <= last_beds[building]:
            phase[building] += 1
        phase.setdefault(building, 1)
        last_beds[building] = beds
        phases.append(phase[building])
    cells = cells.assign(phase=phases)
    multi_phase = cells.groupby("building")["phase"].transform("max") > 1
    cells["label"] = [
        t("bd_cell", lang, building=row.building, beds=row.beds) + (f" · {t('bd_phase', lang, phase=row.phase)}" if many else "")
        for row, many in zip(cells.itertuples(), multi_phase)]
    return cells


def building_chart(doc: dict[str, Any], lang: str) -> alt.Chart | None:
    """Shrunk net increase per labelled cell (bars) with the raw value (tick); pair counts in the tooltip."""
    cells = building_cells(doc, lang)
    if cells is None:
        return None
    order = list(cells.sort_values("net_pct_shrunk")["label"])
    y = alt.Y("label:N", sort=order, title=None)
    tooltip = ["label:N", alt.Tooltip("n_pairs:Q", title=t("bd_col_pairs", lang)),
               alt.Tooltip("net_pct_shrunk:Q", format=".2f"), alt.Tooltip("net_pct_raw:Q", format=".2f")]
    bars = alt.Chart(cells).mark_bar(color=COLOR_NET).encode(
        y=y, x=alt.X("net_pct_shrunk:Q", title=t("bd_axis", lang)), tooltip=tooltip)
    ticks = alt.Chart(cells).mark_tick(color=COLOR_NAIVE, thickness=3, size=BAR_HEIGHT_PX - 8).encode(
        y=y, x="net_pct_raw:Q", tooltip=tooltip)
    return alt.layer(bars, ticks).properties(height=_height(len(cells)))
