"""Baseline forecasts B0 (last year), B1 (trailing mean), B2 (market anchor + gap), and the shared headline helpers.

Implements AGENTS.md Section 7.3 and the headline definition of Section 9.1:
winsorized annualized log growth per segment, aggregated with fixed weights (segment shares of eligible pairs in the
window before the cutoff), headline % = 100 x (exp(sum w_s x mean_s) - 1).

The helpers (`training_pairs`, `winsor_bounds`, `frozen_weights`, `headline_summary`) live here because the backtest
and every later engine need them and this is the lowest FCT module in the import chain.
Everything is a pure function of a Snapshot, so nothing after the cutoff can enter.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from halolens.contracts import PERCENT, ForecastResult, Snapshot
from halolens.measure.pairs import build_pairs

# Headline growth columns of PAIRS and the rent column each one measures
GROWTH_NET = "loggrowth_net"
GROWTH_CONTRACT = "loggrowth_contract"
GROWTH_COLUMNS = (GROWTH_NET, GROWTH_CONTRACT)

# Keys of the log-scale summary dict (one value per reported quantity)
LOG_KEYS = ("log_net", "log_contract", "log_median_net", "log_median_contract")

BASELINE_NAMES = {"last_year": "B0_last_year", "trailing_mean": "B1_trailing_mean", "market_anchor": "B2_market_anchor",
                  "tal_anchor": "B3_tal_anchor"}


def target_year_for(cutoff: pd.Timestamp) -> int:
    """Year being forecast from `cutoff` (cutoff is December 31 of the previous year)."""
    return pd.Timestamp(cutoff).year + 1


def training_pairs(snapshot: Snapshot, cfg: dict) -> pd.DataFrame:
    """Eligible same-unit pairs built from the snapshot leases only (so every pair was knowable at the cutoff)."""
    pairs = build_pairs(snapshot.leases, cfg)
    return pairs[pairs["eligible"]].reset_index(drop=True)


def winsor_bounds(train_pairs: pd.DataFrame, cfg: dict) -> dict[str, tuple[float, float]]:
    """Winsorization thresholds per growth column, learned on the given (training) pairs only."""
    lower, upper = cfg["winsorize"]["lower_quantile"], cfg["winsorize"]["upper_quantile"]
    return {column: (train_pairs[column].quantile(lower), train_pairs[column].quantile(upper))
            for column in GROWTH_COLUMNS}


def frozen_weights(train_pairs: pd.DataFrame, cutoff: pd.Timestamp, cfg: dict) -> pd.DataFrame:
    """Segment weights frozen at `cutoff`: share of eligible pairs per segment in the window before the cutoff.

    Columns: the segment keys, `n_pairs_window`, `weight` (sums to 1). The weights describe the mix of observed
    lease transitions, NOT portfolio occupancy or turnover rate.
    """
    keys = list(cfg["headline"]["segment_keys"])
    window_start = cutoff - pd.DateOffset(years=cfg["headline"]["weight_window_years"])
    recent = train_pairs[(train_pairs["lease_start"] > window_start) & (train_pairs["lease_start"] <= cutoff)]
    if recent.empty:
        raise ValueError("No eligible pairs in the weight window before the cutoff")
    counts = recent.groupby(keys, observed=True).size().rename("n_pairs_window").reset_index()
    counts["weight"] = counts["n_pairs_window"] / counts["n_pairs_window"].sum()
    return counts


def headline_summary(pairs: pd.DataFrame, weights: pd.DataFrame, bounds: dict, cfg: dict) -> dict | None:
    """Fixed-weight headline of `pairs` on the log scale, or None when no weighted segment has a pair.

    Growth is clipped at `bounds` first. Segments of `weights` without pairs are dropped and the remaining weights
    renormalized; `coverage` is the share of the frozen weight that had data. Returned keys: the four LOG_KEYS
    (net, contract, plain median of net, plain median of contract), `n_pairs`, `coverage`, `segments` (DataFrame).
    """
    if pairs.empty:
        return None
    keys = list(cfg["headline"]["segment_keys"])
    clipped = pairs.copy()
    for column, (low, high) in bounds.items():
        clipped[column] = clipped[column].clip(low, high)
    by_segment = clipped.groupby(keys, observed=True).agg(
        n_pairs=("unit_id", "size"), mean_log_net=(GROWTH_NET, "mean"),
        mean_log_contract=(GROWTH_CONTRACT, "mean")).reset_index()
    segments = weights[keys + ["weight"]].merge(by_segment, on=keys, how="left")
    observed = segments["n_pairs"].notna()
    if not observed.any():
        return None
    coverage = float(segments.loc[observed, "weight"].sum())
    renormalized = segments.loc[observed, "weight"] / coverage
    return {
        "log_net": float((renormalized * segments.loc[observed, "mean_log_net"]).sum()),
        "log_contract": float((renormalized * segments.loc[observed, "mean_log_contract"]).sum()),
        "log_median_net": float(clipped[GROWTH_NET].median()),
        "log_median_contract": float(clipped[GROWTH_CONTRACT].median()),
        "n_pairs": int(len(clipped)),
        "coverage": coverage,
        "segments": segments,
    }


def to_pct(log_growth: float) -> float:
    """Annualized log growth to percent: 100 x (exp(x) - 1)."""
    return float(PERCENT * np.expm1(log_growth))


def _year_summaries(pairs: pd.DataFrame, years: list[int], weights: pd.DataFrame, bounds: dict, cfg: dict) -> dict:
    """Headline summary per calendar year (by later lease start); years without usable pairs are omitted."""
    summaries = {year: headline_summary(pairs[pairs["year"] == year], weights, bounds, cfg) for year in years}
    return {year: summary for year, summary in summaries.items() if summary is not None}


def _result(snapshot: Snapshot, logs: dict, segments: pd.DataFrame, model_name: str, components: dict,
            assumptions: list[str]) -> ForecastResult:
    return ForecastResult(
        target_year=target_year_for(snapshot.cutoff), cutoff=snapshot.cutoff,
        headline_net_pct=to_pct(logs["log_net"]), headline_contract_pct=to_pct(logs["log_contract"]),
        median_net_pct=to_pct(logs["log_median_net"]), median_contract_pct=to_pct(logs["log_median_contract"]),
        segments=segments, components=components, model_name=model_name, assumptions=assumptions)


def _training_context(snapshot: Snapshot, cfg: dict) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    pairs = training_pairs(snapshot, cfg)
    return pairs, frozen_weights(pairs, snapshot.cutoff, cfg), winsor_bounds(pairs, cfg)


def last_year(snapshot: Snapshot, cfg: dict) -> ForecastResult:
    """B0: previous year's growth under the headline definition (weights frozen at the cutoff)."""
    pairs, weights, bounds = _training_context(snapshot, cfg)
    year = target_year_for(snapshot.cutoff) - 1
    summary = headline_summary(pairs[pairs["year"] == year], weights, bounds, cfg)
    if summary is None:
        raise ValueError(f"No eligible pairs in {year} for the last-year baseline")
    return _result(snapshot, summary, summary["segments"], BASELINE_NAMES["last_year"],
                   {"source_year": year, "n_pairs": summary["n_pairs"], "weight_coverage": summary["coverage"]},
                   [f"Repeats the {year} same-unit growth; winsor bounds and weights learned before the cutoff."])


def trailing_mean(snapshot: Snapshot, cfg: dict) -> ForecastResult:
    """B1: mean of the trailing window (forecast.yaml baselines.trailing_window_years) of yearly log headlines."""
    pairs, weights, bounds = _training_context(snapshot, cfg)
    target = target_year_for(snapshot.cutoff)
    years = list(range(target - cfg["baselines"]["trailing_window_years"], target))
    summaries = _year_summaries(pairs, years, weights, bounds, cfg)
    if not summaries:
        raise ValueError("No eligible pairs in the trailing window for the trailing-mean baseline")
    logs = {key: float(np.mean([summary[key] for summary in summaries.values()])) for key in LOG_KEYS}
    return _result(snapshot, logs, weights, BASELINE_NAMES["trailing_mean"],
                   {"years_used": sorted(summaries), "years_requested": years,
                    "n_pairs": {year: summary["n_pairs"] for year, summary in summaries.items()}},
                   ["Plain mean of yearly log headlines; years without eligible pairs are skipped and listed."])


def _market_logs_by_year(external: pd.DataFrame, province_weights: pd.Series, cfg: dict) -> dict[int, float]:
    """Province-weighted market growth (log) per reference year from released observations of the anchor series.

    Keeps, for each geography and year, the latest-released value (percent). Geographies must be province codes
    present in `province_weights`; missing provinces are dropped and the weights renormalized.
    """
    series = external[(external["metric"] == cfg["baselines"]["market_anchor_series"])
                      & external["geography"].isin(province_weights.index)].copy()
    if series.empty:
        return {}
    series["year"] = series["ref_period_end"].dt.year
    latest = series.sort_values("release_date").groupby(["geography", "year"], as_index=False).last()
    logs = {}
    for year, rows in latest.groupby("year"):
        weight = province_weights[rows["geography"]]
        logs[int(year)] = float(np.log1p((weight * rows["value"].values).sum() / weight.sum() / PERCENT))
    return logs


def market_anchor(snapshot: Snapshot, cfg: dict) -> ForecastResult:
    """B2: latest released market growth plus the historical internal-vs-market gap (log scale, province-weighted).

    Needs released observations of `baselines.market_anchor_series` with province-code geographies; raises
    ValueError when the snapshot has none or no year has both internal and market growth.
    """
    pairs, weights, bounds = _training_context(snapshot, cfg)
    target = target_year_for(snapshot.cutoff)
    province_of = snapshot.leases.drop_duplicates("prop_code").set_index("prop_code")["province"]
    province_weights = weights.assign(province=weights["prop_code"].map(province_of)).groupby("province")["weight"].sum()
    market = _market_logs_by_year(snapshot.external, province_weights, cfg)
    if not market:
        raise ValueError("No released market observations for the market-anchor baseline")

    years = list(range(target - cfg["baselines"]["market_gap_window_years"], target))
    internal = _year_summaries(pairs, years, weights, bounds, cfg)
    gap_years = sorted(set(internal) & set(market))
    if not gap_years:
        raise ValueError("No year with both internal and market growth to learn the gap")
    latest_year = max(market)
    logs = {key: market[latest_year] + float(np.mean([internal[year][key] - market[year] for year in gap_years]))
            for key in LOG_KEYS}
    return _result(snapshot, logs, weights, BASELINE_NAMES["market_anchor"],
                   {"market_year": latest_year, "gap_years": gap_years,
                    "market_pct": to_pct(market[latest_year])},
                   ["Latest released market growth plus the mean internal-minus-market gap (log scale).",
                    "Market series is province-weighted with the frozen segment weights."])


def rate_logs_by_year(external: pd.DataFrame, metric: str, geography: str) -> dict[int, float]:
    """log(1 + rate/100) per reference year for one regulated rate (TAL percentage, Ontario guideline).

    Reads the snapshot's external rows only (already cut at the external cutoff), keeps the latest-released value for
    each reference year and returns {year: log1p(value / 100)}. Empty when the snapshot has no such rows.
    """
    rows = external[(external["metric"] == metric) & (external["geography"] == geography)]
    if rows.empty:
        return {}
    latest = rows.assign(year=rows["ref_period_end"].dt.year).sort_values("release_date").groupby("year").last()
    return {int(year): float(np.log1p(value / PERCENT)) for year, value in latest["value"].items()}


def resolve_rate_year(rate_logs: dict[int, float], target_year: int) -> int:
    """Year whose rate is used for `target_year`: the target year if public by the external cutoff, else the latest earlier one.

    Raises ValueError when no rate for the target year or any earlier year is available.
    """
    available = [year for year in rate_logs if year <= target_year]
    if not available:
        raise ValueError("No released regulated rate for the target year or any earlier year")
    return target_year if target_year in rate_logs else max(available)


def anchor_gap(growth_by_year: pd.Series, rate_logs: dict[int, float], years: list[int]) -> tuple[float, list[int]]:
    """Mean of (actual log growth - log(1 + rate)) over the training `years` that have both; also returns those years.

    Raises ValueError when no year has both an observed growth and a released rate.
    """
    shared = sorted(set(years) & set(growth_by_year.index) & set(rate_logs))
    if not shared:
        raise ValueError("No training year with both observed growth and a released rate to learn the gap")
    return float(np.mean([growth_by_year[year] - rate_logs[year] for year in shared])), shared


def tal_anchor(snapshot: Snapshot, cfg: dict) -> ForecastResult:
    """B3: portfolio contract growth = TAL reference % of the target year + training gap; net = contract minus last year's spread.

    The TAL rate of the target year is used when public by the external cutoff, otherwise the latest released year's
    rate. The gap is the mean of (portfolio actual contract log growth - log(1 + TAL)) over the
    `anchors.gap_window_years` years before the target. The contract-to-net spread is last year's headline
    (contract log growth - net log growth). Raises ValueError without a TAL rate, a gap year or last-year pairs.
    """
    settings = cfg["anchors"]
    pairs, weights, bounds = _training_context(snapshot, cfg)
    target = target_year_for(snapshot.cutoff)
    rates = rate_logs_by_year(snapshot.external, settings["tal_metric"], settings["tal_geography"])
    rate_year = resolve_rate_year(rates, target)
    years = list(range(target - settings["gap_window_years"], target))
    internal = _year_summaries(pairs, years, weights, bounds, cfg)
    if (target - 1) not in internal:
        raise ValueError(f"No eligible pairs in {target - 1} to measure the contract-to-net spread")
    gap_contract, gap_years = anchor_gap(pd.Series({y: s["log_contract"] for y, s in internal.items()}), rates, years)
    gap_median, _ = anchor_gap(pd.Series({y: s["log_median_contract"] for y, s in internal.items()}), rates, years)
    last = internal[target - 1]
    contract = rates[rate_year] + gap_contract
    median_contract = rates[rate_year] + gap_median
    logs = {"log_contract": contract, "log_net": contract - (last["log_contract"] - last["log_net"]),
            "log_median_contract": median_contract,
            "log_median_net": median_contract - (last["log_median_contract"] - last["log_median_net"])}
    return _result(snapshot, logs, weights, BASELINE_NAMES["tal_anchor"],
                   {"tal_year_used": rate_year, "tal_pct_used": to_pct(rates[rate_year]), "gap_years": gap_years,
                    "gap_log": gap_contract, "spread_log": last["log_contract"] - last["log_net"]},
                   ["TAL reference percentage of the target year (latest released year if not yet public) plus the mean "
                    "training gap between actual portfolio contract growth and the TAL rate.",
                    "Net = contract minus last year's contract-to-net log spread; the TAL rate is Québec's and is applied "
                    "to the whole portfolio on purpose (simple and transparent)."])


BASELINES = {
    BASELINE_NAMES["last_year"]: last_year,
    BASELINE_NAMES["trailing_mean"]: trailing_mean,
    BASELINE_NAMES["market_anchor"]: market_anchor,
    BASELINE_NAMES["tal_anchor"]: tal_anchor,
}
