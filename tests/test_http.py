from unittest.mock import MagicMock

from src.common.http import CachedSession, RateLimiter


def _fake_response(status_code=200, content=b"hello", content_type="text/plain", headers=None):
    resp = MagicMock()
    resp.status_code = status_code
    resp.content = content
    resp.headers = {"Content-Type": content_type, **(headers or {})}
    return resp


def test_successful_fetch_archives_and_manifests(tmp_path):
    session = CachedSession(archive_dir=tmp_path)
    session.session.request = MagicMock(return_value=_fake_response())

    result = session.get("https://example.com/data.txt")

    assert result.status == 200
    assert result.content == b"hello"
    assert result.path.exists()
    manifest = (tmp_path / "_manifest.csv").read_text()
    assert "example.com" in manifest
    assert "https://example.com/data.txt" in manifest


def test_repeat_fetch_hits_cache_not_network(tmp_path):
    session = CachedSession(archive_dir=tmp_path)
    session.session.request = MagicMock(return_value=_fake_response())

    first = session.get("https://example.com/data.txt")
    assert first.cache_hit is False

    second = session.get("https://example.com/data.txt")
    assert second.cache_hit is True
    assert session.session.request.call_count == 1


def test_retries_on_429_then_succeeds(tmp_path):
    session = CachedSession(archive_dir=tmp_path)
    session.session.request = MagicMock(side_effect=[
        _fake_response(status_code=429, headers={"Retry-After": "0"}),
        _fake_response(status_code=200),
    ])

    result = session.get("https://example.com/retry.txt")

    assert result.status == 200
    assert session.session.request.call_count == 2


def test_force_refetch_bypasses_cache(tmp_path):
    session = CachedSession(archive_dir=tmp_path, force_refetch=True)
    session.session.request = MagicMock(return_value=_fake_response())

    session.get("https://example.com/data.txt")
    session.get("https://example.com/data.txt")

    assert session.session.request.call_count == 2


def test_rate_limiter_does_not_error_under_burst():
    limiter = RateLimiter(rate_per_sec=1000.0, burst=5)
    for _ in range(5):
        limiter.acquire()
