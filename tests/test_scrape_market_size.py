from unittest.mock import MagicMock

from src.common.http import CachedSession
from src.macro.scrape_market_size import scrape_market_size_series


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


def test_market_size_series_tidy_frame():
    csv_by_id = {
        "ASCFBL": b"DATE,ASCFBL\n2026-01-01,17071119\n",
        "GFDEBTN": b"DATE,GFDEBTN\n2026-01-01,39065421\n",
    }
    session = _fake_session(csv_by_id)

    df = scrape_market_size_series(session, series={
        "corporate_and_foreign_bonds": "ASCFBL", "treasury_total_public_debt": "GFDEBTN",
    })

    assert list(df.columns) == ["date", "value", "series", "series_id"]
    assert set(df["series"]) == {"corporate_and_foreign_bonds", "treasury_total_public_debt"}
    treas = df[df["series"] == "treasury_total_public_debt"]
    assert treas["value"].iloc[0] == 39065421.0
