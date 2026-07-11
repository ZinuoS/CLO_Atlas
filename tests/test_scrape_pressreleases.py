import pandas as pd

from src.sentiment.scrape_pressreleases import classify_pricing_announcements


def test_classifies_deal_named_pricing_announcement():
    headlines = pd.DataFrame([
        {"title": "CVC Credit Successfully Priced Apidos LVII, A $550 Mln Collateralized Loan Obligation Vehicle",
         "source": "TradingView", "published": "Tue, 07 Jul 2026"},
    ])
    tape = classify_pricing_announcements(headlines)
    assert len(tape) == 1
    assert tape.iloc[0]["manager"] == "CVC Credit"
    assert tape.iloc[0]["deal"] == "Apidos LVII"
    assert tape.iloc[0]["size_usd_millions"] == 550.0


def test_classifies_pricing_announcement_without_deal_name():
    headlines = pd.DataFrame([
        {"title": "CTM Asset Management Prices $408 Million Collateralized Loan Obligation",
         "source": "Business Wire", "published": "Mon, 01 Jun 2026"},
    ])
    tape = classify_pricing_announcements(headlines)
    assert len(tape) == 1
    assert tape.iloc[0]["manager"] == "CTM Asset Management"
    assert tape.iloc[0]["deal"] is None
    assert tape.iloc[0]["size_usd_millions"] == 408.0


def test_converts_billions_to_millions():
    headlines = pd.DataFrame([
        {"title": "Ares Prices $1.2 Billion Collateralized Loan Obligation", "source": "PR Newswire", "published": ""},
    ])
    tape = classify_pricing_announcements(headlines)
    assert tape.iloc[0]["size_usd_millions"] == 1200.0


def test_non_clo_headlines_are_not_classified():
    headlines = pd.DataFrame([
        {"title": "Acme Corp Prices $500 Million Bond Offering", "source": "PR Newswire", "published": ""},
    ])
    tape = classify_pricing_announcements(headlines)
    assert tape.empty


def test_empty_input_returns_empty_frame():
    tape = classify_pricing_announcements(pd.DataFrame())
    assert tape.empty
