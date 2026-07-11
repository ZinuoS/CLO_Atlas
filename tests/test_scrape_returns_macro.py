from pathlib import Path

from src.macro.scrape_returns import (_parse_ishares_characteristics, _parse_janus_characteristics,
                                        _to_pct, _to_years)

FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_ishares_characteristics():
    html = (FIXTURES / "ishares_characteristics_sample.html").read_text()
    parsed = _parse_ishares_characteristics(html)
    assert parsed["Effective Duration"] == "5.77 yrs"
    assert parsed["Average Yield to Maturity"] == "4.81%"


def test_parse_janus_characteristics():
    html = (FIXTURES / "janus_henderson_characteristics_sample.html").read_text()
    parsed = _parse_janus_characteristics(html)
    assert parsed["Effective Duration"] == "0.04"
    assert parsed["Yield to Worst"] == "5.09%"


def test_to_years_and_to_pct_parse_numbers_out_of_units():
    assert _to_years("5.77 yrs") == 5.77
    assert _to_years("0.04") == 0.04
    assert _to_years(None) is None
    assert _to_pct("4.81%") == 0.0481
    assert _to_pct(None) is None
