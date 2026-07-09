import pandas as pd
import pytest

from src.common import cache


def test_write_read_roundtrip_with_provenance(tmp_path):
    df = pd.DataFrame({"deal": ["A", "B"], "par": [100.0, 200.0]})
    path = tmp_path / "sub" / "table.parquet"
    prov = cache.Provenance(source_urls=["https://example.com/a"], parser="test_parser", scrape_timestamp="2026-01-01T00:00:00Z")
    written = cache.write_parquet(df, path, prov)

    assert written == path
    roundtrip = cache.read_parquet(path)
    pd.testing.assert_frame_equal(roundtrip, df)

    sidecar = cache.read_provenance(path)
    assert sidecar["parser"] == "test_parser"
    assert sidecar["row_count"] == 2
    assert sidecar["source_urls"] == ["https://example.com/a"]


def test_read_parquet_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        cache.read_parquet(tmp_path / "does_not_exist.parquet")


def test_exists(tmp_path):
    path = tmp_path / "x.parquet"
    assert cache.exists(path) is False
    cache.write_parquet(pd.DataFrame({"a": [1]}), path, cache.Provenance(parser="t"))
    assert cache.exists(path) is True
