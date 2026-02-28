import logging
import sys
from datetime import datetime, timedelta, timezone

import pytz

from src.config import (
    BOSTON_TIMEZONE,
    LOOKBACK_HOURS,
    SEND_WINDOW_START_HOUR,
    SEND_WINDOW_START_MIN,
    SEND_WINDOW_END_HOUR,
    SEND_WINDOW_END_MIN,
)
from src.sources.google_news_rss import fetch_google_news
from src.sources.rss_feeds import fetch_direct_feeds
from src.processing.relevance_filter import filter_relevant
from src.processing.deduplicator import deduplicate
from src.processing.ai_analyzer import analyze_all
from src.report.formatter import format_report, format_fallback_report
from src.delivery.email_sender import send_report

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)-5s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def is_within_send_window() -> bool:
    """Check if current Boston time is within the send window."""
    boston_tz = pytz.timezone(BOSTON_TIMEZONE)
    now_boston = datetime.now(boston_tz)
    start = now_boston.replace(
        hour=SEND_WINDOW_START_HOUR, minute=SEND_WINDOW_START_MIN, second=0, microsecond=0
    )
    end = now_boston.replace(
        hour=SEND_WINDOW_END_HOUR, minute=SEND_WINDOW_END_MIN, second=0, microsecond=0
    )
    return start <= now_boston <= end


def run(force: bool = False):
    """Main orchestrator pipeline.

    Args:
        force: If True, skip the send-window check (for testing).
    """
    # Step 1: Check send window
    if not force and not is_within_send_window():
        logger.info("Outside send window. Exiting.")
        return

    logger.info("=" * 50)
    logger.info("Starting Daily Security Brief generation")
    logger.info("=" * 50)

    # Step 2: Calculate lookback window
    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(hours=LOOKBACK_HOURS)
    logger.info("Lookback window: %s to %s (UTC)", start_time.strftime("%Y-%m-%d %H:%M"), end_time.strftime("%Y-%m-%d %H:%M"))

    # Step 3: Fetch from all sources
    logger.info("--- FETCH PHASE ---")
    google_articles = fetch_google_news(start_time, end_time)
    direct_articles = fetch_direct_feeds(start_time, end_time)
    all_articles = google_articles + direct_articles
    logger.info("Total articles fetched: %d", len(all_articles))

    # Step 4: Filter and deduplicate
    logger.info("--- FILTER PHASE ---")
    relevant = filter_relevant(all_articles)
    deduped = deduplicate(relevant)
    logger.info("After pipeline: %d articles", len(deduped))

    # Step 5: AI analysis
    logger.info("--- ANALYZE PHASE ---")
    report_data = analyze_all(deduped)

    # Step 6: Format report
    logger.info("--- FORMAT PHASE ---")
    if report_data is not None:
        report_text = format_report(report_data, start_time, end_time)
        status = report_data.get("status", "שקט")
    else:
        logger.warning("AI analysis failed, using fallback format")
        report_text = format_fallback_report(deduped, start_time, end_time)
        status = "לא ידוע"

    logger.info("Report generated:\n%s", report_text)

    # Step 7: Send email
    logger.info("--- DELIVER PHASE ---")
    boston_tz = pytz.timezone(BOSTON_TIMEZONE)
    now_boston = end_time.astimezone(boston_tz)
    date_str = now_boston.strftime("%d/%m")
    subject = f"תדריך ביטחוני | {date_str} | מצב: {status}"

    success = send_report(subject, report_text)
    if success:
        logger.info("Daily brief sent successfully!")
    else:
        logger.error("Failed to send daily brief email")
        sys.exit(1)


if __name__ == "__main__":
    # Allow --force flag for manual/test runs
    force = "--force" in sys.argv
    run(force=force)
