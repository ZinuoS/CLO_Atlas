import pandas as pd
import pytest

from src.cef import analysis_capital_machine as acm


@pytest.fixture(autouse=True)
def _patch_paths(tmp_path, monkeypatch):
    monkeypatch.setattr(acm, "SPLITS_PATH", tmp_path / "splits.parquet")
    monkeypatch.setattr(acm, "NAV_DISCLOSURES_PATH", tmp_path / "nav.parquet")
    monkeypatch.setattr(acm, "PRICES_PATH", tmp_path / "prices.parquet")
    return tmp_path


def test_cumulative_split_factor_is_one_with_no_splits_file():
    assert acm._cumulative_split_factor("OXLC", pd.Timestamp("2020-01-01")) == 1.0


def test_cumulative_split_factor_applies_future_split_only(tmp_path):
    splits = pd.DataFrame([{"ticker": "OXLC", "split_date": pd.Timestamp("2025-09-08"), "ratio": 0.2}])
    splits.to_parquet(acm.SPLITS_PATH, index=False)

    # A disclosure BEFORE the split must pick up the 0.2 ratio (it needs rescaling).
    assert acm._cumulative_split_factor("OXLC", pd.Timestamp("2020-04-30")) == pytest.approx(0.2)
    # A disclosure AFTER the split is already on the current basis.
    assert acm._cumulative_split_factor("OXLC", pd.Timestamp("2025-10-01")) == 1.0


def test_premium_history_rescales_pre_split_nav_to_avoid_absurd_premium(tmp_path):
    # Regression: without rescaling, a pre-split NAV of $2.72 compared
    # against Yahoo's retroactively split-adjusted $24.85 close produces a
    # nonsense 813% "premium" — this is the exact real case that surfaced
    # the bug (OXLC's 2025-09-08 1-for-5 reverse split).
    splits = pd.DataFrame([{"ticker": "OXLC", "split_date": pd.Timestamp("2025-09-08"), "ratio": 0.2}])
    splits.to_parquet(acm.SPLITS_PATH, index=False)

    nav = pd.DataFrame([{"ticker": "OXLC", "nav_as_of": "April 30, 2020", "nav_low": 2.67, "nav_high": 2.77,
                         "nav_mid": 2.72, "shares_outstanding": 87_000_000.0}])
    nav.to_parquet(acm.NAV_DISCLOSURES_PATH, index=False)

    prices = pd.DataFrame([{"ticker": "OXLC", "date": pd.Timestamp("2020-04-30"), "close": 24.85}])
    prices.to_parquet(acm.PRICES_PATH, index=False)

    result = acm.premium_history(fund="OXLC")
    assert len(result) == 1
    row = result.iloc[0]
    assert row["nav_mid"] == pytest.approx(13.6)  # 2.72 / 0.2
    assert row["premium_discount"] == pytest.approx(0.827, abs=0.01)  # ~83%, not ~813%


def test_incremental_issuance_diffs_within_era_not_across(tmp_path, monkeypatch):
    tape = pd.DataFrame([
        {"ticker": "OXLC", "filing_date": "2020-05-06", "period_start": "June 4, 2020", "period_end": "March 12, 2020",
         "shares_sold": 100, "net_proceeds_millions": 5.0},
        {"ticker": "OXLC", "filing_date": "2020-09-09", "period_start": "June 4, 2020", "period_end": "September 8, 2020",
         "shares_sold": 300, "net_proceeds_millions": 15.0},
        {"ticker": "OXLC", "filing_date": "2023-12-08", "period_start": "November 15, 2023", "period_end": "December 7, 2023",
         "shares_sold": 50, "net_proceeds_millions": 2.0},
    ])
    atm_path = tmp_path / "atm_tape.parquet"
    tape.to_parquet(atm_path, index=False)
    monkeypatch.setattr(acm, "ATM_TAPE_PATH", atm_path)

    out = acm.incremental_issuance(fund="OXLC")
    # Second row within the same era diffs against the first (300-100=200).
    second = out[out["filing_date"] == pd.Timestamp("2020-09-09")].iloc[0]
    assert second["incremental_shares"] == 200
    assert second["incremental_net_proceeds_millions"] == pytest.approx(10.0)
    # New era's first row is NOT diffed against the prior era's last value.
    new_era = out[out["filing_date"] == pd.Timestamp("2023-12-08")].iloc[0]
    assert new_era["incremental_shares"] == 50
