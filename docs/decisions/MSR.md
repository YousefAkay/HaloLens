# Decisions MSR

Append one bullet per entry, newest last.
- 2026-10-03 (M-01): Matching key is `prop_code + unit_code` (`pairs.unit_key`), cross-checked one-to-one against `unit_id` (`pairs.cross_check_key`). `sSite + sUnitCode` is used only in the collision test/demo.
- 2026-10-03 (M-01): `build_pairs` returns one row per consecutive lease pair, eligible or not; every excluded pair has a non-empty `exclusion_reason` and every eligible pair has an empty one.
- 2026-10-03 (M-01): Pair tests written before the implementation are marked strict `xfail(raises=NotImplementedError)` so `dev` stays green; M-02 removes the marker.
