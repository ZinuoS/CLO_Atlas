from unittest.mock import MagicMock

from src.common.http import CachedSession
from src.macro.scrape_fred import scrape_fred_series


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


def test_tidy_frame_has_series_alias_and_numeric_value():
    csv_by_id = {
        "FEDFUNDS": b"DATE,FEDFUNDS\n2020-01-01,1.55\n2020-02-01,1.58\n",
        "USREC": b"DATE,USREC\n2020-01-01,0\n2020-02-01,0\n",
    }
    session = _fake_session(csv_by_id)

    df = scrape_fred_series(session, series={"FEDFUNDS": "FEDFUNDS", "USREC": "USREC"})

    assert list(df.columns) == ["date", "value", "series", "series_id"]
    assert set(df["series"]) == {"FEDFUNDS", "USREC"}
    fedfunds = df[df["series"] == "FEDFUNDS"]
    assert fedfunds["value"].tolist() == [1.55, 1.58]


def test_missing_value_coerced_to_nan_not_dropped():
    csv_by_id = {"SOFR": b"DATE,SOFR\n2020-01-01,.\n2020-01-02,0.05\n"}
    session = _fake_session(csv_by_id)

    df = scrape_fred_series(session, series={"SOFR": "SOFR"})

    assert len(df) == 2
    assert df["value"].isna().sum() == 1
    assert df["value"].iloc[1] == 0.05


def test_failed_series_is_skipped_not_fatal():
    csv_by_id = {"FEDFUNDS": b"DATE,FEDFUNDS\n2020-01-01,1.55\n"}
    session = _fake_session(csv_by_id)

    df = scrape_fred_series(session, series={"FEDFUNDS": "FEDFUNDS", "BOGUS": "BOGUS_ID"})

    assert set(df["series"]) == {"FEDFUNDS"}
