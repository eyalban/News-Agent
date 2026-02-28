import os

# --- Time Windows ---
LOOKBACK_HOURS = 12
BOSTON_TIMEZONE = "America/New_York"
ISRAEL_TIMEZONE = "Asia/Jerusalem"
# Send window: only run if Boston time is within this range (handles dual-cron DST)
SEND_WINDOW_START_HOUR = 6
SEND_WINDOW_START_MIN = 30
SEND_WINDOW_END_HOUR = 8
SEND_WINDOW_END_MIN = 0

# --- Google News RSS ---
GOOGLE_NEWS_BASE = "https://news.google.com/rss/search"
GOOGLE_NEWS_PARAMS = {"hl": "en", "gl": "US", "ceid": "US:en"}
GOOGLE_NEWS_QUERIES = [
    "Iran Israel strike when:12h",
    "Iran Israel missile OR rocket OR drone OR ballistic when:12h",
    '"IAF pilot" OR "Israeli Air Force pilot" when:12h',
    "Israel casualties killed injured when:12h",
    "Hezbollah attack Israel when:12h",
    "Iran Israel conflict when:12h",
    "IDF spokesperson Iran when:12h",
    "Israel air defense Iron Dome Arrow when:12h",
    "Israel home front command alert siren when:12h",
]
GOOGLE_NEWS_SITE_QUERIES = [
    "Iran Israel when:12h site:reuters.com",
    "Iran Israel when:12h site:bbc.com",
]

# --- Direct RSS Feeds ---
DIRECT_RSS_FEEDS = {
    "Times of Israel": "https://www.timesofisrael.com/feed/",
    "Jerusalem Post": "https://www.jpost.com/Rss/RssFeedsFrontPage.aspx",
    "Ynetnews": "https://www.ynetnews.com/Integration/StoryRss3254.xml",
    "IDF Spokesperson": "https://idfspokesperson.substack.com/feed",
}

# --- Relevance Keywords ---
ACTORS = [
    "iran", "iranian", "irgc", "islamic republic",
    "israel", "israeli", "idf", "iaf",
    "hezbollah", "houthi", "houthis",
    "hamas", "islamic jihad",
    "tehran", "khamenei",
]

EVENTS = [
    "strike", "strikes", "struck", "attack", "attacked",
    "missile", "missiles", "ballistic", "rocket", "rockets",
    "drone", "drones", "uav", "shahed",
    "intercept", "intercepted", "interception",
    "iron dome", "arrow", "david's sling",
    "air defense", "air defence",
    "casualties", "killed", "injured", "wounded", "dead",
    "pilot", "pilots", "aircrew",
    "alert", "siren", "sirens", "home front command",
    "retaliation", "retaliatory", "escalation",
    "ceasefire", "truce", "de-escalation",
    "nuclear", "enrichment", "natanz", "fordow",
]

# High-priority phrases that match independently (no AND required)
HIGH_PRIORITY = [
    "iaf pilot",
    "israeli air force pilot",
    "iran attacks israel",
    "israel strikes iran",
    "ballistic missile israel",
    "iron dome activation",
    "israeli pilot",
]

# --- OpenAI ---
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_MODEL = "gpt-4o-mini"
OPENAI_MAX_TOKENS = 4000
OPENAI_TEMPERATURE = 0.1

# --- Email (Resend) ---
RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
SENDER_EMAIL = os.environ.get("SENDER_EMAIL", "onboarding@resend.dev")
RECIPIENT_EMAIL = os.environ.get("RECIPIENT_EMAIL", "")

# --- Resilience ---
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 5
REQUEST_TIMEOUT_SECONDS = 30
INTER_REQUEST_DELAY_SECONDS = 1.5
