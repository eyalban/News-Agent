"""Tests for the deduplication module."""

import pytest

from src.processing.deduplicator import (
    deduplicate,
    _normalize_url,
    _title_similarity,
    _source_rank,
)


def _article(title: str, source: str = "Test", link: str = "https://example.com/1") -> dict:
    return {"title": title, "source": source, "link": link, "summary": ""}


class TestNormalizeUrl:
    def test_strips_utm_params(self):
        url = "https://example.com/article?utm_source=twitter&utm_medium=social"
        assert _normalize_url(url) == "https://example.com/article"

    def test_strips_fbclid(self):
        url = "https://example.com/article?fbclid=abc123"
        assert _normalize_url(url) == "https://example.com/article"

    def test_preserves_meaningful_params(self):
        url = "https://example.com/article?id=123"
        assert "id=123" in _normalize_url(url)

    def test_strips_trailing_slash(self):
        url = "https://example.com/article/"
        assert _normalize_url(url) == "https://example.com/article"

    def test_strips_fragment(self):
        url = "https://example.com/article#section"
        assert "#" not in _normalize_url(url)


class TestTitleSimilarity:
    def test_identical_titles(self):
        assert _title_similarity("Iran fires missiles at Israel", "Iran fires missiles at Israel") == 1.0

    def test_completely_different(self):
        sim = _title_similarity("Weather in London today", "Stock market crashes hard")
        assert sim < 0.2

    def test_similar_titles_above_threshold(self):
        """Similar titles should have Jaccard > 0.6."""
        sim = _title_similarity(
            "Iran fires missiles at Israel",
            "Iran fires rockets at Israel",
        )
        assert sim >= 0.6

    def test_distinct_titles_below_threshold(self):
        """Distinct titles about different events should be < 0.6."""
        sim = _title_similarity(
            "Iran fires missiles at Israel",
            "Israel strikes back at Iran nuclear facilities",
        )
        assert sim < 0.6

    def test_short_generic_vs_long_specific(self):
        """Short generic title should NOT absorb long specific one (Jaccard protects)."""
        sim = _title_similarity(
            "Iran warns Israel",
            "Iran warns Israel of massive nuclear retaliation after base strikes",
        )
        # Jaccard denominator is the union, so short title won't match the many extra tokens
        assert sim < 0.6

    def test_empty_title(self):
        assert _title_similarity("", "Iran attack") == 0.0

    def test_both_empty(self):
        assert _title_similarity("", "") == 0.0


class TestSourceRank:
    def test_idf_highest_priority(self):
        assert _source_rank("IDF Spokesperson") == 0

    def test_toi_high_priority(self):
        assert _source_rank("Times of Israel") == 1

    def test_unknown_source_lowest(self):
        rank = _source_rank("Random Blog")
        assert rank == len([
            "IDF Spokesperson", "Times of Israel", "Jerusalem Post",
            "Ynetnews", "Reuters", "BBC", "Al Jazeera", "i24 News",
        ])

    def test_case_insensitive_matching(self):
        assert _source_rank("times of israel") == _source_rank("Times of Israel")


class TestDeduplicate:
    def test_url_dedup(self):
        """Same URL → keep higher priority source."""
        articles = [
            _article("Iran strikes", "Random Blog", "https://example.com/1"),
            _article("Iran strikes", "Times of Israel", "https://example.com/1"),
        ]
        result = deduplicate(articles)
        assert len(result) == 1
        assert result[0]["source"] == "Times of Israel"

    def test_title_dedup(self):
        """Similar titles, different URLs → deduplicated."""
        articles = [
            _article("Iran fires missiles at Israel", "Reuters", "https://reuters.com/1"),
            _article("Iran fires rockets at Israel", "BBC", "https://bbc.com/1"),
        ]
        result = deduplicate(articles)
        assert len(result) == 1
        # Reuters has higher priority than BBC
        assert result[0]["source"] == "Reuters"

    def test_distinct_titles_preserved(self):
        """Different stories should both be kept."""
        articles = [
            _article("Iran fires missiles at Israel", "Reuters", "https://reuters.com/1"),
            _article("Israel economy grows 5% this quarter", "BBC", "https://bbc.com/2"),
        ]
        result = deduplicate(articles)
        assert len(result) == 2

    def test_url_tracking_params_deduped(self):
        """Same article with different tracking params → deduplicated."""
        articles = [
            _article("Story", "Source A", "https://example.com/1?utm_source=twitter"),
            _article("Story", "Source B", "https://example.com/1?utm_source=facebook"),
        ]
        result = deduplicate(articles)
        assert len(result) == 1

    def test_empty_input(self):
        assert deduplicate([]) == []

    def test_single_article(self):
        articles = [_article("Iran attacks")]
        assert len(deduplicate(articles)) == 1
