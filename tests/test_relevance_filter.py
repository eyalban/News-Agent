"""Tests for the relevance filter module."""

from src.processing.relevance_filter import is_relevant, filter_relevant


def _article(title: str, summary: str = "") -> dict:
    return {"title": title, "summary": summary, "source": "Test", "link": ""}


class TestIsRelevant:
    """Test individual article relevance checking."""

    def test_high_priority_match(self):
        assert is_relevant(_article("IAF pilot safe after mission over Iran"))

    def test_high_priority_nevatim(self):
        assert is_relevant(_article("Nevatim air base on high alert"))

    def test_actor_plus_event(self):
        assert is_relevant(_article("Iran launches missiles at Israel"))

    def test_hezbollah_attack(self):
        assert is_relevant(_article("Hezbollah fires rockets into northern Israel"))

    def test_houthi_drone(self):
        assert is_relevant(_article("Houthi drone intercepted near Eilat"))

    def test_actor_only_no_event(self):
        assert not is_relevant(_article("Iran's economy grows 3% in Q4"))

    def test_event_only_no_actor(self):
        assert not is_relevant(_article("North Korea tests ballistic missile"))

    def test_completely_irrelevant(self):
        assert not is_relevant(_article("Tech stocks rise on Wall Street"))

    def test_html_tags_stripped(self):
        """HTML in summary should be stripped before keyword matching."""
        article = _article("Breaking news", "<b>Iran</b> <a href='#'>strike</a> on <i>Israel</i>")
        assert is_relevant(article)

    def test_case_insensitive(self):
        assert is_relevant(_article("IRAN LAUNCHES MISSILES AT ISRAEL"))

    def test_summary_matches(self):
        """Relevance should check both title and summary."""
        article = _article("Breaking: Major escalation", "Iran attacked Israel with drones")
        assert is_relevant(article)

    def test_ceasefire_relevant(self):
        assert is_relevant(_article("Iran and Israel agree to ceasefire"))


class TestFilterRelevant:
    """Test batch filtering."""

    def test_filters_correctly(self):
        articles = [
            _article("Iran strikes Israel"),
            _article("Weather forecast for NYC"),
            _article("Hezbollah rockets hit Haifa"),
        ]
        result = filter_relevant(articles)
        assert len(result) == 2

    def test_empty_input(self):
        assert filter_relevant([]) == []

    def test_all_relevant(self):
        articles = [
            _article("Iran missile attack on Israel"),
            _article("IDF intercepts Iranian drones"),
        ]
        assert len(filter_relevant(articles)) == 2

    def test_none_relevant(self):
        articles = [
            _article("Stock market update"),
            _article("Weather in London"),
        ]
        assert len(filter_relevant(articles)) == 0
