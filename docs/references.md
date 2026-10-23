# References

## Public data (series and URLs in `data/public/sources.csv`)

Every numeric observation has its own URL, location in the source, reference period, release date, accessed date,
extraction mode and verifier.

- **Statistics Canada**, Table 18-10-0004-01, *Consumer Price Index, monthly, not seasonally adjusted*, Rent, Quebec and Ontario.
  https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1810000401
- **Canada Mortgage and Housing Corporation (CMHC)**, *Rental Market Report* data tables (2021 to 2025 editions), Montreal and
  Ottawa: same-sample average rent change (with and without tenant turnover) and the purpose-built vacancy rate (regional context only).
  https://www.cmhc-schl.gc.ca/professionals/housing-markets-data-and-research/market-reports/rental-market-reports-major-centres
- **Tribunal administratif du logement (Quebec)**, annual rent-adjustment percentage, one news page per year.
  https://www.tal.gouv.qc.ca/fr/reconduction-du-bail-et-fixation-de-loyer/pourcentages-applicables-aux-criteres-de-fixation-de-loyer
- **Government of Ontario**, *Rent increase guideline* (also states the exemption for units first occupied as residential after November 15, 2018).
  https://www.ontario.ca/page/rent-increase-guideline ; legal text: Residential Tenancies Act, 2006, s. 6.1.
- **Civil Code of Quebec**, art. 1955 (no rent fixing for five years after a building is ready for habitation).

## Methods

- Intersecretariat Working Group on Price Statistics, 2020, *Consumer Price Index Manual: Concepts and Methods*, IMF. https://www.imf.org/en/Data/Statistics/cpi-manual (fixed-weight aggregation).
- Eurostat, *HICP methodology*. https://ec.europa.eu/eurostat/web/hicp/methodology (weights fixed for the period they apply to).
- Durbin, J. and Koopman, S. J., 2012, *Time Series Analysis by State Space Methods*, 2nd ed., Oxford University Press (nowcast).
- statsmodels, *UnobservedComponents*. https://www.statsmodels.org/stable/generated/statsmodels.tsa.statespace.structural.UnobservedComponents.html
- Hyndman, R. J. and Athanasopoulos, G., 2021, *Forecasting: Principles and Practice*, 3rd ed. https://otexts.com/fpp3/ (benchmarks, out-of-sample evaluation).
- Efron, B. and Tibshirani, R. J., 1993, *An Introduction to the Bootstrap*, Chapman & Hall/CRC (percentile interval).
- Cameron, A. C., Gelbach, J. B. and Miller, D. L., 2008, "Bootstrap-Based Improvements for Inference with Clustered Errors", *Review of Economics and Statistics* 90(3). https://doi.org/10.1162/rest.90.3.414 (cluster resampling; few clusters make inference less reliable).
- James, W. and Stein, C., 1961, "Estimation with Quadratic Loss", *Proc. Fourth Berkeley Symposium*, vol. 1; Efron, B. and Morris, C., 1975, *JASA* 70(350). https://doi.org/10.1080/01621459.1975.10479864 (idea behind shrinkage; we use a simple fixed-strength rule).
- Hastings, Mosteller, Tukey and Winsor, 1947, *Annals of Mathematical Statistics* 18(3). https://doi.org/10.1214/aoms/1177730388 (winsorizing; quantiles are our own choice).

## Software

jupytext, nbclient, Streamlit, jsonschema, pandas, numpy, scipy, scikit-learn, statsmodels and matplotlib (see `requirements.txt`).

## AI tools and provenance

- **Claude (chat)**: planning and review of the method and tasks.
- **Claude Code**: implementation, tests and pre-merge review; every change was reviewed by a human.
- **Claude API**: (1) extraction of values from public web pages into a draft source table; each value was then checked against its official page by Claude, and a human spot-checked a named sample of about ten values (CMHC same-sample growth, Quebec and Ontario regulatory percentages, rent CPI). **Not every value was checked by hand.** (2) A source watcher that re-reads the official public pages and writes unverified candidates that never enter the forecast before human verification. (3) The dashboard's scenario copilot and Q&A over aggregate results, with a number guard.
- No row-level lease data was ever sent to an API.
