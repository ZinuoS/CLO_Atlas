from pathlib import Path

import pytest

from src.etf.scrape_holdings import parse_janus_henderson_table

FIXTURE = Path(__file__).parent / "fixtures" / "janus_henderson_holdings_sample.html"


def test_parses_known_good_rows_and_skips_malformed_and_cash_lines():
    html = FIXTURE.read_text()
    df = parse_janus_henderson_table(html, "JAAA")

    assert len(df) == 2
    assert set(df["cusip"]) == {"48254LAN5", "00038KBA8"}

    kkr = df[df["cusip"] == "48254LAN5"].iloc[0]
    assert kkr["fund"] == "JAAA"
    assert kkr["tranche_ticker"] == "KKR 35A"
    assert kkr["manager_raw"] == "KKR"
    assert kkr["par"] == pytest.approx(249_004_000)
    assert kkr["market_value"] == pytest.approx(251_551_067)
    assert kkr["weight"] == pytest.approx(0.88)
    assert kkr["price"] == pytest.approx(251_551_067 / 249_004_000 * 100)
    assert str(kkr["date"]) == "2026-07-07"


def test_raises_on_table_with_no_rows():
    with pytest.raises(ValueError):
        parse_janus_henderson_table("<table></table>", "JAAA")


def test_raises_when_no_table_present():
    with pytest.raises(ValueError):
        parse_janus_henderson_table("<html><body>no table here</body></html>", "JAAA")
