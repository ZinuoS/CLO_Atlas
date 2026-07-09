"""Reddit mentions of CLOs (Section 6), via PRAW using the user's own personal
app credentials, read from environment variables (REDDIT_CLIENT_ID,
REDDIT_CLIENT_SECRET, REDDIT_USER_AGENT) — never hardcoded, never asked for
in chat. Not available in this run (no credentials in the environment this
project executed in) — logged, not faked. The scraping logic itself is real
and complete; a user with their own Reddit app credentials can run this
directly by exporting those three variables.
"""
from __future__ import annotations

import datetime as dt
import logging
import os
import re

import pandas as pd

import config
from src.common.cache import Provenance, write_parquet

logger = logging.getLogger("clo_atlas.sentiment.scrape_reddit")

OUT_PATH = config.INTERIM_DIR / "reddit_mentions.parquet"

_CONTEXT_PATTERN = re.compile(
    "|".join(re.escape(k) for k in config.REDDIT_DISAMBIGUATION_CONTEXT), re.IGNORECASE
)


def has_credentials() -> bool:
    return all(os.environ.get(k) for k in ("REDDIT_CLIENT_ID", "REDDIT_CLIENT_SECRET", "REDDIT_USER_AGENT"))


def is_clo_relevant(text: str, window_chars: int = 200) -> bool:
    """Disambiguates 'CLO' (collateralized loan obligation) from 'CLO' (chief
    legal officer) / 'Clorox' by requiring a finance-context keyword nearby.
    """
    for m in re.finditer(r"\bCLOs?\b", text):
        start, end = max(0, m.start() - window_chars), min(len(text), m.end() + window_chars)
        if _CONTEXT_PATTERN.search(text[start:end]):
            return True
    # Unambiguous full-name / ticker mentions don't need the disambiguation check.
    unambiguous = ["collateralized loan obligation", "JAAA", "CLOZ", "Oxford Lane", "OXLC", "Eagle Point", "ECC"]
    return any(term.lower() in text.lower() for term in unambiguous)


def scrape_subreddit(reddit, subreddit_name: str, keywords: list[str], limit: int = 200) -> list[dict]:
    rows = []
    sub = reddit.subreddit(subreddit_name)
    for keyword in keywords:
        for submission in sub.search(keyword, sort="new", limit=limit):
            text = f"{submission.title} {submission.selftext}"
            if not is_clo_relevant(text):
                continue
            rows.append({
                "subreddit": subreddit_name, "id": submission.id, "created_utc": submission.created_utc,
                "title": submission.title, "selftext": submission.selftext,
                "score": submission.score, "num_comments": submission.num_comments,
                "author": str(submission.author) if submission.author else None,
                "url": f"https://reddit.com{submission.permalink}",
            })
    return rows


def run() -> pd.DataFrame:
    if not has_credentials():
        logger.warning(
            "scrape_reddit.py: no Reddit API credentials in the environment "
            "(REDDIT_CLIENT_ID/REDDIT_CLIENT_SECRET/REDDIT_USER_AGENT). This is a "
            "personal-app-credential source per the mission brief, not a public "
            "endpoint — export those three variables to run this for real."
        )
        if OUT_PATH.exists():
            return pd.read_parquet(OUT_PATH)
        return pd.DataFrame(columns=["subreddit", "id", "created_utc", "title", "selftext",
                                       "score", "num_comments", "author", "url"])

    import praw
    reddit = praw.Reddit(
        client_id=os.environ["REDDIT_CLIENT_ID"],
        client_secret=os.environ["REDDIT_CLIENT_SECRET"],
        user_agent=os.environ["REDDIT_USER_AGENT"],
    )

    rows = []
    for subreddit_name in config.REDDIT_SUBREDDITS:
        try:
            rows.extend(scrape_subreddit(reddit, subreddit_name, config.REDDIT_KEYWORDS))
        except Exception as exc:
            logger.warning("r/%s failed (%s), skipping", subreddit_name, exc)

    df = pd.DataFrame(rows).drop_duplicates(subset=["id"])
    write_parquet(df, OUT_PATH, Provenance(
        source_urls=[f"https://reddit.com/r/{s}" for s in config.REDDIT_SUBREDDITS],
        scrape_timestamp=dt.datetime.now(dt.timezone.utc).isoformat(),
        parser="src.sentiment.scrape_reddit",
    ))
    logger.info("wrote %d Reddit posts to %s", len(df), OUT_PATH)
    return df


def main():
    logging.basicConfig(level=logging.INFO)
    run()


if __name__ == "__main__":
    main()
