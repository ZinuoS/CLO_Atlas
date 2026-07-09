"""Wayback Machine CDX API backfill utility.

Given a URL (or URL prefix) and a date range, query the CDX API for
snapshots, dedupe by digest, and download each unique snapshot through the
same CachedSession used everywhere else so raw archiving stays uniform.

This is how CLO ETF issuers' "latest holdings file only" pages get turned
into a time series: the file at a fixed URL changes daily, but Wayback keeps
snapshots we can walk.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from src.common.http import CachedSession, FetchResult

logger = logging.getLogger("clo_atlas.wayback")

CDX_ENDPOINT = "http://web.archive.org/cdx/search/cdx"


@dataclass
class Snapshot:
    timestamp: str  # YYYYMMDDhhmmss
    original_url: str
    digest: str
    status_code: str
    mime_type: str

    @property
    def archive_url(self) -> str:
        return f"https://web.archive.org/web/{self.timestamp}id_/{self.original_url}"

    @property
    def date(self) -> str:
        return f"{self.timestamp[0:4]}-{self.timestamp[4:6]}-{self.timestamp[6:8]}"


def list_snapshots(session: CachedSession, url: str, start: str, end: str,
                    match_type: str = "exact", collapse_digest: bool = True) -> list[Snapshot]:
    """Query CDX for snapshots of `url` between `start` and `end` (YYYYMMDD or YYYY-MM-DD).

    match_type: "exact" for one URL, "prefix" to sweep everything under a path.
    """
    start = start.replace("-", "")
    end = end.replace("-", "")
    params = {
        "url": url,
        "from": start,
        "to": end,
        "output": "json",
        "matchType": match_type,
        "filter": "statuscode:200",
    }
    if collapse_digest:
        params["collapse"] = "digest"

    result = session.get(CDX_ENDPOINT, params=params)
    if result.status != 200:
        logger.warning("CDX query failed for %s: status %d", url, result.status)
        return []

    rows = result.json()
    if not rows or len(rows) < 2:
        return []
    header, *records = rows
    idx = {name: i for i, name in enumerate(header)}
    snapshots = []
    for rec in records:
        snapshots.append(Snapshot(
            timestamp=rec[idx["timestamp"]],
            original_url=rec[idx["original"]],
            digest=rec[idx["digest"]],
            status_code=rec[idx.get("statuscode", idx.get("status", 0))],
            mime_type=rec[idx.get("mimetype", 0)] if "mimetype" in idx else "",
        ))
    return snapshots


def fetch_snapshot(session: CachedSession, snapshot: Snapshot) -> FetchResult:
    return session.get(snapshot.archive_url)


def backfill(session: CachedSession, url: str, start: str, end: str,
             match_type: str = "exact") -> list[tuple[Snapshot, FetchResult]]:
    """Convenience: list snapshots then fetch each (digest-deduped) through the cache."""
    snapshots = list_snapshots(session, url, start, end, match_type=match_type)
    logger.info("wayback: %d unique-digest snapshots for %s between %s and %s", len(snapshots), url, start, end)
    out = []
    for snap in snapshots:
        try:
            res = fetch_snapshot(session, snap)
            out.append((snap, res))
        except Exception as exc:
            logger.warning("failed to fetch snapshot %s of %s: %s", snap.timestamp, url, exc)
    return out


def main():
    logging.basicConfig(level=logging.INFO)
    s = CachedSession()
    snaps = list_snapshots(s, "https://www.sec.gov/", "2023-01-01", "2023-01-31")
    print(f"found {len(snaps)} snapshots")


if __name__ == "__main__":
    main()
