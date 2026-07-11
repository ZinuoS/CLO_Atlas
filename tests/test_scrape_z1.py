from unittest.mock import MagicMock

from src.common.http import CachedSession
from src.macro.scrape_z1 import scrape_z1_series


def _fake_session(csv_by_id: dict[str, bytes]) -> CachedSession:
    session = MagicMock(spec=CachedSession)

    def _get(url, params=None, **kwargs):
        series_id = params["id"]
        result = MagicMock()
        if series_id in csv_by_id:
            result.status = 200
            result.content = csv_by_id[series_id]
        else:
            result.status = 404
            result.content = b""
        return result

    session.get.side_effect = _get
    return session


def test_z1_series_tagged_with_fred_and_z1_ids():
    csv_by_id = {
        "BCNSDODNS": b"DATE,BCNSDODNS\n1945-10-01,44653\n2026-01-01,14453810\n",
        "NCBDBIQ027S": b"DATE,NCBDBIQ027S\n1945-10-01,24000\n2026-01-01,8982885\n",
    }
    session = _fake_session(csv_by_id)

    df = scrape_z1_series(session, series={
        "nonfin_corp_total_credit_market_debt": "BCNSDODNS",
        "nonfin_corp_debt_securities": "NCBDBIQ027S",
    })

    assert list(df.columns) == ["date", "value", "series", "series_id"]
    total = df[df["series"] == "nonfin_corp_total_credit_market_debt"]
    assert total["series_id"].iloc[0] == "BCNSDODNS"
    assert total["value"].tolist() == [44653.0, 14453810.0]


def test_loans_derivable_as_total_minus_securities():
    csv_by_id = {
        "BCNSDODNS": b"DATE,BCNSDODNS\n2026-01-01,14453810\n",
        "NCBDBIQ027S": b"DATE,NCBDBIQ027S\n2026-01-01,8982885\n",
    }
    session = _fake_session(csv_by_id)
    df = scrape_z1_series(session, series={
        "nonfin_corp_total_credit_market_debt": "BCNSDODNS",
        "nonfin_corp_debt_securities": "NCBDBIQ027S",
    })
    total = df[df["series"] == "nonfin_corp_total_credit_market_debt"]["value"].iloc[0]
    securities = df[df["series"] == "nonfin_corp_debt_securities"]["value"].iloc[0]
    assert total - securities == 5470925.0
