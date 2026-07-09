import pytest

from src.cef.scrape_filings import parse_nport_xml

FIXTURE_XML = """<?xml version="1.0"?>
<edgarSubmission>
  <formData>
    <genInfo>
      <repPdDate>2026-03-31</repPdDate>
    </genInfo>
    <invstOrSecs>
      <invstOrSec>
        <name>Dryden 53 CLO, Ltd.</name>
        <title>Secured Note - Class F</title>
        <cusip>26243EAL5</cusip>
        <balance>1664500</balance>
        <valUSD>126200</valUSD>
        <pctVal>0.0229</pctVal>
        <assetCat>ABS-CBDO</assetCat>
        <invCountry>KY</invCountry>
      </invstOrSec>
      <invstOrSec>
        <name>Some Corp Bond Inc</name>
        <title>Senior Note</title>
        <cusip>12345ABC0</cusip>
        <balance>500000</balance>
        <valUSD>495000</valUSD>
        <pctVal>0.01</pctVal>
        <assetCat>DBT</assetCat>
        <invCountry>US</invCountry>
      </invstOrSec>
      <invstOrSec>
        <name>Anchorage Capital CLO 1-R, Ltd.</name>
        <title>Anchorage Capital CLO 1-R - Sub Notes</title>
        <cusip>99999XYZ1</cusip>
        <balance>200000</balance>
        <valUSD>180000</valUSD>
        <pctVal>0.005</pctVal>
        <invCountry>KY</invCountry>
      </invstOrSec>
    </invstOrSecs>
  </formData>
</edgarSubmission>
"""


def test_parses_period_and_positions():
    df = parse_nport_xml(FIXTURE_XML, "TESTFUND")
    assert len(df) == 3
    assert (df["period"] == "2026-03-31").all()
    assert (df["fund"] == "TESTFUND").all()


def test_assetcat_clo_detected_by_structured_field():
    df = parse_nport_xml(FIXTURE_XML, "TESTFUND")
    dryden = df[df["cusip"] == "26243EAL5"].iloc[0]
    assert dryden["is_clo"] is True or dryden["is_clo"] == True  # noqa: E712
    assert dryden["clo_detection_method"] == "assetCat"


def test_non_clo_not_flagged():
    df = parse_nport_xml(FIXTURE_XML, "TESTFUND")
    corp = df[df["cusip"] == "12345ABC0"].iloc[0]
    assert corp["is_clo"] == False  # noqa: E712
    assert corp["clo_detection_method"] == "none"


def test_missing_assetcat_falls_back_to_name_regex():
    df = parse_nport_xml(FIXTURE_XML, "TESTFUND")
    anchorage = df[df["cusip"] == "99999XYZ1"].iloc[0]
    assert anchorage["is_clo"] == True  # noqa: E712
    assert anchorage["clo_detection_method"] == "name_regex"


def test_no_positions_raises():
    with pytest.raises(ValueError):
        parse_nport_xml("<edgarSubmission></edgarSubmission>", "TESTFUND")
