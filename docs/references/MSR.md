# References MSR

Append one bullet per entry, newest last. Every numeric observation also sits in `data/public/sources.csv` with its own
URL, location in the source, reference period, release date, accessed date, extraction mode and verifier. Accessed date
for every entry below: 2026-10-03.

## Public data (numeric series in `data/public/sources.csv`)
- **Statistics Canada**, Table 18-10-0004-01, *Consumer Price Index, monthly, not seasonally adjusted*, Rent, Québec and
  Ontario. https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1810000401 (pulled through the StatCan Web Data
  Service, product 18100004). Reference periods: monthly index 2018-01 to 2026-08; annual-average % change 2018 to 2025.
  Release dates: each annual average = release date of that year's December CPI (2019-01-18 for 2018 ... 2026-01-19 for
  2025, from The Daily); monthly index rows = WDS `releaseTime`. Extraction: manual (official download). Used in
  section 07 (reconciliation) and as FCT's B2 market anchor.
- **Canada Mortgage and Housing Corporation (CMHC / SCHL)**, *Rental Market Report* data tables, Montréal CMA and Ottawa
  CMA: same-sample (fixed-sample) average rent change, total and 2-bedroom (with and without tenant turnover), and the
  purpose-built vacancy rate (regional market context only, never a project figure). October survey of each year.
  - 2021 edition (reference Oct 2020 and Oct 2021), released 2022-02-18:
    https://assets.cmhc-schl.gc.ca/sites/cmhc/professional/housing-markets-data-and-research/housing-data-tables/rental-market/rental-market-report-data-tables/2021/rmr-montreal-2021-en.xlsx ;
    https://assets.cmhc-schl.gc.ca/sites/cmhc/professional/housing-markets-data-and-research/housing-data-tables/rental-market/rental-market-report-data-tables/2021/rmr-ottawa-2021-en.xlsx
  - 2022 edition (reference Oct 2022), released 2023-01-26: `.../2022/rmr-montreal-2022-en.xlsx`,
    `.../2022/rmr-ottawa-2022-en.xlsx`, `.../2022/rmr-canada-2022-en.xlsx` (turnover split)
  - 2023 edition (reference Oct 2023), released 2024-01-31: `.../2023/rmr-montreal-2023-en.xlsx`,
    `.../2023/rmr-ottawa-2023-en.xlsx`, `.../2023/rmr-canada-2023-en.xlsx`
  - 2024 edition (reference Oct 2024), released 2024-12-17: `.../2024/rmr-montreal-2024-en.xlsx`,
    `.../2024/rmr-ottawa-2024-en.xlsx`, `.../2024/rmr-canada-2024-en.xlsx`
  - 2025 edition (reference Oct 2025), released 2025-12-11: `.../2025/rmr-montreal-2025-en.xlsx`,
    `.../2025/rmr-ottawa-2025-en.xlsx`, and the report page
    https://www.cmhc-schl.gc.ca/professionals/housing-markets-data-and-research/market-reports/rental-market-reports-major-centres
  - (`...` = https://assets.cmhc-schl.gc.ca/sites/cmhc/professional/housing-markets-data-and-research/housing-data-tables/rental-market/rental-market-report-data-tables)
  - Extraction: workbook values entered manually; 2025 report-page values read by the Claude API, then checked by hand.
    Used in section 07 (reconciliation, provenance table).
- **Tribunal administratif du logement (TAL)**, annual rent-adjustment percentage for an unheated dwelling without
  major work (estimated average increase up to 2025; "pourcentage de base" from 2026, new method announced
  2025-12-17). One news page per lease year, reference period = calendar year:
  - 2019, released 2019-01-18: https://www.tal.gouv.qc.ca/fr/actualites/detail?code=le-calcul-de-l-augmentation-des-loyers-en-2019
  - 2020, released 2020-01-22: https://www.tal.gouv.qc.ca/fr/actualites/detail?code=le-calcul-de-l-augmentation-des-loyers-en-2020
  - 2021, released 2021-01-20: https://www.tal.gouv.qc.ca/fr/actualites/detail?code=le-calcul-de-l-augmentation-des-loyers-en-2021
  - 2022, released 2022-01-19: https://www.tal.gouv.qc.ca/fr/actualites/detail?code=le-calcul-de-l-augmentation-des-loyers-en-2022
  - 2023, released 2023-01-17: https://www.tal.gouv.qc.ca/fr/actualites/detail?code=le-calcul-de-l-ajustement-des-loyers-en-2023
  - 2024, released 2024-01-16: https://www.tal.gouv.qc.ca/fr/actualites/detail?code=le-calcul-de-l-ajustement-des-loyers-en-2024
  - 2025, released 2025-01-21: https://www.tal.gouv.qc.ca/fr/actualites/detail?code=le-calcul-de-l-ajustement-des-loyers-en-2025
  - 2026, released 2026-01-19: https://www.tal.gouv.qc.ca/fr/actualites/detail?code=le-calcul-de-l-ajustement-des-loyers-en-2026
  - Summary page: https://www.tal.gouv.qc.ca/fr/reconduction-du-bail-et-fixation-de-loyer/pourcentages-applicables-aux-criteres-de-fixation-de-loyer
  - Extraction: Claude API on the public pages plus manual entry, each value checked by hand against its page. Used in
    section 06 (reference line for QC renewals) and by FCT (E2 regulated model, B3 baseline).
- **Government of Ontario**, *Rent increase guideline*, https://www.ontario.ca/page/rent-increase-guideline. Reference
  periods: calendar years 2019 to 2026. Release dates: Aug 31 of the year before (RTA s.120(3) publication deadline),
  except 2021 (0 %, Bill 204 Royal Assent 2020-10-01). Extraction: Claude API, checked by hand. Used in section 06
  (reference line for ON renewals; the Ontario new-build evidence) and by FCT (Met alternative scenario).

## Legal and factual sources (no numeric series)
- Government of Ontario, "Rent increase guideline" (states that new buildings first occupied for residential purposes after November 15, 2018 are exempt from rent control; legal text: Residential Tenancies Act, 2006, s. 6.1). https://www.ontario.ca/page/rent-increase-guideline — legal text: https://www.ontario.ca/laws/statute/06r17 (accessed 2026-10-03). Used in section 06 (the Ontario new-build evidence).
- Kucharsky, D. (2023-06-19). "project doubles down on Ottawa with 2nd downtown multires tower". source – Real Estate News Exchange (**trade press / presse spécialisée**). https://source.ca/project-doubles-down-on-ottawa-with-2nd-downtown-multires-tower (accessed 2026-10-03). Public fact: the Ontario new-build (180 Street St., 303 units) was completed and "began occupancy last month" (May 2023). Used in section 06 as evidence for the post-2018 exemption scenario; recorded in `config/measure.yaml` `regulation.exemption_evidence`. An official dated source was searched for on 2026-10-03 (City of Ottawa development files, the owner's site https://metluxuryrentals.com/building/); none states an occupancy date, so source stays the only source and is labelled as trade press.
- Civil Code of Québec, art. 1955 (lease clause F: no rent fixing by the TAL for 5 years after a building is ready for habitation) and the mandatory Québec lease form, section G (lowest rent paid in the previous 12 months). Used in section 06 rule texts (scenario design only).

## Earlier entries (kept for history)
- Canada Mortgage and Housing Corporation (CMHC / SCHL), Rental Market Report data tables, Montréal and Ottawa CMAs, 2021–2025 editions (same-sample average rent change, total and 2-bedroom with / without tenant turnover; vacancy rate as regional context only). URLs and release dates per observation in `data/public/sources.csv`. Used in section 07 (internal vs market reconciliation).
- Statistics Canada, Table 18-10-0004-01, Consumer Price Index, monthly, not seasonally adjusted (Rent, Québec and Ontario), https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1810000401. Annual-average rent CPI change used in section 07 (reconciliation) and as FCT's B2 market anchor; release dates per observation in `data/public/sources.csv`.

## AI tools used by MSR
- **Claude Code** (Anthropic, model Claude Opus 5.5, `claude-opus-5-5`), in the local repository: wrote and tested the MSR
  code (`measure/*`, `market/*`, `scripts/extract_sources.py`), notebook sections 03, 04, 06 and 07, and these docs;
  ran real-data checks that print counts and aggregates only. Every change was reviewed by a human before merge. CRM
  rows were never sent to Claude outside the sponsor-approved local session (approval on record 2026-10-03).
- **Claude API** (Anthropic, `claude-opus-5-5`, via `scripts/extract_sources.py`): read **public pages only** (TAL,
  Government of Ontario, CMHC report page) and returned structured observations into `data/public/sources_draft.csv`.
  Page text and answers are cached in `data/public/extraction_cache/`. A human checked every value against its
  official page (`verified_by`) before it was copied to `sources.csv`. Analysis code never reads the draft file.
- **Claude** (chat, HALO project): planned tasks, wrote task prompts and reviewed Handback Reports. It never received
  CRM rows.
- **Web search** (Claude Code web tools, 2026-10-03): looked for an official first-occupancy source for the Ontario new-build; result
  above.
