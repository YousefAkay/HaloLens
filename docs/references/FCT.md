# References FCT

Append one bullet per entry, newest last. Every entry below was checked against its publisher's, library's or documentation
page on 2026-10-04. A DOI or URL is given where one was confirmed; the book by Efron and Tibshirani is cited in full with its
ISBN because no stable URL was confirmed. "Used in" names the code or notebook section that relies on the idea; none of these
sources contains or was applied to CRM data.

## Growth rates, fixed weights and index construction
- **Intersecretariat Working Group on Price Statistics (Eurostat, ILO, IMF, OECD, UNECE, World Bank)**, 2020, *Consumer Price
  Index Manual: Concepts and Methods*. International Monetary Fund, Washington, DC.
  https://www.imf.org/en/Data/Statistics/cpi-manual ; https://www.ilo.org/publications/consumer-price-index-manual-concepts-and-methods-2020
  Used in: the headline definition (`forecast/baselines.py` `headline_summary`, notebook sections 01 and 08): price change
  measured as a weighted aggregate of segment-level changes with weights fixed in advance. Annualized log growth is our own
  choice (exactly additive across segments and across the contractual-to-net bridge); the manual is the background for the
  fixed-weight aggregation, not a source for that choice.
- **Eurostat**, undated web page (accessed 2026-10-04), *Harmonised Index of Consumer Prices (HICP): methodology*.
  https://ec.europa.eu/eurostat/web/hicp/methodology ; https://ec.europa.eu/eurostat/statistics-explained/index.php/HICP_methodology
  Used in: freezing the segment weights at the cutoff (`frozen_weights`): the HICP is an annually chain-linked Laspeyres-type
  index whose weights are fixed for the period they are applied to, which is the same discipline as our weights frozen at the
  cutoff.

## State-space and time-series methods
- **Durbin, J. and Koopman, S. J.**, 2012, *Time Series Analysis by State Space Methods*, 2nd edition. Oxford University Press,
  Oxford. https://academic.oup.com/book/16563 (ISBN 978-0-19-964117-8).
  Used in: `forecast/nowcast.py`: the local level / local linear trend model, filtered level and slope at the cutoff, handling of
  missing months (notebook section 08).
- **statsmodels developers**, documentation of *UnobservedComponents* (`statsmodels.tsa.statespace.structural`), stable
  version (accessed 2026-10-04).
  https://www.statsmodels.org/stable/generated/statsmodels.tsa.statespace.structural.UnobservedComponents.html
  (the page itself cites Durbin and Koopman 2012). Used in: the implementation of the local linear trend, called as
  `UnobservedComponents(level="local linear trend")`; we project the last filtered state ourselves with a damped slope.

## Forecast evaluation and baselines
- **Hyndman, R. J. and Athanasopoulos, G.**, 2021, *Forecasting: Principles and Practice*, 3rd edition. OTexts, Melbourne.
  https://otexts.com/fpp3/
  Used in: the evaluation design (`evaluate/backtest.py`, `evaluate/metrics.py`, notebook section 09): simple benchmark
  forecasts (last value, average of past values) that a more elaborate model must beat, forecast errors measured out of
  sample at a fixed origin, and mean absolute error as the comparison metric. The decision to choose a model on the selection
  years only and keep the last year as a holdout follows the same out-of-sample logic.

## Resampling
- **Efron, B. and Tibshirani, R. J.**, 1993, *An Introduction to the Bootstrap*. Chapman & Hall/CRC, New York (Monographs on
  Statistics and Applied Probability, 57), ISBN 978-0-412-04231-7.
  Used in: `evaluate/uncertainty.py`: resampling with replacement and the percentile interval of the bootstrap distribution
  (notebook section 11a).
- **Cameron, A. C., Gelbach, J. B. and Miller, D. L.**, 2008, "Bootstrap-Based Improvements for Inference with Clustered
  Errors", *The Review of Economics and Statistics* 90(3): 414-427. https://doi.org/10.1162/rest.90.3.414 ;
  https://www.nber.org/papers/t0344
  Used in: resampling whole clusters (here, a unit's complete lease history) rather than single observations, because
  observations within a cluster are dependent; and the caveat, declared in the notebook, that with few clusters (the units sit
  in six buildings) cluster-level inference is less reliable, so our interval is read as a lower bound on sampling uncertainty.

## Shrinkage and robust summaries
- **James, W. and Stein, C.**, 1961, "Estimation with Quadratic Loss", in *Proceedings of the Fourth Berkeley Symposium on
  Mathematical Statistics and Probability*, Vol. 1, pp. 361-379. University of California Press, Berkeley.
  https://projecteuclid.org/download/pdf_1/euclid.bsmsp/1200512173
  Used in: the idea behind `building_beds_forecast`: estimates for small groups are improved by pulling them toward a group
  mean. We use a simple fixed-strength rule (a number of pseudo-pairs, `combine.shrinkage_strength`), not the James-Stein
  estimator itself.
- **Efron, B. and Morris, C.**, 1975, "Data Analysis Using Stein's Estimator and Its Generalizations", *Journal of the American
  Statistical Association* 70(350): 311-319. https://doi.org/10.1080/01621459.1975.10479864
  Used in: the empirical-Bayes reading of the same rule: a thin building x bedroom cell is shrunk toward the mean of its building,
  and the weight on the cell grows with the number of pairs behind it.
- **Hastings, C. Jr., Mosteller, F., Tukey, J. W. and Winsor, C. P.**, 1947, "Low Moments for Small Samples: A Comparative Study of
  Order Statistics", *The Annals of Mathematical Statistics* 18(3): 413-426. https://doi.org/10.1214/aoms/1177730388
  (open access: https://projecteuclid.org/euclid.aoms/1177730388) and **Tukey, J. W.**, 1962, "The Future of Data Analysis",
  *The Annals of Mathematical Statistics* 33(1): 1-67, https://projecteuclid.org/euclid.aoms/1177704711.
  Used in: winsorization (`forecast/baselines.py` `winsor_bounds`): the technique is named after Charles P. Winsor and consists
  of limiting extreme values (here, annualized log growth clipped at training-pair quantiles from `config/measure.yaml`) to reduce
  the influence of outliers. The two papers are the references usually given for the name and the practice (the
  Wikipedia entry "Winsorizing" lists both as its primary references); the quantile thresholds are our own choice and are learned
  on training pairs only.
