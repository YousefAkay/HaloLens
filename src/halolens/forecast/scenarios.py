"""Low / central / high scenarios and per building x beds forecasts.

Owner: FCT. Implements `scenario_table` (AGENTS.md Section 7.3) and `building_beds_forecast` (F-07).

Scenarios are computed from the segment table of an E2_regulated forecast, so they are exact re-aggregations of the same
segment forecasts, not new models. Levers (forecast.yaml `scenarios`): incentive intensity (shift of every segment's
forecast discount share d1), renewal mix (shift of the renewal share of the frozen weights), and new-build applicability
(Ontario guideline applies to the Ontario new-build property's renewals instead of the exempt central case). Scenario ranges are scenarios, not
prediction intervals (AGENTS.md 9.4).
"""

from __future__ import annotations

import copy
import itertools

import numpy as np
import pandas as pd
from halolens.contracts import PERCENT, ForecastResult
from halolens.forecast.baselines import to_pct

SCENARIO_COLUMNS = ["scenario", "incentive_shift_pp", "renewal_share_shift_pp", "ontario_newbuild_guideline_applies",
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
                      renewal_share_shift_pp: float = 0.0, ontario_newbuild_guideline_applies: bool = False) -> dict:
    """Headline net and contract % for one lever setting, re-aggregating the segment forecasts.

    Returns {"headline_net_pct", "headline_contract_pct"}; both NaN when `ontario_newbuild_guideline_applies` is requested but the
    segment table has no Ontario-guideline contract growth for every segment.
    """
    contract = segments["g_contract_alt"] if ontario_newbuild_guideline_applies else segments["g_contract"]
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

    Rows: `central` (no shift, new-build exempt); one row per lever moved alone (`incentives_deeper` / `incentives_shallower`,
    `more_renewals` / `fewer_renewals`, `ontario_newbuild_guideline_applies`); and `low` / `high`, the lowest and highest net headline
    over every combination of the levers. `delta_net_pp` is relative to central. Expects an E2_regulated result
    (its segments carry `g_contract_alt`); on any other result the new-build rows are NaN and left out of low/high.
    """
    settings = cfg["scenarios"]
    incentive, renewal = settings["incentive_intensity_shift_pp"], settings["renewal_share_shift_pp"]
    newbuild_values = list(settings["ontario_newbuild_guideline_applies"])
    segments = result.segments
    if "g_contract_alt" not in segments.columns:
        segments = segments.assign(g_contract_alt=np.nan)

    def run(i, r, m):
        return evaluate_scenario(segments, cfg, i, r, m)

    central = run(0.0, 0.0, False)
    named = {CENTRAL: (0.0, 0.0, False), "incentives_deeper": (incentive, 0.0, False),
             "incentives_shallower": (-incentive, 0.0, False), "more_renewals": (0.0, renewal, False),
             "fewer_renewals": (0.0, -renewal, False)}
    if any(newbuild_values):
        named["ontario_newbuild_guideline_applies"] = (0.0, 0.0, True)
    rows = [{"scenario": name, "incentive_shift_pp": i, "renewal_share_shift_pp": r, "ontario_newbuild_guideline_applies": m,
             **run(i, r, m)} for name, (i, r, m) in named.items()]

    combos = [{"incentive_shift_pp": i, "renewal_share_shift_pp": r, "ontario_newbuild_guideline_applies": m, **run(i, r, m)}
              for i, r, m in itertools.product((-incentive, 0.0, incentive), (-renewal, 0.0, renewal), newbuild_values)]
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


PROVINCE_COLUMNS = ["province", "weight_share", "n_segments", "net_pct", "contract_pct"]
ALL_ROW = "all"


def _segment_forecast_columns(segments: pd.DataFrame) -> tuple[str, str] | None:
    """Names of the per-segment (net, contract) forecast columns, or None when the model has none."""
    for net, contract in (("g_net", "g_contract"), ("mean_log_net", "mean_log_contract")):
        if net in segments.columns and contract in segments.columns:
            return net, contract
    return None


def headline_by_province(result: ForecastResult, province_of: pd.Series) -> pd.DataFrame:
    """The headline split by province, with the same fixed weights (renormalized inside each province). Aggregates only.

    `province_of` maps prop_code to province (QC, ON). Works on any ForecastResult whose segment table has either
    `g_net` / `g_contract` (engines) or `mean_log_net` / `mean_log_contract` (B0); segments without a forecast are left
    out and the rest renormalized, as in the headline itself. Columns: PROVINCE_COLUMNS (province, weight_share of the
    total frozen weight, n_segments, net_pct, contract_pct). A final `all` row repeats the portfolio aggregation.

    Models that forecast only the portfolio (B1 trailing mean, B2 market anchor, B3 TAL anchor) have no segment-level
    forecast, so no honest split exists: the table then holds the `all` row alone, taken from the model's own headline
    (weight_share 1), and callers show the province split as "not available for this model".
    """
    segments = result.segments
    columns = _segment_forecast_columns(segments)
    if columns is None:
        return pd.DataFrame([{"province": ALL_ROW, "weight_share": 1.0, "n_segments": len(segments),
                              "net_pct": result.headline_net_pct, "contract_pct": result.headline_contract_pct}],
                            columns=PROVINCE_COLUMNS)
    net, contract = columns
    total_weight = float(segments["weight"].sum())
    usable = segments.assign(province=segments["prop_code"].map(province_of)).dropna(subset=[net, contract])

    def aggregate(label, group):
        weight = float(group["weight"].sum())
        return {"province": label, "weight_share": weight / total_weight, "n_segments": len(group),
                "net_pct": to_pct(float((group["weight"] * group[net]).sum() / weight)),
                "contract_pct": to_pct(float((group["weight"] * group[contract]).sum() / weight))}

    rows = [aggregate(province, group) for province, group in usable.groupby("province", sort=True)]
    rows.append(aggregate(ALL_ROW, usable))
    return pd.DataFrame(rows, columns=PROVINCE_COLUMNS)


# ---------------------------------------------------------------------------
# Sensitivity of the headline to one assumption at a time (tornado chart, F-10)
# ---------------------------------------------------------------------------
SENSITIVITY_COLUMNS = ["assumption", "variant", "setting", "model", "headline_net_pct", "base_net_pct", "delta_pp",
                       "abs_delta_pp", "note"]
E2_NAME = "E2_regulated"


def _with_values(cfg: dict, updates: dict[tuple, object]) -> dict:
    """Deep copy of the config with the given (path -> value) changes; the original is never modified."""
    changed = copy.deepcopy(cfg)
    for path, value in updates.items():
        node = changed
        for key in path[:-1]:
            node = node[key]
        node[path[-1]] = value
    return changed


def sensitivity_table(tables, external: pd.DataFrame, cfg: dict, champion: str | None = None, models: dict | None = None,
                      year: int | None = None) -> pd.DataFrame:
    """Headline change from altering ONE assumption at a time, sorted by absolute change. Aggregates only.

    The champion model (chosen once under the base configuration and held fixed) is rerun with each data or rule choice
    changed alone: public-data information rule (agreed vs strict), pair gap bounds (including 6-month leases and two
    alternative upper bounds), winsorization quantiles, and the weight window moved by plus and minus a step.
    E2_regulated is rerun for the regulatory levers (new-build exempt vs guideline applies, incentive intensity, renewal mix,
    which are the scenario levers) and for the information rule, because it is the model that reads the TAL rate.
    Model choice compares every model in `sensitivity.model_choices` with the champion. Each row's `delta_pp` is
    relative to the base run of the SAME model (champion base or E2 central; model-choice rows: relative to the champion),
    so the sign says whether the assumption raises or lowers that model's headline. Values and sizes of the variants are
    in forecast.yaml (`sensitivity`, `scenarios`); nothing is combined. These are sensitivities, not prediction intervals.
    A variant that cannot run keeps its row with NaN values and the reason in `note`.
    """
    from halolens.evaluate.backtest import all_models, champion_pipeline
    from halolens.forecast.asof import snapshot_for_year

    models = models if models is not None else all_models()
    year = cfg["forecast_years"]["target_year"] if year is None else year
    champion = champion if champion is not None else champion_pipeline(tables, external, cfg)["champion"]
    settings = cfg["sensitivity"]
    rows: list[dict] = []

    def run(model: str, variant_cfg: dict, strict: bool = False) -> float:
        snapshot = snapshot_for_year(tables, external, year, variant_cfg, strict=strict)
        return models[model](snapshot, variant_cfg).headline_net_pct

    def add(assumption: str, variant: str, setting, model: str, base: float, variant_cfg: dict | None = None,
            strict: bool = False, value: float | None = None) -> None:
        row = {"assumption": assumption, "variant": variant, "setting": str(setting), "model": model,
               "headline_net_pct": np.nan, "base_net_pct": base, "delta_pp": np.nan, "abs_delta_pp": np.nan, "note": ""}
        try:
            net = value if value is not None else run(model, variant_cfg or cfg, strict)
        except ValueError as problem:
            row["note"] = str(problem)
        else:
            row.update(headline_net_pct=net, delta_pp=net - base, abs_delta_pp=abs(net - base))
        rows.append(row)

    def unavailable(assumption: str, variant: str, setting, model: str, note: str) -> None:
        rows.append({"assumption": assumption, "variant": variant, "setting": str(setting), "model": model,
                     "headline_net_pct": np.nan, "base_net_pct": np.nan, "delta_pp": np.nan, "abs_delta_pp": np.nan,
                     "note": note})

    base_champion = run(champion, cfg)

    # data and rule choices, rerun on the champion
    add("information_rule", "strict_dec31", "dec31_strict", champion, base_champion, strict=True)
    add("gap_bounds", "include_six_month_leases", cfg["pairs"]["sensitivity_min_gap_years"], champion, base_champion,
        _with_values(cfg, {("pairs", "min_gap_years"): cfg["pairs"]["sensitivity_min_gap_years"]}))
    for upper in settings["max_gap_alternatives_years"]:
        add("gap_bounds", "max_gap", upper, champion, base_champion, _with_values(cfg, {("pairs", "max_gap_years"): upper}))
    for lower_q, upper_q in settings["winsor_alternatives"]:
        add("winsorization", "quantiles", [lower_q, upper_q], champion, base_champion,
            _with_values(cfg, {("winsorize", "lower_quantile"): lower_q, ("winsorize", "upper_quantile"): upper_q}))
    window = cfg["headline"]["weight_window_years"]
    for shifted in (window - settings["weight_window_step_years"], window + settings["weight_window_step_years"]):
        add("weight_window", "years", shifted, champion, base_champion,
            _with_values(cfg, {("headline", "weight_window_years"): shifted}))

    # regulatory levers, rerun on E2 (central base)
    try:
        e2_result = models[E2_NAME](snapshot_for_year(tables, external, year, cfg), cfg)
        scenarios = scenario_table(e2_result, cfg).set_index("scenario")
        e2_base = float(scenarios.loc[CENTRAL, "headline_net_pct"])
    except ValueError as problem:
        e2_base, scenarios, e2_note = np.nan, None, str(problem)
    lever_rows = [("newbuild_applicability", "ontario_newbuild_guideline_applies", "guideline_applies", "ontario_newbuild_guideline_applies"),
                  ("incentive_intensity", "incentives_deeper", cfg["scenarios"]["incentive_intensity_shift_pp"], "incentives_deeper"),
                  ("incentive_intensity", "incentives_shallower", -cfg["scenarios"]["incentive_intensity_shift_pp"], "incentives_shallower"),
                  ("renewal_mix", "more_renewals", cfg["scenarios"]["renewal_share_shift_pp"], "more_renewals"),
                  ("renewal_mix", "fewer_renewals", -cfg["scenarios"]["renewal_share_shift_pp"], "fewer_renewals")]
    for assumption, variant, setting, scenario in lever_rows:
        if scenarios is None:
            unavailable(assumption, variant, setting, E2_NAME, e2_note)
        else:
            add(assumption, variant, setting, E2_NAME, e2_base, value=float(scenarios.loc[scenario, "headline_net_pct"]))
    if champion != E2_NAME:
        if scenarios is None:
            unavailable("information_rule", "strict_dec31", "dec31_strict", E2_NAME, e2_note)
        else:
            add("information_rule", "strict_dec31", "dec31_strict", E2_NAME, e2_base, strict=True)

    # model choice, relative to the champion
    for name in settings["model_choices"]:
        if name != champion:
            add("model_choice", name, name, name, base_champion, cfg)

    table = pd.DataFrame(rows)[SENSITIVITY_COLUMNS]
    return table.sort_values("abs_delta_pp", ascending=False, na_position="last", kind="stable").reset_index(drop=True)
