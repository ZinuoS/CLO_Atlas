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
