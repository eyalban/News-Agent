import logging
import re
import time
from html import unescape
from urllib.parse import urlparse

import requests

from src.config import REQUEST_TIMEOUT_SECONDS

logger = logging.getLogger(__name__)

# Max articles to fetch full content for
MAX_ARTICLES_TO_FETCH = 30

# Max chars of extracted text per article
MAX_CONTENT_LENGTH = 3000

# Domains known to block scraping — skip these
BLOCKED_DOMAINS = {"twitter.com", "x.com", "facebook.com", "instagram.com",
                   "youtube.com", "tiktok.com", "news.google.com"}

# Request headers
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "en-US,en;q=0.9",
}


def _extract_text_from_html(html: str) -> str:
    """Extract readable text from HTML. Lightweight, no BeautifulSoup needed."""
    text = re.sub(r"<script[^>]*>.*?</script>", " ", html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<style[^>]*>.*?</style>", " ", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<nav[^>]*>.*?</nav>", " ", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<footer[^>]*>.*?</footer>", " ", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<header[^>]*>.*?</header>", " ", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<!--.*?-->", " ", text, flags=re.DOTALL)
    text = re.sub(r"<[^>]+>", " ", text)
    text = unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _is_fetchable_url(url: str) -> bool:
    """Check if a URL can be fetched (not a Google News redirect)."""
    if not url:
        return False
    domain = urlparse(url).netloc.replace("www.", "")
    return domain not in BLOCKED_DOMAINS


def _fetch_one(url: str) -> str | None:
    """Fetch and extract text content from a single URL."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT_SECONDS, allow_redirects=True)
        resp.raise_for_status()

        content_type = resp.headers.get("content-type", "")
        if "html" not in content_type.lower():
            return None

        text = _extract_text_from_html(resp.text)

        if len(text) > MAX_CONTENT_LENGTH:
            text = text[:MAX_CONTENT_LENGTH] + "..."
        return text if len(text) > 100 else None

    except Exception as e:
        logger.debug("Failed to fetch content from %s: %s", url[:60], e)
        return None


def enrich_articles_with_content(articles: list[dict]) -> list[dict]:
    """Fetch full article text for articles that have fetchable URLs.

    Google News RSS URLs use JS-based redirects that cannot be resolved
    server-side. So we prioritize articles from direct RSS feeds
    (Times of Israel, Jerusalem Post, Ynetnews, etc.) which have real URLs.

    Modifies articles in-place by updating the 'summary' field.
    """
    # Separate articles with fetchable vs unfetchable URLs
    fetchable = []
    for article in articles:
        url = article.get("link", "")
        if _is_fetchable_url(url):
            fetchable.append(article)

    to_fetch = fetchable[:MAX_ARTICLES_TO_FETCH]
    enriched_count = 0

    if not to_fetch:
        logger.info("Content enrichment: no fetchable URLs found (all Google News redirects)")
        return articles

    logger.info("Fetching full content for %d articles with direct URLs...", len(to_fetch))

    for i, article in enumerate(to_fetch):
        url = article.get("link", "")
        content = _fetch_one(url)
        if content:
            article["summary"] = content
            enriched_count += 1

        if i < len(to_fetch) - 1:
            time.sleep(0.3)

    logger.info("Content enrichment: %d/%d articles got full text", enriched_count, len(to_fetch))
    return articles
