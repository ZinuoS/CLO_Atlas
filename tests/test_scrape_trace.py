import io

import openpyxl
import pytest

from src.official.scrape_trace import parse_pxtables_clo_sheet


def _build_fixture_workbook() -> bytes:
    """Minimal CBO-CDO-CLO sheet mimicking FINRA's real layout: a price-stats
    block, then a $-volume block, then a trade-count block that reuses the
    same row labels (CUSTOMER BUY, etc.) — the case that broke the parser
    the first time (duplicate keys) before block-tracking was added.
    """
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "CBO-CDO-CLO"
    rows = [
        [None] * 12,
        [None, "FINRA-ICE DATA SERVICES: Structured Pricing Tables"] + [None] * 10,
        [None, None, "DATA AS OF: ", "2026-07-08"] + [None] * 8,
        [None, "PRICING TABLE: CBO/CDO/CLO"] + [None] * 10,
        [None, "Metric", "CBO/CDO/CLO", None, "AAA", None] + [None] * 6,
        [None, None, None, None, "PRE-2023", "2023-2026"] + [None] * 6,
        [None, "AVERAGE PRICE", 98.7, None, 100.1, 100.1] + [None] * 6,
        [None, "VOLUME OF TRADES (000'S)", 1128806.6, None, 405399.3, 247427] + [None] * 6,
        [None, "CUSTOMER BUY", 590750.4, None, 185948, 164757] + [None] * 6,
        [None, "NUMBER OF TRADES", 277, None, 73, 48] + [None] * 6,
        [None, "CUSTOMER BUY", 152, None, 44, 32] + [None] * 6,
    ]
    for row in rows:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_volume_and_trade_count_customer_buy_dont_collide():
    xlsx_bytes = _build_fixture_workbook()
    df = parse_pxtables_clo_sheet(xlsx_bytes)

    customer_buy_rows = df[(df["metric"] == "CUSTOMER BUY") & (df["rating_band"] == "AAA") & (df["vintage"] == "PRE-2023")]
    assert len(customer_buy_rows) == 2
    blocks = set(customer_buy_rows["block"])
    assert blocks == {"volume_usd_000s", "trade_count"}

    volume_row = customer_buy_rows[customer_buy_rows["block"] == "volume_usd_000s"].iloc[0]
    count_row = customer_buy_rows[customer_buy_rows["block"] == "trade_count"].iloc[0]
    assert volume_row["value"] == pytest.approx(185948)
    assert count_row["value"] == pytest.approx(44)


def test_price_stat_block_before_any_block_header():
    xlsx_bytes = _build_fixture_workbook()
    df = parse_pxtables_clo_sheet(xlsx_bytes)
    avg_price = df[(df["metric"] == "AVERAGE PRICE") & (df["rating_band"] == "AAA") & (df["vintage"] == "PRE-2023")]
    assert len(avg_price) == 1
    assert avg_price.iloc[0]["block"] == "price_stat"


def test_as_of_date_parsed():
    xlsx_bytes = _build_fixture_workbook()
    df = parse_pxtables_clo_sheet(xlsx_bytes)
    assert str(df["date"].iloc[0]) == "2026-07-08"


def test_no_rating_band_header_raises():
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "CBO-CDO-CLO"
    ws.append(["nothing", "relevant", "here"])
    buf = io.BytesIO()
    wb.save(buf)
    with pytest.raises(ValueError):
        parse_pxtables_clo_sheet(buf.getvalue())
