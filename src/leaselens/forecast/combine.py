"""Renewal + turnover + incentive engines combined with fixed weights.

Owner: FCT. Implements `forecast` (AGENTS.md Section 7.3), the single pipeline behind `estimate_2026()` and `backtest()`.

Per frozen-weight segment (prop_code x beds x is_renewal, core.yaml headline.segment_keys), contractual annualized log growth is
    renewal engine : weighted blend of the segment's recent history and the portfolio nowcast level
    turnover engine: weighted blend of recent history, MSR's asking-rent signal and the nowcast level
and the incentive engine (F-03) turns it into net growth: log net = log contract + log(1 - d1) - log(1 - d0).
Segment forecasts are aggregated with the fixed weights, headline % = 100 x (exp(sum w_s x g_s) - 1) (AGENTS.md 9.1).
Everything is read from the Snapshot, so nothing after the cutoff can enter. Weights live in forecast.yaml (`combine`).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from leaselens.contracts import ForecastResult, Snapshot
from leaselens.forecast.baselines import frozen_weights, target_year_for, to_pct, training_pairs, winsor_bounds
from leaselens.forecast.monthly_index import build_monthly_index
from leaselens.forecast.nowcast import nowcast
from leaselens.incentives.engine import forecast_discount, net_log_growth
from leaselens.market.asking import turnover_signal

MODEL_NAME = "E1_engine_blend"
MEDIAN_QUANTILE = 0.5  # share of the total weight at which the weighted median sits
GROWTH = "loggrowth_contract"
POOL_PROVINCE_KEYS = ["province", "is_renewal"]
POOL_PORTFOLIO_KEYS = ["is_renewal"]
SOURCE_SEGMENT, SOURCE_PROVINCE, SOURCE_PORTFOLIO, SOURCE_NONE = "segment", "province_pool", "portfolio_pool", "none"


def weighted_median(values: pd.Series, weights: pd.Series) -> float:
    """Smallest value whose cumulative weight reaches half of the total weight."""
    order = np.argsort(values.to_numpy())
    cumulative = np.cumsum(weights.to_numpy()[order])
    return float(values.to_numpy()[order][np.searchsorted(cumulative, cumulative[-1] * MEDIAN_QUANTILE)])


def _history(pairs: pd.DataFrame, weights: pd.DataFrame, bounds: dict, cutoff: pd.Timestamp, cfg: dict) -> pd.DataFrame:
    """Recent winsorized contractual growth per segment, pooling thin segments by province then portfolio.

    Returns the segment keys plus `hist_contract` and `hist_source`.
    """
    settings = cfg["combine"]
    keys = list(cfg["headline"]["segment_keys"])
    start = cutoff - pd.DateOffset(years=settings["history_window_years"])
    recent = pairs[(pairs["lease_start"] > start) & (pairs["lease_start"] <= cutoff)].copy()
    low, high = bounds[GROWTH]
    recent[GROWTH] = recent[GROWTH].clip(low, high)
    province_of = pairs.drop_duplicates("prop_code").set_index("prop_code")["province"]
    levels = [(keys, SOURCE_SEGMENT, settings["min_pairs_history"]),
              (POOL_PROVINCE_KEYS, SOURCE_PROVINCE, settings["min_pairs_history"]),
              (POOL_PORTFOLIO_KEYS, SOURCE_PORTFOLIO, 1)]
    stats = {tuple(level_keys): recent.groupby(level_keys, observed=True)[GROWTH].agg(["mean", "size"])
             for level_keys, _, _ in levels}
    rows = []
    for _, segment in weights[keys].iterrows():
        segment = segment.copy()
        segment["province"] = province_of[segment["prop_code"]]
        value, source = np.nan, SOURCE_NONE
        for level_keys, name, minimum in levels:
            label = tuple(segment[key] for key in level_keys)
            table = stats[tuple(level_keys)]
            if label in table.index and table.loc[label, "size"] >= minimum:
                value, source = float(table.loc[label, "mean"]), name
                break
        rows.append({**{key: segment[key] for key in keys}, "hist_contract": value, "hist_source": source})
    return pd.DataFrame(rows)


def _blend(components: list[tuple[float, float]]) -> float:
    """Weighted mean over the components that exist (value not NaN); NaN if none."""
    usable = [(weight, value) for weight, value in components if not np.isnan(value)]
    if not usable:
        return float("nan")
    total = sum(weight for weight, _ in usable)
    return float(sum(weight * value for weight, value in usable) / total)


def _nowcast_level(pairs: pd.DataFrame, cutoff: pd.Timestamp, cfg: dict) -> dict:
    """Portfolio nowcast of contractual and net growth; a failure is recorded and the component is dropped."""
    try:
        result = nowcast(build_monthly_index(pairs, cfg, cutoff=cutoff), cutoff, cfg)
    except ValueError as problem:
        return {"year_log_contract": float("nan"), "year_log_net": float("nan"), "error": str(problem)}
    return {key: result[key] for key in ("year_log_contract", "year_log_net", "method_used", "months_observed",
                                         "fallback_reason")}


def forecast(snapshot: Snapshot, cfg: dict) -> ForecastResult:
    """The single forecasting pipeline used by estimate_2026() and backtest().

    Inputs: a Snapshot (already cut at the cutoff) and the merged config (`combine`, `headline`, `winsorize`, `pairs`,
    `asking`, `incentives`, `nowcast`). Output: ForecastResult for the year after the cutoff. `segments` holds, per
    frozen-weight segment: weight, each component (hist_contract, signal_contract, nowcast_contract), the blended
    contractual growth, d0, d1 and net growth (all annualized log growth except the discounts). The headline medians
    are WEIGHTED medians of the segment forecasts (a robustness check, not a median of pairs). Raises ValueError
    when a segment has no component at all.
    """
    settings = cfg["combine"]
    keys = list(cfg["headline"]["segment_keys"])
    cutoff = snapshot.cutoff
    pairs = training_pairs(snapshot, cfg)
    weights = frozen_weights(pairs, cutoff, cfg)
    bounds = winsor_bounds(pairs, cfg)

    table = weights[keys + ["weight"]].merge(_history(pairs, weights, bounds, cutoff, cfg), on=keys)
    # TODO(REQUEST-FCT-01): market.asking.turnover_signal raises on an empty asking table; skip the signal then.
    signal = (turnover_signal(snapshot, cfg) if len(snapshot.asking)
              else pd.DataFrame(columns=["prop_code", "beds", "is_renewal", "expected_loggrowth_contract",
                                         "signal_source"]))
    signal = signal[["prop_code", "beds", "is_renewal", "expected_loggrowth_contract", "signal_source"]]
    table = table.merge(signal.rename(columns={"expected_loggrowth_contract": "signal_contract"}),
                        on=["prop_code", "beds", "is_renewal"], how="left")
    table["signal_contract"] = table["signal_contract"].astype(float)
    now = _nowcast_level(pairs, cutoff, cfg)
    table["nowcast_contract"] = now["year_log_contract"]

    contract = []
    for _, row in table.iterrows():
        if row["is_renewal"]:
            parts = [(settings["renewal_history_weight"], row["hist_contract"]),
                     (settings["renewal_nowcast_weight"], row["nowcast_contract"])]
        else:
            parts = [(settings["turnover_history_weight"], row["hist_contract"]),
                     (settings["turnover_signal_weight"], row["signal_contract"]),
                     (settings["turnover_nowcast_weight"], row["nowcast_contract"])]
        value = _blend(parts)
        if np.isnan(value):
            raise ValueError(f"No forecast component for segment {tuple(row[keys])} at {cutoff.date()}")
        contract.append(value)
    table["g_contract"] = contract

    discounts = forecast_discount(snapshot, cfg)[keys + ["d0", "d1"]]
    table = table.merge(discounts, on=keys, how="left")
    if table[["d0", "d1"]].isna().any().any():
        raise ValueError("Incentive engine returned no discount for a weighted segment")
    table["g_net"] = [net_log_growth(g, d0, d1) for g, d0, d1 in zip(table["g_contract"], table["d0"], table["d1"])]

    log_contract = float((table["weight"] * table["g_contract"]).sum())
    log_net = float((table["weight"] * table["g_net"]).sum())
    return ForecastResult(
        target_year=target_year_for(cutoff), cutoff=cutoff,
        headline_net_pct=to_pct(log_net), headline_contract_pct=to_pct(log_contract),
        median_net_pct=to_pct(weighted_median(table["g_net"], table["weight"])),
        median_contract_pct=to_pct(weighted_median(table["g_contract"], table["weight"])),
        segments=table, model_name=MODEL_NAME,
        components={
            "engine_weights": {name: settings[name] for name in settings if name.endswith(("_weight",))},
            "nowcast": now,
            "history_sources": table["hist_source"].value_counts().to_dict(),
            "signal_sources": table.loc[~table["is_renewal"].astype(bool), "signal_source"].fillna(SOURCE_NONE)
                                   .value_counts().to_dict(),
            "n_segments": len(table),
            "nowcast_net_pct_crosscheck": to_pct(now["year_log_net"]) if not np.isnan(now["year_log_net"]) else None,
        },
        assumptions=[
            "Contractual growth per segment blends history, nowcast level and (turnovers) the asking-rent signal; "
            "net growth adds the discount change log(1-d1) - log(1-d0) from the incentive engine.",
            "Segment weights are frozen shares of eligible pairs in the window before the cutoff; they describe lease "
            "transitions, not occupancy or turnover rate.",
            "No regulatory cap is applied to renewals in this model; Québec TAL and Ontario guideline scenarios are F-07.",
        ])
