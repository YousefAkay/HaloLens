# Rubric checklist (INT)

Status at the final build. Evidence refers to sections of the submitted notebook `project_analysis.ipynb`.

| Criterion | Pts | Evidence in notebook | Owner | Status |
|---|---:|---|---|---|
| Definition of the increase | 10 | §00 (answer and definition), §01 (definition, population, horizon, weighting, companions) | INT | done |
| Data analysis & composition | 15 | §02 (dictionary, QA), §03 (naive median vs same-unit, mix shares, rent bridge) | INT + MSR | done |
| Same-unit matching | 15 | §04 (safe vs unsafe key, exclusion audit, coverage, gap sensitivity) | MSR | done |
| Concessions | 10 | §05 (contract vs net, PromoPay lump credits, reconciliation to leases) | FCT | done |
| Renewals vs turnovers | 10 | §06 (split by province, QC and ON rules, applicability matrix) | MSR | done |
| External data | 15 | §07 (provenance, release dates, reconciliation with CMHC and CPI), §12 (references) | MSR | done |
| Forecast & backtest | 15 | §08 (method), §09 (backtest 2023–2025, champion rule), §10 (`estimate_2026`, `backtest`) | FCT | done |
| Notebook quality | 10 | all sections: Markdown before each data-changing step, numbers generated from results and config, runs top to bottom | all | done |
| Bonus: Ontario rules, per building × beds, scenarios + tornado + bootstrap, dashboard + AI | — | §06 (Ontario guideline and the Ontario new-build scenarios), §11a and §11b (scenarios, sensitivity tornado, unit bootstrap), app (building × beds, scenario copilot and Q&A with number guard) | MSR, FCT, INT | done |

Sponsor point losses checked: no magic numbers (thresholds in `config/*.yaml`); consistent names (`contracts.py`); matching on `sPropCode + sUnitCode` only; Markdown cells present; no occupancy, vacancy, absorption or rent-roll figure quoted.
