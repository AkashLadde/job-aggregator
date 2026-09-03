"""
Sends one or more PDF reports via Gmail SMTP to a list of recipients
(via BCC, so recipients can't see each other's addresses).
"""
import os
import logging
import smtplib
from email.message import EmailMessage

logger = logging.getLogger(__name__)

GMAIL_ADDRESS = os.getenv("GMAIL_ADDRESS")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")
EMAIL_RECIPIENT_RAW = os.getenv("EMAIL_RECIPIENT", GMAIL_ADDRESS)

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 465


def send_email_with_pdfs(pdf_paths: list[str], total_job_count: int) -> bool:
    """
    pdf_paths: list of file paths to attach (e.g. cybersecurity + general CSE digests).
    Only paths that actually exist on disk get attached; others are skipped with a warning.
    """
    if not GMAIL_ADDRESS or not GMAIL_APP_PASSWORD:
        logger.error("GMAIL_ADDRESS / GMAIL_APP_PASSWORD not set. Skipping email.")
        return False

    recipients = [r.strip() for r in EMAIL_RECIPIENT_RAW.split(",") if r.strip()]
    if not recipients:
        logger.error("No valid recipients found in EMAIL_RECIPIENT. Skipping email.")
        return False

    msg = EmailMessage()
    msg["Subject"] = f"📋 Engineering Jobs Digest — {total_job_count} new opportunities"
    msg["From"] = GMAIL_ADDRESS
    msg["To"] = GMAIL_ADDRESS
    msg["Bcc"] = ", ".join(recipients)
    msg.set_content(
        f"Good day!\n\n"
        f"Attached are today's digests: Cyber Security opportunities and General CSE/Allied "
        f"Branch opportunities, across India and major global tech hubs.\n\n"
        f"This is an automated message from the Job Aggregator pipeline."
    )

    attached_count = 0
    for path in pdf_paths:
        try:
            with open(path, "rb") as f:
                pdf_data = f.read()
            msg.add_attachment(
                pdf_data, maintype="application", subtype="pdf",
                filename=os.path.basename(path),
            )
            attached_count += 1
        except FileNotFoundError:
            logger.warning("PDF file not found at %s, skipping attachment.", path)

    if attached_count == 0:
        logger.error("No PDF files could be attached. Skipping email.")
        return False

    try:
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=20) as smtp:
            smtp.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
            smtp.send_message(msg)
        logger.info("Email sent successfully to %d recipient(s) with %d attachment(s).", len(recipients), attached_count)
        return True
    except smtplib.SMTPAuthenticationError:
        logger.error("SMTP auth failed. Check GMAIL_APP_PASSWORD is a valid App Password.")
        return False
    except Exception as e:
        logger.error("Failed to send email: %s", e)
        return False
