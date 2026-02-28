"""Tests for the report formatter module."""

from datetime import datetime, timezone

from src.report.formatter import format_report, format_fallback_report


def _make_times():
    """Create start/end times for testing."""
    end = datetime(2026, 2, 28, 12, 0, 0, tzinfo=timezone.utc)
    start = datetime(2026, 2, 28, 0, 0, 0, tzinfo=timezone.utc)
    return start, end


def _quiet_report() -> dict:
    return {
        "status": "שקט",
        "key_developments": [],
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
        "sources_used": ["Reuters", "BBC"],
    }


def _critical_report() -> dict:
    return {
        "status": "קריטי",
        "key_developments": [
            "איראן שיגרה טילים בליסטיים לעבר ישראל",
            "ישראל וארה\"ב תקפו מטרות באיראן",
        ],
        "total_launches": 200,
        "total_intercepted": 160,
        "total_impact": 21,
        "strikes": [
            {
                "time_israel": "01:30",
                "origin": "איראן",
                "weapon_type": "בליסטי",
                "target_location": "תל אביב",
                "result": "פגיעה",
            },
            {
                "time_israel": "02:00",
                "origin": "איראן",
                "weapon_type": "שיוט",
                "target_location": "חיפה",
                "result": "יורט",
            },
        ],
        "killed": 1,
        "injured": 20,
        "civilian_killed": 1,
        "civilian_injured": 18,
        "military_killed": 0,
        "military_injured": 2,
        "casualty_details": [
            {"description": "אישה בת 40", "location": "תל אביב", "status": "נהרג/ה"},
        ],
        "pilot_status": "טייסי חה\"א השתתפו במבצע. לא דווח על פגיעה.",
        "airbase_status": "בסיסי חה\"א הוזכרו כיעד אך לא דווח על נזק.",
        "active_alerts": ["צפירות באזור תל אביב", "צפירות בצפון הארץ"],
        "sources_used": ["Times of Israel", "Reuters", "Al Jazeera"],
    }


class TestFormatReport:
    def test_returns_html(self):
        html = format_report(_quiet_report(), *_make_times())
        assert html.startswith("<!DOCTYPE html>")
        assert "</html>" in html

    def test_rtl_direction(self):
        html = format_report(_quiet_report(), *_make_times())
        assert 'dir="rtl"' in html
        assert 'lang="he"' in html

    def test_quiet_status_green(self):
        html = format_report(_quiet_report(), *_make_times())
        assert "#2e7d32" in html  # green color
        assert "שקט" in html

    def test_critical_status_red(self):
        html = format_report(_critical_report(), *_make_times())
        assert "#b71c1c" in html  # red color (status or casualty)
        assert "קריטי" in html

    def test_no_strikes_message(self):
        html = format_report(_quiet_report(), *_make_times())
        assert "לא דווחו תקיפות" in html

    def test_strikes_table_rendered(self):
        html = format_report(_critical_report(), *_make_times())
        assert "200 שיגורים" in html
        assert "160 יורטו" in html
        assert "21 פגיעות" in html
        assert "תל אביב" in html
        assert "חיפה" in html

    def test_strikes_table_has_origin_column(self):
        html = format_report(_critical_report(), *_make_times())
        assert "מקור" in html  # origin column header
        assert "איראן" in html  # origin value

    def test_no_casualties_message(self):
        html = format_report(_quiet_report(), *_make_times())
        assert "לא דווחו נפגעים" in html

    def test_casualties_headline_format(self):
        """Casualties show as simple headline: הרוגים: X | פצועים: Y."""
        html = format_report(_critical_report(), *_make_times())
        assert "הרוגים: 1" in html
        assert "פצועים: 20" in html

    def test_casualties_no_grid_table(self):
        """Old grid table (אזרחים/צבאיים) should no longer appear."""
        html = format_report(_critical_report(), *_make_times())
        assert "אזרחים" not in html
        assert "צבאיים" not in html

    def test_casualty_details_shows_dead_only(self):
        """Detail table should only show killed, not injured."""
        html = format_report(_critical_report(), *_make_times())
        assert "אישה בת 40" in html
        assert "פרטי הנספים" in html  # table header
        assert "מיקום" in html  # table header

    def test_casualty_details_filters_injured(self):
        """Injured entries should NOT appear in the detail table."""
        report = _critical_report()
        report["casualty_details"] = [
            {"description": "אישה בת 40", "location": "תל אביב", "status": "נהרג/ה"},
            {"description": "3 פצועים קל", "location": "חיפה", "status": "נפצע/ה קל"},
        ]
        html = format_report(report, *_make_times())
        assert "אישה בת 40" in html      # dead — shown
        assert "3 פצועים קל" not in html   # injured — filtered out

    def test_no_casualty_details_when_no_dead(self):
        report = _quiet_report()
        report["killed"] = 0
        report["injured"] = 5
        report["casualty_details"] = [
            {"description": "3 פצועים", "location": "חיפה", "status": "נפצע/ה"},
        ]
        html = format_report(report, *_make_times())
        assert "פרטי הנספים" not in html  # no dead detail table

    def test_pilot_safe_green(self):
        html = format_report(_quiet_report(), *_make_times())
        assert "✅" in html
        assert "#2e7d32" in html  # green

    def test_pilot_warning_orange(self):
        report = _quiet_report()
        report["pilot_status"] = "דווח על פגיעה בטייס אחד"
        html = format_report(report, *_make_times())
        assert "⚠️" in html

    def test_airbase_safe(self):
        html = format_report(_quiet_report(), *_make_times())
        assert "לא דווח על פגיעה בבסיסי חיל האוויר" in html

    def test_active_alerts_rendered(self):
        html = format_report(_critical_report(), *_make_times())
        assert "צפירות באזור תל אביב" in html
        assert "צפירות בצפון הארץ" in html

    def test_no_alerts_message(self):
        html = format_report(_quiet_report(), *_make_times())
        assert "אין התרעות" in html

    def test_sources_listed(self):
        html = format_report(_critical_report(), *_make_times())
        assert "Times of Israel" in html
        assert "Reuters" in html

    def test_key_developments_rendered(self):
        html = format_report(_critical_report(), *_make_times())
        assert "התפתחויות עיקריות" in html
        assert "איראן שיגרה טילים" in html

    def test_no_developments_message(self):
        html = format_report(_quiet_report(), *_make_times())
        assert "אין התפתחויות משמעותיות" in html

    def test_date_in_hebrew(self):
        html = format_report(_quiet_report(), *_make_times())
        assert "פברואר" in html
        assert "2026" in html

    def test_disclaimer_present(self):
        html = format_report(_quiet_report(), *_make_times())
        assert "דוח זה מבוסס על כתבות חדשותיות בלבד" in html


class TestFallbackReport:
    def test_returns_html(self):
        html = format_fallback_report([], *_make_times())
        assert "<!DOCTYPE html>" in html

    def test_shows_ai_unavailable_banner(self):
        html = format_fallback_report([], *_make_times())
        assert "סיכום AI לא זמין" in html

    def test_no_articles_message(self):
        html = format_fallback_report([], *_make_times())
        assert "לא נמצאו כתבות" in html

    def test_articles_listed(self):
        articles = [
            {"source": "Reuters", "title": "Iran conflict update", "link": "https://example.com/1"},
            {"source": "BBC", "title": "Missiles fired at Israel", "link": "https://example.com/2"},
        ]
        html = format_fallback_report(articles, *_make_times())
        assert "Iran conflict update" in html
        assert "Missiles fired at Israel" in html
        assert "[Reuters]" in html
        assert "[BBC]" in html
