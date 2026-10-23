# Decisions

Short architecture-decision list. Details are in [methodology.md](methodology.md).

1. **Headline is log-mean growth in net rent, fixed weights.** Exact additivity across segments and the contractual-to-net bridge; median reported as robustness check.
2. **Same-unit pairs on `prop_code + unit_code`.** Cross-checked with the source unit id; site-name keys are rejected.
3. **Gap bounds 0.5 to 2.5 years, with sensitivity.** Shorter gaps are usually double-recorded leases; longer ones are not like for like.
4. **Weights frozen at the cutoff, from a trailing window of pairs.** A mix change cannot masquerade as a price change.
5. **Winsor thresholds learned on training pairs only.** A year more extreme than earlier years is capped at the earlier maximum.
6. **Renewals and turnovers are separate segments.** Province rules are never cross-applied.
7. **Cutoff is December 31 of y-1; public data allowed up to January 31 of the target year.** Strict version reported as sensitivity.
8. **Concession credits are linked to leases by reconciliation fit, not multiplied.** Lump credits stay lump.
9. **Champion chosen on selection years, last year held out.** Losing models are shown in the backtest table.
10. **Engine weights are untuned starting values.** They may be re-examined on selection years only.
11. **Shrinkage uses a fixed number of pseudo-pairs** rather than a fitted estimator.
12. **Uncertainty = scenarios + sensitivities + unit-cluster bootstrap**, each labelled for what it is.
13. **Notebook is generated from jupytext sections** and executed on a clean kernel; figures are aggregates only.
14. **AI layer sits behind a privacy wall.** The API receives public pages, aggregate JSON, committed notes stripped of data numbers, and the question. A number guard rejects any figure absent from the aggregates; cached answers are the fallback.
15. **No trained model is saved.** The champion is a transparent rule over the data; parameters live in `config/*.yaml`.
