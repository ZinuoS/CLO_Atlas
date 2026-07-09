# Sources actually used

Every row here is discovered and recorded at runtime by the scraper that uses
it — this file is append-only ground truth, not aspirational. Format:

`Section | Domain/Endpoint | What it provides | First used by | Notes`

| Section | Domain / Endpoint | Provides | Scraper | Notes |
|---|---|---|---|---|
| common | `data.sec.gov`, `www.sec.gov`, `efts.sec.gov` | EDGAR filings, full-text search | `src/edgar/*`, `src/cef/scrape_filings.py` | Rate-limited to 5 req/s in `config.RATE_LIMITS`, well under SEC's 10 req/s fair-access ceiling |
| common | `web.archive.org/cdx/search/cdx` | Historical snapshots for backfill | `src/common/wayback.py` | Digest-deduped |
| common | `fred.stlouisfed.org` | SOFR, HY OAS, T-bill, EFFR | `src/official/scrape_fred.py` | No API key needed for `fredgraph.csv` |

_(Populated as each section's scrapers run against live endpoints and confirm the actual URL.)_
