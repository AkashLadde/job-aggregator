"""
Sends a WhatsApp notification via Twilio.
"""
import os
import logging
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException

logger = logging.getLogger(__name__)

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_WHATSAPP_FROM = os.getenv("TWILIO_WHATSAPP_FROM")
WHATSAPP_TO = os.getenv("WHATSAPP_TO")


def send_whatsapp_digest(job_count: int, pdf_public_url: str | None = None) -> bool:
    if not all([TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_WHATSAPP_FROM, WHATSAPP_TO]):
        logger.error("Twilio env vars not fully set. Skipping WhatsApp notification.")
        return False

    body = (
        f"📋 *Daily Engineering Jobs Digest*\n"
        f"{job_count} new opportunities found today (Govt + Private).\n"
        + (f"\nFull PDF: {pdf_public_url}" if pdf_public_url else "\nCheck your email for the full PDF report.")
    )

    try:
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        kwargs = {"from_": TWILIO_WHATSAPP_FROM, "to": WHATSAPP_TO, "body": body}
        if pdf_public_url:
            kwargs["media_url"] = [pdf_public_url]
        message = client.messages.create(**kwargs)
        logger.info("WhatsApp message sent, SID=%s", message.sid)
        return True
    except TwilioRestException as e:
        logger.error("Twilio API error: %s", e)
        return False
    except Exception as e:
        logger.error("Failed to send WhatsApp message: %s", e)
        return False
