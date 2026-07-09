from src.common import entity


def test_normalize_strips_legal_suffixes_and_punctuation():
    assert entity.normalize("Carlyle Global Market Strategies, LLC") == "carlyle global market strategies"
    assert entity.normalize("Ares Capital Corporation") == "ares capital"
    assert entity.normalize("  ") == ""


def test_exact_match():
    resolver = entity.EntityResolver(
        canonical_path=entity.CANONICAL_PATH.with_suffix(".test.parquet"),
        alias_path=entity.ALIAS_PATH.with_suffix(".test.parquet"),
    )
    resolver.bootstrap(["Carlyle GMS Finance, Inc."])
    result = resolver.resolve("Carlyle GMS Finance, Inc.")
    assert result.method == "exact"
    assert result.canonical_id is not None


def test_fuzzy_auto_accept_above_threshold():
    resolver = entity.EntityResolver(
        canonical_path=entity.CANONICAL_PATH.with_suffix(".test2.parquet"),
        alias_path=entity.ALIAS_PATH.with_suffix(".test2.parquet"),
    )
    resolver.bootstrap(["Ares Capital Corporation"])
    result = resolver.resolve("ARES CAPITAL CORP")
    assert result.method in ("fuzzy_auto", "exact")
    assert result.score is None or result.score >= entity.config.ENTITY_AUTO_ACCEPT_SCORE


def test_review_queue_band():
    resolver = entity.EntityResolver(
        canonical_path=entity.CANONICAL_PATH.with_suffix(".test3.parquet"),
        alias_path=entity.ALIAS_PATH.with_suffix(".test3.parquet"),
    )
    resolver.bootstrap(["Ares Capital Corporation"])
    result = resolver.resolve("Aries Capital Co")
    assert result.method in ("fuzzy_review", "fuzzy_auto", "unresolved")


def test_match_funnel_stats_sums_to_total():
    resolver = entity.EntityResolver(
        canonical_path=entity.CANONICAL_PATH.with_suffix(".test4.parquet"),
        alias_path=entity.ALIAS_PATH.with_suffix(".test4.parquet"),
    )
    resolver.bootstrap(["Carlyle GMS", "Ares Capital Corporation"])
    results = resolver.resolve_many(["Carlyle GMS", "Ares Capital Corp", "Brand New LLC"], source="test")
    stats = resolver.match_funnel_stats(results)
    assert stats["total"] == 3
    assert stats["exact"] + stats["alias"] + stats["fuzzy_auto"] + stats["fuzzy_review"] + stats["unresolved"] == 3
