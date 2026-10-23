"""Time-respecting backtests on 2023-2025.

Owner: FCT. Implements AGENTS.md Section 7.3. Every fold forecasts as of December 31 of the year before the target
through `snapshot_for_year` (CRM cut at Dec 31, public data at Jan 31 of the target year), then compares with the actual of that year under the same headline definition.
`run_backtest` uses `forecast.combine.forecast` (F-05); `backtest_baselines` runs B0-B2 through the same machinery.
"""

from __future__ import annotations

from typing import Callable

import numpy as np
import pandas as pd
from halolens.config import cutoff_for
from halolens.contracts import (ASKING_COLUMNS, CONCESSIONS_COLUMNS, EXTERNAL_COLUMNS, UNITS_COLUMNS, BacktestResult,
                                 CanonicalTables, ForecastResult, Snapshot)
from halolens.evaluate.metrics import absolute_error_pp, mean_absolute_error_pp, signed_error_pp
from halolens.forecast.asof import snapshot_for_year
from halolens.forecast.baselines import (BASELINES, frozen_weights, headline_summary, to_pct, training_pairs,
                                          winsor_bounds)
from halolens.forecast.combine import MODEL_NAME as ENGINE_MODEL_NAME
from halolens.forecast.combine import REGULATED_MODEL_NAME, forecast, forecast_regulated
from halolens.measure.pairs import build_pairs

Forecaster = Callable[[Snapshot, dict], ForecastResult]


def actual_for_year(tables: CanonicalTables, year: int, weights: pd.DataFrame, cfg: dict) -> dict:
    """Actual headline for `year` with weights frozen at that year's cutoff.

    Pairs are eligible same-unit pairs whose later lease starts in `year`. Winsorization thresholds are learned on
    pairs known at the year's cutoff, not on the year itself. Returns net_pct, contract_pct, median_net_pct,
    median_contract_pct, n_pairs, weight_coverage and the per-segment table; raises ValueError without pairs.
    """
    pairs = build_pairs(tables.leases, cfg)
    pairs = pairs[pairs["eligible"]]
    cutoff = cutoff_for(year, cfg)
    known = pairs[(pairs["sign_date"] <= cutoff) & (pairs["lease_start"] <= cutoff)]
    summary = headline_summary(pairs[pairs["year"] == year], weights, winsor_bounds(known, cfg), cfg)
    if summary is None:
        raise ValueError(f"No eligible pairs with weighted segments in {year}")
    return {
        "net_pct": to_pct(summary["log_net"]), "contract_pct": to_pct(summary["log_contract"]),
        "median_net_pct": to_pct(summary["log_median_net"]),
        "median_contract_pct": to_pct(summary["log_median_contract"]),
        "n_pairs": summary["n_pairs"], "weight_coverage": summary["coverage"], "segments": summary["segments"],
    }


def _fold(forecaster: Forecaster, tables: CanonicalTables, external: pd.DataFrame, target_year: int,
          cfg: dict, strict: bool = False) -> BacktestResult:
    """One backtest fold: snapshot under the information-date rule, forecast, then the actual.

    `strict=False` is the agreed rule (public data released by January 31 of the target year); `strict=True` is the
    Dec-31 sensitivity. CRM data is cut at December 31 of the year before the target either way.
    """
    cutoff = cutoff_for(target_year, cfg)
    snapshot = snapshot_for_year(tables, external, target_year, cfg, strict=strict)
    result = forecaster(snapshot, cfg)
    weights = frozen_weights(training_pairs(snapshot, cfg), cutoff, cfg)
    actual = actual_for_year(tables, target_year, weights, cfg)
    return BacktestResult(
        target_year=target_year, forecast=result,
        actual_net_pct=actual["net_pct"], actual_contract_pct=actual["contract_pct"],
        error_pp_net=signed_error_pp(result.headline_net_pct, actual["net_pct"]),
        error_pp_contract=signed_error_pp(result.headline_contract_pct, actual["contract_pct"]),
        coverage={"n_pairs_actual": actual["n_pairs"], "weight_coverage": actual["weight_coverage"],
                  "n_leases_known": len(snapshot.leases)})


SENSITIVITY_KEY = "sensitivity_strict_dec31"


def run_backtest(tables: CanonicalTables, external: pd.DataFrame, target_year: int, cfg: dict) -> BacktestResult:
    """Forecast as of Dec 31 of target_year - 1 with forecast.combine.forecast, then compare with the actual.

    CRM data is cut at December 31 of target_year - 1; public data at January 31 of target_year (information-date rule). When
    `forecast_years.external_cutoff_strict_sensitivity` is true, `coverage["sensitivity_strict_dec31"]` holds the same
    fold with public data cut at December 31 as well: forecast_net_pct, forecast_contract_pct, error_pp_net,
    error_pp_contract.
    """
    result = _fold(forecast, tables, external, target_year, cfg)
    if cfg["forecast_years"]["external_cutoff_strict_sensitivity"]:
        strict = _fold(forecast, tables, external, target_year, cfg, strict=True)
        result.coverage[SENSITIVITY_KEY] = {
            "forecast_net_pct": strict.forecast.headline_net_pct,
            "forecast_contract_pct": strict.forecast.headline_contract_pct,
            "error_pp_net": strict.error_pp_net, "error_pp_contract": strict.error_pp_contract}
    return result


RULE_JAN31, RULE_DEC31 = "jan31", "dec31_strict"


def backtest_table(tables: CanonicalTables, external: pd.DataFrame, cfg: dict, models: dict[str, Forecaster],
                   years: list[int] | None = None, strict: bool = False) -> pd.DataFrame:
    """Backtest table: one row per model x year with forecast, actual and errors (pp). Aggregates only.

    `strict` selects the information-date rule (False: public data by January 31 of the target year; True: December
    31 sensitivity); the `rule` column says which. Contract-rent columns sit next to the net ones.

    A model that cannot run for a fold (for example B2 without released market data) keeps its row with NaN
    values and the reason in `note`, so a losing or missing model stays visible.
    """
    years = years if years is not None else cfg["forecast_years"]["backtest_years"]
    rows = []
    for name, forecaster in models.items():
        for year in years:
            row = {"model": name, "year": year, "rule": RULE_DEC31 if strict else RULE_JAN31,
                   "forecast_net_pct": np.nan, "actual_net_pct": np.nan, "error_pp_net": np.nan,
                   "abs_error_pp_net": np.nan, "forecast_contract_pct": np.nan, "actual_contract_pct": np.nan,
                   "error_pp_contract": np.nan, "note": ""}
            try:
                fold = _fold(forecaster, tables, external, year, cfg, strict=strict)
            except ValueError as problem:
                row["note"] = str(problem)
            else:
                row.update(forecast_net_pct=fold.forecast.headline_net_pct, actual_net_pct=fold.actual_net_pct,
                           error_pp_net=fold.error_pp_net,
                           abs_error_pp_net=absolute_error_pp(fold.forecast.headline_net_pct, fold.actual_net_pct),
                           forecast_contract_pct=fold.forecast.headline_contract_pct,
                           actual_contract_pct=fold.actual_contract_pct, error_pp_contract=fold.error_pp_contract)
            rows.append(row)
    return pd.DataFrame(rows)


def all_models() -> dict[str, Forecaster]:
    """Every model that is backtested and eligible for champion selection: B0-B3, E1_engine_blend, E2_regulated."""
    return {**BASELINES, ENGINE_MODEL_NAME: forecast, REGULATED_MODEL_NAME: forecast_regulated}


def backtest_baselines(tables: CanonicalTables, external: pd.DataFrame, cfg: dict,
                       years: list[int] | None = None, strict: bool = False) -> pd.DataFrame:
    """Backtest table for B0-B2 only (same columns as `backtest_table`)."""
    return backtest_table(tables, external, cfg, dict(BASELINES), years, strict)


def backtest_all_models(tables: CanonicalTables, external: pd.DataFrame, cfg: dict,
                        years: list[int] | None = None, strict: bool = False) -> pd.DataFrame:
    """Backtest table for every model (B0-B3, E1, E2; see `all_models`), each through the same folds."""
    return backtest_table(tables, external, cfg, all_models(), years, strict)


def backtest_both_rules(tables: CanonicalTables, external: pd.DataFrame, cfg: dict,
                        years: list[int] | None = None) -> pd.DataFrame:
    """All models under the agreed January-31 rule, plus the Dec-31 sensitivity when the config asks for it (`rule` column)."""
    tables_by_rule = [backtest_all_models(tables, external, cfg, years)]
    if cfg["forecast_years"]["external_cutoff_strict_sensitivity"]:
        tables_by_rule.append(backtest_all_models(tables, external, cfg, years, strict=True))
    return pd.concat(tables_by_rule, ignore_index=True)


def summarize_models(table: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Per model: mean absolute net error (pp) over the selection years, over the holdout year and over all years.

    Selection and holdout years come from core.yaml (forecast_years). The champion is chosen on the selection years only
    (F-07); the holdout column is for the final comparison. Columns: model, mae_selection_pp, mae_holdout_pp,
    mae_all_pp, n_folds_run (folds that produced a forecast). A `rule` column is added and the summary is computed
    per rule when the table holds both information-date rules.
    """
    selection = cfg["forecast_years"]["selection_years"]
    holdout = cfg["forecast_years"]["holdout_year"]
    rows = []
    group_keys = ["rule", "model"] if "rule" in table.columns else ["model"]
    for label, group in table.groupby(group_keys, sort=False):
        name = label[-1] if isinstance(label, tuple) else label
        errors = group.set_index("year")["abs_error_pp_net"]
        rows.append({**({"rule": label[0]} if len(group_keys) == 2 else {}), "model": name,
                     "mae_selection_pp": mean_absolute_error_pp(errors.reindex(selection)),
                     "mae_holdout_pp": mean_absolute_error_pp(errors.reindex([holdout])),
                     "mae_all_pp": mean_absolute_error_pp(errors), "n_folds_run": int(errors.notna().sum())})
    return pd.DataFrame(rows)


def select_champion(table: pd.DataFrame, cfg: dict) -> dict:
    """Pre-declared champion rule: lowest mean absolute net error (pp) over the selection years, on the agreed Jan-31 rule.

    Only `selection_years` (core.yaml, 2023-24) are used to choose; the holdout year (2025) is reported in the ranking
    but never used to choose. A model is eligible only if it produced a forecast for every selection year; ties keep the
    order of the table (simplest model first). Returns champion, rule, metric, selection_years, holdout_year and
    ranking (model, mae_selection_pp, n_selection_folds_run, eligible, mae_holdout_pp), best first.
    Raises ValueError when no model is eligible or the configured metric is not supported.
    """
    metric = cfg["selection"]["metric"]
    if metric != "mean_absolute_error_pp":
        raise ValueError(f"Unsupported selection metric: {metric!r}")
    selection = cfg["forecast_years"]["selection_years"]
    holdout = cfg["forecast_years"]["holdout_year"]
    agreed = table[table["rule"] == RULE_JAN31] if "rule" in table.columns else table
    rows = []
    for name, group in agreed.groupby("model", sort=False):
        errors = group.set_index("year")["abs_error_pp_net"]
        in_selection = errors.reindex(selection)
        rows.append({"model": name, "mae_selection_pp": mean_absolute_error_pp(in_selection),
                     "n_selection_folds_run": int(in_selection.notna().sum()),
                     "eligible": bool(in_selection.notna().all()),
                     "mae_holdout_pp": mean_absolute_error_pp(errors.reindex([holdout]))})
    ranking = pd.DataFrame(rows)
    eligible = ranking[ranking["eligible"]].sort_values("mae_selection_pp", kind="stable")
    if eligible.empty:
        raise ValueError("No model produced a forecast for every selection year")
    ranking = pd.concat([eligible, ranking[~ranking["eligible"]]], ignore_index=True)
    return {"champion": eligible["model"].iloc[0], "rule": RULE_JAN31, "metric": metric,
            "selection_years": list(selection), "holdout_year": holdout, "ranking": ranking}


# ---------------------------------------------------------------------------
# Champion pipeline: the one path behind estimate_2026() and backtest() (notebook section 10)
# ---------------------------------------------------------------------------
def empty_external() -> pd.DataFrame:
    """An external table with the contract columns and no rows (models that need public data then report a reason)."""
    return pd.DataFrame(columns=EXTERNAL_COLUMNS).astype(
        {"release_date": "datetime64[ns]", "ref_period_start": "datetime64[ns]", "ref_period_end": "datetime64[ns]",
         "accessed_date": "datetime64[ns]", "value": float})


def tables_from_leases(leases: pd.DataFrame, asking: pd.DataFrame) -> CanonicalTables:
    """CanonicalTables from the two tables the notebook-facing signatures receive; concessions and listings are left empty.

    No model uses them: the incentive engine works from the lease rows (contract vs net rent) and listings are never
    used for historical folds.
    """
    return CanonicalTables(leases=leases, concessions=pd.DataFrame(columns=CONCESSIONS_COLUMNS), asking=asking,
                           units=pd.DataFrame(columns=UNITS_COLUMNS))


def champion_pipeline(tables: CanonicalTables, external: pd.DataFrame | None, cfg: dict,
                      table: pd.DataFrame | None = None) -> dict:
    """Run the pre-declared champion rule: backtest every model, select_champion, return that model's forecaster.

    `table` may carry an already computed Jan-31 backtest table (from `backtest_all_models`) to avoid recomputing it.
    Returns the `select_champion` dict plus `forecaster`. The rule is fixed in advance (core.yaml selection years,
    forecast.yaml selection metric); nothing here looks at the holdout year.
    """
    external = empty_external() if external is None else external
    table = backtest_all_models(tables, external, cfg) if table is None else table
    chosen = select_champion(table, cfg)
    return {**chosen, "forecaster": all_models()[chosen["champion"]]}


def champion_forecast(tables: CanonicalTables, external: pd.DataFrame | None, cfg: dict,
                      year: int | None = None, table: pd.DataFrame | None = None) -> ForecastResult:
    """The champion model's ForecastResult for `year` (default: the target year) under the agreed Jan-31 information date."""
    external = empty_external() if external is None else external
    year = cfg["forecast_years"]["target_year"] if year is None else year
    pipeline = champion_pipeline(tables, external, cfg, table)
    return pipeline["forecaster"](snapshot_for_year(tables, external, year, cfg), cfg)


def champion_backtest(tables: CanonicalTables, external: pd.DataFrame | None, target_year: int, cfg: dict,
                      table: pd.DataFrame | None = None) -> BacktestResult:
    """One backtest fold of the champion model (same fold code as `run_backtest`), reporting the Dec-31 sensitivity too.

    For 2023 and 2024 this is a selection fold (the champion was chosen on those years by a rule declared in advance);
    2025 is the out-of-sample holdout.
    """
    external = empty_external() if external is None else external
    pipeline = champion_pipeline(tables, external, cfg, table)
    result = _fold(pipeline["forecaster"], tables, external, target_year, cfg)
    if cfg["forecast_years"]["external_cutoff_strict_sensitivity"]:
        strict = _fold(pipeline["forecaster"], tables, external, target_year, cfg, strict=True)
        result.coverage[SENSITIVITY_KEY] = {
            "forecast_net_pct": strict.forecast.headline_net_pct,
            "forecast_contract_pct": strict.forecast.headline_contract_pct,
            "error_pp_net": strict.error_pp_net, "error_pp_contract": strict.error_pp_contract}
    result.coverage["champion"] = pipeline["champion"]
    return result


def headline_table(tables: CanonicalTables, external: pd.DataFrame | None, cfg: dict,
                   year: int | None = None) -> pd.DataFrame:
    """Headline of every model for `year` (default: the target year) under the Jan-31 rule and the Dec-31 sensitivity.

    Columns: rule ("jan31" / "dec31_strict"), model, net_pct, contract_pct, median_net_pct, median_contract_pct, note
    (the reason when a model cannot run, with NaN values). Aggregates only.
    """
    external = empty_external() if external is None else external
    year = cfg["forecast_years"]["target_year"] if year is None else year
    rules = [(False, RULE_JAN31)] + ([(True, RULE_DEC31)] if cfg["forecast_years"]["external_cutoff_strict_sensitivity"] else [])
    rows = []
    for strict, rule in rules:
        snapshot = snapshot_for_year(tables, external, year, cfg, strict=strict)
        for name, forecaster in all_models().items():
            row = {"rule": rule, "model": name, "net_pct": np.nan, "contract_pct": np.nan, "median_net_pct": np.nan,
                   "median_contract_pct": np.nan, "note": ""}
            try:
                result = forecaster(snapshot, cfg)
            except ValueError as problem:
                row["note"] = str(problem)
            else:
                row.update(net_pct=result.headline_net_pct, contract_pct=result.headline_contract_pct,
                           median_net_pct=result.median_net_pct, median_contract_pct=result.median_contract_pct)
            rows.append(row)
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Presentation helpers for notebook text (dates are generated from config, never typed in Markdown)
# ---------------------------------------------------------------------------
MONTHS_FR = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre",
             "novembre", "décembre"]


def french_day_month(date) -> str:
    """'31 janvier' for any date-like value."""
    date = pd.Timestamp(date)
    return f"{date.day} {MONTHS_FR[date.month - 1]}"


def french_date(date) -> str:
    """'15 novembre 2018' for any date-like value."""
    return f"{french_day_month(date)} {pd.Timestamp(date).year}"
