import pytest

from src.edgar.scrape_bdc_soi import parse_soi_report

FIXTURE_HTML = """
<html><body>
<table>
<tr><th>SCHEDULE OF INVESTMENTS</th><th></th><th>Mar. 31, 2026</th><th></th><th>Dec. 31, 2025</th><th></th></tr>
<tr><td>Investment, Identifier [Axis]: Acme Corp, First lien senior secured loan</td><td></td><td></td><td></td><td></td><td></td></tr>
<tr><td>Fair Value</td><td></td><td>$ 33.5</td><td></td><td>$ 30.0</td><td></td></tr>
<tr><td>Amortized Cost</td><td></td><td>$ 34.0</td><td></td><td>$ 30.5</td><td></td></tr>
<tr><td>Principal</td><td></td><td>35.0</td><td></td><td>31.0</td><td></td></tr>
<tr><td>Coupon</td><td></td><td>7.83%</td><td></td><td>7.50%</td><td></td></tr>
<tr><td>Spread</td><td></td><td>5.25%</td><td></td><td>5.00%</td><td></td></tr>
<tr><td>Investment, Identifier [Axis]: Beta Holdings LLC, Common stock</td><td></td><td></td><td></td><td></td><td></td></tr>
<tr><td>Fair Value</td><td></td><td>$ 12.0</td><td></td><td>$ 10.0</td><td></td></tr>
<tr><td>Shares/Units</td><td></td><td>500000</td><td></td><td>500000</td><td></td></tr>
""" + "\n".join(f"<tr><td>Filler row {i}</td><td></td><td></td><td></td><td></td><td></td></tr>" for i in range(100)) + """
</table>
</body></html>
"""


def test_parses_two_positions_two_periods():
    df = parse_soi_report(FIXTURE_HTML, "TESTBDC")
    acme = df[df["company"] == "Acme Corp"]
    assert len(acme) == 2  # current + prior period
    assert set(acme["period"]) == {"Mar. 31, 2026", "Dec. 31, 2025"}


def test_numeric_fields_parsed_from_dollar_and_percent_strings():
    df = parse_soi_report(FIXTURE_HTML, "TESTBDC")
    acme_current = df[(df["company"] == "Acme Corp") & (df["period"] == "Mar. 31, 2026")].iloc[0]
    assert acme_current["fair_value"] == pytest.approx(33.5)
    assert acme_current["amortized_cost"] == pytest.approx(34.0)
    assert acme_current["coupon"] == pytest.approx(7.83)
    assert acme_current["spread"] == pytest.approx(5.25)


def test_instrument_type_extracted_from_identifier():
    df = parse_soi_report(FIXTURE_HTML, "TESTBDC")
    acme = df[df["company"] == "Acme Corp"].iloc[0]
    assert "first lien" in acme["instrument_type"].lower()
    beta = df[df["company"] == "Beta Holdings LLC"].iloc[0]
    assert "common stock" in beta["instrument_type"].lower()


def test_no_identifier_rows_raises():
    with pytest.raises(ValueError):
        parse_soi_report("<table><tr><td>nothing relevant</td></tr></table>", "TESTBDC")
