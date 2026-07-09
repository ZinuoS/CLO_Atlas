# Sources actually used

Every row here is discovered and recorded at runtime by the scraper that uses
it — this file is append-only ground truth, not aspirational. Format:

`Section | Domain/Endpoint | What it provides | First used by | Notes`

| Section | Domain / Endpoint | Provides | Scraper | Notes |
|---|---|---|---|---|
| common | `data.sec.gov`, `www.sec.gov`, `efts.sec.gov` | EDGAR filings, full-text search | `src/edgar/*`, `src/cef/scrape_filings.py` | Rate-limited to 5 req/s in `config.RATE_LIMITS`, well under SEC's 10 req/s fair-access ceiling |
| common | `web.archive.org/cdx/search/cdx` | Historical snapshots for backfill | `src/common/wayback.py` | Digest-deduped |
| common | `fred.stlouisfed.org` | SOFR, HY OAS, T-bill, EFFR | `src/official/scrape_fred.py` | No API key needed for `fredgraph.csv` |
| 1 (ETF) | `janushenderson.com/.../full-holdings/` | JAAA, JBBB tranche-level holdings (CUSIP, par, MV, weight) | `src/etf/scrape_holdings.py` | Server-rendered HTML table, no JS/captcha needed for the data itself (the "download as file" button is captcha-gated, but the page we scrape isn't). robots.txt allows. Verified 2026-07-08. |
| 1 (ETF) | Yahoo Finance (via `yfinance`) | Full daily OHLCV price history per ticker; single point-in-time NAV/shares snapshot | `src/etf/scrape_nav_flows.py` | yfinance manages its own HTTP; raw CSV still archived to `data/raw/yfinance/` before parsing. No historical NAV/shares time series available for free — see module docstring. |
| 1 (ETF) | `fred.stlouisfed.org/graph/fredgraph.csv` | SOFR, 3m T-bill (DTB3), HY OAS (BAMLH0A0HYM2), EFFR | `src/etf/scrape_nav_flows.py` | No key required |
| 4 (official) | `cdn.finra.org/trace/FINRA_IDS_PXTABLES.xlsx` | TRACE-sourced CLO/CBO/CDO pricing, volume, trade counts, customer/dealer split by rating band and vintage | `src/official/scrape_trace.py` | Direct unauthenticated binary download, no login. Same-day snapshot republished daily at a fixed URL — history accretes from repeated runs. Verified 2026-07-09. |
| 4 (official) | Fed FEDS Note (federalreserve.gov, hand-cited, not live-scraped) | Domestic CLO holdings by investor type, as of Dec 2018 | `src/official/scrape_efa.py` | TO-VERIFY: single dated snapshot from published prose/table-images, no linked machine-readable file. See config.FED_CLO_HOLDER_CITATION. |
| 4 (official) | `fred.stlouisfed.org/graph/fredgraph.csv` | SOFR, 3m T-bill, HY OAS, BBB OAS, EFFR | `src/official/scrape_fred.py` | No key required |
| 2 (CEF) | Yahoo Finance (via `yfinance`) | Price history, `bookValue` (NAV proxy), full dividend history | `src/cef/scrape_prices_nav.py` | `navPrice` unavailable (these tickers are classified EQUITY, not FUND); `bookValue`/`priceToBook` used instead, clearly labeled as a proxy. Dividend history is complete and real, no caveat needed. |
| 2 (CEF) | `data.sec.gov/submissions/CIK*.json` + `www.sec.gov/Archives/edgar/data/.../primary_doc.xml` | Quarterly CLO-equity portfolio positions (NPORT-P) | `src/cef/scrape_filings.py`, `src/edgar/scrape_nport.py` (shared logic in `src/common/nport.py`) | Raw XML sits at the bare `primary_doc.xml` filename, NOT the `xslFormNPORT-P_X01/primary_doc.xml` path the submissions API's `primaryDocument` field gives (that path is SEC's rendered-HTML viewer). Verified 2026-07-09. |
| 3 (EDGAR) | `www.sec.gov/files/investment/data/other/.../ia*.zip` (+ 2 older path variants) | SEC Form ADV bulk firm roster, incl. RAUM (Item 5.F) | `src/edgar/scrape_adv.py` | 3 dated snapshots (2012/2018/2026) for a real historical trend; the SEC has restructured this page's paths multiple times so each snapshot's path is stored as-scraped. Older snapshots ship `.xlsx`, recent ones `.csv`. Verified 2026-07-09. |
| 3 (EDGAR) | `www.sec.gov/Archives/edgar/data/.../R*.htm` (via `FilingSummary.xml`) | BDC Schedules of Investment (loan-level: company, instrument, fair value, coupon, spread) | `src/edgar/scrape_bdc_soi.py` | The giant combined 10-K/10-Q HTML doesn't yield the SOI via `pandas.read_html` at all — the per-statement XBRL-rendered report fragment (`R5.htm` etc.) does, in a long "Investment, Identifier [Axis]" format reshaped by this parser. 5/8 tracked BDCs succeeded this run (12,708 real position-period rows); failures logged per-filing, not fatal. Verified 2026-07-09 against ARCC. Identifier format varies by filer — ARCC uses comma-separated free text, GBDC/OBDC/MAIN use `Company | Instrument | Affiliation` pipe-delimiting; both are parsed. |

| 6 (sentiment) | `federalreserve.gov/publications/files/financial-stability-report-*.pdf` | Fed Financial Stability Reports, free PDFs | `src/sentiment/scrape_regulators.py` | 11 reports discovered from the listing page, 2020-2026. |
| 6 (sentiment) | `bis.org/publ/qtrpdf/r_qt<YYMM>.pdf` | BIS Quarterly Review, free PDFs | `src/sentiment/scrape_regulators.py` | Predictable URL pattern for quarter-end months, generated programmatically and verified by HTTP status (not every YYMM exists). 24 reports, 2020-2026. |
| 6 (sentiment) | `ecb.europa.eu/press/financial-stability-publications/fsr/pdf/<slug>.pdf` | ECB Financial Stability Review, free PDFs | `src/sentiment/scrape_regulators.py` | Slugs (with random hash suffix) extracted directly from the index page's server-rendered links, not guessed — see `config.ECB_FSR_REPORTS`. Covers the 5 most recent issues (May 2024-May 2026); older archive not resolved (see docs/excluded_sources.md). |

_(Populated as each section's scrapers run against live endpoints and confirm the actual URL.)_
