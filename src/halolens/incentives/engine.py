"""Discount-share trend per segment (renewals and turnovers separately).

Implements `forecast_discount` (AGENTS.md Section 7.3).

Discount share of a lease = 1 - rent_net_all_incentives / rent_contract (all concession codes, accessories included).
Same-unit net growth splits exactly on the log scale:
    log(net_i / net_{i-1}) = log(contract_i / contract_{i-1}) + log(1 - d1) - log(1 - d0)
where d0 is the discount embedded in the previous lease and d1 the discount of the new lease. This engine forecasts
d0 and d1 per segment; `net_log_growth` applies them to a contractual growth forecast.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from halolens.contracts import Snapshot
from halolens.forecast.baselines import frozen_weights, target_year_for, training_pairs

# Pooling levels: the segment itself, then its province pool, then the whole portfolio when the cell is too thin
BASE_KEYS = ["prop_code", "beds"]          # d0: the previous lease can be a renewal or a turnover, so renewal is pooled
BASE_FALLBACK_KEYS = ["province"]
NEW_FALLBACK_KEYS = ["province", "is_renewal"]
PORTFOLIO_KEYS: list[str] = []             # d0: every lease
PORTFOLIO_NEW_KEYS = ["is_renewal"]        # d1: every lease with the same renewal flag
TREND_DEGREE = 1                           # straight-line trend; with one usable year the trend is flat


def discount_share(leases: pd.DataFrame) -> pd.Series:
    """Per-lease discount share 1 - net/contract (NaN where the contract rent is not positive)."""
    contract = leases["rent_contract"].where(leases["rent_contract"] > 0)
    return 1 - leases["rent_net_all_incentives"] / contract


def net_log_growth(contract_log_growth: float, d0: float, d1: float) -> float:
    """Net annualized log growth implied by a contractual one and the discount shares of the old and new lease."""
    return float(contract_log_growth + np.log1p(-d1) - np.log1p(-d0))


def _yearly_cells(leases: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    """Mean discount share and lease count per group and lease-start year (all leases when `keys` is empty)."""
    frame = leases.assign(year=leases["lease_start"].dt.year, discount=discount_share(leases))
    frame = frame.dropna(subset=["discount"])
    return frame.groupby(keys + ["year"], observed=True).agg(
        discount=("discount", "mean"), n_leases=("discount", "size")).reset_index()


def _trend(cells: pd.DataFrame, years: list[int], target_year: int, cfg: dict) -> float:
    """Discount share for `target_year` from the usable cells (enough leases, year in `years`); NaN without any."""
    settings = cfg["incentives"]
    usable = cells[cells["year"].isin(years) & (cells["n_leases"] >= settings["min_leases_per_cell"])]
    if usable.empty:
        return float("nan")
    if usable["year"].nunique() == 1:
        value = usable["discount"].iloc[0]
    else:
        slope, intercept = np.polyfit(usable["year"], usable["discount"], TREND_DEGREE)
        value = slope * target_year + intercept
    return float(np.clip(value, 0.0, settings["max_discount_share"]))


def _lookup(cells: pd.DataFrame, keys: list[str], row: pd.Series) -> pd.DataFrame:
    """Rows of `cells` matching the key values of `row`."""
    mask = pd.Series(True, index=cells.index)
    for key in keys:
        mask &= cells[key] == row[key]
    return cells[mask]


def forecast_discount(snapshot: Snapshot, cfg: dict) -> pd.DataFrame:
    """Return per segment the current discount share d0 and forecast d1, where discount = 1 - net/contract.

    Segments are those of the frozen weights at the cutoff (core.yaml headline.segment_keys), so the output merges
    straight onto the weights. Inputs: snapshot leases only (everything already known at the cutoff).
    - d1: discount share of leases of the segment (renewals and turnovers separately) starting in each of the last
      `incentives.trend_window_years` years, extrapolated to the target year with a straight line (flat with one
      year), clipped to [0, max_discount_share].
    - d0: discount share of all leases of the (prop_code, beds) pool starting in the last year before the target
      year, because the previous lease of a future pair may be either a renewal or a turnover.
    A cell with fewer than `min_leases_per_cell` leases is ignored; the segment then uses the pool of its province
    (d1: province x renewal flag, d0: province) and, failing that, the whole portfolio (d1: same renewal flag, d0: all
    leases). Raises ValueError if no usable history exists at all.
    Columns: segment keys, d0, d1, n_leases_d0 (leases behind d0), n_leases_d1 (latest-year leases of the segment),
    d1_source ("segment", "province_pool" or "portfolio_pool").
    """
    keys = list(cfg["headline"]["segment_keys"])
    target = target_year_for(snapshot.cutoff)
    window = cfg["incentives"]["trend_window_years"]
    trend_years = list(range(target - window, target))
    base_year = [target - 1]

    segments = frozen_weights(training_pairs(snapshot, cfg), snapshot.cutoff, cfg)[keys]
    leases = snapshot.leases
    province_of = leases.drop_duplicates("prop_code").set_index("prop_code")["province"]
    segments = segments.assign(province=segments["prop_code"].map(province_of))

    new_cells = _yearly_cells(leases, keys)
    new_fallback = _yearly_cells(leases, NEW_FALLBACK_KEYS)
    new_portfolio = _yearly_cells(leases, PORTFOLIO_NEW_KEYS)
    base_cells = _yearly_cells(leases, BASE_KEYS)
    base_fallback = _yearly_cells(leases, BASE_FALLBACK_KEYS)
    base_portfolio = _yearly_cells(leases, PORTFOLIO_KEYS)

    rows = []
    for _, segment in segments.iterrows():
        d1 = _trend(_lookup(new_cells, keys, segment), trend_years, target, cfg)
        d1_source = "segment"
        if np.isnan(d1):
            d1 = _trend(_lookup(new_fallback, NEW_FALLBACK_KEYS, segment), trend_years, target, cfg)
            d1_source = "province_pool"
        if np.isnan(d1):
            d1 = _trend(_lookup(new_portfolio, PORTFOLIO_NEW_KEYS, segment), trend_years, target, cfg)
            d1_source = "portfolio_pool"
        d0 = _trend(_lookup(base_cells, BASE_KEYS, segment), base_year, target, cfg)
        if np.isnan(d0):
            d0 = _trend(_lookup(base_fallback, BASE_FALLBACK_KEYS, segment), base_year, target, cfg)
        if np.isnan(d0):
            d0 = _trend(base_portfolio, base_year, target, cfg)
        if np.isnan(d0) or np.isnan(d1):
            raise ValueError(f"No usable discount history for segment {tuple(segment[keys])} before {snapshot.cutoff.date()}")
        base = _lookup(base_cells, BASE_KEYS, segment)
        latest = _lookup(new_cells, keys, segment)
        rows.append({**{key: segment[key] for key in keys}, "d0": d0, "d1": d1,
                     "n_leases_d0": int(base.loc[base["year"].isin(base_year), "n_leases"].sum()),
                     "n_leases_d1": int(latest.loc[latest["year"] == target - 1, "n_leases"].sum()),
                     "d1_source": d1_source})
    return pd.DataFrame(rows)
