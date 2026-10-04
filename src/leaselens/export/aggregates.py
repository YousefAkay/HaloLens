"""Aggregate export: build the aggregates JSON from the pipeline and validate it before writing. Owner: INT (I-09).

Only aggregates leave this module: counts, percentages, dates and source metadata. No lease, unit, segment or
pair rows. The output is validated against contracts.AGGREGATES_SCHEMA (closed objects), so a unit-level field
cannot be written.

The headline, companions, 2026 model range and province split come from `_headline`, which calls the champion
pipeline (`champion_forecast`, the same path as `estimate_2026()`), so the export and the notebook agree.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from jsonschema import Draft202012Validator, FormatChecker

from leaselens.config import cutoff_for, external_cutoff_for
from leaselens.contracts import AGGREGATES_SCHEMA, AGGREGATES_SCHEMA_VERSION, CanonicalTables
from leaselens.evaluate.backtest import (RULE_JAN31, backtest_both_rules, champion_forecast, champion_pipeline,
                                        headline_table)
from leaselens.forecast.asof import snapshot_for_year
from leaselens.forecast.baselines import BASELINE_NAMES, frozen_weights, training_pairs
from leaselens.forecast.combine import MODEL_NAME as ENGINE_MODEL_NAME
from leaselens.forecast.combine import REGULATED_MODEL_NAME, forecast_regulated
from leaselens.forecast.scenarios import CENTRAL, headline_by_province, scenario_table
from leaselens.measure.pairs import build_pairs

DEFINITION = (
    "Croissance à composition fixe et à unité constante du loyer net de toutes concessions, pour l'année cible "
    "(AGENTS.md §9.1). Chaque paire compare un bail à son bail précédent dans la même unité ; les poids de segment "
    "sont figés à la date de coupure et décrivent les transitions de baux observées, pas l'occupation ni le taux de "
    "roulement du portefeuille. Les compagnons (loyer contractuel, médianes) sont toujours présentés à côté."
)
NOTE_REAL = ("Agrégats seulement : pourcentages, comptes et dates. Ne pas publier avant l'approbation du "
             "commanditaire pour ce qui peut sortir de la machine.")
NOTE_SYNTHETIC = ("EXEMPLE SYNTHÉTIQUE calculé sur les données fictives du dépôt : la mode, les comptes et les "
                  "chiffres ne décrivent pas project.")
RULE_ORDER = ("jan31", "dec31_strict")
BACKTEST_RENAMES = {"rule": "information_rule"}
BACKTEST_FIELDS = ["year", "model", "information_rule", "forecast_net_pct", "actual_net_pct", "error_pp_net",
                   "forecast_contract_pct", "actual_contract_pct", "error_pp_contract"]


def _clean(value: Any) -> Any:
    """JSON-safe scalar: NaN becomes None, numpy scalars become Python numbers."""
    if value is None:
        return None
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        return None if math.isnan(value) else float(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    return value


MODEL_RANGE_NAMES = (BASELINE_NAMES["last_year"], BASELINE_NAMES["trailing_mean"], ENGINE_MODEL_NAME,
                     REGULATED_MODEL_NAME)  # the candidates behind the 2026 model range (B0, B1, E1, E2)


def _headline(tables: CanonicalTables, external: pd.DataFrame, cfg: dict,
              table: pd.DataFrame | None = None) -> dict[str, Any]:
    """Headline, companions, 2026 model range and province split, from the pre-declared champion.

    Uses the same pipeline as estimate_2026(): champion_forecast with the Jan-31 information date. `table` may carry the
    backtest_both_rules table already computed for the backtest rows, so the folds run once.
    """
    target = cfg["forecast_years"]["target_year"]
    table = backtest_both_rules(tables, external, cfg) if table is None else table
    champion = champion_pipeline(tables, external, cfg, table=table)["champion"]
    result = champion_forecast(tables, external, cfg, table=table)
    province_of = tables.leases.drop_duplicates("prop_code").set_index("prop_code")["province"]
    provinces = headline_by_province(result, province_of).set_index("province")
    candidates = headline_table(tables, external, cfg, year=target)
    candidates = candidates[(candidates["rule"] == RULE_JAN31) & candidates["model"].isin(MODEL_RANGE_NAMES)]
    net_range = candidates["net_pct"].dropna()

    def province(name: str) -> dict[str, Any]:
        if name not in provinces.index:
            return {"net_pct": None, "contract_pct": None}
        row = provinces.loc[name]
        return {"net_pct": _clean(row["net_pct"]), "contract_pct": _clean(row["contract_pct"])}

    return {
        "headline": {
            "net_pct": _clean(result.headline_net_pct), "contract_pct": _clean(result.headline_contract_pct),
            "information_rule": "jan31", "model": champion,
            "model_range": {"low_net_pct": _clean(net_range.min()) if len(net_range) else None,
                            "high_net_pct": _clean(net_range.max()) if len(net_range) else None},
            "provinces": {"QC": province("QC"), "ON": province("ON")},
        },
        "companions": {"median_net_pct": _clean(result.median_net_pct),
                       "median_contract_pct": _clean(result.median_contract_pct)},
    }


def _backtest_rows(table: pd.DataFrame) -> list[dict[str, Any]]:
    """Every model x backtest year x information rule, from the same folds the champion is chosen on."""
    table = table.rename(columns=BACKTEST_RENAMES)
    rows = []
    for record in table.sort_values(["information_rule", "model", "year"]).to_dict("records"):
        rows.append({field: _clean(record[field]) for field in BACKTEST_FIELDS})
    return rows


def _scenarios(tables: CanonicalTables, external: pd.DataFrame, target_year: int, cfg: dict) -> dict[str, Any]:
    """Low, central and high 2026 net headline from the scenario levers (E2 engine, as in section 11b)."""
    result = forecast_regulated(snapshot_for_year(tables, external, target_year, cfg), cfg)
    table = scenario_table(result, cfg).set_index("scenario")["headline_net_pct"]
    return {"low_net_pct": _clean(table["low"]), "central_net_pct": _clean(table[CENTRAL]),
            "high_net_pct": _clean(table["high"])}


def _sources(external: pd.DataFrame, ext_cutoff: pd.Timestamp) -> list[dict[str, Any]]:
    """One entry per public series released by the external cutoff: publisher, URL and latest release date."""
    released = external[external["release_date"] <= ext_cutoff]
    grouped = released.groupby("series_id").agg(publisher=("publisher", "first"), url=("url", "first"),
                                                release_date=("release_date", "max")).reset_index()
    return [{"series_id": record["series_id"], "publisher": record["publisher"], "url": record["url"],
             "release_date": record["release_date"].date().isoformat()}
            for record in grouped.to_dict("records")]


def build_aggregates(tables: CanonicalTables, external: pd.DataFrame, cfg: dict) -> dict[str, Any]:
    """Aggregates document for the app and the narrative, conforming to AGGREGATES_SCHEMA. Aggregates only."""
    target = cfg["forecast_years"]["target_year"]
    crm_cutoff = cutoff_for(target, cfg)
    ext_cutoff = external_cutoff_for(target, cfg)
    snapshot = snapshot_for_year(tables, external, target, cfg)
    pairs = build_pairs(tables.leases, cfg)
    weights = frozen_weights(training_pairs(snapshot, cfg), snapshot.cutoff, cfg)
    backtest = backtest_both_rules(tables, external, cfg)  # folds run once: rows here, champion choice in _headline
    head = _headline(tables, external, cfg, table=backtest)
    mode = cfg["data"]["mode"]
    return {
        "schema_version": AGGREGATES_SCHEMA_VERSION,
        "mode": mode,
        "target_year": target,
        "as_of": {"crm_cutoff": crm_cutoff.date().isoformat(), "external_cutoff": ext_cutoff.date().isoformat(),
                  "external_strict_cutoff": crm_cutoff.date().isoformat()},
        "definition": DEFINITION,
        "headline": head["headline"],
        "companions": head["companions"],
        "backtest": _backtest_rows(backtest),
        "coverage": {
            "leases": int(len(tables.leases)),
            "units": int(tables.leases[cfg["pairs"]["unit_key"]].drop_duplicates().shape[0]),
            "eligible_pairs": int(pairs["eligible"].sum()),
            "excluded_pairs": int((~pairs["eligible"]).sum()),
            "segments": int(len(weights)),
            "concessions": int(len(tables.concessions)),
            "asking_rows": int(len(tables.asking)),
            "external_rows": int(len(snapshot.external)),
        },
        "scenarios": _scenarios(tables, external, target, cfg),
        "sources": _sources(external, ext_cutoff),
        "note": NOTE_SYNTHETIC if mode == "synthetic" else NOTE_REAL,
    }


def validate(results: dict) -> None:
    """Raise jsonschema.ValidationError if the document does not conform to AGGREGATES_SCHEMA."""
    Draft202012Validator(AGGREGATES_SCHEMA, format_checker=FormatChecker()).validate(results)


def export(results: dict, path) -> None:
    """Validate the aggregates document, then write it as JSON. Nothing is written when validation fails."""
    validate(results)
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(results, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
