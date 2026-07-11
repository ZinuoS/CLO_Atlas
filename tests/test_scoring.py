import json

import pandas as pd
import pytest

from src.sentiment import scoring


def test_extract_clo_sections_windows_around_mentions():
    text = "Equity markets rallied. The CLO market showed resilient issuance. Rates were unchanged."
    sections = scoring.extract_clo_sections(text)
    assert len(sections) == 1
    assert "CLO" in sections[0]


def test_score_section_domain_without_lm_still_scores_vulnerability():
    out = scoring.score_section_domain("Contagion and fire sale risk are elevated.", lm=None)
    assert out["vulnerability_rate"] > 0
    assert out["lm_negative_rate"] is None


def test_additive_alarm_index_is_not_multiplicative():
    # A report with heavy mentions but non-negative measured tone must NOT
    # be zeroed out — the original bug this rewrite fixes.
    report_level = pd.DataFrame([
        {"institution": "Fed", "date": "2020-01-01", "mentions_per_1000": 5.0, "vulnerability_rate": 0.0, "lm_negative_rate": 0.0},
        {"institution": "Fed", "date": "2021-01-01", "mentions_per_1000": 1.0, "vulnerability_rate": 0.01, "lm_negative_rate": 0.02},
    ])
    out = scoring.additive_alarm_index(report_level)
    heavy_coverage_row = out[out["mentions_per_1000"] == 5.0].iloc[0]
    assert heavy_coverage_row["alarm_index_v2"] != 0.0


def test_institution_zscore_is_within_group():
    df = pd.DataFrame([
        {"institution": "Fed", "x": 1.0}, {"institution": "Fed", "x": 3.0},
        {"institution": "BIS", "x": 100.0}, {"institution": "BIS", "x": 300.0},
    ])
    z = scoring.institution_zscore(df, "x")
    # Fed's z-scores shouldn't be dragged toward BIS's much larger raw scale.
    assert abs(z.iloc[0]) < 2 and abs(z.iloc[1]) < 2


def test_coverage_table_counts_documents_by_institution_and_year():
    reports = pd.DataFrame([
        {"institution": "Fed", "date": "2020-05-01"},
        {"institution": "Fed", "date": "2020-11-01"},
        {"institution": "BIS", "date": "2020-03-01"},
    ])
    cov = scoring.coverage_table(reports)
    fed_2020 = cov[(cov["institution"] == "Fed") & (cov["year"] == 2020)]
    assert fed_2020.iloc[0]["n_documents"] == 2


def test_llm_rubric_score_cached_reads_existing_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(scoring, "LLM_RUBRIC_CACHE_DIR", tmp_path)
    excerpt = "CLO vulnerabilities remain elevated."
    import hashlib
    key = hashlib.sha256(excerpt.encode()).hexdigest()
    (tmp_path / f"sentiment_rubric_{key}.json").write_text(json.dumps({"alarm": 3, "stance": "risk-flagging", "evidence_quote": "vulnerabilities remain elevated"}))

    result = scoring.llm_rubric_score_cached(excerpt)
    assert result["alarm"] == 3


def test_llm_rubric_score_cached_raises_when_not_cached(tmp_path, monkeypatch):
    monkeypatch.setattr(scoring, "LLM_RUBRIC_CACHE_DIR", tmp_path)
    with pytest.raises(NotImplementedError):
        scoring.llm_rubric_score_cached("some excerpt never scored before")
