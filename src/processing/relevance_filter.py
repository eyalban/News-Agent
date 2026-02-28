import logging

from src.config import ACTORS, EVENTS, HIGH_PRIORITY

logger = logging.getLogger(__name__)


def is_relevant(article: dict) -> bool:
    """Check if an article is relevant to the Iran-Israel conflict.

    An article is relevant if:
    - It matches a HIGH_PRIORITY phrase, OR
    - It contains at least one ACTOR keyword AND at least one EVENT keyword.
    """
    text = f"{article.get('title', '')} {article.get('summary', '')}".lower()

    # Check high-priority phrases first (match independently)
    for phrase in HIGH_PRIORITY:
        if phrase in text:
            return True

    # Check ACTOR + EVENT combination
    has_actor = any(actor in text for actor in ACTORS)
    has_event = any(event in text for event in EVENTS)

    return has_actor and has_event


def filter_relevant(articles: list[dict]) -> list[dict]:
    """Filter a list of articles to only those relevant to the conflict."""
    relevant = [a for a in articles if is_relevant(a)]
    logger.info(
        "Relevance filter: %d/%d articles passed", len(relevant), len(articles)
    )
    return relevant
