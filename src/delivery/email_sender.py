import logging
import time

import resend

from src.config import (
    RESEND_API_KEY,
    SENDER_EMAIL,
    RECIPIENT_EMAILS,
    MAX_RETRIES,
    RETRY_DELAY_SECONDS,
)

logger = logging.getLogger(__name__)


def send_report(subject: str, body_html: str) -> bool:
    """Send the report email via Resend API.

    Args:
        subject: Email subject line (Hebrew).
        body_html: HTML email body.

    Returns:
        True if sent successfully, False otherwise.
    """
    if not RESEND_API_KEY or not RECIPIENT_EMAILS:
        logger.error("Email configuration incomplete. Check RESEND_API_KEY and RECIPIENT_EMAIL.")
        return False

    resend.api_key = RESEND_API_KEY

    for attempt in range(MAX_RETRIES):
        try:
            result = resend.Emails.send({
                "from": f"Daily Brief <{SENDER_EMAIL}>",
                "to": RECIPIENT_EMAILS,
                "subject": subject,
                "html": body_html,
            })
            logger.info("Email sent successfully to %s (id: %s)", RECIPIENT_EMAILS, result.get("id", "?"))
            return True
        except Exception as e:
            logger.warning("Email send attempt %d failed: %s", attempt + 1, e)
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY_SECONDS)

    logger.error("Failed to send email after %d attempts", MAX_RETRIES)
    return False
