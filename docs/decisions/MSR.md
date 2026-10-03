# Decisions MSR

Append one bullet per entry, newest last.
- 2026-10-03 (M-01): Matching key is `prop_code + unit_code` (`pairs.unit_key`), cross-checked one-to-one against `unit_id` (`pairs.cross_check_key`). `sSite + sUnitCode` is used only in the collision test/demo.
- 2026-10-03 (M-01): `build_pairs` returns one row per consecutive lease pair, eligible or not; every excluded pair has a non-empty `exclusion_reason` and every eligible pair has an empty one.
- 2026-10-03 (M-01): Pair tests written before the implementation are marked strict `xfail(raises=NotImplementedError)` so `dev` stays green; M-02 removes the marker.
- 2026-10-03 (M-02): Pairs are formed within `pairs.unit_key`, ordered by `lease_start` then `lease_seq`. Segment attributes (`beds`, `is_renewal`, building, province), `sign_date` and `year` come from the later lease of the pair.
- 2026-10-03 (M-02): Exclusion reasons are fixed codes (`missing_rent_or_date`, `non_positive_rent`, `gap_too_short`, `gap_too_long`, `unit_id_mismatch`), joined with `;` when a pair fails several rules. `unit_id_mismatch` = same safe key but a different hUnit on the two leases: the pair is rejected, not guessed.
- 2026-10-03 (M-02): Log growth is computed for every pair with positive rents and a positive gap, eligible or not, so `gap_sensitivity` can re-apply other bounds without rebuilding pairs. Downstream code must filter on `eligible`.
- 2026-10-03 (M-02): Added helpers `exclusion_summary(pairs)` and `gap_sensitivity(pairs, cfg)` (aggregates only) for section 04.
