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
                "key_developments": {
                    "type": "array",
                    "items": {"type": "string"},
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
                            "origin": {"type": "string"},
                            "target_location": {"type": "string"},
                            "result": {"type": "string"},
                        },
                        "required": ["time_israel", "weapon_type", "origin", "target_location", "result"],
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
            "required": ["status", "key_developments", "total_launches", "total_intercepted", "total_impact",
                         "strikes", "killed", "injured", "civilian_killed", "civilian_injured",
                         "military_killed", "military_injured", "pilot_status", "airbase_status",
                         "active_alerts", "sources_used"],
            "additionalProperties": False,
        },
    },
}

# --- System Prompt ---

SYSTEM_PROMPT = """You are a military intelligence analyst producing a daily security brief about the Iran-Israel conflict for the family of an active-duty Israeli Air Force pilot.

ACCURACY IS PARAMOUNT — a wrong number is worse than no number. This person's family depends on this report to know their loved one is safe.

You will receive news article headlines AND (when available) full article text from the last 12 hours. Some articles may only have headlines with brief snippets — extract what you can.

=== YOUR TASKS ===

1. KEY DEVELOPMENTS (key_developments):
   Write 2-5 short Hebrew sentences summarizing the most important events. Examples:
   - "ישראל וארה"ב תקפו מטרות באיראן"
   - "איראן שיגרה טילים בליסטיים לעבר ישראל"
   - "צפירות ברחבי הארץ"
   This gives the reader an instant overview before the detailed data.

2. STRIKES ON ISRAEL (strikes table + totals):
   - ONLY count strikes/projectiles launched AT Israel — NOT Israeli strikes on other countries.
   - Israeli strikes on Iran/Lebanon/Gaza should be mentioned in key_developments but NOT in the strikes table.
   - Each row in strikes = one confirmed strike event or wave. Use details from the articles.
   - origin = who launched it (e.g., "איראן", "חיזבאללה", "חות'ים", "חמאס")
   - If articles report a total number of missiles/rockets (e.g., "Iran launched 150 missiles"), use that for total_launches.
   - If articles report interceptions (e.g., "most were intercepted", "IDF intercepted 130"), use the stated number for total_intercepted.
   - If multiple articles give DIFFERENT numbers for the same event, use the number from the most authoritative source (IDF > Reuters/AP > others).

3. CASUALTIES IN ISRAEL (killed/injured):
   - ONLY count casualties/injuries INSIDE Israel from attacks ON Israel.
   - Do NOT count casualties in Iran, Lebanon, Gaza, or other countries.
   - ONLY use numbers explicitly stated in articles. "casualties reported" without a number = 0.
   - Default: civilian. Only classify as military if article explicitly says soldier/military/IDF.
   - If one article says "1 killed" and another says "2 killed" about different events, ADD them.
   - If they describe the SAME event, use the higher/more recent number.

4. PILOT STATUS (pilot_status):
   - Specifically check for ANY mention of Israeli Air Force / IAF / חה"א pilots, aircrew.
   - If pilots are mentioned participating in strikes but no harm reported, say: "טייסי חה"א השתתפו במבצע. לא דווח על פגיעה."
   - If no pilot info at all: "לא דווח על פגיעה בטייסי חיל האוויר."
   - If harm reported: describe exactly what was reported.

5. AIR BASE STATUS (airbase_status):
   - Check for: Nevatim, Ramon, Ramat David, Hatzerim, Palmachim, Hatzor, Ovda, Tel Nof.
   - If bases were targeted: describe what happened.
   - If bases mentioned but no damage: "בסיסי חה"א הוזכרו כיעד אך לא דווח על נזק."
   - Default: "לא דווח על פגיעה בבסיסי חיל האוויר."

6. ACTIVE ALERTS (active_alerts):
   - List active siren/alert areas mentioned in articles.
   - Format: ["צפירות באזור תל אביב", "צפירות בצפון הארץ"]

7. THREAT STATUS:
   - שקט: No strikes on Israel, no casualties, no alerts
   - מוגבר: Tensions, military movements, minor incidents, small rocket attacks
   - גבוה: Confirmed strikes on Israel, casualties, widespread alerts
   - קריטי: Major multi-wave attack, multiple killed, nationwide alerts

=== CRITICAL ACCURACY RULES ===
- NEVER invent numbers. If unsure, use 0.
- When articles conflict, prefer: IDF official statements > major wire services (Reuters, AP) > regional media.
- Distinguish CAREFULLY between strikes ON Israel vs BY Israel. The strikes table is ONLY for attacks ON Israel.
- ALL output text in Hebrew. Source names stay in English.
- Times in Israel time (HH:MM) if available, or "—" if unknown.
- weapon_type: בליסטי, שיוט, רקטה, מל"ט, or the stated type.
- result: יורט, פגיעה, לא ידוע."""


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

        # Allow longer summaries for better extraction — critical for accuracy
        if summary and len(summary) > 1500:
            summary = summary[:1500] + "..."

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
