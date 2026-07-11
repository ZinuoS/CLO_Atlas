from src.cef.analysis_portfolio_style import _shelf_name


def test_shelf_name_strips_series_number_and_entity_suffix():
    assert _shelf_name("Octagon Investment Partners 27, Ltd.") == "Octagon Investment Partners"


def test_shelf_name_strips_trailing_clo_and_entity_suffix():
    # Number-before-"CLO" orderings (e.g. "Dryden 53 CLO") only lose the
    # trailing "CLO, Ltd." — the number stays, since this is a lightweight
    # proxy, not full natural-language parsing (documented in the module).
    assert _shelf_name("Dryden 53 CLO, Ltd.") == "Dryden 53"


def test_shelf_name_strips_year_dash_suffix():
    assert _shelf_name("CIFC Funding 2019-III, Ltd.") == "CIFC Funding"


def test_shelf_name_strips_refi_marker():
    assert _shelf_name("HarbourView CLO VII-R, Ltd.") == "HarbourView"
