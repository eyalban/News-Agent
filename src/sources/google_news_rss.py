import logging
import time
from datetime import datetime, timezone
from urllib.parse import urlencode

import feedparser
from dateutil import parser as dateparser

from src.config import (
    GOOGLE_NEWS_BASE,
    GOOGLE_NEWS_PARAMS,
    GOOGLE_NEWS_QUERIES,
    GOOGLE_NEWS_SITE_QUERIES,
    INTER_REQUEST_DELAY_SECONDS,
    REQUEST_TIMEOUT_SECONDS,
)

logger = logging.getLogger(__name__)


def _build_url(query: str) -> str:
    params = {**GOOGLE_NEWS_PARAMS, "q": query}
    return f"{GOOGLE_NEWS_BASE}?{urlencode(params)}"


def _parse_feed(url: str) -> list[dict]:
    """Fetch and parse a single Google News RSS feed URL."""
    try:
        feed = feedparser.parse(
            url,
            request_headers={"User-Agent": "NewsAgent/1.0"},
        )
        if feed.bozo and not feed.entries:
            logger.warning("Feed parse error for %s: %s", url, feed.bozo_exception)
            return []

        articles = []
        for entry in feed.entries:
            pub_date = None
            if hasattr(entry, "published"):
                try:
                    pub_date = dateparser.parse(entry.published)
                    if pub_date and pub_date.tzinfo is None:
                        pub_date = pub_date.replace(tzinfo=timezone.utc)
                except (ValueError, TypeError):
                    pass

            articles.append({
                "title": entry.get("title", ""),
                "link": entry.get("link", ""),
                "published": pub_date,
                "summary": entry.get("summary", ""),
                "source": entry.get("source", {}).get("title", "Google News"),
            })
        return articles
    except Exception as e:
        logger.error("Failed to fetch Google News RSS %s: %s", url, e)
        return []


def fetch_google_news(start_time: datetime, end_time: datetime) -> list[dict]:
    """Fetch articles from Google News RSS for all configured queries.

    Args:
        start_time: UTC datetime for the start of the lookback window.
        end_time: UTC datetime for the end of the lookback window.

    Returns:
        List of article dicts with keys: title, link, published, summary, source.
    """
    all_queries = GOOGLE_NEWS_QUERIES + GOOGLE_NEWS_SITE_QUERIES
    all_articles = []

    for i, query in enumerate(all_queries):
        url = _build_url(query)
        logger.info("Fetching Google News RSS: query %d/%d — %s", i + 1, len(all_queries), query[:50])
        articles = _parse_feed(url)

        # Filter by date window
        for article in articles:
            if article["published"] is None:
                # Include articles without dates (better safe than sorry)
                all_articles.append(article)
            elif start_time <= article["published"] <= end_time:
                all_articles.append(article)

        if i < len(all_queries) - 1:
            time.sleep(INTER_REQUEST_DELAY_SECONDS)

    logger.info("Google News RSS: fetched %d articles total", len(all_articles))
    return all_articles
