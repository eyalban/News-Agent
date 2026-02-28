import json
import logging
import time

from openai import OpenAI

from src.config import (
    OPENAI_API_KEY,
    OPENAI_MODEL,
    OPENAI_MAX_TOKENS,
    OPENAI_TEMPERATURE,
    MAX_RETRIES,
    RETRY_DELAY_SECONDS,
)

logger = logging.getLogger(__name__)

client = OpenAI(api_key=OPENAI_API_KEY)

# Maximum articles to send to OpenAI (keeps within token limits)
MAX_ARTICLES_FOR_AI = 60

# --- JSON Schema for Structured Output ---

REPORT_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "report_synthesis",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "enum": ["שקט", "מוגבר", "גבוה", "קריטי"],
                },
                "total_launches": {"type": "integer"},
                "total_intercepted": {"type": "integer"},
                "total_impact": {"type": "integer"},
                "strikes": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "time_israel": {"type": "string"},
                            "weapon_type": {"type": "string"},
                            "target_location": {"type": "string"},
                            "result": {"type": "string"},
                        },
                        "required": ["time_israel", "weapon_type", "target_location", "result"],
                        "additionalProperties": False,
                    },
                },
                "killed": {"type": "integer"},
                "injured": {"type": "integer"},
                "civilian_killed": {"type": "integer"},
                "civilian_injured": {"type": "integer"},
                "military_killed": {"type": "integer"},
                "military_injured": {"type": "integer"},
                "pilot_status": {"type": "string"},
                "active_alerts": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "sources_used": {
                    "type": "array",
                    "items": {"type": "string"},
                },
            },
            "required": ["status", "total_launches", "total_intercepted", "total_impact",
                         "strikes", "killed", "injured", "civilian_killed", "civilian_injured",
                         "military_killed", "military_injured", "pilot_status",
                         "active_alerts", "sources_used"],
            "additionalProperties": False,
        },
    },
}

# --- System Prompt ---

SYSTEM_PROMPT = """You are a military intelligence analyst producing a daily security brief about the Iran-Israel conflict.

You will receive a batch of news article headlines and summaries from the last 12 hours. Your job is to:

1. IDENTIFY all relevant strike events on Israel (missile, rocket, drone, ballistic) from the articles.
2. DEDUPLICATE: Multiple articles may report the same event. Count each real-world event only once.
3. EXTRACT casualty numbers. When multiple sources report different numbers, use the HIGHEST credible report.
4. PAY SPECIAL ATTENTION to any mention of Israeli Air Force (IAF/חה"א) pilots, aircrew, or air force personnel being harmed, injured, or killed.
5. IDENTIFY any active alerts or sirens mentioned.
6. DETERMINE the overall threat status:
   - שקט (CALM): No strikes, no casualties, no active alerts
   - מוגבר (ELEVATED): Diplomatic tensions, military movements, minor incidents, rocket attacks from Gaza/Lebanon
   - גבוה (HIGH): Confirmed strikes from Iran/proxies, casualties reported, active alerts
   - קריטי (CRITICAL): Major multi-wave Iranian attack, significant casualties, ongoing alerts

RULES:
- Extract ONLY facts explicitly stated in the articles. Never speculate.
- Times should be in Israel time (IST/IDT) in HH:MM format if available, or "—" if unknown.
- weapon_type in Hebrew: בליסטי, שיוט, רקטה, מל"ט, or the original term.
- result in Hebrew: יורט, פגיעה, לא ידוע.
- pilot_status in Hebrew. Default: "לא דווח על פגיעה בטייסי חיל האוויר."
- If there IS news about pilots, provide details in Hebrew.
- ALL text values in Hebrew except source names (which stay in English).
- If no relevant strike/conflict events are found, return status שקט with all zeros."""


def _call_openai(messages: list[dict], response_format: dict) -> dict | None:
    """Call OpenAI with retries. Returns parsed JSON dict or None."""
    for attempt in range(MAX_RETRIES):
        try:
            response = client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=messages,
                temperature=OPENAI_TEMPERATURE,
                max_tokens=OPENAI_MAX_TOKENS,
                response_format=response_format,
            )
            content = response.choices[0].message.content
            return json.loads(content)
        except Exception as e:
            logger.warning("OpenAI call attempt %d failed: %s", attempt + 1, e)
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY_SECONDS)
    return None


def _format_articles_for_prompt(articles: list[dict]) -> str:
    """Format articles into a compact text block for the AI prompt."""
    lines = []
    for i, article in enumerate(articles, 1):
        source = article.get("source", "Unknown")
        title = article.get("title", "No title")
        published = article.get("published", "")
        summary = article.get("summary", "")

        # Truncate summary to ~200 chars to keep prompt size reasonable
        if summary and len(summary) > 200:
            summary = summary[:200] + "..."

        entry = f"[{i}] ({source}) {title}"
        if published:
            entry += f" | Published: {published}"
        if summary:
            entry += f"\n    {summary}"
        lines.append(entry)

    return "\n".join(lines)


def analyze_all(articles: list[dict]) -> dict | None:
    """Analyze all articles in a SINGLE API call and return the synthesized report.

    This sends all article titles+summaries to OpenAI in one request,
    instead of making individual calls per article. Much faster and cheaper.

    Returns the synthesized report dict, or None if analysis fails.
    """
    if not articles:
        logger.info("No articles to analyze, returning quiet-day report")
        return _quiet_day_report()

    # Cap articles to avoid exceeding token limits
    if len(articles) > MAX_ARTICLES_FOR_AI:
        logger.info("Capping articles from %d to %d for AI analysis", len(articles), MAX_ARTICLES_FOR_AI)
        articles = articles[:MAX_ARTICLES_FOR_AI]

    logger.info("Sending %d articles to OpenAI in a single batch call...", len(articles))

    articles_text = _format_articles_for_prompt(articles)
    user_content = (
        f"Here are {len(articles)} news articles from the last 12 hours. "
        "Analyze them and produce a structured security brief:\n\n"
        + articles_text
    )

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]

    result = _call_openai(messages, REPORT_SCHEMA)

    if result:
        logger.info("AI analysis complete. Status: %s", result.get("status", "?"))
    else:
        logger.error("AI analysis failed after all retries")

    return result


def _quiet_day_report() -> dict:
    """Return a default quiet-day report structure."""
    return {
        "status": "שקט",
        "total_launches": 0,
        "total_intercepted": 0,
        "total_impact": 0,
        "strikes": [],
        "killed": 0,
        "injured": 0,
        "civilian_killed": 0,
        "civilian_injured": 0,
        "military_killed": 0,
        "military_injured": 0,
        "pilot_status": "לא דווח על פגיעה בטייסי חיל האוויר.",
        "active_alerts": [],
        "sources_used": [],
    }
