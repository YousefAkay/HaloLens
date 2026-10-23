# Q&A knowledge: how the estimate works

Plain-language notes used by the dashboard's question-and-answer feature. They contain no data values.

- The headline is the growth of rent net of all incentives for the same unit between consecutive leases, annualized and averaged in log terms over segments (property, bedrooms, renewal or turnover) with weights frozen at the forecast date.
- The contractual-rent version is reported next to it. The gap between the two is the effect of incentives such as free months.
- Comparing each unit with itself avoids composition effects: a new, pricier building joining the portfolio does not look like a price increase.
- Units are matched on property code plus unit code. A site name plus unit code merges distinct apartments and is not used.
- Renewals and turnovers are separated because regulated and market increases differ. Quebec and Ontario rules are never mixed.
- In Quebec the housing tribunal's percentage guides rent fixing when an increase is refused; it is a benchmark, not a cap. A method change announced in December 2025 is flagged.
- In Ontario the guideline caps renewals for non-exempt units; units first occupied as residential after November 15, 2018 are exempt. For a building in that situation, the exemption is a scenario, not a legal conclusion.
- The forecast uses information available at the cutoff only (December 31 of the previous year for lease data, public data released by January 31). A test checks that adding future rows changes nothing.
- Models are compared by backtest on past years with the same code as the real forecast. The champion was chosen on the earlier years and the last year held out. With three backtest years, rankings are statistically weak.
- Uncertainty is shown three ways: scenarios (incentive intensity, renewal share, Ontario exemption), one-at-a-time sensitivities, and a unit-cluster bootstrap. Scenario ranges are not prediction intervals.
- The data cannot measure occupancy, vacancy, absorption or total rent roll, so none is quoted. Regional vacancy from public surveys is market context only.
- Net rent is concession-adjusted rent, not cash collected.
