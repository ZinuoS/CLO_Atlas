from pathlib import Path

from src.cef.scrape_capital_actions import _ATM_SALES_PATTERN, _PREFERRED_SERIES_PATTERN, _normalize_series_name

FIXTURES = Path(__file__).parent / "fixtures"


def test_atm_sales_pattern_matches_real_oxlc_language():
    text = (FIXTURES / "oxlc_424b3_atm_sample.txt").read_text()
    match = _ATM_SALES_PATTERN.search(text)
    assert match is not None
    start, end, shares, gross, gross_unit, net, net_unit = match.groups()
    assert start == "November 12, 2024"
    assert end == "June 10, 2025"
    assert shares == "127,496,226"
    assert gross == "629.2" and gross_unit == "million"
    assert net == "625.9" and net_unit == "million"


def test_atm_sales_pattern_crosses_sentence_boundary():
    # Regression: the source text has a period between "...offering." and
    # "The total amount of capital raised" — an earlier version of this
    # regex used [^.]*? there, which can never cross a literal period.
    text = "From May 1, 2024 to June 1, 2024, we sold a total of 1,000 shares of common stock pursuant to the offering. The total amount of capital raised was approximately $10.0 million and net proceeds were approximately $9.5 million."
    assert _ATM_SALES_PATTERN.search(text) is not None


def test_preferred_series_pattern_matches_real_ecc_language():
    text = (FIXTURES / "ecc_424b3_preferred_sample.txt").read_text()
    matches = _PREFERRED_SERIES_PATTERN.findall(text)
    assert len(matches) == 3
    coupons = {m[0] for m in matches}
    assert coupons == {"6.50", "6.75", "8.00"}


def test_normalize_series_name_collapses_whitespace_and_case():
    assert _normalize_series_name("Series\nC") == "SERIES C"
    assert _normalize_series_name("  Series   A ") == "SERIES A"
    assert _normalize_series_name("SERIES A") == "SERIES A"
