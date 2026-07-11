from pathlib import Path

from src.anatomy.scrape_circular import parse_circular

FIXTURE = Path(__file__).parent / "fixtures" / "hps_circular_excerpt.txt"


def test_parse_circular_extracts_real_trigger_tables():
    text = FIXTURE.read_text()
    params = parse_circular(text)

    assert params["reinvestment_end_month"] == "April 2030"
    assert "2027" in params["non_call_end"]
    assert params["ic_triggers_pct"] == {"A/B": 115.0, "C": 110.0, "D": 105.0}
    assert params["oc_triggers_pct"] == {"A/B": 121.58, "C": 113.95, "D": 106.68, "E": 103.2}
    assert params["ccc_limit_pct"] == 7.5
    assert params["interest_diversion_trigger_pct"] == 103.7


def test_parse_circular_citation_is_present():
    params = parse_circular("no matches in this text at all")
    assert params["citation"]["deal_name"].startswith("HPS Loan Management")
    assert params["non_call_end"] is None
    assert params["oc_triggers_pct"] is None
