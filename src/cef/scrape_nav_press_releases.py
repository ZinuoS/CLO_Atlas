"""Oxford Lane Capital Corp.'s own NAV-update press releases (Section 2
deep-dive) — a real, richer, and far more current NAV disclosure trail than
the EDGAR 424B3/497 ATM-supplement "financial update" paragraphs
`scrape_capital_actions.scrape_nav_disclosures` depends on.

**How this list was found**: OXLC issues a monthly NAV-estimate press
release (via GlobeNewswire) and files a combined quarterly NAV/financial
results release roughly every three months, both distributed publicly (not
gated) — this was not previously known to the project. Discovered via web
search 2026-07-15 after a desk question about whether the premium/discount
chart's underlying data was actually current. GlobeNewswire's own
organization/search page is a client-rendered SPA (confirmed: fetching it
returns an empty shell, no article links in the raw HTML) and OXLC's own
investor-relations site (ir.oxfordlanecapital.com) timed out on every
retry attempt (also likely JS-rendered) — so unlike scrape_filings.py's
NPORT-P list (walked via the EDGAR submissions API), this URL list is
manually curated from search results, the same way scrape_circular.py's
single circular URL was found. Extend it by adding new URLs as they're
found; there is currently no way for this scraper to auto-discover new
releases.

Every URL was independently fetched and its extracted NAV figure verified
against the fetched page text before being added here — one early search
result (unrelated to this scraper) turned out to be a different company's
similarly-numbered deal, so nothing in this list is taken on a search
snippet's word alone.
"""
from __future__ import annotations

import datetime as dt
import logging
import re

import pandas as pd

import config
from src.common.cache import Provenance, write_parquet
from src.common.http import CachedSession

logger = logging.getLogger("clo_atlas.cef.scrape_nav_press_releases")

OUT_PATH = config.INTERIM_DIR / "cef_oxlc_nav_press_releases.parquet"

# (release_date, url) — release_date is when GlobeNewswire published it, not
# the NAV as-of date (that's parsed from the article text itself).
PRESS_RELEASE_URLS = [
    ("2022-11-01", "https://www.globenewswire.com/news-release/2022/11/01/2545422/0/en/Oxford-Lane-Capital-Corp-Announces-Net-Asset-Value-and-Selected-Financial-Results-for-the-Second-Fiscal-Quarter-and-Declaration-of-Distributions-on-Common-Stock-for-the-Months-Endi.html"),
    ("2023-11-01", "https://www.globenewswire.com/news-release/2023/11/01/2771088/0/en/Oxford-Lane-Capital-Corp-Announces-Net-Asset-Value-and-Selected-Financial-Results-for-the-Second-Fiscal-Quarter-and-Notes-its-Previously-Announced-Distributions-on-Common-Stock-for.html"),
    ("2024-01-26", "https://www.globenewswire.com/news-release/2024/01/26/2817911/0/en/Oxford-Lane-Capital-Corp-Announces-Net-Asset-Value-and-Selected-Financial-Results-for-the-Third-Fiscal-Quarter-and-Declaration-of-Distributions-on-Common-Stock-for-the-Months-Endin.html"),
    ("2024-11-08", "https://www.globenewswire.com/news-release/2024/11/08/2977595/0/en/Oxford-Lane-Capital-Corp-Provides-October-Net-Asset-Value-Update.html"),
    ("2024-12-10", "https://www.globenewswire.com/news-release/2024/12/10/2994504/0/en/Oxford-Lane-Capital-Corp-Provides-November-Net-Asset-Value-Update.html"),
    ("2025-05-19", "https://www.globenewswire.com/news-release/2025/05/19/3083952/0/en/Oxford-Lane-Capital-Corp-Announces-Net-Asset-Value-and-Selected-Financial-Results-for-the-Fourth-Fiscal-Quarter-and-Provides-April-Net-Asset-Value-Update.html"),
    ("2025-08-08", "https://www.globenewswire.com/news-release/2025/08/08/3130096/0/en/Oxford-Lane-Capital-Corp-Provides-July-2025-Net-Asset-Value-Update.html"),
    ("2025-09-12", "https://www.globenewswire.com/news-release/2025/09/12/3149160/0/en/Oxford-Lane-Capital-Corp-Provides-September-8-2025-Net-Asset-Value-Update.html"),
    ("2025-11-03", "https://www.globenewswire.com/news-release/2025/11/03/3179203/0/en/Oxford-Lane-Capital-Corp-Announces-Net-Asset-Value-and-Selected-Financial-Results-for-the-Second-Fiscal-Quarter-and-Declaration-of-Distributions-on-Common-Stock-for-the-Months-Endi.html"),
    ("2025-11-13", "https://www.globenewswire.com/news-release/2025/11/13/3187270/0/en/Oxford-Lane-Capital-Corp-Provides-October-2025-Net-Asset-Value-Update.html"),
    ("2025-12-11", "https://www.globenewswire.com/news-release/2025/12/11/3203854/0/en/Oxford-Lane-Capital-Corp-Provides-November-2025-Net-Asset-Value-Update.html"),
    ("2026-01-30", "https://www.globenewswire.com/news-release/2026/01/30/3229485/0/en/Oxford-Lane-Capital-Corp-Announces-Net-Asset-Value-and-Selected-Financial-Results-for-the-Third-Fiscal-Quarter-and-Declaration-of-Distributions-on-Common-Stock-for-the-Months-Endin.html"),
    ("2026-02-17", "https://www.globenewswire.com/news-release/2026/02/17/3239194/0/en/Oxford-Lane-Capital-Corp-Provides-January-2026-Net-Asset-Value-Update.html"),
    ("2026-03-10", "https://www.globenewswire.com/news-release/2026/03/10/3253293/0/en/Oxford-Lane-Capital-Corp-Provides-February-2026-Net-Asset-Value-Update.html"),
    ("2026-05-19", "https://www.globenewswire.com/news-release/2026/05/19/3297430/0/en/Oxford-Lane-Capital-Corp-Announces-April-Net-Asset-Value-and-Selected-Financial-Results-for-the-Fourth-Fiscal-Quarter-and-Declaration-of-Common-Stock-Distributions-for-the-Months-E.html"),
    ("2026-06-15", "https://www.globenewswire.com/news-release/2026/06/15/3311722/0/en/Oxford-Lane-Capital-Corp-Provides-May-2026-Net-Asset-Value-Update.html"),
]

# Monthly "estimate" phrasing: "...NAV per share of our common stock as of
# <date>, is between $<low> and $<high>."
_RANGE_PATTERN = re.compile(
    r"NAV per share of our common stock as of ([A-Z][a-z]+ \d{1,2}, \d{4}),\s*is between \$(\d+\.\d+) and \$(\d+\.\d+)"
)
# Quarterly "actual" phrasing: 'Net asset value ("NAV") per share as of
# <date> stood at $<value>, compared with a NAV per share on <date> of $<value>.'
_POINT_PATTERN = re.compile(
    r"per share as of ([A-Z][a-z]+ \d{1,2}, \d{4}) stood at \$(\d+\.\d+),\s*compared with a NAV per share on "
    r"([A-Z][a-z]+ \d{1,2}, \d{4}) of \$(\d+\.\d+)"
)
_SHARES_PATTERN = re.compile(
    r"As of ([A-Z][a-z]+ \d{1,2}, \d{4}), the Company had approximately (\d+\.\d+) million shares of common stock "
    r"issued and outstanding"
)


def _clean_html(html: str) -> str:
    text = re.sub(r"<script[^>]*>.*?</script>", " ", html, flags=re.DOTALL)
    text = re.sub(r"<style[^>]*>.*?</style>", " ", text, flags=re.DOTALL)
    text = re.sub(r"<[^>]+>", " ", text)
    text = text.replace("&#8217;", "'").replace("&#8220;", '"').replace("&#8221;", '"')
    return re.sub(r"\s+", " ", text)


def parse_press_release(html: str, release_date: str, url: str) -> list[dict]:
    """A single release can carry a monthly estimate, a quarterly actual, or
    both (the combined quarterly-results-plus-next-month-estimate releases
    do) — return one row per NAV figure found."""
    text = _clean_html(html)
    rows = []

    for m in _RANGE_PATTERN.finditer(text):
        as_of, low, high = m.groups()
        rows.append({
            "as_of_date": as_of, "nav_low": float(low), "nav_high": float(high),
            "nav_mid": (float(low) + float(high)) / 2, "figure_type": "monthly_estimate",
            "release_date": release_date, "source_url": url,
        })

    for m in _POINT_PATTERN.finditer(text):
        as_of, value, prior_date, prior_value = m.groups()
        rows.append({
            "as_of_date": as_of, "nav_low": float(value), "nav_high": float(value),
            "nav_mid": float(value), "figure_type": "quarterly_actual",
            "release_date": release_date, "source_url": url,
        })
        rows.append({
            "as_of_date": prior_date, "nav_low": float(prior_value), "nav_high": float(prior_value),
            "nav_mid": float(prior_value), "figure_type": "quarterly_actual",
            "release_date": release_date, "source_url": url,
        })

    shares_match = _SHARES_PATTERN.search(text)
    if shares_match and rows:
        shares_as_of, shares_millions = shares_match.groups()
        for row in rows:
            if row["as_of_date"] == shares_as_of:
                row["shares_outstanding"] = float(shares_millions) * 1e6

    if not rows:
        logger.warning("no NAV figure found in %s (%s) — pattern may need updating", url, release_date)
    return rows


def run() -> pd.DataFrame:
    session = CachedSession()
    all_rows = []
    for release_date, url in PRESS_RELEASE_URLS:
        result = session.get(url)
        if result.status != 200:
            logger.warning("%s: fetch failed (status %d), skipping", url, result.status)
            continue
        rows = parse_press_release(result.text(), release_date, url)
        all_rows.extend(rows)
        logger.info("%s: parsed %d NAV figure(s)", release_date, len(rows))

    df = pd.DataFrame(all_rows)
    if not df.empty:
        df["as_of_date"] = pd.to_datetime(df["as_of_date"])
        df = df.drop_duplicates(subset=["as_of_date", "figure_type"]).sort_values("as_of_date").reset_index(drop=True)

    write_parquet(df, OUT_PATH, Provenance(
        source_urls=[u for _, u in PRESS_RELEASE_URLS],
        scrape_timestamp=dt.datetime.now(dt.timezone.utc).isoformat(),
        parser="src.cef.scrape_nav_press_releases",
        notes=f"OXLC's own NAV-update press releases (GlobeNewswire), {len(PRESS_RELEASE_URLS)} releases, manually "
              "curated URL list (see module docstring) -- not auto-discovered. Figures are pre-split where the "
              "release predates OXLC's 2025-09-08 1-for-5 reverse split; rescale before comparing across that date "
              "(see analysis_capital_machine._cumulative_split_factor).",
    ))
    logger.info("wrote %d NAV figures (%d monthly estimates, %d quarterly actuals) to %s",
                len(df), (df["figure_type"] == "monthly_estimate").sum() if len(df) else 0,
                (df["figure_type"] == "quarterly_actual").sum() if len(df) else 0, OUT_PATH)
    return df


def main():
    logging.basicConfig(level=logging.INFO)
    df = run()
    print(df.to_string(index=False))


if __name__ == "__main__":
    main()
