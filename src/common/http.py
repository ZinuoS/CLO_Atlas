"""CachedSession: the only way scrapers should talk to the network.

Every response body is archived verbatim to data/raw/<domain>/<sha256>.<ext>
before any parsing happens, with a manifest row recording url, timestamp,
status, and digest. Rate limiting is a token bucket keyed by domain (see
config.RATE_LIMITS). Retries use exponential backoff and specifically respect
429/503 with Retry-After when present.

No scraper in this project should call `requests.get` / `requests.post`
directly — go through `CachedSession.get()` / `.post()` instead, so every
fetch is rate-limited, retried, and archived uniformly.
"""
from __future__ import annotations

import csv
import hashlib
import json
import logging
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import requests

import config

logger = logging.getLogger("clo_atlas.http")

_MANIFEST_FIELDS = ["timestamp", "url", "domain", "status", "sha256", "path", "method", "cache_hit"]
_MANIFEST_LOCK = threading.Lock()

_EXT_BY_CONTENT_TYPE = {
    "text/html": "html",
    "application/xhtml+xml": "html",
    "application/json": "json",
    "text/json": "json",
    "application/pdf": "pdf",
    "text/csv": "csv",
    "application/csv": "csv",
    "text/xml": "xml",
    "application/xml": "xml",
    "application/vnd.ms-excel": "xls",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "xlsx",
    "text/plain": "txt",
}


class RateLimiter:
    """Token bucket, one instance per domain, shared across threads."""

    def __init__(self, rate_per_sec: float, burst: int):
        self.rate = rate_per_sec
        self.capacity = burst
        self.tokens = float(burst)
        self.last_refill = time.monotonic()
        self._lock = threading.Lock()

    def acquire(self) -> None:
        with self._lock:
            now = time.monotonic()
            elapsed = now - self.last_refill
            self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
            self.last_refill = now
            if self.tokens < 1.0:
                wait = (1.0 - self.tokens) / self.rate
                time.sleep(max(wait, 0.0))
                self.tokens = 0.0
                self.last_refill = time.monotonic()
            else:
                self.tokens -= 1.0


@dataclass
class FetchResult:
    url: str
    status: int
    content: bytes
    headers: dict
    path: Path
    cache_hit: bool
    from_status_error: bool = False

    def text(self, encoding: str | None = None) -> str:
        return self.content.decode(encoding or "utf-8", errors="replace")

    def json(self):
        return json.loads(self.text())


class CachedSession:
    """Wraps requests.Session with rate limiting, retry/backoff, and raw archiving.

    Parameters
    ----------
    archive_dir: where raw responses are written (defaults to config.RAW_DIR)
    force_refetch: if True, bypass the on-disk cache and hit the network again
    """

    def __init__(self, archive_dir: Path | None = None, force_refetch: bool = False):
        self.archive_dir = Path(archive_dir or config.RAW_DIR)
        self.archive_dir.mkdir(parents=True, exist_ok=True)
        self.force_refetch = force_refetch
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": config.USER_AGENT})
        self._limiters: dict[str, RateLimiter] = {}
        self._limiters_lock = threading.Lock()
        self._manifest_path = self.archive_dir / "_manifest.csv"
        self._ensure_manifest()

    # -- manifest -----------------------------------------------------
    def _ensure_manifest(self) -> None:
        if not self._manifest_path.exists():
            with open(self._manifest_path, "w", newline="") as f:
                csv.writer(f).writerow(_MANIFEST_FIELDS)

    def _append_manifest(self, row: dict) -> None:
        with _MANIFEST_LOCK:
            with open(self._manifest_path, "a", newline="") as f:
                csv.writer(f).writerow([row.get(k, "") for k in _MANIFEST_FIELDS])

    # -- rate limiting --------------------------------------------------
    def _limiter_for(self, domain: str) -> RateLimiter:
        with self._limiters_lock:
            if domain not in self._limiters:
                rate, burst = config.RATE_LIMITS.get(domain, config.DEFAULT_RATE_LIMIT)
                self._limiters[domain] = RateLimiter(rate, burst)
            return self._limiters[domain]

    # -- content addressing ----------------------------------------------
    def _digest_path(self, domain: str, url: str, content: bytes, content_type: str) -> Path:
        digest = hashlib.sha256(content).hexdigest()
        ext = "bin"
        for ct, e in _EXT_BY_CONTENT_TYPE.items():
            if ct in (content_type or ""):
                ext = e
                break
        else:
            path_suffix = Path(urlparse(url).path).suffix.lstrip(".")
            if path_suffix:
                ext = path_suffix
        domain_dir = self.archive_dir / domain
        domain_dir.mkdir(parents=True, exist_ok=True)
        return domain_dir / f"{digest}.{ext}"

    def _cache_lookup(self, url: str) -> Path | None:
        """Return a cached raw file for this exact URL if the manifest has one, else None."""
        if not self._manifest_path.exists():
            return None
        with open(self._manifest_path, newline="") as f:
            reader = csv.DictReader(f)
            hit = None
            for row in reader:
                if row["url"] == url and row["status"] == "200":
                    hit = row
        if hit:
            p = Path(hit["path"])
            if p.exists():
                return p
        return None

    # -- core fetch --------------------------------------------------
    def get(self, url: str, params: dict | None = None, headers: dict | None = None,
             timeout: int = 30, allow_cache: bool = True) -> FetchResult:
        return self._fetch("GET", url, params=params, headers=headers, timeout=timeout, allow_cache=allow_cache)

    def post(self, url: str, data=None, json_body=None, headers: dict | None = None,
              timeout: int = 30, allow_cache: bool = True) -> FetchResult:
        return self._fetch("POST", url, data=data, json_body=json_body, headers=headers,
                            timeout=timeout, allow_cache=allow_cache)

    def _fetch(self, method: str, url: str, params: dict | None = None, data=None,
               json_body=None, headers: dict | None = None, timeout: int = 30,
               allow_cache: bool = True) -> FetchResult:
        full_url = url
        if params:
            req = requests.Request(method, url, params=params).prepare()
            full_url = req.url

        if allow_cache and not self.force_refetch:
            cached_path = self._cache_lookup(full_url)
            if cached_path is not None:
                content = cached_path.read_bytes()
                return FetchResult(url=full_url, status=200, content=content, headers={},
                                    path=cached_path, cache_hit=True)

        domain = urlparse(url).netloc
        limiter = self._limiter_for(domain)

        last_exc = None
        for attempt in range(config.MAX_RETRIES):
            limiter.acquire()
            try:
                resp = self.session.request(method, url, params=params, data=data, json=json_body,
                                             headers=headers, timeout=timeout)
            except requests.RequestException as exc:
                last_exc = exc
                sleep_s = config.BACKOFF_BASE_SECONDS * (2 ** attempt)
                logger.warning("network error on %s (attempt %d/%d): %s; backing off %.1fs",
                                full_url, attempt + 1, config.MAX_RETRIES, exc, sleep_s)
                time.sleep(sleep_s)
                continue

            if resp.status_code in (429, 503):
                retry_after = resp.headers.get("Retry-After")
                sleep_s = float(retry_after) if retry_after else config.BACKOFF_BASE_SECONDS * (2 ** attempt)
                logger.warning("%d from %s (attempt %d/%d); backing off %.1fs",
                                resp.status_code, full_url, attempt + 1, config.MAX_RETRIES, sleep_s)
                time.sleep(sleep_s)
                continue

            content = resp.content
            content_type = resp.headers.get("Content-Type", "")
            path = self._digest_path(domain, full_url, content, content_type)
            if not path.exists():
                path.write_bytes(content)
            self._append_manifest({
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "url": full_url,
                "domain": domain,
                "status": resp.status_code,
                "sha256": path.stem,
                "path": str(path),
                "method": method,
                "cache_hit": False,
            })

            if resp.status_code >= 400:
                logger.warning("non-2xx status %d for %s (archived, not retrying further)",
                                resp.status_code, full_url)
            return FetchResult(url=full_url, status=resp.status_code, content=content,
                                headers=dict(resp.headers), path=path, cache_hit=False,
                                from_status_error=resp.status_code >= 400)

        raise RuntimeError(f"exhausted retries fetching {full_url}: {last_exc}")


def default_session(**kwargs) -> CachedSession:
    return CachedSession(**kwargs)


def main():
    logging.basicConfig(level=logging.INFO)
    s = default_session()
    r = s.get("https://www.sec.gov/cgi-bin/browse-edgar", params={"action": "getcompany", "company": "test", "type": "10-K", "count": "1"})
    print(f"status={r.status} cached_at={r.path} cache_hit={r.cache_hit}")


if __name__ == "__main__":
    main()
