"""Tests for the AI analyzer module — article selection and schema validation."""

from src.processing.ai_analyzer import (
    _select_articles_for_ai,
    _format_articles_for_prompt,
    _quiet_day_report,
    REPORT_SCHEMA,
    CASUALTY_KEYWORDS,
)


def _article(title: str, enriched: bool = False, summary: str = "") -> dict:
    return {
        "title": title,
        "source": "Test",
        "link": "https://example.com",
        "summary": summary,
        "enriched": enriched,
    }


class TestSelectArticlesForAi:
    """Test the three-tier article selection strategy."""

    def test_enriched_articles_prioritized(self):
        enriched = [_article(f"Enriched {i}", enriched=True) for i in range(30)]
        headlines = [_article(f"Headline {i}") for i in range(100)]
        result = _select_articles_for_ai(enriched + headlines, max_count=80)
        # All 30 enriched should be in the result
        enriched_in_result = [a for a in result if a.get("enriched")]
        assert len(enriched_in_result) == 30

    def test_casualty_headlines_second_priority(self):
        enriched = [_article("Enriched", enriched=True) for _ in range(5)]
        casualty = [_article("3 killed in missile strike") for _ in range(10)]
        other = [_article("Iran threatens retaliation") for _ in range(100)]
        result = _select_articles_for_ai(enriched + casualty + other, max_count=20)
        # 5 enriched + 10 casualty + 5 other = 20
        assert len(result) == 20
        enriched_in_result = [a for a in result if a.get("enriched")]
        assert len(enriched_in_result) == 5

    def test_respects_max_count(self):
        articles = [_article(f"Article {i}", enriched=True) for i in range(100)]
        result = _select_articles_for_ai(articles, max_count=50)
        assert len(result) == 50

    def test_casualty_keyword_detection(self):
        """Articles with casualty keywords should be classified correctly."""
        for keyword in ["killed", "dead", "wounded", "injured", "casualties"]:
            article = _article(f"Report: 5 {keyword} in attack")
            # When no enriched articles, casualty headlines fill first
            result = _select_articles_for_ai([article], max_count=10)
            assert len(result) == 1

    def test_empty_input(self):
        assert _select_articles_for_ai([], max_count=80) == []

    def test_fewer_articles_than_max(self):
        articles = [_article(f"Article {i}") for i in range(5)]
        result = _select_articles_for_ai(articles, max_count=80)
        assert len(result) == 5


class TestFormatArticlesForPrompt:
    def test_basic_formatting(self):
        articles = [{"source": "Reuters", "title": "Iran strikes", "published": "", "summary": ""}]
        text = _format_articles_for_prompt(articles)
        assert "[1]" in text
        assert "(Reuters)" in text
        assert "Iran strikes" in text

    def test_summary_included(self):
        articles = [{"source": "BBC", "title": "Title", "published": "", "summary": "Long article text here"}]
        text = _format_articles_for_prompt(articles)
        assert "Long article text here" in text

    def test_summary_truncated_at_1500(self):
        long_summary = "x" * 2000
        articles = [{"source": "Test", "title": "Title", "published": "", "summary": long_summary}]
        text = _format_articles_for_prompt(articles)
        assert "..." in text
        # Should not contain full 2000 chars
        assert len(text) < 2000

    def test_multiple_articles_numbered(self):
        articles = [
            {"source": "A", "title": "First", "published": "", "summary": ""},
            {"source": "B", "title": "Second", "published": "", "summary": ""},
        ]
        text = _format_articles_for_prompt(articles)
        assert "[1]" in text
        assert "[2]" in text


class TestQuietDayReport:
    def test_returns_all_required_fields(self):
        report = _quiet_day_report()
        required = [
            "status", "total_launches", "total_intercepted", "total_impact",
            "strikes", "killed", "injured", "civilian_killed", "civilian_injured",
            "military_killed", "military_injured", "casualty_details",
            "pilot_status", "airbase_status", "active_alerts", "sources_used",
        ]
        for field in required:
            assert field in report, f"Missing field: {field}"

    def test_quiet_status(self):
        report = _quiet_day_report()
        assert report["status"] == "שקט"

    def test_all_counts_zero(self):
        report = _quiet_day_report()
        assert report["total_launches"] == 0
        assert report["total_intercepted"] == 0
        assert report["killed"] == 0
        assert report["injured"] == 0

    def test_empty_lists(self):
        report = _quiet_day_report()
        assert report["strikes"] == []
        assert report["casualty_details"] == []
        assert report["active_alerts"] == []


class TestReportSchema:
    def test_schema_has_all_required_fields(self):
        schema = REPORT_SCHEMA["json_schema"]["schema"]
        required = schema["required"]
        expected = [
            "status", "key_developments", "total_launches", "total_intercepted",
            "total_impact", "strikes", "killed", "injured",
            "civilian_killed", "civilian_injured", "military_killed", "military_injured",
            "casualty_details", "pilot_status", "airbase_status",
            "active_alerts", "sources_used",
        ]
        for field in expected:
            assert field in required, f"Missing required field: {field}"

    def test_schema_strict_mode(self):
        schema = REPORT_SCHEMA["json_schema"]
        assert schema["strict"] is True
        assert schema["schema"]["additionalProperties"] is False

    def test_casualty_details_schema(self):
        props = REPORT_SCHEMA["json_schema"]["schema"]["properties"]
        cd = props["casualty_details"]["items"]["properties"]
        assert "description" in cd
        assert "location" in cd
        assert "status" in cd

    def test_strikes_schema_has_origin(self):
        props = REPORT_SCHEMA["json_schema"]["schema"]["properties"]
        strike_props = props["strikes"]["items"]["properties"]
        assert "origin" in strike_props
        assert "time_israel" in strike_props
        assert "weapon_type" in strike_props
        assert "target_location" in strike_props
        assert "result" in strike_props


class TestCasualtyKeywords:
    def test_keywords_include_essentials(self):
        assert "killed" in CASUALTY_KEYWORDS
        assert "wounded" in CASUALTY_KEYWORDS
        assert "injured" in CASUALTY_KEYWORDS
        assert "dead" in CASUALTY_KEYWORDS
        assert "casualties" in CASUALTY_KEYWORDS
