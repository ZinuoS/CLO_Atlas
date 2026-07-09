from src.sentiment.analysis_alarm_index import _CLO_MENTION_PATTERN


def test_clo_mention_pattern_matches_word_boundary_only():
    assert _CLO_MENTION_PATTERN.search("Banks hold CLO tranches.")
    assert _CLO_MENTION_PATTERN.search("CLOs grew rapidly.")
    assert not _CLO_MENTION_PATTERN.search("The market will close soon.")
    assert not _CLO_MENTION_PATTERN.search("Clocks and clouds are unrelated words.")


def test_clo_mention_pattern_case_insensitive():
    assert _CLO_MENTION_PATTERN.search("clo issuance rose")
    assert _CLO_MENTION_PATTERN.search("Clo issuance rose")
