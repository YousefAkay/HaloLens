"""Small local-trend / state-space model on the monthly index.

Owner: FCT. Implements `nowcast` (F-04). A local linear trend (statsmodels UnobservedComponents) is fitted to the
monthly annualized log growth up to the cutoff; its last filtered level and slope are projected 12 months ahead with
a damped slope, then the months of the target year are combined with the calendar-month shares of recent pairs
(leases cluster in some months, so a plain average of the twelve months would misstate the year).
With too little history, or `nowcast.method: trailing_mean`, a trailing mean of the last observed months is used.
"""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
from halolens.contracts import MONTHS_PER_YEAR
from statsmodels.tsa.statespace.structural import UnobservedComponents

METHOD_LOCAL_TREND = "local_linear_trend"
METHOD_TRAILING_MEAN = "trailing_mean"
GROWTH_SERIES = {"log_net": "log_net", "log_contract": "log_contract"}


def _observed_through(index: pd.DataFrame, cutoff: pd.Timestamp) -> pd.DataFrame:
    """Index rows for months that end on or before the month of the cutoff."""
    return index[index["month"] <= pd.Timestamp(cutoff).to_period("M")]


def _trailing_mean_path(series: pd.Series, horizon: int, window: int) -> tuple[np.ndarray, float]:
    """Flat projection at the mean of the last `window` observed values; returns (path, level at cutoff)."""
    observed = series.dropna().tail(window)
    if observed.empty:
        raise ValueError("No observed months for the trailing-mean nowcast")
    level = float(observed.mean())
    return np.full(horizon, level), level


def _local_trend_path(series: pd.Series, horizon: int, damping: float) -> tuple[np.ndarray, float]:
    """Fit a local linear trend (NaN months allowed) and project the last filtered state with a damped slope."""
    model = UnobservedComponents(series.to_numpy(dtype=float), level="local linear trend")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        fitted = model.fit(disp=False)
    level, slope = (float(value) for value in fitted.filtered_state[:2, -1])
    steps = np.arange(1, horizon + 1)
    cumulative_damping = np.cumsum(damping ** steps)
    path = level + slope * cumulative_damping
    if not np.all(np.isfinite(path)):
        raise ValueError("local linear trend produced a non-finite projection")
    return path, level


def _month_shares(index: pd.DataFrame, cutoff: pd.Timestamp, window_years: int) -> pd.Series:
    """Share of recent pairs per calendar month (1-12) over the weight window ending at the cutoff."""
    window_start = (pd.Timestamp(cutoff) - pd.DateOffset(years=window_years)).to_period("M")
    recent = _observed_through(index, cutoff)
    recent = recent[recent["month"] > window_start]
    calendar = recent.groupby(recent["month"].dt.month)["n_pairs"].sum()
    calendar = calendar.reindex(range(1, MONTHS_PER_YEAR + 1), fill_value=0)
    if calendar.sum() == 0:
        raise ValueError("No pairs in the weight window to derive calendar-month shares")
    return calendar / calendar.sum()


def nowcast(index: pd.DataFrame, cutoff: pd.Timestamp, cfg: dict) -> dict:
    """Return the trend estimate at cutoff and its 12-month-ahead projection.

    Inputs: monthly index from `build_monthly_index` (only months up to the cutoff are used), the cutoff, merged config
    (`nowcast.*`, `headline.weight_window_years`). Output dict:
    - trend_log_net, trend_log_contract: estimated level of annualized log growth at the cutoff;
    - year_log_net, year_log_contract: projection for the target year, months weighted by calendar-month pair shares;
    - projection: DataFrame (month, log_net, log_contract) for the 12 months after the cutoff;
    - method_used ("local_linear_trend" or "trailing_mean"), months_observed (months with a value), fallback_reason.
    """
    settings = cfg["nowcast"]
    cutoff = pd.Timestamp(cutoff)
    known = _observed_through(index, cutoff)
    full_range = pd.period_range(known["month"].min(), cutoff.to_period("M"), freq="M")
    known = known.set_index("month").reindex(full_range)
    horizon = MONTHS_PER_YEAR
    future = pd.period_range(cutoff.to_period("M") + 1, periods=horizon, freq="M")

    method, reason = settings["method"], ""
    observed = int(known["log_net"].notna().sum())
    if method == METHOD_LOCAL_TREND and observed < settings["min_observed_months"]:
        method, reason = METHOD_TRAILING_MEAN, f"only {observed} observed months"

    paths, levels = {}, {}
    for column in GROWTH_SERIES.values():
        series = known[column]
        if method == METHOD_LOCAL_TREND:
            try:
                paths[column], levels[column] = _local_trend_path(series, horizon, settings["trend_damping"])
            except (ValueError, np.linalg.LinAlgError) as problem:
                method, reason = METHOD_TRAILING_MEAN, f"local trend failed: {problem}"
        if method == METHOD_TRAILING_MEAN:
            paths[column], levels[column] = _trailing_mean_path(series, horizon, settings["fallback_window_months"])
    if method == METHOD_TRAILING_MEAN:   # a failure on the second series must not leave a mixed result
        for column in GROWTH_SERIES.values():
            paths[column], levels[column] = _trailing_mean_path(known[column], horizon,
                                                                settings["fallback_window_months"])

    projection = pd.DataFrame({"month": future, **{column: paths[column] for column in GROWTH_SERIES.values()}})
    shares = _month_shares(index, cutoff, cfg["headline"]["weight_window_years"])
    target_year = cutoff.year + 1
    target_rows = projection[projection["month"].dt.year == target_year]
    target_shares = shares.loc[target_rows["month"].dt.month].to_numpy()
    if target_shares.sum() == 0:
        raise ValueError("No calendar-month pair share falls in the target year")
    target_shares = target_shares / target_shares.sum()
    return {
        "trend_log_net": levels["log_net"], "trend_log_contract": levels["log_contract"],
        "year_log_net": float((target_rows["log_net"].to_numpy() * target_shares).sum()),
        "year_log_contract": float((target_rows["log_contract"].to_numpy() * target_shares).sum()),
        "projection": projection, "method_used": method, "months_observed": observed, "fallback_reason": reason,
    }
