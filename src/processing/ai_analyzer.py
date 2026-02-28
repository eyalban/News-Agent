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
MAX_ARTICLES_FOR_AI = 80

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
                "casualty_details": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "description": {"type": "string"},
                            "location": {"type": "string"},
                            "status": {"type": "string"},
                        },
                        "required": ["description", "location", "status"],
                        "additionalProperties": False,
                    },
                },
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
                         "military_killed", "military_injured", "casualty_details",
                         "pilot_status", "airbase_status",
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
   - total_launches = number of INCOMING projectiles toward Israel (missiles, rockets, drones).
   - If articles report interceptions (e.g., "most were intercepted", "IDF intercepted 130"), use the stated number.
   - If multiple articles give DIFFERENT numbers for the same event, use the number from the most authoritative source (IDF > Reuters/AP > others).

   ⚠️ COMMON CONFUSION — READ CAREFULLY:
   - "200 Israeli aircraft" or "200 IAF jets" = Israeli planes striking Iran. This is NOT 200 launches AT Israel. Do NOT use this number for total_launches.
   - "500 targets struck in Iran" = Israeli/US offensive strikes. This is NOT incoming fire on Israel.
   - total_launches must ONLY reflect projectiles FIRED AT Israel (e.g., "Iran fired 40 ballistic missiles at Israel" → total_launches=40).
   - If no specific count of incoming projectiles is stated, use 0 and describe what you know in the strikes table rows.

3. CASUALTIES IN ISRAEL (killed/injured + casualty_details):
   - ONLY count casualties/injuries INSIDE Israel from attacks ON Israel.
   - Do NOT count casualties in Iran, Lebanon, Gaza, or other countries.
   - ONLY use numbers explicitly stated in articles. "casualties reported" without a number = 0.
   - Default: civilian. Only classify as military if article explicitly says soldier/military/IDF.
   - If one article says "1 killed" and another says "2 killed" about different events, ADD them.
   - If they describe the SAME event, use the higher/more recent number.

   CASUALTY DETAILS (casualty_details):
   - For each identified casualty or group, create an entry with any available metadata.
   - description: Hebrew text with whatever identifying info is available — name, age, gender.
     Examples: "אישה בת 40", "גבר בשנות ה-30", "עתי כהן אנג'ל, 74", "3 פצועים קל"
   - location: city/area in Hebrew (e.g., "תל אביב", "רמת גן", "חיפה")
   - status: "נהרג/ה" or "נפצע/ה קל/בינוני/קשה" or "נפצע/ה"
   - Only include details that are EXPLICITLY stated. Do not guess demographics.

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


CASUALTY_KEYWORDS = {"killed", "dead", "wounded", "injured", "hurt", "casualties", "fatalities"}


def _select_articles_for_ai(articles: list[dict], max_count: int) -> list[dict]:
    """Select articles for AI analysis, balancing enriched content and headline diversity.

    Strategy:
    1. First: articles enriched with full content (marked by content_fetcher)
    2. Then: headline articles containing casualty-related keywords (ensures numbers are captured)
    3. Then: remaining articles to fill quota (broad headline coverage)
    This ensures the AI gets detailed text + casualty-specific headlines + broad coverage.
    """
    enriched = []
    casualty_headlines = []
    other = []

    for article in articles:
        if article.get("enriched"):
            enriched.append(article)
        else:
            title_lower = article.get("title", "").lower()
            if any(kw in title_lower for kw in CASUALTY_KEYWORDS):
                casualty_headlines.append(article)
            else:
                other.append(article)

    selected = enriched[:max_count]
    remaining = max_count - len(selected)

    # Add casualty headlines next — these often have key numbers
    if remaining > 0:
        selected.extend(casualty_headlines[:remaining])
        remaining = max_count - len(selected)

    # Fill with remaining headlines for broad coverage
    if remaining > 0:
        selected.extend(other[:remaining])

    return selected


def analyze_all(articles: list[dict]) -> dict | None:
    """Analyze all articles in a SINGLE API call and return the synthesized report.

    This sends all article titles+summaries to OpenAI in one request,
    instead of making individual calls per article. Much faster and cheaper.

    Returns the synthesized report dict, or None if analysis fails.
    """
    if not articles:
        logger.info("No articles to analyze, returning quiet-day report")
        return _quiet_day_report()

    # Smart selection: prioritize enriched articles, then casualty headlines, then rest
    selected = _select_articles_for_ai(articles, MAX_ARTICLES_FOR_AI)
    enriched_count = sum(1 for a in selected if a.get("enriched"))
    casualty_count = sum(1 for a in selected if not a.get("enriched") and
                         any(kw in a.get("title", "").lower() for kw in CASUALTY_KEYWORDS))
    headline_count = len(selected) - enriched_count - casualty_count
    logger.info("Sending %d articles to OpenAI (%d enriched, %d casualty headlines, %d other headlines)...",
                len(selected), enriched_count, casualty_count, headline_count)

    articles_text = _format_articles_for_prompt(selected)
    user_content = (
        f"Here are {len(selected)} news articles from the last 12 hours. "
        "Analyze them and produce a structured security brief.\n\n"
        "IMPORTANT REMINDERS:\n"
        "- LAUNCHES: total_launches = ONLY projectiles/missiles fired AT Israel. "
        "'200 Israeli jets' or '500 targets in Iran' are ISRAELI OFFENSIVE operations — do NOT count as launches AT Israel. "
        "If articles say 'Iran fired 40 missiles at Israel', then total_launches=40.\n"
        "- STRIKES TABLE: Only attacks directed AT Israel (not Israeli strikes on Iran/others).\n"
        "- CASUALTIES: Search ALL articles for 'killed', 'dead', 'wounded', 'injured' WITH numbers. "
        "If article A says '1 killed' and article B says '20 wounded' about different events, ADD them. "
        "Same event → use highest number. Also extract identity details (name, age, gender, city) into casualty_details.\n"
        "- STATUS: Multi-wave attacks with casualties → קריטי.\n"
        "- HEADLINES: Short headlines often contain key numbers — extract them.\n\n"
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
        "casualty_details": [],
        "pilot_status": "לא דווח על פגיעה בטייסי חיל האוויר.",
        "airbase_status": "לא דווח על פגיעה בבסיסי חיל האוויר.",
        "active_alerts": [],
        "sources_used": [],
    }
