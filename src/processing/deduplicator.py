import logging
import re
from urllib.parse import urlparse, urlencode, parse_qs

logger = logging.getLogger(__name__)

# Source priority: lower index = higher priority
SOURCE_PRIORITY = [
    "IDF Spokesperson",
    "Times of Israel",
    "Jerusalem Post",
    "Ynetnews",
    "Reuters",
    "BBC",
    "Al Jazeera",
    "i24 News",
]


def _normalize_url(url: str) -> str:
    """Normalize URL by removing tracking parameters and fragments."""
    parsed = urlparse(url)
    # Remove common tracking params
    params = parse_qs(parsed.query)
    tracking_keys = {"utm_source", "utm_medium", "utm_campaign", "utm_content", "ref", "fbclid", "gclid"}
    clean_params = {k: v for k, v in params.items() if k.lower() not in tracking_keys}
    clean_query = urlencode(clean_params, doseq=True) if clean_params else ""
    normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
    if clean_query:
        normalized += f"?{clean_query}"
    return normalized.rstrip("/")


def _tokenize(text: str) -> set[str]:
    """Extract lowercase word tokens from text."""
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def _title_similarity(title_a: str, title_b: str) -> float:
    """Compute Jaccard similarity (intersection / union) between two titles.

    Uses union-based denominator to prevent short generic titles from
    absorbing longer, distinct titles as false duplicates.
    """
    tokens_a = _tokenize(title_a)
    tokens_b = _tokenize(title_b)
    if not tokens_a or not tokens_b:
        return 0.0
    intersection = tokens_a & tokens_b
    union = tokens_a | tokens_b
    return len(intersection) / len(union) if union else 0.0


def _source_rank(source: str) -> int:
    """Lower rank = higher priority."""
    source_lower = source.lower()
    for i, name in enumerate(SOURCE_PRIORITY):
        if name.lower() in source_lower:
            return i
    return len(SOURCE_PRIORITY)


def deduplicate(articles: list[dict], similarity_threshold: float = 0.6) -> list[dict]:
    """Remove duplicate articles based on URL and title similarity.

    When duplicates are found, keep the article from the higher-priority source.
    """
    # Phase 1: URL-based dedup
    seen_urls: dict[str, int] = {}  # normalized_url -> index in result
    url_deduped: list[dict] = []

    for article in articles:
        norm_url = _normalize_url(article.get("link", ""))
        if norm_url in seen_urls:
            # Keep the higher-priority source
            existing_idx = seen_urls[norm_url]
            if _source_rank(article["source"]) < _source_rank(url_deduped[existing_idx]["source"]):
                url_deduped[existing_idx] = article
        else:
            seen_urls[norm_url] = len(url_deduped)
            url_deduped.append(article)

    # Phase 2: Title-similarity dedup
    result: list[dict] = []
    for article in url_deduped:
        is_dup = False
        for i, existing in enumerate(result):
            if _title_similarity(article["title"], existing["title"]) >= similarity_threshold:
                # Keep higher-priority source
                if _source_rank(article["source"]) < _source_rank(existing["source"]):
                    result[i] = article
                is_dup = True
                break
        if not is_dup:
            result.append(article)

    logger.info("Deduplication: %d -> %d articles", len(articles), len(result))
    return result
