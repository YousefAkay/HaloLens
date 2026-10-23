"""Unit-cluster bootstrap: resample whole unit histories and recompute the headline.

Implements `unit_bootstrap` (AGENTS.md Section 7.3).

Each draw resamples UNITS with replacement (every lease, concession and asking row of a drawn unit travels with it), so the
within-unit dependence of consecutive leases is kept. A unit drawn twice becomes two distinct units (suffix "~0", "~1"),
otherwise matching on the unit key would merge the copies into one history. The champion model, chosen once on the original
data, is rerun on every draw through the same snapshot and forecast pipeline as the real headline. The interval measures
SAMPLING uncertainty only: it does not cover the choice of model or of assumptions (see the scenarios and sensitivities).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from halolens.contracts import CanonicalTables
from halolens.evaluate.backtest import all_models, champion_pipeline
from halolens.forecast.asof import snapshot_for_year

DRAW_COLUMNS = ["draw", "model", "n_units", "net_pct", "contract_pct", "median_net_pct", "median_contract_pct", "note"]
COPY_SEPARATOR = "~"
NET, CONTRACT = "net_pct", "contract_pct"


def _relabel(frame: pd.DataFrame, picks: pd.DataFrame) -> pd.DataFrame:
    """Rows of `frame` for the drawn units, one copy per draw, with the copy number appended to unit_id and unit_code."""
    if frame is None or frame.empty:
        return frame
    merged = frame.merge(picks, on="unit_id", how="inner")
    suffix = COPY_SEPARATOR + merged["copy"].astype(str)
    merged["unit_id"] = merged["unit_id"] + suffix
    if "unit_code" in merged.columns:
        merged["unit_code"] = merged["unit_code"] + suffix
    return merged.drop(columns="copy").reset_index(drop=True)


def resample_units(tables: CanonicalTables, rng: np.random.Generator) -> CanonicalTables:
    """One bootstrap sample: units drawn with replacement, each with its complete history. Inputs are not modified.

    The number of drawn units equals the number of units with leases; the number of leases varies with the draw. Listings
    (`units`) are passed through untouched because no model reads them for a historical or current fold.
    """
    unit_ids = tables.leases["unit_id"].unique()
    drawn = rng.choice(unit_ids, size=len(unit_ids), replace=True)
    picks = pd.DataFrame({"unit_id": drawn})
    picks["copy"] = picks.groupby("unit_id").cumcount()
    return CanonicalTables(leases=_relabel(tables.leases, picks), concessions=_relabel(tables.concessions, picks),
                           asking=_relabel(tables.asking, picks), units=tables.units)


def unit_bootstrap(tables: CanonicalTables, external: pd.DataFrame, cfg: dict, n_boot: int, champion: str | None = None,
                   models: dict | None = None, year: int | None = None) -> pd.DataFrame:
    """Return one row per bootstrap draw with the recomputed headline (seed from core.yaml).

    Inputs: canonical tables, the verified public data, merged config (`random_seed`, `uncertainty`), the number of draws.
    `champion` defaults to the model chosen by the pre-declared rule on the original data and is held fixed across draws
    (re-selecting inside each draw would add model-choice variation to a sampling interval and cost a full backtest per draw).
    Draw i uses the random stream seeded with [random_seed, i], so a draw does not depend on how many draws are requested.
    Columns: draw, model, n_units, net_pct, contract_pct, median_net_pct, median_contract_pct, note. A draw whose forecast
    cannot be computed keeps its row with NaN values and the reason in `note`. Aggregates only: no unit identifiers.
    """
    models = models if models is not None else all_models()
    year = cfg["forecast_years"]["target_year"] if year is None else year
    champion = champion if champion is not None else champion_pipeline(tables, external, cfg)["champion"]
    forecaster = models[champion]
    rows = []
    for draw in range(n_boot):
        sample = resample_units(tables, np.random.default_rng([cfg["random_seed"], draw]))
        row = {"draw": draw, "model": champion, "n_units": int(sample.leases["unit_id"].nunique()), "net_pct": np.nan,
               "contract_pct": np.nan, "median_net_pct": np.nan, "median_contract_pct": np.nan, "note": ""}
        try:
            result = forecaster(snapshot_for_year(sample, external, year, cfg), cfg)
        except ValueError as problem:
            row["note"] = str(problem)
        else:
            row.update(net_pct=result.headline_net_pct, contract_pct=result.headline_contract_pct,
                       median_net_pct=result.median_net_pct, median_contract_pct=result.median_contract_pct)
        rows.append(row)
    return pd.DataFrame(rows, columns=DRAW_COLUMNS)


def bootstrap_interval(draws: pd.DataFrame, cfg: dict) -> dict:
    """Percentile interval of the net and contract headline over the successful draws.

    Quantiles come from `uncertainty.interval_quantiles` (core.yaml). Returns lower, upper, mean and sd for each of net and
    contract, plus n_draws, n_ok and n_failed. Quantiles are NaN when no draw succeeded.
    """
    low, high = cfg["uncertainty"]["interval_quantiles"]
    ok = draws.dropna(subset=[NET, CONTRACT])
    summary = {"n_draws": len(draws), "n_ok": len(ok), "n_failed": len(draws) - len(ok),
               "quantiles": [low, high]}
    for name in (NET, CONTRACT):
        values = ok[name]
        summary[name] = {"lower": float(values.quantile(low)) if len(values) else np.nan,
                         "upper": float(values.quantile(high)) if len(values) else np.nan,
                         "mean": float(values.mean()) if len(values) else np.nan,
                         "sd": float(values.std(ddof=1)) if len(values) > 1 else np.nan}
    return summary
