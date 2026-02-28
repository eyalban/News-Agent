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
                "airbase_status": {"type": "string"},
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
                         "military_killed", "military_injured", "pilot_status", "airbase_status",
                         "active_alerts", "sources_used"],
            "additionalProperties": False,
        },
    },
}

# --- System Prompt ---

SYSTEM_PROMPT = """You are a military intelligence analyst producing a daily security brief about the Iran-Israel conflict. This report is for the family of an active-duty pilot. ACCURACY IS PARAMOUNT — a wrong number is worse than no number.

You will receive news article headlines AND full article text from the last 12 hours.

YOUR TASKS:
1. IDENTIFY all strike/attack events targeting Israel (missile, rocket, drone, ballistic, cruise).
   - Distinguish between strikes ON Israel vs. Israeli/US strikes on Iran — these are SEPARATE events.
   - Use timestamps, locations, and weapon types to distinguish unique events.
   - If multiple articles describe the same strike from different angles, count it ONCE.
   - total_launches = total number of projectiles/missiles/drones launched AT Israel (not by Israel).
2. EXTRACT casualty numbers ONLY from explicit statements in the text.
3. CHECK for any mention of Israeli Air Force (IAF/חה"א) pilots, aircrew, or air force personnel.
4. CHECK for any mention of Israeli air bases: Nevatim, Ramon, Ramat David, Hatzerim, Palmachim, Hatzor, Ovda, Tel Nof.
5. IDENTIFY active alerts or sirens.
6. DETERMINE threat status:
   - שקט: No strikes on Israel, no casualties, no alerts
   - מוגבר: Tensions, military movements, minor incidents
   - גבוה: Confirmed strikes on Israel, casualties, active alerts
   - קריטי: Major multi-wave attack on Israel, significant casualties

CRITICAL ACCURACY RULES — READ CAREFULLY:
- NEVER invent, estimate, or guess numbers. If an article says "casualties reported" but gives no count, set killed=0 and injured=0 — do NOT make up numbers.
- ONLY count casualties explicitly stated with numbers in the text (e.g., "3 killed", "12 wounded"). Vague phrases like "casualties reported" or "people hurt" without numbers = 0.
- NEVER classify casualties as military unless the text EXPLICITLY says "soldier", "military", "IDF", "servicemember", or similar. Default: if unspecified, count as civilian.
- For total_launches: ONLY use a number if the text explicitly states it (e.g., "Iran fired 180 ballistic missiles"). If no specific count is given, use 0 and list what you know in the strikes table.
- For interceptions: ONLY count if explicitly stated. Do not assume interceptions.
- If information is uncertain or not explicitly stated, USE ZERO or USE DEFAULT. Never fill in plausible-sounding numbers.
- The strikes table should list each UNIQUE strike event you can confirm from the text.

OUTPUT RULES:
- Times in Israel time (HH:MM) if available, or "—" if unknown.
- weapon_type in Hebrew: בליסטי, שיוט, רקטה, מל"ט, or original term.
- result in Hebrew: יורט, פגיעה, לא ידוע.
- pilot_status in Hebrew. Default: "לא דווח על פגיעה בטייסי חיל האוויר."
- airbase_status in Hebrew. Default: "לא דווח על פגיעה בבסיסי חיל האוויר."
- ALL text in Hebrew except source names (English).
- If nothing relevant found, return status שקט with all zeros."""


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

        # Allow longer summaries for better extraction
        if summary and len(summary) > 400:
            summary = summary[:400] + "..."

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
        "Analyze them and produce a structured security brief.\n\n"
        "REMINDERS:\n"
        "- Only count strikes/launches directed AT Israel (not Israeli strikes on Iran).\n"
        "- Only report casualty numbers you find explicitly stated in the article text.\n"
        "- If you cannot find a specific number, use 0 — NEVER guess.\n"
        "- Only classify casualties as military if the text explicitly says so.\n\n"
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
        "airbase_status": "לא דווח על פגיעה בבסיסי חיל האוויר.",
        "active_alerts": [],
        "sources_used": [],
    }
