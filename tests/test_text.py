from unittest.mock import MagicMock

from src.common import text


def test_split_sentences_basic():
    sample = "The CLO market grew. Spreads tightened in Q3. Volatility returned in April."
    sentences = text.split_sentences(sample)
    assert len(sentences) == 3
    assert sentences[0] == "The CLO market grew."


def test_tokenize_lowercases_and_strips_punctuation():
    tokens = text.tokenize("CLO tranches, AAA-rated, aren't risk-free.")
    assert "clo" in tokens
    assert "aren't" in tokens or "aren" in tokens


def test_mention_rate_per_1000_counts_phrases_and_words():
    sample = "CLO CLO bonds are not CDOs. This is a CLO market update."
    rates = text.mention_rate_per_1000(sample, ["CLO"])
    assert rates["CLO"] > 0


def test_score_lm_net_sentiment_sign():
    lexicon = text.LMLexicon(
        positive={"resilient", "strong", "growth"},
        negative={"risk", "loss", "uncertainty"},
        uncertainty={"uncertainty", "may", "could"},
        litigious={"litigation", "lawsuit"},
    )
    positive_text = "The market showed resilient strong growth this quarter."
    negative_text = "Risk of loss and uncertainty dominated the quarter."
    pos_score = text.score_lm(positive_text, lexicon)
    neg_score = text.score_lm(negative_text, lexicon)
    assert pos_score.net_sentiment > 0
    assert neg_score.net_sentiment < 0


def test_collocates_finds_neighbors_within_window():
    sample = "The senior AAA tranche of the CLO deal priced tight this week."
    collocs = text.collocates(sample, "CLO", window=3)
    words = [w for w, _ in collocs]
    assert "tranche" in words or "deal" in words


def test_score_vulnerability_matches_stems_and_phrases():
    stems = ["vulnerab", "contagion", "fire sale"]
    high = "Vulnerabilities and contagion risk are elevated amid fire sale dynamics."
    low = "The market performed steadily with no notable stress."
    assert text.score_vulnerability(high, stems) > text.score_vulnerability(low, stems)
    assert text.score_vulnerability("", stems) == 0.0


def test_score_vulnerability_stem_matches_word_variants():
    # "vulnerab" should match vulnerable/vulnerability/vulnerabilities without
    # those exact forms being enumerated in the stem list.
    rate = text.score_vulnerability("Vulnerabilities in vulnerable, correlated portfolios.", ["vulnerab", "correlated"])
    assert rate > 0


def _fake_session(landing_html: bytes, csv_bytes: bytes):
    session = MagicMock()

    def _get(url, **kwargs):
        result = MagicMock()
        if "drive.google.com" in url:
            result.status = 200
            result.text.return_value = csv_bytes.decode()
        else:
            result.status = 200
            result.text.return_value = landing_html.decode()
        return result

    session.get.side_effect = _get
    return session


def test_fetch_lm_dictionary_discovers_drive_link_and_validates_header(tmp_path, monkeypatch):
    monkeypatch.setattr(text.config, "LM_DICTIONARY_PATH", tmp_path / "lm.csv")
    landing_html = b'''<p>CSV Format: <a href="https://drive.google.com/file/d/ABC123XYZ/view?usp=sharing">Loughran-McDonald_MasterDictionary_1993-2025.csv</a></p>'''
    csv_bytes = b"Word,Negative,Positive,Uncertainty,Litigious\nRISK,1,0,0,0\n"
    session = _fake_session(landing_html, csv_bytes)

    path = text.fetch_lm_dictionary(session)

    assert path.exists()
    assert "RISK" in path.read_text()
    sidecar = path.with_suffix(path.suffix + ".provenance.json")
    assert sidecar.exists()


def test_fetch_lm_dictionary_rejects_non_csv_response(tmp_path, monkeypatch):
    monkeypatch.setattr(text.config, "LM_DICTIONARY_PATH", tmp_path / "lm.csv")
    landing_html = b'''<p>CSV Format: <a href="https://drive.google.com/file/d/ABC123XYZ/view?usp=sharing">x.csv</a></p>'''
    interstitial_html = b"<html>Google Drive can't scan this file for viruses.</html>"
    session = _fake_session(landing_html, interstitial_html)

    try:
        text.fetch_lm_dictionary(session)
        assert False, "expected RuntimeError"
    except RuntimeError as exc:
        assert "doesn't look like" in str(exc)
