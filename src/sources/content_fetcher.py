import logging
import re
import time
from html import unescape

import requests

from src.config import REQUEST_TIMEOUT_SECONDS, INTER_REQUEST_DELAY_SECONDS

logger = logging.getLogger(__name__)

# Max articles to fetch full content for
MAX_ARTICLES_TO_FETCH = 25

# Max chars of extracted text per article
MAX_CONTENT_LENGTH = 1500

# Domains known to block scraping (skip these)
BLOCKED_DOMAINS = {"twitter.com", "x.com", "facebook.com", "instagram.com"}

# Request headers to look like a real browser
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "en-US,en;q=0.9",
}


def _extract_text_from_html(html: str) -> str:
    """Extract readable text from HTML using basic regex.

    This is a lightweight alternative to BeautifulSoup that avoids
    an extra dependency. It strips tags, scripts, styles, and normalizes whitespace.
    """
    # Remove scripts and styles
    text = re.sub(r"<script[^>]*>.*?</script>", " ", html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<style[^>]*>.*?</style>", " ", text, flags=re.DOTALL | re.IGNORECASE)
    # Remove HTML comments
    text = re.sub(r"<!--.*?-->", " ", text, flags=re.DOTALL)
    # Remove tags
    text = re.sub(r"<[^>]+>", " ", text)
    # Decode HTML entities
    text = unescape(text)
    # Normalize whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _resolve_google_news_url(url: str) -> str:
    """Google News RSS links redirect through Google. Follow the redirect."""
    if "news.google.com" in url:
        try:
            resp = requests.head(url, headers=HEADERS, timeout=10, allow_redirects=True)
            return resp.url
        except Exception:
            return url
    return url


def _fetch_one(url: str) -> str | None:
    """Fetch and extract text content from a single URL."""
    try:
        # Skip blocked domains
        from urllib.parse import urlparse
        domain = urlparse(url).netloc.replace("www.", "")
        if domain in BLOCKED_DOMAINS:
            return None

        resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT_SECONDS, allow_redirects=True)
        resp.raise_for_status()

        # Only process HTML pages
        content_type = resp.headers.get("content-type", "")
        if "html" not in content_type.lower():
            return None

        text = _extract_text_from_html(resp.text)

        # Return up to MAX_CONTENT_LENGTH chars
        if len(text) > MAX_CONTENT_LENGTH:
            text = text[:MAX_CONTENT_LENGTH] + "..."
        return text if len(text) > 100 else None  # Skip very short extractions

    except Exception as e:
        logger.debug("Failed to fetch content from %s: %s", url[:60], e)
        return None


def enrich_articles_with_content(articles: list[dict]) -> list[dict]:
    """Fetch full article text for the top articles.

    Modifies articles in-place by updating the 'summary' field with
    the full article text when available.

    Args:
        articles: List of article dicts (already filtered and deduped).

    Returns:
        The same list with enriched content.
    """
    to_fetch = articles[:MAX_ARTICLES_TO_FETCH]
    enriched_count = 0

    logger.info("Fetching full content for up to %d articles...", len(to_fetch))

    for i, article in enumerate(to_fetch):
        url = article.get("link", "")
        if not url:
            continue

        # Resolve Google News redirects
        resolved_url = _resolve_google_news_url(url)

        content = _fetch_one(resolved_url)
        if content:
            article["summary"] = content
            enriched_count += 1

        # Politeness delay (but shorter than RSS fetching)
        if i < len(to_fetch) - 1:
            time.sleep(0.5)

    logger.info("Content enrichment: %d/%d articles got full text", enriched_count, len(to_fetch))
    return articles
