import logging
import smtplib
import time
from email.mime.text import MIMEText

from src.config import (
    SMTP_SERVER,
    SMTP_PORT,
    SENDER_EMAIL,
    RECIPIENT_EMAIL,
    GMAIL_APP_PASSWORD,
    MAX_RETRIES,
    RETRY_DELAY_SECONDS,
)

logger = logging.getLogger(__name__)


def send_report(subject: str, body: str) -> bool:
    """Send the report email via Gmail SMTP.

    Args:
        subject: Email subject line (Hebrew).
        body: Plain text email body (Hebrew).

    Returns:
        True if sent successfully, False otherwise.
    """
    if not all([SENDER_EMAIL, RECIPIENT_EMAIL, GMAIL_APP_PASSWORD]):
        logger.error("Email configuration incomplete. Check SENDER_EMAIL, RECIPIENT_EMAIL, GMAIL_APP_PASSWORD.")
        return False

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = SENDER_EMAIL
    msg["To"] = RECIPIENT_EMAIL

    for attempt in range(MAX_RETRIES):
        try:
            with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, timeout=30) as server:
                server.login(SENDER_EMAIL, GMAIL_APP_PASSWORD)
                server.sendmail(SENDER_EMAIL, [RECIPIENT_EMAIL], msg.as_string())
            logger.info("Email sent successfully to %s", RECIPIENT_EMAIL)
            return True
        except Exception as e:
            logger.warning("Email send attempt %d failed: %s", attempt + 1, e)
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY_SECONDS)

    logger.error("Failed to send email after %d attempts", MAX_RETRIES)
    return False
