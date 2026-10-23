# Methodology

## Definition of the increase

Headline: **fixed-composition same-unit growth in rent net of all incentives** for the target year.

- For each eligible pair of consecutive leases of the same unit, annualized log growth is `ln(P_i / P_{i-1}) / gap_years`,
  where P is the monthly rent net of all concession codes (`rent_net_all_incentives`).
- Growth is winsorized at quantiles set in `config/measure.yaml`, with thresholds learned on training pairs only.
- Segments are `prop_code x beds x is_renewal`. Each segment's mean log growth is weighted by fixed weights, the segment
  shares of eligible pairs in a window before the cutoff (`headline.weight_window_years`). Weights are frozen at each
  cutoff and describe the mix of observed lease transitions, not occupancy or turnover rate.
- Headline % = `100 x (exp(sum_s w_s * mean_s) - 1)`.
- Companions always reported next to it: the same measure on contractual rent, and plain medians of both.
- Log means make segment forecasts aggregate exactly and make the composition waterfall and the contractual-to-net bridge
  exactly additive. The median is the robustness check.
- Net rent is concession-adjusted rent, not cash collected.

Why not the median of all leases? It mostly measures composition: new premium buildings entering the portfolio raise it
even when no tenant pays more. The composition section decomposes that effect.

## Same-unit matching

- Units are matched on `prop_code + unit_code`, cross-checked against the source unit id. A site name plus unit code is
  unsafe because it merges distinct apartments; the notebook shows the collision with counts.
- Pairs are consecutive leases of one unit ordered by lease start. The gap between starts must lie strictly between the
  bounds in `config/measure.yaml` (0.5 and 2.5 years by default); both rents must be positive.
- Every rejected pair keeps an `exclusion_reason`, and exclusions are counted. A pair belongs to the calendar year of its
  later lease start. Sensitivity to the gap bounds (including 6-month leases) is reported.

## Incentives (concessions)

- Net rent is explained rather than assumed: each concession credit is linked to the lease it belongs to (same unit,
  signed on or before the credit starts, active at that time), scored by how well the reconstructed net rent reproduces
  the reported one. Links are `unique`, `resolved_by_fit` or `unresolved`, and the reconciliation rate is reported.
- Lump credits (a one-off promotional payment) are not monthly discounts and are never multiplied by months. Accessory
  credits are included in net rent.
- The incentive engine forecasts the discount share per segment (renewals and turnovers separately) from a short linear
  trend, clipped to a maximum share. Example: a 5% contract increase with one free month on a 12-month lease is about -3.75% net.

## Renewals vs turnovers and regulation

- Renewals and turnovers are analysed separately and read under the regime of their province; a rule of one province is
  never applied to the other.
- Quebec: the housing tribunal's annual percentage guides rent fixing when a tenant refuses an increase; it is a
  benchmark, not a cap on an accepted increase. A change of method announced in December 2025 is flagged when comparing
  2026 with earlier years. New buildings may be outside rent fixing for five years (Civil Code art. 1955): scenario note only.
- Ontario: the annual guideline caps renewal increases for non-exempt units; units first occupied as residential after
  November 15, 2018 are exempt (Residential Tenancies Act, s. 6.1). Turnovers are not capped. For a building first leased
  after that date, the central scenario is that the exemption is plausible and the alternative is that the guideline applies.
  This is a scenario, never a legal determination.
- Regulation reference lines come from the public sources table with release dates, never typed from memory.

## External data

- Public series (rent price indices, market rental surveys, regulatory percentages) are stored in `data/public/sources.csv`
  with publisher, URL, location in the source, reference period, release date and extraction mode.
- Regional vacancy and similar market statistics are context only; they are never a portfolio occupancy figure.

## Forecast

- Renewal engine: the segment's own recent contractual growth, blended with a portfolio-level monthly nowcast; a regulated
  model (E2) anchors renewals to the public percentage plus a learned gap.
- Turnover engine: segment history, an asking-rent signal (asking rents posted before the cutoff against the prior rent,
  minus an asking-to-signed spread learned on training years) and the nowcast.
- Incentive engine converts contractual growth into net growth. Engines are combined with fixed weights; thin building x
  bedroom cells are shrunk toward their building mean.
- Baselines: B0 last year's growth, B1 trailing mean, B2 market anchor plus learned gap, B3 regulatory anchor.
- The monthly nowcast is a local linear trend (state space) with damped slope, falling back to a trailing mean.

## Time and leakage policy

- The cutoff for forecasting year y is December 31 of y-1. Training uses leases whose signing and start dates are both on or
  before the cutoff; asking rents up to the cutoff; concessions starting on or before it.
- Public data counts if released on or before an external cutoff, January 31 of the target year by default (regulatory
  percentages are published in mid-January). The strict December 31 version is reported as a sensitivity.
- Every threshold, weight, quantile or model is fit on training data only. A test appends fake future rows and checks the
  forecast does not change.
- Backtest years are evaluated with the same code path as the real forecast. The champion is chosen on the selection years
  and the last year is held out. Three backtest years support weak conclusions.

## Uncertainty

- Scenarios (low / central / high) vary incentive intensity, renewal share, and the applicability of the Ontario
  new-build exemption. One-at-a-time sensitivities (gap bounds, winsorizing, weight window, model choice) are shown as a tornado chart.
- A unit-cluster bootstrap resamples whole unit histories with replacement, reruns the forecast per draw and reports a
  5-95% interval. It captures sampling uncertainty only; with few buildings it is a lower bound. Scenario ranges are
  scenarios, not prediction intervals.

## What a lease extract cannot tell us

Occupancy, vacancy, absorption and total rent roll cannot be measured from lease history and are never computed or quoted.
