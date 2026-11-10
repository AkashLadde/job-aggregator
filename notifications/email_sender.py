"""
Sends the daily digest via Gmail SMTP to a list of recipients (BCC, so
recipients can't see each other's addresses).

The email body now contains the job list itself (title, company, location,
why it's fresher-friendly, apply link) so you can read it on your phone
without opening the PDF. The PDFs are still attached.
"""
import os
import logging
import smtplib
from html import escape
from datetime import datetime
from email.message import EmailMessage

logger = logging.getLogger(__name__)

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 465
MAX_IN_BODY = int((os.getenv("EMAIL_MAX_JOBS_IN_BODY") or "60"))

TYPE_COLOUR = {"Internship": "#2e7d32", "Apprenticeship": "#6a1b9a", "Job": "#1565c0"}


def _rows(jobs: list[dict]) -> str:
    out = []
    for j in jobs[:MAX_IN_BODY]:
        jt = j.get("job_type", "Job")
        tags = ", ".join(j.get("fresher_tags") or [])
        out.append(
            "<tr>"
            f'<td style="padding:6px;border-bottom:1px solid #eee;vertical-align:top">'
            f'<span style="color:{TYPE_COLOUR.get(jt, "#1565c0")};font-weight:bold;font-size:11px">{escape(jt)}</span><br>'
            f'<a href="{escape(j["apply_url"], quote=True)}" style="font-weight:bold;color:#1a237e">{escape(j["title"])}</a><br>'
            f'<span style="color:#444">{escape(j["company"])} · {escape(j["location"])}</span>'
            + (f'<br><span style="color:#999;font-size:11px">via {escape(j["source"])}</span>' if j.get("source") else "")
            + "</td>"
            f'<td style="padding:6px;border-bottom:1px solid #eee;vertical-align:top;font-size:12px;color:#2e7d32">'
            f'{escape(j.get("fresher_reason", ""))}'
            + (f'<br><span style="color:#777">{escape(tags)}</span>' if tags else "")
            + "</td></tr>"
        )
    return "".join(out)


def _section(title: str, jobs: list[dict]) -> str:
    if not jobs:
        return ""
    more = (f'<p style="color:#777">+ {len(jobs) - MAX_IN_BODY} more in the attached PDF.</p>'
            if len(jobs) > MAX_IN_BODY else "")
    return (
        f'<h3 style="background:#1a237e;color:#fff;padding:6px 10px;margin:18px 0 4px">{escape(title)} ({len(jobs)})</h3>'
        f'<table style="border-collapse:collapse;width:100%;font-family:Arial,sans-serif;font-size:13px">'
        f'<tr><th align="left" style="padding:6px">Opportunity</th><th align="left" style="padding:6px">Why it is for freshers</th></tr>'
        f"{_rows(jobs)}</table>{more}"
    )


def build_html(sections: list[tuple[str, list[dict]]]) -> str:
    total = sum(len(j) for _, j in sections)
    interns = sum(1 for _, js in sections for j in js if j.get("job_type") == "Internship")
    body = "".join(_section(t, js) for t, js in sections)
    return (
        '<div style="font-family:Arial,sans-serif;max-width:760px">'
        f'<h2 style="color:#1a237e;margin-bottom:2px">Fresher Internships &amp; Jobs — {datetime.now():%d %b %Y}</h2>'
        f'<p style="color:#555;margin-top:0">{total} new opportunities ({interns} internships). '
        "Each one passed the automatic fresher check. Always read the full ad before applying, "
        "and never pay any fee to apply for a job.</p>"
        f"{body}"
        '<p style="color:#999;font-size:11px;margin-top:20px">Automated message from your Job Aggregator pipeline. '
        "PDF versions are attached.</p></div>"
    )


def send_email_with_pdfs(pdf_paths: list[str], total_job_count: int,
                         sections: list[tuple[str, list[dict]]] | None = None) -> bool:
    """
    pdf_paths: PDFs to attach (missing files are skipped).
    sections:  [(section title, jobs), ...] shown in the email body.
    """
    gmail = os.getenv("GMAIL_ADDRESS")
    password = os.getenv("GMAIL_APP_PASSWORD")
    recipients_raw = os.getenv("EMAIL_RECIPIENT") or gmail or ""

    if not gmail or not password:
        logger.error("GMAIL_ADDRESS / GMAIL_APP_PASSWORD not set. Skipping email.")
        return False

    recipients = [r.strip() for r in recipients_raw.split(",") if r.strip()]
    if not recipients:
        logger.error("No valid recipients found in EMAIL_RECIPIENT. Skipping email.")
        return False

    interns = sum(1 for _, js in (sections or []) for j in js if j.get("job_type") == "Internship")
    msg = EmailMessage()
    msg["Subject"] = (f"🎓 Fresher Jobs & Internships — {total_job_count} new"
                      + (f" ({interns} internships)" if interns else "")
                      + f" · {datetime.now():%d %b}")
    msg["From"] = gmail
    msg["To"] = gmail
    msg["Bcc"] = ", ".join(recipients)
    msg.set_content(
        f"{total_job_count} new fresher internships/jobs today. "
        "Open this email in an HTML-capable client, or see the attached PDFs."
    )
    if sections:
        msg.add_alternative(build_html(sections), subtype="html")

    attached = 0
    for path in pdf_paths:
        try:
            with open(path, "rb") as f:
                msg.add_attachment(f.read(), maintype="application", subtype="pdf",
                                   filename=os.path.basename(path))
            attached += 1
        except FileNotFoundError:
            logger.warning("PDF file not found at %s, skipping attachment.", path)

    try:
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=30) as smtp:
            smtp.login(gmail, password)
            smtp.send_message(msg)
        logger.info("Email sent to %d recipient(s) with %d attachment(s).", len(recipients), attached)
        return True
    except smtplib.SMTPAuthenticationError:
        logger.error("SMTP auth failed. Check GMAIL_APP_PASSWORD is a valid App Password.")
        return False
    except Exception as e:
        logger.error("Failed to send email: %s", e)
        return False
