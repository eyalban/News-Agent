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
    "שקט": "#4caf50",      # soft green
    "מוגבר": "#ffb74d",    # soft amber
    "גבוה": "#ff8a65",     # soft orange
    "קריטי": "#e57373",    # soft red
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

    # RTL base style applied to every block
    rtl = "direction:rtl;text-align:right;"

    # --- Key developments ---
    developments = report.get("key_developments", [])
    if developments:
        dev_items = ""
        for dev in developments:
            dev_items += f'<li style="margin-bottom:4px;{rtl}">{dev}</li>'
        developments_html = f'<ul style="margin:4px 0;padding-right:20px;font-size:15px;{rtl}">{dev_items}</ul>'
    else:
        developments_html = f'<p style="color:#555;{rtl}">אין התפתחויות משמעותיות.</p>'

    # --- Build strikes table ---
    strikes = report.get("strikes", [])
    total_launches = report.get("total_launches", 0)
    total_intercepted = report.get("total_intercepted", 0)
    total_impact = report.get("total_impact", 0)

    if total_launches == 0 and not strikes:
        strikes_html = f'<p style="color:#555;{rtl}">לא דווחו תקיפות על ישראל בתקופה זו.</p>'
    else:
        strikes_html = f'<p style="{rtl}"><strong>סה"כ: {total_launches} שיגורים &nbsp;|&nbsp; {total_intercepted} יורטו &nbsp;|&nbsp; {total_impact} פגיעות</strong></p>'
        if strikes:
            rows = ""
            for s in strikes:
                time_il = s.get("time_israel", "—") or "—"
                wtype = s.get("weapon_type", "—") or "—"
                origin = s.get("origin", "—") or "—"
                target = s.get("target_location", "—") or "—"
                result = s.get("result", "—") or "—"
                result_color = "#7a4a4a" if result == "פגיעה" else ("#4a7a5c" if result == "יורט" else "#777")
                rows += f"""<tr>
                    <td style="padding:4px 8px;border-bottom:1px solid #eee;{rtl}">{time_il}</td>
                    <td style="padding:4px 8px;border-bottom:1px solid #eee;{rtl}">{origin}</td>
                    <td style="padding:4px 8px;border-bottom:1px solid #eee;{rtl}">{wtype}</td>
                    <td style="padding:4px 8px;border-bottom:1px solid #eee;{rtl}">{target}</td>
                    <td style="padding:4px 8px;border-bottom:1px solid #eee;color:{result_color};font-weight:bold;{rtl}">{result}</td>
                </tr>"""
            strikes_html += f"""<table style="width:100%;border-collapse:collapse;margin-top:6px;font-size:13px;{rtl}">
                <thead>
                    <tr style="background:#f5f5f5;">
                        <th style="padding:6px 8px;text-align:right;border-bottom:2px solid #ccc;">שעה (IL)</th>
                        <th style="padding:6px 8px;text-align:right;border-bottom:2px solid #ccc;">מקור</th>
                        <th style="padding:6px 8px;text-align:right;border-bottom:2px solid #ccc;">סוג</th>
                        <th style="padding:6px 8px;text-align:right;border-bottom:2px solid #ccc;">יעד</th>
                        <th style="padding:6px 8px;text-align:right;border-bottom:2px solid #ccc;">תוצאה</th>
                    </tr>
                </thead>
                <tbody>{rows}</tbody>
            </table>"""

    # --- Casualties ---
    killed = report.get("killed", 0)
    injured = report.get("injured", 0)

    if killed == 0 and injured == 0:
        casualties_html = f'<p style="color:#555;{rtl}">לא דווחו נפגעים בישראל בתקופה זו.</p>'
    else:
        casualties_html = f"""<p style="font-size:15px;margin-top:4px;{rtl}">
            <strong style="color:#7a4a4a;">הרוגים: {killed}</strong>
            &nbsp;&nbsp;·&nbsp;&nbsp;
            <strong style="color:#8a6d3b;">פצועים: {injured}</strong>
        </p>"""

    # --- Casualty details (dead only) ---
    casualty_details = report.get("casualty_details", [])
    # Only show detail rows for those killed
    dead_details = [cd for cd in casualty_details if "נהרג" in cd.get("status", "")]
    if dead_details:
        detail_rows = ""
        for cd in dead_details:
            desc = cd.get("description", "—")
            loc = cd.get("location", "—")
            detail_rows += f"""<tr>
                <td style="padding:4px 8px;border-bottom:1px solid #eee;{rtl}">{desc}</td>
                <td style="padding:4px 8px;border-bottom:1px solid #eee;{rtl}">{loc}</td>
            </tr>"""
        casualties_html += f"""<table style="width:100%;border-collapse:collapse;margin-top:8px;font-size:13px;{rtl}">
            <thead>
                <tr style="background:#f5f5f5;">
                    <th style="padding:6px 8px;text-align:right;border-bottom:2px solid #ccc;">פרטי הנספים</th>
                    <th style="padding:6px 8px;text-align:right;border-bottom:2px solid #ccc;">מיקום</th>
                </tr>
            </thead>
            <tbody>{detail_rows}</tbody>
        </table>"""

    # --- Pilot status ---
    pilot_status = report.get("pilot_status", "לא דווח על פגיעה בטייסי חיל האוויר.")
    pilot_is_clear = "לא דווח על פגיעה" in pilot_status
    pilot_icon = "✅" if pilot_is_clear else "⚠️"
    pilot_color = "#4a7a5c" if pilot_is_clear else "#c48a3f"

    # --- Air base status ---
    airbase_status = report.get("airbase_status", "לא דווח על פגיעה בבסיסי חיל האוויר.")
    airbase_is_clear = "לא דווח על פגיעה" in airbase_status
    airbase_icon = "✅" if airbase_is_clear else "⚠️"
    airbase_color = "#4a7a5c" if airbase_is_clear else "#c48a3f"

    # --- Alerts ---
    alerts = report.get("active_alerts", [])
    if not alerts:
        alerts_html = f'<p style="color:#555;{rtl}">אין התרעות בזמן הדוח.</p>'
    else:
        alerts_html = f"<ul style='margin:4px 0;padding-right:20px;{rtl}'>"
        for alert in alerts:
            alerts_html += f'<li style="{rtl}">{alert}</li>'
        alerts_html += "</ul>"

    # --- Sources ---
    sources = report.get("sources_used", [])
    if sources:
        sources_html = " &bull; ".join(sources)
    else:
        sources_html = "מקורות שנבדקו: " + ", ".join(DEFAULT_SOURCES) + ". לא נמצאו דיווחים רלוונטיים."

    # --- Assemble full HTML ---
    html = f"""<!DOCTYPE html>
<html dir="rtl" lang="he">
<head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;font-family:'Segoe UI',Tahoma,Arial,sans-serif;background:#eef2f7;{rtl}">
<div style="max-width:600px;margin:20px auto;background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 1px 4px rgba(0,0,0,0.08);{rtl}">

    <!-- Header -->
    <div style="background:linear-gradient(135deg,#3f6b9e,#5a8fc4);color:#fff;padding:20px 28px;{rtl}">
        <h1 style="margin:0;font-size:19px;font-weight:600;letter-spacing:0.3px;{rtl}">עדכון יומי</h1>
        <p style="margin:6px 0 0;font-size:13px;opacity:0.8;{rtl}">{date_str} &nbsp;·&nbsp; {period_str}</p>
    </div>

    <!-- Status banner -->
    <div style="background:{status_color};color:#fff;padding:10px 28px;font-size:16px;font-weight:600;{rtl}">
        {status_emoji} מצב: {status}
    </div>

    <div style="padding:24px 28px;{rtl}">

        <!-- Pilot Status — first for quick reassurance -->
        <div style="background:#f0f7f0;border-radius:8px;padding:14px 18px;margin-bottom:20px;border-right:4px solid {pilot_color};{rtl}">
            <h2 style="font-size:15px;color:#3f6b9e;margin:0 0 6px;{rtl}">
                מצב טייסים
            </h2>
            <p style="color:{pilot_color};font-weight:600;font-size:14px;margin:0;{rtl}">
                {pilot_icon} {pilot_status}
            </p>
        </div>

        <!-- Air Base Status -->
        <div style="background:#f0f4f8;border-radius:8px;padding:14px 18px;margin-bottom:20px;border-right:4px solid {airbase_color};{rtl}">
            <h2 style="font-size:15px;color:#3f6b9e;margin:0 0 6px;{rtl}">
                מצב בסיסי חה"א
            </h2>
            <p style="color:{airbase_color};font-weight:600;font-size:14px;margin:0;{rtl}">
                {airbase_icon} {airbase_status}
            </p>
        </div>

        <!-- Key Developments -->
        <h2 style="font-size:15px;color:#3f6b9e;border-bottom:1px solid #d8e2ee;padding-bottom:6px;margin-top:4px;{rtl}">
            התפתחויות עיקריות
        </h2>
        {developments_html}

        <!-- Strikes -->
        <h2 style="font-size:15px;color:#3f6b9e;border-bottom:1px solid #d8e2ee;padding-bottom:6px;margin-top:20px;{rtl}">
            תקיפות על ישראל (12 שעות אחרונות)
        </h2>
        {strikes_html}

        <!-- Casualties -->
        <h2 style="font-size:15px;color:#3f6b9e;border-bottom:1px solid #d8e2ee;padding-bottom:6px;margin-top:20px;{rtl}">
            נפגעים בישראל
        </h2>
        {casualties_html}

        <!-- Active Alerts -->
        <h2 style="font-size:15px;color:#3f6b9e;border-bottom:1px solid #d8e2ee;padding-bottom:6px;margin-top:20px;{rtl}">
            התרעות פעילות
        </h2>
        {alerts_html}

    </div>

    <!-- Sources footer -->
    <div style="background:#f7f9fb;padding:14px 28px;font-size:12px;color:#8899aa;border-top:1px solid #e8edf2;{rtl}">
        <strong>מקורות:</strong> {sources_html}
    </div>

    <!-- Disclaimer -->
    <div style="padding:10px 28px 14px;font-size:11px;color:#aab5c2;{rtl}">
        דוח זה מבוסס על כתבות חדשותיות בלבד. מספרים מופיעים רק כאשר דווחו במפורש במקורות. נפגעים = בישראל בלבד.
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

    rtl = "direction:rtl;text-align:right;"

    date_str = f"{now_boston.day} ב{HEBREW_MONTHS[now_boston.month]} {now_boston.year}"
    period_str = (
        f"{start_boston.strftime('%d/%m %H:%M')} — "
        f"{now_boston.strftime('%d/%m %H:%M')} (שעון בוסטון)"
    )

    if not articles:
        articles_html = f'<p style="color:#555;{rtl}">לא נמצאו כתבות רלוונטיות בתקופה זו.</p>'
    else:
        items = ""
        for article in articles[:30]:
            source = article.get("source", "")
            title = article.get("title", "")
            link = article.get("link", "")
            if link:
                items += f'<li style="margin-bottom:6px;{rtl}"><strong>[{source}]</strong> <a href="{link}">{title}</a></li>'
            else:
                items += f'<li style="margin-bottom:6px;{rtl}"><strong>[{source}]</strong> {title}</li>'
        articles_html = f'<ol style="padding-right:20px;{rtl}">{items}</ol>'

    html = f"""<!DOCTYPE html>
<html dir="rtl" lang="he">
<head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;font-family:'Segoe UI',Tahoma,Arial,sans-serif;background:#eef2f7;{rtl}">
<div style="max-width:600px;margin:20px auto;background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 1px 4px rgba(0,0,0,0.08);{rtl}">

    <div style="background:linear-gradient(135deg,#3f6b9e,#5a8fc4);color:#fff;padding:20px 28px;{rtl}">
        <h1 style="margin:0;font-size:19px;font-weight:600;{rtl}">עדכון יומי</h1>
        <p style="margin:6px 0 0;font-size:13px;opacity:0.8;{rtl}">{date_str} &nbsp;·&nbsp; {period_str}</p>
    </div>

    <div style="background:#ffb74d;color:#fff;padding:10px 28px;font-size:15px;font-weight:600;{rtl}">
        סיכום AI לא זמין — כותרות בלבד
    </div>

    <div style="padding:24px 28px;{rtl}">
        {articles_html}
    </div>

</div>
</body>
</html>"""

    return html
