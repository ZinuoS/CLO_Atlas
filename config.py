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
FIGURES_ANATOMY_DIR = FIGURES_DIR / "anatomy"  # waterfall frame sequences (high file count, kept out of the flat figures/ dir)
DOCS_DIR = ROOT / "docs"
CACHE_MANIFEST = RAW_DIR / "_manifest.csv"
LLM_CACHE_DIR = DATA_DIR / "_llm_cache"

for d in (RAW_DIR, INTERIM_DIR, FINAL_DIR, FIGURES_DIR, FIGURES_INTERACTIVE_DIR,
          FIGURES_FINAL_DIR, FIGURES_ANATOMY_DIR, DOCS_DIR, LLM_CACHE_DIR):
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
    # GDELT's own published policy is "one request every 5 seconds"; run
    # noticeably slower than that ceiling since this project's sandboxed
    # egress appears to share a quota with other traffic (empirically 429s
    # even at 8-10s spacing during development, 2026-07-11).
    "api.gdeltproject.org": (0.05, 1),
    "news.google.com": (1.0, 2),
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
# Listed preferred/baby-bond tickers per fund (its observable marginal cost
# of capital) — verified individually resolvable via yfinance 2026-07-11;
# tickers guessed from each issuer's normal <BASE><SERIES LETTER> convention
# and kept only if real price data came back (ECCD/ECCF/ECCX/ECCW guessed
# but returned no data — dropped, not fabricated).
CLO_CEF_PREFERRED_TICKERS = {
    "OXLC": ["OXLCZ", "OXLCL", "OXLCI", "OXLCO", "OXLCP", "OXLCN", "OXLCM"],
    "ECC": ["ECCC", "ECCV"],
}

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
# Section 6 v2 — Sentiment corpora, high-frequency attention/tone backbone
# ---------------------------------------------------------------------------
# Kept deliberately short given api.gdeltproject.org's strict rate limiting
# (see RATE_LIMITS) — each query costs two slow requests (volume + tone).
GDELT_QUERIES = [
    "collateralized loan obligation",
    "CLO market",
    "leveraged loan",
    "CLO ETF",
    "Oxford Lane",
]
GDELT_TIMESPAN = "15years"

NEWS_RSS_QUERIES = [
    "collateralized loan obligation", "CLO ETF", "CLO market", "leveraged loan fund", "Oxford Lane Capital",
]
YF_NEWS_TICKERS = ["JAAA", "CLOZ", "ECC", "OXLC", "XFLT", "OCCI", "BKLN"]

# ---------------------------------------------------------------------------
# Section 6 — Sentiment corpora
# ---------------------------------------------------------------------------
# Fed Financial Stability Report: discovered at runtime from the listing page
# (federalreserve.gov/publications/financial-stability-report.htm), which
# currently lists 2020-2026. BIS Quarterly Review: predictable URL pattern
# https://www.bis.org/publ/qtrpdf/r_qt<YYMM>.pdf for quarter-end months
# (03/06/09/12); generated programmatically and verified by HTTP status, not
# hardcoded per-issue. IMF GFSR: re-checked 2026-07-09 across several access
# points (main pub page, elibrary.imf.org, direct file paths) — every one
# returns HTTP 403 from an AkamaiGHost server, same as S&P Global Ratings.
# Confirmed blocked, not a missed discovery step; logged in
# docs/excluded_sources.md.
REGULATOR_REPORT_START_YEAR = 2020
BIS_QTR_MONTHS = ["03", "06", "09", "12"]

# ECB Financial Stability Review: the index page's PDF links carry a random
# hash suffix per issue (not derivable from the date), and only the 5 most
# recent issues are server-rendered on the index page (older years appear to
# require JS pagination this project didn't resolve). These 5 were extracted
# from that page directly and verified reachable 2026-07-09.
ECB_FSR_REPORTS = [
    {"date": "2024-05", "slug": "ecb.fsr202405~7f212449c8.en"},
    {"date": "2024-11", "slug": "ecb.fsr202411~dd60fc02c3.en"},
    {"date": "2025-05", "slug": "ecb.fsr202505~0cde5244f6.en"},
    {"date": "2025-11", "slug": "ecb.fsr202511~263b5810d4.en"},
    {"date": "2026-05", "slug": "ecb.fsr202605~50566915a7.en"},
]
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
# Macro opener (slides 1-2) — regime, disintermediation, scale, income
# ---------------------------------------------------------------------------
# Policy & curve, credit spreads, bank credit conditions (SLOOS), lending
# stock, inflation/real economy, recession shading. All 18 IDs verified live
# against fredgraph.csv (HTTP 200) 2026-07-11 before being added here.
MACRO_FRED_SERIES = {
    # Policy & curve
    "FEDFUNDS": "FEDFUNDS", "SOFR": "SOFR", "UST_3M": "DGS3MO", "UST_2Y": "DGS2",
    "UST_10Y": "DGS10", "T10Y2Y": "T10Y2Y",
    # Credit spreads
    "IG_OAS": "BAMLC0A0CM", "AAA_OAS": "BAMLC0A1CAAA", "BBB_OAS": "BAMLC0A4CBBB",
    "HY_OAS": "BAMLH0A0HYM2", "CCC_OAS": "BAMLH0A3HYC",
    # Bank credit conditions (Senior Loan Officer Opinion Survey)
    "SLOOS_TIGHTENING_LARGE": "DRTSCILM", "SLOOS_TIGHTENING_SMALL": "DRTSCIS",
    "SLOOS_SPREAD_OVER_COF": "DRSDCILM",
    # Lending stock
    "BUSLOANS": "BUSLOANS", "TOTCI": "TOTCI",
    # Inflation & real economy (regime shading)
    "CPI": "CPIAUCSL", "UNRATE": "UNRATE",
    # Recession indicator (shading)
    "USREC": "USREC",
}

# Rate-regime segmentation thresholds applied to FEDFUNDS (config, not fitted —
# this is exposition, not a statistical regime-switching model). ZIRP = level
# at/below the threshold; hiking/easing = 12m change beyond the ROC threshold
# while off zero; plateau = everything else (flat, off-zero).
MACRO_ZIRP_THRESHOLD_PCT = 0.25
MACRO_REGIME_ROC_THRESHOLD_PCT = 1.0  # 12-month change in FEDFUNDS, percentage points

# Illustrative SOFR + spread floater coupons for the mechanics table (labeled
# "illustrative" wherever plotted — not any specific real CLO tranche's terms).
MACRO_ILLUSTRATIVE_FLOATER_SPREADS_BPS = {"illustrative AAA-like": 150, "illustrative BBB-like": 300, "illustrative single-B-like": 500}

# Z.1 Financial Accounts of the United States, mirrored through FRED rather
# than the raw Data Download Program CSV packages: Choose.aspx?rel=Z1 serves
# only opaque hash-keyed "preformatted package" values with no server-rendered
# mnemonic-to-hash mapping discoverable without an undocumented extra lookup
# step, whereas FRED publishes the identical Board-published Z.1 figures under
# stable BOGZ1<mnemonic> IDs. Verified live 2026-07-11; underlying Z.1 series
# codes noted alongside each FRED ID in docs/sources.md.
MACRO_Z1_SERIES = {
    "nonfin_corp_total_credit_market_debt": "BCNSDODNS",  # debt securities + loans, liability, level
    "nonfin_corp_debt_securities": "NCBDBIQ027S",          # debt securities only, liability, level
    "nonfin_corp_bank_loans": "BLNECLBSNNCB",              # depository-institution loans n.e.c., liability, level
}

# Market-size comparators, all FRED-mirrored Fed/Treasury data, verified live
# 2026-07-11. CLO outstanding has no dedicated Z.1/FRED series (config's
# FED_CLO_HOLDER_CITATION already documents why); the scale comparison reuses
# that Section 4 citation instead of re-deriving a number here.
MACRO_MARKET_SIZE_FRED = {
    "corporate_and_foreign_bonds": "ASCFBL",           # all sectors, liability, level
    "treasury_total_public_debt": "GFDEBTN",           # federal debt, total public debt
    "municipal_securities": "SLGMSOQ027S",             # state & local govt, liability, level
    "agency_mbs_pools": "AGSEBMPTCMAHDFS",             # agency/GSE-backed mortgage pools, total mortgages, asset level
}

# ---------------------------------------------------------------------------
# Slide export dimensions (16:9 @ 300dpi) — used only if a figure is meant to
# drop into a deck without rescaling; most macro exhibits are standalone
# panel-sized charts sized like every other section's figures.
# ---------------------------------------------------------------------------
SLIDE_W_IN = 13.333
SLIDE_H_IN = 7.5

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

# Custom vulnerability lexicon (Section 6 alarm index v2): regulator alarm
# about CLOs lives in this vocabulary, not in LM's general finance polarity
# or VADER's social-media valence, neither of which fires reliably on
# professionally neutral prose. Single-token entries are stem-matched
# (substring prefix); multi-word entries are matched as literal phrases.
# Hand-curated, not derived from a corpus — documented here rather than
# buried in a scoring module so it's auditable/editable in one place.
VULNERABILITY_STEMS = [
    "vulnerab", "opacity", "opaque", "amplif", "fire sale", "run risk",
    "spillover", "contagion", "deteriorat", "cascade", "correlated",
    "leverage loop", "maturity mismatch", "forced sell",
]

# ---------------------------------------------------------------------------
# src/anatomy/ — CLO anatomy from the arranger's seat (model-driven section).
#
# HARD RULE: zero firm data. Every structural parameter below is adapted
# from ONE real, public offering circular — HPS Loan Management 2023-17,
# Ltd. / HPS Loan Management 2023-17 LLC, Final Offering Circular (a
# refinancing), dated 2025-06-06, listed on the Global Exchange Market of
# Euronext Dublin (see src/anatomy/scrape_circular.py for how this was
# found and fetched). Every figure below is either (a) taken directly from
# that circular's own tables/text — tagged "circular" — or (b) a market-
# standard convention this project is choosing because the circular didn't
# state it or because the model simplifies it away — tagged "TO-VERIFY".
#
# Two real tranches (Class A-R Notes $52mm + Class A-L-R Loans $200mm) are
# collapsed into one stylized "AAA" class ($252mm total, both pay the same
# spread and rank pari passu in the real deal); Class D-1-R and D-2-R are
# collapsed into one "BBB" class at their par-weighted blended spread; the
# Class Z Notes (a $39.7mm notional retention/IRR-tracking overlay with no
# independent economic claim on collateral) are dropped entirely — all
# three simplifications are restated on every figure's notes line, not just
# here.
# ---------------------------------------------------------------------------
ANATOMY_CIRCULAR_CITATION = {
    "deal_name": "HPS Loan Management 2023-17, Ltd. / HPS Loan Management 2023-17 LLC",
    "document": "Final Offering Circular (Refinancing)",
    "document_date": "2025-06-06",
    "manager": "HPS Investment Partners CLO (UK) LLP",
    "listing": "Global Exchange Market, Euronext Dublin",
    "source_url": "https://ise-prodnr-eu-west-1-data-integration.s3-eu-west-1.amazonaws.com/202506/168fabf3-c71c-42f7-9556-fcd803d3f379.pdf",
    "accessed": "2026-07-11",
}

# Real, VERIFIED pre-closing history found directly in the refinancing
# circular's "General" section on the Issuer (not previously extracted by
# scrape_circular.py's regex patterns, found on a manual re-read prompted by
# a desk question about whether the warehouse chart's timing was real).
# [circular, "General" / Issuer description section]
ANATOMY_ORIGINAL_HISTORY = {
    "incorporation_date": "2023-01-20",       # as "Courchevel Warehouse Ltd." in Jersey, registered no. 147155
    "original_entity_name": "Courchevel Warehouse Ltd.",
    "renamed_date": "2023-03-14",             # renamed to "HPS Loan Management 2023-17, Ltd."
    "original_closing_date": "2023-03-29",    # circular's own defined term: the "Original Closing Date"
    "issuer_publishes_financial_statements": False,  # circular's own words: "The Issuer does not publish any financial statements."
    "reporting_note": (
        "Monthly investor reports are prepared (Collateral Administration Agreement, EU Securitisation Regulation "
        "Article 7 disclosure) and distributed via a third-party reporting platform (Findox) and the Collateral "
        "Trustee's own website -- both noteholder/investor-restricted, not publicly accessible."
    ),
}

ANATOMY_DEAL = {
    # Dates: closing re-anchored to quarter 0; every other date is the
    # circular's own real gap from closing, in whole quarters (all landed
    # on exact quarter boundaries — not rounded). Absolute calendar dates
    # are illustrative (this refi circular doesn't state the *original*
    # 2023 deal's warehouse/pricing dates); the RELATIVE structure
    # (non-call length, reinvestment length, tenor) is the circular's real
    # figures. [circular: non-call end, reinvestment end, stated maturity;
    # TO-VERIFY: warehouse open, pricing date, effective date]
    "dates": {
        "warehouse_open_quarter": -3, "pricing_quarter": -1, "closing_quarter": 0,
        "effective_date_quarter": 0, "non_call_end_quarter": 8, "reinvestment_end_quarter": 20,
        "stated_maturity_quarter": 52,
        "closing_date_calendar": "2025-04-08", "non_call_end_calendar": "2027-04-23",
        "reinvestment_end_calendar": "2030-04-30", "stated_maturity_calendar": "2038-04-30",
    },
    # Liabilities: sizes and spreads are the circular's own figures (with
    # the two collapses noted above); ratings are the circular's expected
    # ratings for the closest real class. [circular]
    #
    # spread_bps is the REFINANCING spread (this circular, dated 2025-06-06,
    # resets pricing on the original March 2023 deal without changing deal
    # mechanics — see scrape_circular.py's docstring). It is NOT the 2023
    # new-issue (NI) spread the notes originally priced at. Searched for the
    # original 2023-17 Class A/AAA NI spread via third-party NPORT-P holder
    # disclosures (the same technique that works for finding other funds'
    # HPS holdings) and web search on 2026-07-14; found only unrelated deals
    # (a same-numbered GoldenTree CLO, other HPS vintages) and could not
    # independently verify the 2023 figure within reasonable search effort
    # -- every notebook/chart display of spread_bps is labeled "refi spread"
    # rather than left ambiguous, and the NI spread is left unfilled (None)
    # rather than guessed. [circular: refi spread; TO-VERIFY / not found: NI spread]
    "tranches": [
        {"name": "AAA", "size": 252_000_000, "spread_bps": 127, "rating": "Aaa/AAA", "pikable": False},
        {"name": "AA", "size": 52_000_000, "spread_bps": 165, "rating": "AA", "pikable": False},
        {"name": "A", "size": 24_000_000, "spread_bps": 180, "rating": "A", "pikable": True},
        {"name": "BBB", "size": 27_000_000, "spread_bps": 292, "rating": "BBB-", "pikable": True},  # par-weighted D-1/D-2 blend
        {"name": "BB", "size": 13_000_000, "spread_bps": 550, "rating": "BB-", "pikable": True},
        {"name": "equity", "size": 39_700_000, "spread_bps": None, "rating": None, "pikable": False},
    ],
    "target_par": 407_700_000,  # sum of tranches above; collateral principal ~= rated debt + equity [TO-VERIFY: standard simplifying assumption, ignores modest structuring arbitrage]
    # Coverage tests: trigger levels are the circular's own table.
    # [circular]
    "oc_triggers_pct": {"AAA": 121.58, "AA": 121.58, "A": 113.95, "BBB": 106.68, "BB": 103.20},
    "ic_triggers_pct": {"AAA": 115.00, "AA": 115.00, "A": 110.00, "BBB": 105.00},  # no IC test on BB, per circular
    "interest_diversion_trigger_pct": 103.70,  # tied to the BB (Class E-R) OC ratio, reinvestment-period only [circular]
    "ccc_limit_pct": 7.5,  # of collateral principal amount, both Moody's/S&P buckets [circular]
    "ccc_haircut_to_market_value": True,  # excess-CCC (above the limit) carried at min(market value, par) rather than par [TO-VERIFY: standard mechanic, circular describes the test but this project's engine applies the conventional haircut treatment]
    # Fees: incentive-fee rate is the circular's own figure; hurdle and
    # management-fee percentages are not stated in the sections this
    # project extracted (see scrape_circular.py) — market-standard
    # convention used instead. [TO-VERIFY]
    "senior_mgmt_fee_pct": 0.15, "sub_mgmt_fee_pct": 0.20,  # % p.a. of collateral principal [TO-VERIFY: convention]
    "incentive_fee_pct": 20.0,  # of residual after equity hurdle [circular]
    "incentive_hurdle_irr_pct": 12.0,  # [TO-VERIFY: convention, not stated in extracted sections]
    "senior_expense_cap_usd_annual": 250_000,  # [TO-VERIFY: convention]
    # Portfolio / collateral assumptions — explicitly NOT from the circular
    # (a live BSL portfolio's actual WAS/WARF/diversity are reported
    # figures at a point in time, not structural terms); market-standard
    # pricing-convention values, as the brief instructs. [TO-VERIFY]
    "was_bps_over_sofr": 350, "warf": 2900, "diversity_score": 65,
    "recovery_rate_pct": 67.5, "base_cdr_pct": 2.0, "base_cpr_pct": 20.0,
    "sofr_base_pct": 4.30,  # illustrative flat base case; scenarios override
}

# The click-through PNG frame sequences are the deliverable; GIF assembly is
# a convenience for reviewing them and must never drive a design decision
# (fixed frame count/spacing, layout) — off by default.
ANATOMY_BUILD_GIFS = False

# Warehouse-facility economics: warehouse lending terms are a private
# arrangement between the arranger/warehouse lender and the manager, never
# disclosed in a public offering circular (ours included — a refinancing
# circular for an already-closed deal has no reason to restate the original
# 2023 warehouse terms). Every figure here is a market-standard convention,
# not a circular figure. [TO-VERIFY: entire block]
ANATOMY_WAREHOUSE = {
    # 90% advance rate (10% at-risk equity) — real warehouse facilities are
    # highly levered because the lender's exposure is short-duration and
    # overcollateralized; the residual 10% capital commitment is sized to
    # land in the same order of magnitude as the CLO's own equity tranche,
    # since it is largely the SAME capital that rolls into that tranche at
    # closing (a lower, more "cautious-sounding" advance rate would imply
    # warehouse equity multiples larger than the deal's own equity check,
    # which is not how these facilities are actually sized in practice).
    "advance_rate_pct": 90.0,       # % of ramped par financed by warehouse debt; remainder is at-risk equity capital
    "spread_bps_over_sofr": 180,    # warehouse facility financing spread
    "loan_yield_bps_over_sofr": ANATOMY_DEAL["was_bps_over_sofr"],  # ramped loans priced like the eventual portfolio
    "ramp_start_quarter": ANATOMY_DEAL["dates"]["warehouse_open_quarter"],
    "takeout_quarter": ANATOMY_DEAL["dates"]["closing_quarter"],
    "target_ramp_par": ANATOMY_DEAL["target_par"],
    "ramp_profile": "s_curve",      # slow-fast-slow accumulation, not linear — standard ramp shape
}
