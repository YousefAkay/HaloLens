# Assumptions MSR

Append one bullet per entry, newest last.
- 2026-10-03 (M-01): Gap bounds keep the starter values (0.5 < gap_years < 2.5, strict). Note: a 6-month gap measures 181–184 days (0.496–0.504 years), so the 0.5 bound admits some 6-month leases and not others depending on the calendar months. M-02 reports how many pairs sit in that band; `sensitivity_min_gap_years: 0.45` admits all of them.
- 2026-10-03 (M-01): Growth is annualized as `ln(P_t / P_t-1) / gap_years` with `gap_years = days / 365.25` (contracts.DAYS_PER_YEAR), so a 365-day doubling reads ~100.1%/year rather than exactly 100%.
