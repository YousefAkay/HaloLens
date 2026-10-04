"""Low / central / high scenarios and per building x beds forecasts.

Owner: FCT. Implements `scenario_table` (AGENTS.md Section 7.3) and `building_beds_forecast` (F-07).

Scenarios are computed from the segment table of an E2_regulated forecast, so they are exact re-aggregations of the same
segment forecasts, not new models. Levers (forecast.yaml `scenarios`): incentive intensity (shift of every segment's
forecast discount share d1), renewal mix (shift of the renewal share of the frozen weights), and Met applicability
(Ontario guideline applies to the Ontario new-build renewals instead of the exempt central case). Scenario ranges are scenarios, not
prediction intervals (AGENTS.md 9.4).
"""

from __future__ import annotations

import itertools

import numpy as np
import pandas as pd
from leaselens.contracts import PERCENT, ForecastResult
from leaselens.forecast.baselines import to_pct

SCENARIO_COLUMNS = ["scenario", "incentive_shift_pp", "renewal_share_shift_pp", "met_guideline_applies",
                    "headline_net_pct", "headline_contract_pct", "delta_net_pp"]
CENTRAL = "central"


def _reweight(weights: pd.Series, is_renewal: pd.Series, shift: float) -> pd.Series:
    """Move `shift` (a fraction) of the total weight onto renewals (negative: onto turnovers); sums stay at 1.

    A shift that would empty either group is clipped just short of it; with only one group present nothing moves.
    """
    renewal = float(weights[is_renewal].sum())
    if shift == 0 or renewal <= 0 or renewal >= 1:
        return weights
    target = float(np.clip(renewal + shift, 0.0, 1.0))
    return weights.where(~is_renewal, weights * target / renewal).where(is_renewal, weights * (1 - target) / (1 - renewal))


def evaluate_scenario(segments: pd.DataFrame, cfg: dict, incentive_shift_pp: float = 0.0,
                      renewal_share_shift_pp: float = 0.0, met_guideline_applies: bool = False) -> dict:
    """Headline net and contract % for one lever setting, re-aggregating the segment forecasts.

    Returns {"headline_net_pct", "headline_contract_pct"}; both NaN when `met_guideline_applies` is requested but the
    segment table has no Ontario-guideline contract growth for every segment.
    """
    contract = segments["g_contract_met_alt"] if met_guideline_applies else segments["g_contract"]
    if contract.isna().any():
        return {"headline_net_pct": np.nan, "headline_contract_pct": np.nan}
    cap = cfg["incentives"]["max_discount_share"]
    d1 = (segments["d1"] + incentive_shift_pp / PERCENT).clip(0.0, cap)
    net = contract + np.log1p(-d1) - np.log1p(-segments["d0"])
    weights = _reweight(segments["weight"], segments["is_renewal"].astype(bool), renewal_share_shift_pp / PERCENT)
    return {"headline_net_pct": to_pct(float((weights * net).sum())),
            "headline_contract_pct": to_pct(float((weights * contract).sum()))}


def scenario_table(result: ForecastResult, cfg: dict) -> pd.DataFrame:
    """Return headline under each scenario lever (forecast.yaml scenarios).

    Rows: `central` (no shift, Met exempt); one row per lever moved alone (`incentives_deeper` / `incentives_shallower`,
    `more_renewals` / `fewer_renewals`, `met_guideline_applies`); and `low` / `high`, the lowest and highest net headline
    over every combination of the levers. `delta_net_pp` is relative to central. Expects an E2_regulated result
    (its segments carry `g_contract_met_alt`); on any other result the Ontario new-build rows are NaN and left out of low/high.
    """
    settings = cfg["scenarios"]
    incentive, renewal = settings["incentive_intensity_shift_pp"], settings["renewal_share_shift_pp"]
    met_values = list(settings["met_guideline_applies"])
    segments = result.segments
    if "g_contract_met_alt" not in segments.columns:
        segments = segments.assign(g_contract_met_alt=np.nan)

    def run(i, r, m):
        return evaluate_scenario(segments, cfg, i, r, m)

    central = run(0.0, 0.0, False)
    named = {CENTRAL: (0.0, 0.0, False), "incentives_deeper": (incentive, 0.0, False),
             "incentives_shallower": (-incentive, 0.0, False), "more_renewals": (0.0, renewal, False),
             "fewer_renewals": (0.0, -renewal, False)}
    if any(met_values):
        named["met_guideline_applies"] = (0.0, 0.0, True)
    rows = [{"scenario": name, "incentive_shift_pp": i, "renewal_share_shift_pp": r, "met_guideline_applies": m,
             **run(i, r, m)} for name, (i, r, m) in named.items()]

    combos = [{"incentive_shift_pp": i, "renewal_share_shift_pp": r, "met_guideline_applies": m, **run(i, r, m)}
              for i, r, m in itertools.product((-incentive, 0.0, incentive), (-renewal, 0.0, renewal), met_values)]
    valid = [combo for combo in combos if not np.isnan(combo["headline_net_pct"])]
    for label, pick in (("low", min), ("high", max)):
        best = pick(valid, key=lambda combo: combo["headline_net_pct"])
        rows.append({"scenario": label, **best})
    table = pd.DataFrame(rows)
    table["delta_net_pp"] = table["headline_net_pct"] - central["headline_net_pct"]
    return table[SCENARIO_COLUMNS]


def building_beds_forecast(result: ForecastResult, cfg: dict) -> pd.DataFrame:
    """Per building (prop_code) x beds net and contract forecast, shrunk toward the building mean. Aggregates only.

    A cell aggregates the segment forecasts of its renewal and turnover segments with the frozen weights. Thin cells are
    pulled toward their building's weighted mean: shrunk = (n x cell + k x building) / (n + k), where n = eligible pairs
    behind the cell in the weight window and k = `combine.shrinkage_strength` pseudo-pairs. The portfolio headline is
    NOT recomputed from the shrunk cells (they are descriptive). Columns: prop_code, beds, weight, n_pairs,
    net_pct_raw, net_pct_shrunk, contract_pct_raw, contract_pct_shrunk, building_net_pct.
    """
    strength = cfg["combine"]["shrinkage_strength"]
    segments = result.segments
    cells = []
    for (prop_code, beds), group in segments.groupby(["prop_code", "beds"], sort=True):
        weight = float(group["weight"].sum())
        cells.append({"prop_code": prop_code, "beds": beds, "weight": weight,
                      "n_pairs": int(group["n_pairs_window"].sum()),
                      "net_log": float((group["weight"] * group["g_net"]).sum() / weight),
                      "contract_log": float((group["weight"] * group["g_contract"]).sum() / weight)})
    table = pd.DataFrame(cells)
    building = table.groupby("prop_code").apply(
        lambda cell: pd.Series({"building_net_log": (cell["weight"] * cell["net_log"]).sum() / cell["weight"].sum(),
                                "building_contract_log": (cell["weight"] * cell["contract_log"]).sum() / cell["weight"].sum()}),
        include_groups=False)
    table = table.join(building, on="prop_code")
    share = table["n_pairs"] / (table["n_pairs"] + strength)
    table["net_shrunk_log"] = share * table["net_log"] + (1 - share) * table["building_net_log"]
    table["contract_shrunk_log"] = share * table["contract_log"] + (1 - share) * table["building_contract_log"]
    out = pd.DataFrame({"prop_code": table["prop_code"], "beds": table["beds"], "weight": table["weight"],
                        "n_pairs": table["n_pairs"],
                        "net_pct_raw": table["net_log"].map(to_pct), "net_pct_shrunk": table["net_shrunk_log"].map(to_pct),
                        "contract_pct_raw": table["contract_log"].map(to_pct),
                        "contract_pct_shrunk": table["contract_shrunk_log"].map(to_pct),
                        "building_net_pct": table["building_net_log"].map(to_pct)})
    return out.reset_index(drop=True)


def headline_by_province(result: ForecastResult, province_of: pd.Series) -> pd.DataFrame:
    """The headline split by province, with the same fixed weights (renormalized inside each province). Aggregates only.

    `province_of` maps prop_code to province (QC, ON). Works on any ForecastResult whose segment table has either
    `g_net` / `g_contract` (engines) or `mean_log_net` / `mean_log_contract` (baselines B0); segments without a
    forecast are left out and the rest renormalized, as in the headline itself. Columns: province, weight_share (of the
    total frozen weight), n_segments, net_pct, contract_pct. A final `all` row repeats the portfolio aggregation.
    """
    segments = result.segments
    net, contract = ("g_net", "g_contract") if "g_net" in segments.columns else ("mean_log_net", "mean_log_contract")
    total_weight = float(segments["weight"].sum())
    usable = segments.assign(province=segments["prop_code"].map(province_of)).dropna(subset=[net, contract])

    def aggregate(label, group):
        weight = float(group["weight"].sum())
        return {"province": label, "weight_share": weight / total_weight, "n_segments": len(group),
                "net_pct": to_pct(float((group["weight"] * group[net]).sum() / weight)),
                "contract_pct": to_pct(float((group["weight"] * group[contract]).sum() / weight))}

    rows = [aggregate(province, group) for province, group in usable.groupby("province", sort=True)]
    rows.append(aggregate("all", usable))
    return pd.DataFrame(rows)
