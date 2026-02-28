from datetime import datetime

import pytz

from src.config import BOSTON_TIMEZONE, ISRAEL_TIMEZONE

# Hebrew month names
HEBREW_MONTHS = {
    1: "ינואר", 2: "פברואר", 3: "מרס", 4: "אפריל",
    5: "מאי", 6: "יוני", 7: "יולי", 8: "אוגוסט",
    9: "ספטמבר", 10: "אוקטובר", 11: "נובמבר", 12: "דצמבר",
}

# Sources that were checked (shown on quiet days)
DEFAULT_SOURCES = [
    "IDF Spokesperson", "Times of Israel", "Jerusalem Post",
    "Ynetnews", "Reuters", "BBC", "Al Jazeera",
]


def format_report(report: dict, start_time: datetime, end_time: datetime) -> str:
    """Format a synthesized report dict into the Hebrew Format A text.

    Args:
        report: Synthesized report dict from ai_analyzer.synthesize_report.
        start_time: UTC start of lookback window.
        end_time: UTC end of lookback window.

    Returns:
        Formatted report string in Hebrew.
    """
    boston_tz = pytz.timezone(BOSTON_TIMEZONE)
    israel_tz = pytz.timezone(ISRAEL_TIMEZONE)

    now_boston = end_time.astimezone(boston_tz)
    start_boston = start_time.astimezone(boston_tz)

    date_str = f"{now_boston.day} ב{HEBREW_MONTHS[now_boston.month]} {now_boston.year}"
    period_str = (
        f"{start_boston.strftime('%d/%m %H:%M')} — "
        f"{now_boston.strftime('%d/%m %H:%M')} (שעון בוסטון)"
    )

    lines = []
    lines.append("=" * 44)
    lines.append(f"  תדריך ביטחוני יומי | {date_str}")
    lines.append(f"  תקופה: {period_str}")
    lines.append("=" * 44)
    lines.append("")
    lines.append(f"מצב: {report['status']}")
    lines.append("")

    # --- Strikes ---
    lines.append("--- תקיפות (12 שעות אחרונות) ---")
    strikes = report.get("strikes", [])
    total_launches = report.get("total_launches", 0)
    total_intercepted = report.get("total_intercepted", 0)
    total_impact = report.get("total_impact", 0)

    if total_launches == 0 and not strikes:
        lines.append("לא דווחו תקיפות בתקופה זו.")
    else:
        lines.append(f"סה\"כ: {total_launches} שיגורים | {total_intercepted} יורטו | {total_impact} פגיעות")
        lines.append("")
        if strikes:
            lines.append(f"{'שעה(IL)':<10}{'סוג':<11}{'יעד':<14}{'תוצאה'}")
            for s in strikes:
                time_il = s.get("time_israel", "—") or "—"
                wtype = s.get("weapon_type", "—") or "—"
                target = s.get("target_location", "—") or "—"
                result = s.get("result", "—") or "—"
                lines.append(f"{time_il:<10}{wtype:<11}{target:<14}{result}")
    lines.append("")

    # --- Casualties ---
    lines.append("--- נפגעים ---")
    killed = report.get("killed", 0)
    injured = report.get("injured", 0)
    civ_killed = report.get("civilian_killed", 0)
    civ_injured = report.get("civilian_injured", 0)
    mil_killed = report.get("military_killed", 0)
    mil_injured = report.get("military_injured", 0)

    if killed == 0 and injured == 0:
        lines.append("לא דווחו נפגעים בתקופה זו.")
    else:
        lines.append(f"הרוגים: {killed} | פצועים: {injured}")
        lines.append(f"אזרחים: {civ_killed} הרוגים, {civ_injured} פצועים | צבאיים: {mil_killed} הרוגים, {mil_injured} פצועים")
    lines.append("")

    # --- IAF Pilot Status ---
    lines.append("--- מצב טייסי חה\"א ---")
    pilot_status = report.get("pilot_status", "לא דווח על פגיעה בטייסי חיל האוויר.")
    lines.append(pilot_status)
    lines.append("")

    # --- Active Alerts ---
    lines.append("--- התרעות פעילות ---")
    alerts = report.get("active_alerts", [])
    if not alerts:
        lines.append("אין התרעות בזמן הדוח.")
    else:
        for alert in alerts:
            lines.append(f"• {alert}")
    lines.append("")

    # --- Sources ---
    lines.append("--- מקורות ---")
    sources = report.get("sources_used", [])
    if sources:
        lines.append("• " + "  • ".join(sources))
    else:
        lines.append("מקורות שנבדקו: " + ", ".join(DEFAULT_SOURCES) + ".")
        lines.append("לא נמצאו דיווחים רלוונטיים.")
    lines.append("")

    lines.append("=" * 44)
    lines.append("         סוף תדריך")
    lines.append("=" * 44)

    return "\n".join(lines)


def format_fallback_report(articles: list[dict], start_time: datetime, end_time: datetime) -> str:
    """Format a fallback report with raw headlines when AI is unavailable.

    Args:
        articles: List of relevant article dicts.
        start_time: UTC start of lookback window.
        end_time: UTC end of lookback window.

    Returns:
        Formatted fallback report string.
    """
    boston_tz = pytz.timezone(BOSTON_TIMEZONE)
    now_boston = end_time.astimezone(boston_tz)
    start_boston = start_time.astimezone(boston_tz)

    date_str = f"{now_boston.day} ב{HEBREW_MONTHS[now_boston.month]} {now_boston.year}"
    period_str = (
        f"{start_boston.strftime('%d/%m %H:%M')} — "
        f"{now_boston.strftime('%d/%m %H:%M')} (שעון בוסטון)"
    )

    lines = []
    lines.append("=" * 44)
    lines.append(f"  תדריך ביטחוני יומי | {date_str}")
    lines.append(f"  תקופה: {period_str}")
    lines.append("=" * 44)
    lines.append("")
    lines.append("⚠ סיכום AI לא זמין — כותרות גולמיות בלבד ⚠")
    lines.append("")

    if not articles:
        lines.append("לא נמצאו כתבות רלוונטיות בתקופה זו.")
    else:
        for i, article in enumerate(articles[:30], 1):
            source = article.get("source", "")
            title = article.get("title", "")
            link = article.get("link", "")
            lines.append(f"{i}. [{source}] {title}")
            if link:
                lines.append(f"   {link}")
            lines.append("")

    lines.append("=" * 44)
    lines.append("         סוף תדריך")
    lines.append("=" * 44)

    return "\n".join(lines)
