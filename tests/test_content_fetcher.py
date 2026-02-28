"""Tests for the content fetcher module."""

from src.sources.content_fetcher import (
    _is_fetchable_url,
    _extract_text_from_html,
)


class TestIsFetchableUrl:
    def test_twitter_blocked(self):
        assert not _is_fetchable_url("https://twitter.com/user/status/123")

    def test_x_blocked(self):
        assert not _is_fetchable_url("https://x.com/user/status/123")

    def test_facebook_blocked(self):
        assert not _is_fetchable_url("https://facebook.com/post/123")

    def test_youtube_blocked(self):
        assert not _is_fetchable_url("https://youtube.com/watch?v=abc")

    def test_google_news_blocked(self):
        assert not _is_fetchable_url("https://news.google.com/rss/articles/abc")

    def test_timesofisrael_allowed(self):
        assert _is_fetchable_url("https://www.timesofisrael.com/article-123")

    def test_jpost_allowed(self):
        assert _is_fetchable_url("https://www.jpost.com/article-123")

    def test_reuters_allowed(self):
        assert _is_fetchable_url("https://www.reuters.com/article/123")

    def test_bbc_allowed(self):
        assert _is_fetchable_url("https://www.bbc.com/news/article-123")

    def test_empty_url(self):
        assert not _is_fetchable_url("")

    def test_www_prefix_stripped(self):
        """www. should be stripped for domain comparison."""
        assert not _is_fetchable_url("https://www.twitter.com/user")


class TestExtractTextFromHtml:
    def test_strips_script_tags(self):
        html = "<p>Hello</p><script>alert('x')</script><p>World</p>"
        text = _extract_text_from_html(html)
        assert "alert" not in text
        assert "Hello" in text
        assert "World" in text

    def test_strips_style_tags(self):
        html = "<p>Content</p><style>.x{color:red}</style>"
        text = _extract_text_from_html(html)
        assert "color" not in text
        assert "Content" in text

    def test_strips_nav_footer(self):
        html = "<nav>Menu</nav><p>Article body</p><footer>Footer</footer>"
        text = _extract_text_from_html(html)
        assert "Menu" not in text
        assert "Footer" not in text
        assert "Article body" in text

    def test_unescapes_html_entities(self):
        html = "<p>Iran &amp; Israel &mdash; conflict</p>"
        text = _extract_text_from_html(html)
        assert "&amp;" not in text
        assert "Iran" in text

    def test_collapses_whitespace(self):
        html = "<p>  Multiple    spaces   here  </p>"
        text = _extract_text_from_html(html)
        assert "  " not in text

    def test_removes_html_comments(self):
        html = "<p>Before</p><!-- comment --><p>After</p>"
        text = _extract_text_from_html(html)
        assert "comment" not in text
