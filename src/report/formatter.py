from datetime import datetime

import pytz

from src.config import BOSTON_TIMEZONE, ISRAEL_TIMEZONE

# Hebrew month names
HEBREW_MONTHS = {
    1: "ינואר", 2: "פברואר", 3: "מרס", 4: "אפריל",
    5: "מאי", 6: "יוני", 7: "יולי", 8: "אוגוסט",
    9: "ספטמבר", 10: "אוקטובר", 11: "נובמבר", 12: "דצמבר",
}

DEFAULT_SOURCES = [
    "IDF Spokesperson", "Times of Israel", "Jerusalem Post",
    "Ynetnews", "Reuters", "BBC", "Al Jazeera",
]

STATUS_COLORS = {
    "שקט": "#2e7d32",      # green
    "מוגבר": "#f57f17",    # amber
    "גבוה": "#e65100",     # orange
    "קריטי": "#b71c1c",    # red
}

STATUS_EMOJI = {
    "שקט": "🟢",
    "מוגבר": "🟡",
    "גבוה": "🟠",
    "קריטי": "🔴",
}


def format_report(report: dict, start_time: datetime, end_time: datetime) -> str:
    """Format a synthesized report dict into an HTML email.

    Args:
        report: Synthesized report dict from ai_analyzer.
        start_time: UTC start of lookback window.
        end_time: UTC end of lookback window.

    Returns:
        HTML string for the email body.
    """
    boston_tz = pytz.timezone(BOSTON_TIMEZONE)

    now_boston = end_time.astimezone(boston_tz)
    start_boston = start_time.astimezone(boston_tz)

    date_str = f"{now_boston.day} ב{HEBREW_MONTHS[now_boston.month]} {now_boston.year}"
    period_str = (
        f"{start_boston.strftime('%d/%m %H:%M')} — "
        f"{now_boston.strftime('%d/%m %H:%M')} (שעון בוסטון)"
    )

    status = report.get("status", "שקט")
    status_color = STATUS_COLORS.get(status, "#333")
    status_emoji = STATUS_EMOJI.get(status, "")

    # --- Build strikes table ---
    strikes = report.get("strikes", [])
    total_launches = report.get("total_launches", 0)
    total_intercepted = report.get("total_intercepted", 0)
    total_impact = report.get("total_impact", 0)

    if total_launches == 0 and not strikes:
        strikes_html = '<p style="color:#555;">לא דווחו תקיפות בתקופה זו.</p>'
    else:
        strikes_html = f'<p><strong>סה"כ: {total_launches} שיגורים &nbsp;|&nbsp; {total_intercepted} יורטו &nbsp;|&nbsp; {total_impact} פגיעות</strong></p>'
        if strikes:
            rows = ""
            for s in strikes:
                time_il = s.get("time_israel", "—") or "—"
                wtype = s.get("weapon_type", "—") or "—"
                target = s.get("target_location", "—") or "—"
                result = s.get("result", "—") or "—"
                result_color = "#b71c1c" if result == "פגיעה" else ("#2e7d32" if result == "יורט" else "#555")
                rows += f"""<tr>
                    <td style="padding:4px 10px;border-bottom:1px solid #eee;">{time_il}</td>
                    <td style="padding:4px 10px;border-bottom:1px solid #eee;">{wtype}</td>
                    <td style="padding:4px 10px;border-bottom:1px solid #eee;">{target}</td>
                    <td style="padding:4px 10px;border-bottom:1px solid #eee;color:{result_color};font-weight:bold;">{result}</td>
                </tr>"""
            strikes_html += f"""<table style="width:100%;border-collapse:collapse;margin-top:6px;font-size:14px;">
                <thead>
                    <tr style="background:#f5f5f5;">
                        <th style="padding:6px 10px;text-align:right;border-bottom:2px solid #ccc;">שעה (IL)</th>
                        <th style="padding:6px 10px;text-align:right;border-bottom:2px solid #ccc;">סוג</th>
                        <th style="padding:6px 10px;text-align:right;border-bottom:2px solid #ccc;">יעד</th>
                        <th style="padding:6px 10px;text-align:right;border-bottom:2px solid #ccc;">תוצאה</th>
                    </tr>
                </thead>
                <tbody>{rows}</tbody>
            </table>"""

    # --- Casualties ---
    killed = report.get("killed", 0)
    injured = report.get("injured", 0)
    civ_killed = report.get("civilian_killed", 0)
    civ_injured = report.get("civilian_injured", 0)
    mil_killed = report.get("military_killed", 0)
    mil_injured = report.get("military_injured", 0)

    if killed == 0 and injured == 0:
        casualties_html = '<p style="color:#555;">לא דווחו נפגעים בתקופה זו.</p>'
    else:
        casualties_html = f"""<table style="border-collapse:collapse;font-size:14px;margin-top:4px;">
            <tr>
                <td style="padding:3px 12px;"></td>
                <td style="padding:3px 12px;font-weight:bold;text-align:center;">הרוגים</td>
                <td style="padding:3px 12px;font-weight:bold;text-align:center;">פצועים</td>
            </tr>
            <tr style="background:#f5f5f5;">
                <td style="padding:3px 12px;font-weight:bold;">אזרחים</td>
                <td style="padding:3px 12px;text-align:center;">{civ_killed}</td>
                <td style="padding:3px 12px;text-align:center;">{civ_injured}</td>
            </tr>
            <tr>
                <td style="padding:3px 12px;font-weight:bold;">צבאיים</td>
                <td style="padding:3px 12px;text-align:center;">{mil_killed}</td>
                <td style="padding:3px 12px;text-align:center;">{mil_injured}</td>
            </tr>
            <tr style="border-top:2px solid #ccc;">
                <td style="padding:3px 12px;font-weight:bold;">סה"כ</td>
                <td style="padding:3px 12px;text-align:center;font-weight:bold;">{killed}</td>
                <td style="padding:3px 12px;text-align:center;font-weight:bold;">{injured}</td>
            </tr>
        </table>"""

    # --- Pilot status ---
    pilot_status = report.get("pilot_status", "לא דווח על פגיעה בטייסי חיל האוויר.")
    pilot_is_clear = "לא דווח" in pilot_status
    pilot_icon = "✅" if pilot_is_clear else "⚠️"
    pilot_color = "#2e7d32" if pilot_is_clear else "#b71c1c"

    # --- Air base status ---
    airbase_status = report.get("airbase_status", "לא דווח על פגיעה בבסיסי חיל האוויר.")
    airbase_is_clear = "לא דווח" in airbase_status
    airbase_icon = "✅" if airbase_is_clear else "⚠️"
    airbase_color = "#2e7d32" if airbase_is_clear else "#b71c1c"

    # --- Alerts ---
    alerts = report.get("active_alerts", [])
    if not alerts:
        alerts_html = '<p style="color:#555;">אין התרעות בזמן הדוח.</p>'
    else:
        alerts_html = "<ul style='margin:4px 0;padding-right:20px;'>"
        for alert in alerts:
            alerts_html += f"<li>{alert}</li>"
        alerts_html += "</ul>"

    # --- Sources ---
    sources = report.get("sources_used", [])
    if sources:
        sources_html = " &bull; ".join(sources)
    else:
        sources_html = "מקורות שנבדקו: " + ", ".join(DEFAULT_SOURCES) + ". לא נמצאו דיווחים רלוונטיים."

    # RTL base style applied to every block
    rtl = "direction:rtl;text-align:right;"

    # --- Assemble full HTML ---
    html = f"""<!DOCTYPE html>
<html dir="rtl" lang="he">
<head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;font-family:Arial,Helvetica,sans-serif;background:#f0f0f0;{rtl}">
<div style="max-width:600px;margin:20px auto;background:#fff;border-radius:8px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.1);{rtl}">

    <!-- Header -->
    <div style="background:#1a237e;color:#fff;padding:16px 24px;{rtl}">
        <h1 style="margin:0;font-size:20px;font-weight:bold;{rtl}">🛡️ תדריך ביטחוני יומי</h1>
        <p style="margin:4px 0 0;font-size:13px;opacity:0.85;{rtl}">{date_str} &nbsp;|&nbsp; תקופה: {period_str}</p>
    </div>

    <!-- Status banner -->
    <div style="background:{status_color};color:#fff;padding:12px 24px;font-size:18px;font-weight:bold;{rtl}">
        {status_emoji} מצב: {status}
    </div>

    <div style="padding:20px 24px;{rtl}">

        <!-- Strikes -->
        <h2 style="font-size:16px;color:#1a237e;border-bottom:2px solid #1a237e;padding-bottom:6px;margin-top:0;{rtl}">
            🚀 תקיפות על ישראל (12 שעות אחרונות)
        </h2>
        {strikes_html}

        <!-- Casualties -->
        <h2 style="font-size:16px;color:#1a237e;border-bottom:2px solid #1a237e;padding-bottom:6px;{rtl}">
            🏥 נפגעים
        </h2>
        {casualties_html}

        <!-- Pilot Status -->
        <h2 style="font-size:16px;color:#1a237e;border-bottom:2px solid #1a237e;padding-bottom:6px;{rtl}">
            ✈️ מצב טייסי חה"א
        </h2>
        <p style="color:{pilot_color};font-weight:bold;font-size:15px;{rtl}">
            {pilot_icon} {pilot_status}
        </p>

        <!-- Air Base Status -->
        <h2 style="font-size:16px;color:#1a237e;border-bottom:2px solid #1a237e;padding-bottom:6px;{rtl}">
            🛩️ מצב בסיסי חה"א
        </h2>
        <p style="color:{airbase_color};font-weight:bold;font-size:15px;{rtl}">
            {airbase_icon} {airbase_status}
        </p>

        <!-- Active Alerts -->
        <h2 style="font-size:16px;color:#1a237e;border-bottom:2px solid #1a237e;padding-bottom:6px;{rtl}">
            🚨 התרעות פעילות
        </h2>
        {alerts_html}

    </div>

    <!-- Sources footer -->
    <div style="background:#f5f5f5;padding:12px 24px;font-size:12px;color:#777;border-top:1px solid #e0e0e0;{rtl}">
        <strong>מקורות:</strong> {sources_html}
    </div>

    <!-- Disclaimer -->
    <div style="padding:8px 24px;font-size:11px;color:#999;{rtl}">
        דוח זה מבוסס על כתבות חדשותיות בלבד. מספרים מופיעים רק כאשר דווחו במפורש במקורות.
    </div>

</div>
</body>
</html>"""

    return html


def format_fallback_report(articles: list[dict], start_time: datetime, end_time: datetime) -> str:
    """Format a fallback HTML report with raw headlines when AI is unavailable."""
    boston_tz = pytz.timezone(BOSTON_TIMEZONE)
    now_boston = end_time.astimezone(boston_tz)
    start_boston = start_time.astimezone(boston_tz)

    date_str = f"{now_boston.day} ב{HEBREW_MONTHS[now_boston.month]} {now_boston.year}"
    period_str = (
        f"{start_boston.strftime('%d/%m %H:%M')} — "
        f"{now_boston.strftime('%d/%m %H:%M')} (שעון בוסטון)"
    )

    if not articles:
        articles_html = '<p style="color:#555;">לא נמצאו כתבות רלוונטיות בתקופה זו.</p>'
    else:
        items = ""
        for article in articles[:30]:
            source = article.get("source", "")
            title = article.get("title", "")
            link = article.get("link", "")
            if link:
                items += f'<li style="margin-bottom:6px;"><strong>[{source}]</strong> <a href="{link}">{title}</a></li>'
            else:
                items += f'<li style="margin-bottom:6px;"><strong>[{source}]</strong> {title}</li>'
        articles_html = f'<ol style="padding-right:20px;">{items}</ol>'

    html = f"""<!DOCTYPE html>
<html dir="rtl" lang="he">
<head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;font-family:Arial,Helvetica,sans-serif;background:#f0f0f0;">
<div style="max-width:600px;margin:20px auto;background:#fff;border-radius:8px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.1);">

    <div style="background:#1a237e;color:#fff;padding:16px 24px;">
        <h1 style="margin:0;font-size:20px;">🛡️ תדריך ביטחוני יומי</h1>
        <p style="margin:4px 0 0;font-size:13px;opacity:0.85;">{date_str} &nbsp;|&nbsp; {period_str}</p>
    </div>

    <div style="background:#f57f17;color:#fff;padding:12px 24px;font-size:16px;font-weight:bold;">
        ⚠️ סיכום AI לא זמין — כותרות גולמיות בלבד
    </div>

    <div style="padding:20px 24px;">
        {articles_html}
    </div>

</div>
</body>
</html>"""

    return html
