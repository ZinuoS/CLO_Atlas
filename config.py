"""Single source of truth for clo-atlas: paths, tickers, rate limits, dates, seeds.

Nothing in src/ should hardcode a path, ticker list, URL anchor, or rate limit.
Import from here instead.
"""
from __future__ import annotations

import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Identity / contact (used in the User-Agent string sent to every scraped host,
# and specifically required by SEC EDGAR's fair-access policy)
# ---------------------------------------------------------------------------
CONTACT_NAME = os.environ.get("CLO_ATLAS_NAME", "CLO Atlas Research")
CONTACT_EMAIL = os.environ.get("CLO_ATLAS_EMAIL", "zinuoashley@gmail.com")
USER_AGENT = f"{CONTACT_NAME} research bot ({CONTACT_EMAIL})"

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
INTERIM_DIR = DATA_DIR / "interim"
FINAL_DIR = DATA_DIR / "final"
FIGURES_DIR = ROOT / "figures"
FIGURES_INTERACTIVE_DIR = FIGURES_DIR / "interactive"
FIGURES_FINAL_DIR = FIGURES_DIR / "final"
DOCS_DIR = ROOT / "docs"
CACHE_MANIFEST = RAW_DIR / "_manifest.csv"
LLM_CACHE_DIR = DATA_DIR / "_llm_cache"

for d in (RAW_DIR, INTERIM_DIR, FINAL_DIR, FIGURES_DIR, FIGURES_INTERACTIVE_DIR,
          FIGURES_FINAL_DIR, DOCS_DIR, LLM_CACHE_DIR):
    d.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Reproducibility
# ---------------------------------------------------------------------------
RANDOM_SEED = 20260708

# ---------------------------------------------------------------------------
# Rate limits: (requests_per_second, burst) keyed by domain. Unlisted domains
# fall back to DEFAULT_RATE_LIMIT. SEC EDGAR is capped at 10 req/s per their
# fair-access policy; we run well under that.
# ---------------------------------------------------------------------------
DEFAULT_RATE_LIMIT = (2.0, 4)
RATE_LIMITS: dict[str, tuple[float, int]] = {
    "www.sec.gov": (5.0, 8),
    "data.sec.gov": (5.0, 8),
    "efts.sec.gov": (5.0, 8),
    "web.archive.org": (1.0, 2),
    "fred.stlouisfed.org": (2.0, 4),
    "query1.finance.yahoo.com": (2.0, 4),
    "query2.finance.yahoo.com": (2.0, 4),
}
MAX_RETRIES = 5
BACKOFF_BASE_SECONDS = 1.5

# ---------------------------------------------------------------------------
# Date range for historical backfills (Wayback, filings, etc.)
# ---------------------------------------------------------------------------
HISTORY_START = "2016-01-01"  # first CLO ETF launches ~2020, but macro/official series go back further
TODAY = os.environ.get("CLO_ATLAS_TODAY")  # override for deterministic test runs; else "now" at call sites

# ---------------------------------------------------------------------------
# Section 1 — CLO ETFs
# ---------------------------------------------------------------------------
# Each entry's `holdings_url` / `holdings_parser` are populated only once
# verified against the live issuer site (see docs/sources.md). Where a fund's
# holdings page could not be resolved to a scrapable, non-JS-gated endpoint at
# scaffold time, holdings_parser is None and scrape_holdings.py logs the gap
# to docs/excluded_sources.md instead of guessing — NAV/price/flows for that
# ticker still come through scrape_nav_flows.py via yfinance regardless.
CLO_ETF_TICKERS = {
    "JAAA": {
        "issuer": "Janus Henderson", "tranche_focus": "AAA",
        "holdings_url": "https://www.janushenderson.com/en-us/advisor/product/jaaa-aaa-clo-etf/full-holdings/",
        "holdings_parser": "janus_henderson_table",
    },
    "JBBB": {
        "issuer": "Janus Henderson", "tranche_focus": "B-BBB",
        "holdings_url": "https://www.janushenderson.com/en-us/advisor/product/jbbb-b-bbb-clo-etf/full-holdings/",
        "holdings_parser": "janus_henderson_table",
    },
    "CLOZ": {
        "issuer": "Eldridge (fka Panagram)", "tranche_focus": "BBB-B",
        "holdings_url": None,  # clozfund.com publishes only quarterly PDFs, no daily CSV/HTML table found
        "holdings_parser": None,
    },
    "CLOB": {
        "issuer": "VanEck", "tranche_focus": "AA-BB",
        "holdings_url": "https://www.vaneck.com/us/en/investments/aa-bb-clo-etf-clob/",
        "holdings_parser": None,  # vaneck.com gated a cookie-consent redirect loop under plain HTTP; unresolved
    },
    "CLOI": {
        "issuer": "VanEck", "tranche_focus": "IG",
        "holdings_url": "https://www.vaneck.com/us/en/investments/clo-etf-cloi/",
        "holdings_parser": None,  # same vaneck.com gating as CLOB
    },
    "CLOA": {
        "issuer": "BlackRock/iShares", "tranche_focus": "AAA",
        "holdings_url": "https://www.ishares.com/us/products/330488/ishares-aaa-clo-active-etf",
        "holdings_parser": None,  # product page has no server-rendered full-holdings table; ajax CSV endpoint returns an HTML shell, not data
    },
    "CLOD": {
        "issuer": "BlackRock/iShares", "tranche_focus": "BBB",
        "holdings_url": None,  # product id not yet resolved
        "holdings_parser": None,
    },
    "ICLO": {
        "issuer": "Invesco", "tranche_focus": "AAA",
        "holdings_url": None,  # invesco.com returns HTTP 406 to a plain scripted client
        "holdings_parser": None,
    },
}

# Comparison universe for Section 1 total-return analysis
ETF_COMPARISON_TICKERS = ["AGG", "HYG", "BKLN", "LQD", "SHV"]

FRED_SERIES = {
    "SOFR": "SOFR",
    "3M_TBILL": "DTB3",
    "HY_OAS": "BAMLH0A0HYM2",
    "EFFR": "DFF",
}

# ---------------------------------------------------------------------------
# Section 4 — Official-sector data
# ---------------------------------------------------------------------------
# Extends FRED_SERIES with the additional macro comparison series Section 4
# uses (BBB OAS alongside the HY OAS already pulled in Section 1).
OFFICIAL_FRED_SERIES = {**FRED_SERIES, "BBB_OAS": "BAMLC0A4CBBB"}

# FINRA/ICE Data Services structured-product pricing tables. Confirmed
# working 2026-07-09: no login, a direct binary download, robots.txt on
# www.finra.org doesn't block it. The file is a same-day snapshot re-published
# daily at this fixed URL (not a historical archive), so — like the ETF NAV
# snapshots in Section 1 — a real time series accretes only from whenever
# this project starts scraping it regularly; Wayback backfill is a documented
# future option since the URL is stable.
FINRA_PXTABLES_URL = "https://cdn.finra.org/trace/FINRA_IDS_PXTABLES.xlsx"
FINRA_PXTABLES_CLO_SHEET = "CBO-CDO-CLO"

# The Fed's Enhanced Financial Accounts project has no dedicated CLO page
# (checked directly), and the Financial Accounts (Z.1) "Issuers of ABS"
# sector series aggregate all ABS issuers, not CLOs specifically. The one
# genuinely CLO-specific breakdown the Fed has published is a narrative FEDS
# Note with data only in table images/text, no linked machine-readable file.
# Rather than fabricate a "scraped" series from that, these are the article's
# own published numbers, hand-transcribed with full citation, and every
# downstream use tags them TO-VERIFY (an external figure quoted from a
# source, not computed in this repo) per the project's honesty doctrine.
FED_CLO_HOLDER_CITATION = {
    "source_title": "Who Owns U.S. CLO Securities? An Update by Tranche",
    "source_url": "https://www.federalreserve.gov/econres/notes/feds-notes/who-owns-us-clo-securities-an-update-by-tranche-20200625.html",
    "as_of": "2018-12-31",
    "accessed": "2026-07-09",
    "note": "Domestic holdings of Cayman-issued U.S. CLO securities, by investor type. "
            "This is the most recent Fed-published sector breakdown found with no paywall; "
            "it is not a live series and cannot be back-filled or updated by scraping.",
    "holdings_by_investor_type_usd_millions": {
        "Insurance company": 111_610,
        "Mutual fund": 61_537,
        "Depository institution": 61_204,
        "Other financial organizations": 35_353,
        "Nonfinancial organizations": 27_338,
        "Pension fund": 22_359,
        "Fund or other investment vehicle": 20_182,
    },
}

# ---------------------------------------------------------------------------
# Section 2 — Listed CLO closed-end funds
# ---------------------------------------------------------------------------
CLO_CEF_TICKERS = ["ECC", "OXLC", "XFLT", "OCCI", "CCIF", "SPMC"]
# Resolved once from SEC's ticker->CIK map (www.sec.gov/files/company_tickers.json)
# and hardcoded since CIKs don't change; scrape_filings.py re-verifies at runtime.
CLO_CEF_CIKS = {
    "ECC": "1604174",
    "OXLC": "1495222",
    "XFLT": "1703079",
    "OCCI": "1716951",
    "CCIF": "1517767",
    "SPMC": "1930147",
}

# ---------------------------------------------------------------------------
# Section 3 — BDC / fund filings (EDGAR)
# ---------------------------------------------------------------------------
BDC_TICKERS = ["ARCC", "FSK", "OBDC", "BXSL", "OCSL", "GBDC", "PSEC", "MAIN"]
# Resolved from SEC's ticker->CIK map (www.sec.gov/files/company_tickers.json).
BDC_CIKS = {
    "ARCC": "1287750", "FSK": "1422183", "OBDC": "1655888", "BXSL": "1736035",
    "OCSL": "1414932", "GBDC": "1476765", "PSEC": "1287032", "MAIN": "1396440",
}

# ---------------------------------------------------------------------------
# Section 3 — BDC & fund filings (EDGAR)
# ---------------------------------------------------------------------------
# SEC Form ADV bulk firm-roster snapshots (FOIA data distribution). The SEC
# has restructured this page's file paths multiple times over the years, so
# each snapshot's full relative path is stored as-scraped rather than
# assuming one shared base URL. These three give a real decade-spanning
# manager-count/RAUM trend without pulling every historical snapshot (each
# is ~40MB). Verified 2026-07-09.
# Large closed-end bank-loan/floating-rate funds likely to hold CLO tranches
# alongside broadly syndicated loans, resolved from SEC's ticker->CIK map.
BANK_LOAN_FUND_CIKS = {
    "EFT": "1288992",   # Eaton Vance Floating-Rate Income Trust
    "BGH": "1521404",   # Barings Global Short Duration High Yield Fund
    "JFR": "1276533",   # Nuveen Floating Rate Income Fund
    "JQC": "1227476",   # Nuveen Credit Strategies Income Fund
}

ADV_BULK_SNAPSHOTS = {
    "2012-01-01": "/files/data/frequently-requested-foia-document-information-about-registered-investment-advisers-and-exempt/ia010112.zip",
    "2018-01-01": "/files/data/information-about-registered-investment-advisers-and-exempt-reporting-advisers/ia010118.zip",
    "2026-07-01": "/files/investment/data/other/information-about-registered-investment-advisers-exempt-reporting-advisers/ia07012026.zip",
}

# ---------------------------------------------------------------------------
# Section 5 — Rating agencies / presales
# ---------------------------------------------------------------------------
RATING_AGENCIES = ["S&P", "Fitch"]

# ---------------------------------------------------------------------------
# Section 6 — Sentiment corpora
# ---------------------------------------------------------------------------
# Fed Financial Stability Report: discovered at runtime from the listing page
# (federalreserve.gov/publications/financial-stability-report.htm), which
# currently lists 2020-2026. BIS Quarterly Review: predictable URL pattern
# https://www.bis.org/publ/qtrpdf/r_qt<YYMM>.pdf for quarter-end months
# (03/06/09/12); generated programmatically and verified by HTTP status, not
# hardcoded per-issue. IMF GFSR's publication page returns a redirect this
# project couldn't resolve to a stable PDF pattern in the time available —
# logged in docs/excluded_sources.md rather than guessed.
REGULATOR_REPORT_START_YEAR = 2020
BIS_QTR_MONTHS = ["03", "06", "09", "12"]
REDDIT_SUBREDDITS = ["investing", "bonds", "fixedincome", "dividends", "wallstreetbets", "ETFs"]
REDDIT_KEYWORDS = ["CLO", "collateralized loan obligation", "JAAA", "CLOZ", "Oxford Lane", "OXLC", "Eagle Point", "ECC"]
REDDIT_DISAMBIGUATION_CONTEXT = ["loan", "tranche", "AAA", "credit", "ETF", "yield", "collateralized", "leveraged"]

ALT_MANAGER_TICKERS = ["CG", "ARES", "OWL", "BX"]  # Carlyle, Ares, Blue Owl, Blackstone

# ---------------------------------------------------------------------------
# Shared event registry — used by common/style.py for annotation flags across
# every chart in the project. Keep dates as ISO strings; each event is a
# point-in-time flag (vertical line) or a span (start, end).
# ---------------------------------------------------------------------------
EVENTS = [
    {"date": "2020-03-01", "end": "2020-04-30", "label": "COVID-19 shock", "kind": "span"},
    {"date": "2023-03-09", "end": "2023-03-15", "label": "SVB / regional bank stress", "kind": "span"},
    {"date": "2024-08-05", "end": "2024-08-09", "label": "Aug-2024 vol unwind", "kind": "span"},
    {"date": "2025-04-02", "end": "2025-04-11", "label": "Apr-2025 tariff shock", "kind": "span"},
    {"date": "2025-01-29", "end": None, "label": "First Warsh FOMC", "kind": "point"},
]

# ---------------------------------------------------------------------------
# Entity resolution thresholds (common/entity.py)
# ---------------------------------------------------------------------------
ENTITY_AUTO_ACCEPT_SCORE = 92
ENTITY_REVIEW_MIN_SCORE = 80
LEGAL_SUFFIXES = [
    "llc", "inc", "incorporated", "corp", "corporation", "holdings", "holding",
    "intermediate", "midco", "bidco", "finco", "borrower", "sarl", "s.a.r.l",
    "bv", "b.v", "lux", "luxembourg", "lp", "l.p", "ltd", "limited", "co",
    "company", "group", "gp",
]

# ---------------------------------------------------------------------------
# Loughran-McDonald master dictionary (Section 5/6 sentiment scoring)
# ---------------------------------------------------------------------------
# The free master dictionary is published on Notre Dame's Software Repository
# for Accounting and Finance (SRAF). The exact CSV/XLSX filename changes with
# each vintage, so text.py discovers the live link by parsing this landing
# page rather than hardcoding a versioned file URL; the resolved link gets
# recorded in docs/sources.md on first successful fetch.
LM_DICTIONARY_LANDING_PAGE = "https://sraf.nd.edu/loughranmcdonald-master-dictionary/"
LM_DICTIONARY_PATH = DATA_DIR / "_lexicons" / "lm_master_dictionary.csv"
