"""Asking-rent leading indicator for turnover rents.

Implements `turnover_signal` (AGENTS.md Section 7.3).

Idea: a unit listed before the cutoff tells us what the next tenant will be asked to pay. Comparing that asking rent
with the contractual rent of the unit's current lease gives a forward-looking turnover growth. Asking rents are not
signed rents, so a spread log(signed / asking), learned on turnover leases signed before the cutoff, is added.

    expected turnover log growth (unit) = [ln(asking / prior rent_contract) + spread(province)] / gap_years

`gap_years` runs from the prior lease start to the asking month, i.e. the same annualization as PAIRS. The signal is
contractual (asking rents are offers before incentives); FCT's incentive engine converts it to net.
Units are matched on the safe key `pairs.unit_key` (prop_code + unit_code), never on the site name.
Every input comes from a Snapshot, so nothing posted, signed or started after the cutoff can enter.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from halolens.contracts import DAYS_PER_YEAR, Snapshot
from halolens.forecast.baselines import frozen_weights, training_pairs

# Pooling levels: the segment itself, then its province pool when too few units are listed
SEGMENT_KEYS = ["prop_code", "beds"]
FALLBACK_KEYS = ["province"]
SOURCE_SEGMENT = "segment"
SOURCE_PROVINCE = "province_pool"
SOURCE_NONE = "none"
SPREAD_ALL_PROVINCES = "all"
AGGREGATES = ("median", "mean")

SIGNAL_COLUMNS = [
    "prop_code", "beds", "is_renewal", "expected_loggrowth_contract", "asking_loggrowth", "spread_log",
    "n_listings", "n_spread_leases", "signal_source", "spread_source",
]


SIGNAL_DTYPES = {
    "prop_code": str, "beds": "int64", "is_renewal": bool, "expected_loggrowth_contract": float,
    "asking_loggrowth": float, "spread_log": float, "n_listings": "int64", "n_spread_leases": "int64",
    "signal_source": str, "spread_source": str,
}


def _empty_signal() -> pd.DataFrame:
    """SIGNAL_COLUMNS table with no rows and the usual dtypes (no asking history at the cutoff)."""
    return pd.DataFrame({column: pd.Series(dtype=SIGNAL_DTYPES[column]) for column in SIGNAL_COLUMNS})


def _month_start(month: pd.Series) -> pd.Series:
    """First day of each pandas Period[M] as a Timestamp."""
    return month.dt.to_timestamp(how="start")


def _aggregate(values: pd.Series, how: str) -> float:
    if how not in AGGREGATES:
        raise ValueError(f"asking.aggregate must be one of {AGGREGATES}, got {how!r}")
    return float(values.median() if how == "median" else values.mean())


def matched_spreads(snapshot: Snapshot, cfg: dict) -> pd.DataFrame:
    """Per turnover lease signed in the spread window: the latest asking rent posted shortly before signing.

    A lease is matched when its unit (pairs.unit_key) has an asking rent in the `asking.match_lookback_months`
    months up to and including its signing month. Columns: province, spread_log = ln(rent_contract / asking_rent).
    Only snapshot data is used, so every lease was signed and started on or before the cutoff.
    """
    unit_key = list(cfg["pairs"]["unit_key"])
    settings = cfg["asking"]
    window_start = snapshot.cutoff - pd.DateOffset(years=settings["spread_window_years"])
    leases = snapshot.leases
    turnovers = leases[~leases["is_renewal"].astype(bool) & (leases["sign_date"] > window_start)
                       & (leases["rent_contract"] > 0)]
    turnovers = turnovers.assign(_lease_row=np.arange(len(turnovers)),
                                 _sign_month=turnovers["sign_date"].dt.to_period("M"))

    asking = snapshot.asking[snapshot.asking["asking_rent"] > 0][unit_key + ["month", "asking_rent"]]
    candidates = turnovers[unit_key + ["province", "rent_contract", "_lease_row", "_sign_month"]].merge(
        asking, on=unit_key, how="inner")
    months_before = (candidates["_sign_month"] - candidates["month"]).map(lambda offset: offset.n)
    candidates = candidates[(months_before >= 0) & (months_before <= settings["match_lookback_months"])]
    latest = candidates.sort_values("month").groupby("_lease_row").tail(1)
    spreads = latest.assign(spread_log=np.log(latest["rent_contract"] / latest["asking_rent"]))
    return spreads[["province", "spread_log"]].reset_index(drop=True)


def _spread_by_province(spreads: pd.DataFrame, cfg: dict) -> dict:
    """Spread per province, with the all-province spread for thin provinces. Values: (spread_log, n, source)."""
    settings = cfg["asking"]
    how = settings["aggregate"]
    pooled = (_aggregate(spreads["spread_log"], how), len(spreads), SPREAD_ALL_PROVINCES) if len(spreads) \
        else (float("nan"), 0, SOURCE_NONE)
    result = {SPREAD_ALL_PROVINCES: pooled}
    for province, group in spreads.groupby("province"):
        if len(group) >= settings["min_spread_leases"]:
            result[province] = (_aggregate(group["spread_log"], how), len(group), province)
    return result


def listing_growth(snapshot: Snapshot, cfg: dict) -> pd.DataFrame:
    """Per unit listed in the signal window: annualized log growth of its latest asking rent over its current lease.

    The window is the `asking.signal_window_months` months ending with the cutoff month. The prior lease is the
    unit's latest lease starting before the asking month (so a lease signed from this listing is never its own base).
    Units whose gap falls outside the PAIRS bounds (pairs.min_gap_years, pairs.max_gap_years) are dropped, so the
    signal is comparable with eligible pairs. Columns: prop_code, beds, province, gap_years, asking_loggrowth
    (= ln(asking / prior rent_contract) / gap_years, before the spread).
    """
    unit_key = list(cfg["pairs"]["unit_key"])
    settings = cfg["asking"]
    cutoff_month = snapshot.cutoff.to_period("M")
    first_month = cutoff_month - (settings["signal_window_months"] - 1)

    asking = snapshot.asking
    recent = asking[(asking["month"] >= first_month) & (asking["month"] <= cutoff_month) & (asking["asking_rent"] > 0)]
    latest = recent.sort_values("month").groupby(unit_key).tail(1)
    latest = latest.assign(_month_start=_month_start(latest["month"]))[unit_key + ["month", "_month_start", "asking_rent"]]

    lease_columns = list(dict.fromkeys(unit_key + ["prop_code", "beds", "province", "lease_start", "rent_contract"]))
    leases = snapshot.leases[lease_columns]
    candidates = latest.merge(leases, on=unit_key, how="inner")
    candidates = candidates[(candidates["lease_start"] < candidates["_month_start"]) & (candidates["rent_contract"] > 0)]
    prior = candidates.sort_values("lease_start").groupby(unit_key).tail(1)

    gap_years = (prior["_month_start"] - prior["lease_start"]).dt.days / DAYS_PER_YEAR
    in_bounds = (gap_years > cfg["pairs"]["min_gap_years"]) & (gap_years < cfg["pairs"]["max_gap_years"])
    prior = prior.assign(gap_years=gap_years)[in_bounds]
    prior = prior.assign(asking_loggrowth=np.log(prior["asking_rent"] / prior["rent_contract"]) / prior["gap_years"])
    return prior[["prop_code", "beds", "province", "gap_years", "asking_loggrowth"]].reset_index(drop=True)


def turnover_signal(snapshot: Snapshot, cfg: dict) -> pd.DataFrame:
    """Return expected turnover contractual log growth per segment from asking rents posted before the cutoff.

    Segments are the turnover segments (is_renewal False) of the frozen weights at the cutoff, so the output merges
    straight onto the weights. Per segment (prop_code x beds):
    - spread: `asking.aggregate` of ln(signed / asking) over turnover leases signed in the last
      `asking.spread_window_years` years (`matched_spreads`), per province; a province with fewer than
      `min_spread_leases` matches uses the all-province spread.
    - signal: `asking.aggregate` over listed units of [ln(asking / prior rent) + spread] / gap_years
      (`listing_growth`); a segment with fewer than `min_listings_per_segment` listed units uses its province pool.
    Columns: SIGNAL_COLUMNS. `expected_loggrowth_contract` is NaN (signal_source "none") when no listing or no
    spread is available; the caller decides the fallback. A snapshot without asking rows (cut before any asking
    history) returns an empty SIGNAL_COLUMNS table. Inputs are not modified.
    """
    if snapshot.asking.empty:
        return _empty_signal()
    weights = frozen_weights(training_pairs(snapshot, cfg), snapshot.cutoff, cfg)
    segments = weights.loc[~weights["is_renewal"].astype(bool), ["prop_code", "beds", "is_renewal"]]
    province_of = snapshot.leases.drop_duplicates("prop_code").set_index("prop_code")["province"]
    segments = segments.assign(province=segments["prop_code"].map(province_of)).reset_index(drop=True)

    settings = cfg["asking"]
    how = settings["aggregate"]
    spreads = _spread_by_province(matched_spreads(snapshot, cfg), cfg)
    listings = listing_growth(snapshot, cfg)
    listings = listings.assign(spread_log=listings["province"].map(
        lambda province: spreads.get(province, spreads[SPREAD_ALL_PROVINCES])[0]))
    listings = listings.assign(expected=listings["asking_loggrowth"] + listings["spread_log"] / listings["gap_years"])

    rows = []
    for _, segment in segments.iterrows():
        spread_log, n_spread, spread_source = spreads.get(segment["province"], spreads[SPREAD_ALL_PROVINCES])
        cell = listings[(listings["prop_code"] == segment["prop_code"]) & (listings["beds"] == segment["beds"])]
        source = SOURCE_SEGMENT
        if len(cell) < settings["min_listings_per_segment"]:
            cell = listings[listings["province"] == segment["province"]]
            source = SOURCE_PROVINCE
        usable = cell.dropna(subset=["expected"])
        if usable.empty:
            source = SOURCE_NONE
        rows.append({
            "prop_code": segment["prop_code"], "beds": segment["beds"], "is_renewal": False,
            "expected_loggrowth_contract": _aggregate(usable["expected"], how) if len(usable) else float("nan"),
            "asking_loggrowth": _aggregate(cell["asking_loggrowth"], how) if len(cell) else float("nan"),
            "spread_log": spread_log, "n_listings": len(usable), "n_spread_leases": n_spread,
            "signal_source": source, "spread_source": spread_source,
        })
    return pd.DataFrame(rows, columns=SIGNAL_COLUMNS)
