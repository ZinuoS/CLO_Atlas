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

_(Populated as each section's scrapers run against live endpoints and confirm the actual URL.)_
