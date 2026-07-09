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

_(Populated as each section's scrapers run against live endpoints and confirm the actual URL.)_
