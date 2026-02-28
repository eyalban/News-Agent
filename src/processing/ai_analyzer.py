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

# --- JSON Schemas for Structured Outputs ---

ARTICLE_ANALYSIS_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "article_analysis",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "is_relevant": {"type": "boolean"},
                "category": {
                    "type": "string",
                    "enum": ["strike", "casualties", "pilot_status", "alert",
                             "diplomatic", "military_movement", "other"],
                },
                "strikes": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "time_israel": {"type": ["string", "null"]},
                            "weapon_type": {"type": ["string", "null"]},
                            "target_location": {"type": ["string", "null"]},
                            "result": {"type": ["string", "null"]},
                            "launched_by": {"type": ["string", "null"]},
                        },
                        "required": ["time_israel", "weapon_type", "target_location", "result", "launched_by"],
                        "additionalProperties": False,
                    },
                },
                "casualties": {
                    "type": ["object", "null"],
                    "properties": {
                        "killed": {"type": "integer"},
                        "injured": {"type": "integer"},
                        "civilian_killed": {"type": "integer"},
                        "civilian_injured": {"type": "integer"},
                        "military_killed": {"type": "integer"},
                        "military_injured": {"type": "integer"},
                    },
                    "required": ["killed", "injured", "civilian_killed", "civilian_injured",
                                 "military_killed", "military_injured"],
                    "additionalProperties": False,
                },
                "pilot_report": {
                    "type": ["object", "null"],
                    "properties": {
                        "has_pilot_news": {"type": "boolean"},
                        "details": {"type": ["string", "null"]},
                    },
                    "required": ["has_pilot_news", "details"],
                    "additionalProperties": False,
                },
                "active_alerts": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "summary_sentence": {"type": "string"},
                "source_name": {"type": "string"},
            },
            "required": ["is_relevant", "category", "strikes", "casualties",
                         "pilot_report", "active_alerts", "summary_sentence", "source_name"],
            "additionalProperties": False,
        },
    },
}

SYNTHESIS_SCHEMA = {
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

# --- System Prompts ---

EXTRACTION_SYSTEM_PROMPT = """You are a military intelligence analyst extracting structured data from news articles about the Iran-Israel conflict.

RULES:
- Extract ONLY facts explicitly stated in the article. Never speculate or infer.
- If a piece of information is not mentioned, use null.
- Times should be in Israel time (IST/IDT) in HH:MM format if available.
- weapon_type should be one of: בליסטי, שיוט, רקטה, מל"ט, or the original term if unclear.
- result should be one of: יורט, פגיעה, לא ידוע.
- Pay special attention to any mention of pilots, aircrew, or air force personnel.
- For casualties, distinguish between civilian and military where possible. Use 0 if a category is explicitly not mentioned.
- is_relevant should be false for articles about diplomacy-only or unrelated conflicts."""

SYNTHESIS_SYSTEM_PROMPT = """You are a military intelligence analyst producing a daily security brief synthesis.

You will receive structured extractions from multiple news articles about the Iran-Israel conflict.

Your task:
1. Aggregate all strike events, removing duplicates (same event reported by multiple sources).
2. Determine total casualties by taking the HIGHEST reported numbers (not summing duplicates).
3. Determine the overall threat status:
   - שקט (CALM): No strikes, no casualties, no active alerts
   - מוגבר (ELEVATED): Diplomatic tensions, military movements, minor incidents
   - גבוה (HIGH): Confirmed strikes, casualties reported, active alerts
   - קריטי (CRITICAL): Major multi-wave attack, significant casualties, ongoing alerts
4. For pilot_status: Report in Hebrew. Default: "לא דווח על פגיעה בטייסי חיל האוויר." If there IS news about pilots, provide details in Hebrew.
5. Deduplicate strikes: if multiple sources report the same strike (same time, same location), keep only one entry.
6. List all source names that contributed information.

Output ALL text values in Hebrew except for source names (which stay in English)."""


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


def analyze_article(article: dict) -> dict | None:
    """Extract structured data from a single article using OpenAI.

    Returns the parsed analysis dict, or None on failure.
    """
    user_content = (
        f"Source: {article['source']}\n"
        f"Title: {article['title']}\n"
        f"Published: {article.get('published', 'unknown')}\n"
        f"Content: {article.get('summary', 'No content available')}\n"
    )

    messages = [
        {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]

    return _call_openai(messages, ARTICLE_ANALYSIS_SCHEMA)


def synthesize_report(analyses: list[dict]) -> dict | None:
    """Synthesize all article analyses into a single report structure.

    Args:
        analyses: List of successful article analysis dicts.

    Returns:
        Synthesized report dict, or None on failure.
    """
    if not analyses:
        # Return a quiet-day report
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

    user_content = (
        "Here are the extracted analyses from all relevant articles. "
        "Synthesize them into a single report:\n\n"
        + json.dumps(analyses, ensure_ascii=False, indent=2)
    )

    messages = [
        {"role": "system", "content": SYNTHESIS_SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]

    return _call_openai(messages, SYNTHESIS_SCHEMA)


def analyze_all(articles: list[dict]) -> dict | None:
    """Full analysis pipeline: analyze each article, then synthesize.

    Returns the synthesized report dict, or None if synthesis fails.
    """
    if not articles:
        logger.info("No articles to analyze, returning quiet-day report")
        return synthesize_report([])

    logger.info("Analyzing %d articles with OpenAI...", len(articles))
    analyses = []
    for i, article in enumerate(articles):
        logger.info("  Analyzing article %d/%d: %s", i + 1, len(articles), article["title"][:60])
        result = analyze_article(article)
        if result and result.get("is_relevant"):
            analyses.append(result)

    logger.info("OpenAI analysis: %d/%d articles were relevant", len(analyses), len(articles))
    logger.info("Synthesizing final report...")
    return synthesize_report(analyses)
