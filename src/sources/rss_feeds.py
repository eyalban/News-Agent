import logging
import time
from datetime import datetime, timezone

import feedparser
from dateutil import parser as dateparser

from src.config import DIRECT_RSS_FEEDS, INTER_REQUEST_DELAY_SECONDS

logger = logging.getLogger(__name__)


def fetch_direct_feeds(start_time: datetime, end_time: datetime) -> list[dict]:
    """Fetch articles from direct RSS feeds, filtered by date window.

    Args:
        start_time: UTC datetime for the start of the lookback window.
        end_time: UTC datetime for the end of the lookback window.

    Returns:
        List of article dicts with keys: title, link, published, summary, source.
    """
    all_articles = []
    feed_names = list(DIRECT_RSS_FEEDS.keys())

    for i, (name, url) in enumerate(DIRECT_RSS_FEEDS.items()):
        logger.info("Fetching direct RSS: %s", name)
        try:
            feed = feedparser.parse(
                url,
                request_headers={"User-Agent": "NewsAgent/1.0"},
            )
            if feed.bozo and not feed.entries:
                logger.warning("Feed parse error for %s: %s", name, feed.bozo_exception)
                continue

            count = 0
            for entry in feed.entries:
                pub_date = None
                for date_field in ("published", "updated", "created"):
                    if hasattr(entry, date_field):
                        try:
                            parsed = dateparser.parse(getattr(entry, date_field))
                            if parsed is not None:
                                if parsed.tzinfo is None:
                                    parsed = parsed.replace(tzinfo=timezone.utc)
                                pub_date = parsed
                                break
                        except (ValueError, TypeError):
                            continue

                # Skip articles outside the time window
                if pub_date is not None and not (start_time <= pub_date <= end_time):
                    continue

                all_articles.append({
                    "title": entry.get("title", ""),
                    "link": entry.get("link", ""),
                    "published": pub_date,
                    "summary": entry.get("summary", ""),
                    "source": name,
                })
                count += 1

            logger.info("  %s: %d articles in time window", name, count)
        except Exception as e:
            logger.error("Failed to fetch RSS feed %s: %s", name, e)

        if i < len(feed_names) - 1:
            time.sleep(INTER_REQUEST_DELAY_SECONDS)

    logger.info("Direct RSS feeds: fetched %d articles total", len(all_articles))
    return all_articles
