"""
Turns a list of job dicts into a styled, professional PDF report for
fresher-focused CSE/Cyber Security opportunities. Landscape A4 to fit
the extra columns (country, posted date) alongside bulleted eligibility.
"""
import logging
from datetime import datetime
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
)

logger = logging.getLogger(__name__)

styles = getSampleStyleSheet()

TITLE_STYLE = ParagraphStyle(
    "TitleStyle", parent=styles["Title"], fontSize=18, textColor=colors.HexColor("#1a237e")
)
SUBTITLE_STYLE = ParagraphStyle(
    "SubtitleStyle", parent=styles["Normal"], fontSize=9, textColor=colors.grey, spaceAfter=12
)
NOTE_STYLE = ParagraphStyle(
    "NoteStyle", parent=styles["Normal"], fontSize=8, textColor=colors.HexColor("#b71c1c"), spaceAfter=10
)
SECTION_STYLE = ParagraphStyle(
    "SectionStyle", parent=styles["Heading2"], fontSize=13,
    textColor=colors.white, backColor=colors.HexColor("#1a237e"),
    spaceBefore=8, spaceAfter=6, leftIndent=6, borderPadding=(4, 4, 4, 4),
)
CELL_STYLE = ParagraphStyle("CellStyle", parent=styles["Normal"], fontSize=7.5, leading=9.5)
LINK_STYLE = ParagraphStyle(
    "LinkStyle", parent=styles["Normal"], fontSize=7.5, leading=9.5, textColor=colors.HexColor("#1565c0")
)


def _p(text: str, style=CELL_STYLE) -> Paragraph:
    # eligibility text intentionally allows <br/> for bullets, so don't escape it
    return Paragraph(text or "", style)


def _plain(text: str) -> Paragraph:
    return Paragraph(escape(text or ""), CELL_STYLE)


def _link(url: str) -> Paragraph:
    if not url:
        return _plain("N/A")
    safe_url = escape(url.replace('"', ""))  # Adzuna links contain '&'
    return Paragraph(f'<link href="{safe_url}">Direct Link</link>', LINK_STYLE)


def _search_link(company: str, title: str) -> Paragraph:
    import urllib.parse
    query = urllib.parse.quote(f"{company} official careers page {title}")
    url = f"https://www.google.com/search?q={query}"
    return Paragraph(f'<link href="{url}">Verify/Find Official Site</link>', LINK_STYLE)


HEADER_STYLE = ParagraphStyle(
    "HeaderStyle", parent=styles["Normal"], fontSize=7.5, leading=9,
    textColor=colors.white, fontName="Helvetica-Bold", alignment=1
)


def _h(text: str) -> Paragraph:
    return Paragraph(text, HEADER_STYLE)


TYPE_ORDER = {"Internship": 0, "Apprenticeship": 1, "Job": 2}


def sort_jobs(jobs: list[dict]) -> list[dict]:
    """Internships first, then apprenticeships, then jobs; newest first inside each."""
    by_date = sorted(jobs, key=lambda j: j.get("posted_date") or "", reverse=True)
    return sorted(by_date, key=lambda j: TYPE_ORDER.get(j.get("job_type", "Job"), 2))


def _role_cell(job: dict) -> Paragraph:
    jt = job.get("job_type", "Job")
    colour = {"Internship": "#2e7d32", "Apprenticeship": "#6a1b9a"}.get(jt, "#1565c0")
    title = escape(job["title"])
    return Paragraph(f'<font color="{colour}"><b>[{jt}]</b></font><br/>{title}', CELL_STYLE)


def _company_cell(job: dict) -> Paragraph:
    src = job.get("source")
    extra = f'<br/><font color="#777777"><i>via {escape(src)}</i></font>' if src else ""
    return Paragraph(escape(job["company"]) + extra, CELL_STYLE)


def _fresher_cell(job: dict) -> Paragraph:
    reason = escape(job.get("fresher_reason") or "")
    tags = ", ".join(job.get("fresher_tags") or [])
    text = f"<b>{reason}</b>" + (f"<br/><i>{escape(tags)}</i>" if tags else "")
    return Paragraph(text, CELL_STYLE)


def _build_section_table(jobs: list[dict], start_index: int = 1) -> Table:
    header = [
        _h("#"), _h("Role"), _h("Company"), _h("Eligibility (from the ad)"), _h("Fresher check"),
        _h("Location"), _h("Country"), _h("Posted"), _h("Deadline"), _h("Direct Link"),
        _h("Verify Official Site"),
    ]
    data = [header]
    for i, job in enumerate(jobs, start=start_index):
        data.append([
            _plain(str(i)),
            _role_cell(job),
            _company_cell(job),
            _p(job["eligibility"]),
            _fresher_cell(job),
            _plain(job["location"]),
            _plain(job.get("country", "N/A")),
            _plain(job.get("posted_date") or "Not available"),
            _plain(job["deadline"]),
            _link(job["apply_url"]),
            _search_link(job["company"], job["title"]),
        ])

    # total 27.6 cm = landscape A4 width minus margins
    col_widths = [0.7*cm, 3.4*cm, 2.6*cm, 6.0*cm, 3.0*cm, 2.3*cm, 1.6*cm, 2.0*cm, 1.7*cm, 1.7*cm, 2.6*cm]
    table = Table(data, colWidths=col_widths, repeatRows=1)

    style_cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#3949ab")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 8),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cfd8dc")),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]
    for i in range(1, len(data)):
        bg = colors.HexColor("#f5f6fa") if i % 2 == 0 else colors.white
        style_cmds.append(("BACKGROUND", (0, i), (-1, i), bg))

    table.setStyle(TableStyle(style_cmds))
    return table


def generate_pdf_report(jobs: list[dict], output_path: str, report_title: str = "Freshers — Daily Digest") -> str:
    doc = SimpleDocTemplate(
        output_path, pagesize=landscape(A4),
        topMargin=1.2*cm, bottomMargin=1.2*cm, leftMargin=1.0*cm, rightMargin=1.0*cm,
    )

    elements = []
    today_str = datetime.now().strftime("%A, %d %B %Y")

    elements.append(Paragraph(report_title, TITLE_STYLE))
    n_intern = sum(1 for j in jobs if j.get("job_type") == "Internship")
    elements.append(Paragraph(
        f"Generated on {today_str} · {len(jobs)} new fresher opportunities "
        f"({n_intern} internships, {len(jobs) - n_intern} jobs/apprenticeships)", SUBTITLE_STYLE))
    elements.append(Paragraph(
        "Every listing passed an automatic fresher check (no senior titles, no 1+ years experience, "
        "batch year matches). 'Fresher check' shows why it was included - still read the full ad. "
        "'Direct Link' is the original posting source (often LinkedIn/a job board, not always the "
        "company's own site). Use 'Verify Official Site' to confirm before applying. Pin codes and hard "
        "deadlines are not reliably available from the data source and are omitted rather than guessed.",
        NOTE_STYLE
    ))

    if not jobs:
        elements.append(Paragraph("No new opportunities found this run. Check back next time!", styles["Normal"]))
    else:
        govt_jobs = sort_jobs([j for j in jobs if j.get("category") == "Govt"])
        private_jobs = sort_jobs([j for j in jobs if j.get("category") != "Govt"])

        if govt_jobs:
            elements.append(Paragraph(f"Government / PSU Opportunities ({len(govt_jobs)})", SECTION_STYLE))
            elements.append(_build_section_table(govt_jobs, start_index=1))
            elements.append(Spacer(1, 14))

        if private_jobs:
            elements.append(Paragraph(f"Private Sector Opportunities ({len(private_jobs)})", SECTION_STYLE))
            elements.append(_build_section_table(private_jobs, start_index=len(govt_jobs) + 1))

    try:
        doc.build(elements)
        logger.info("PDF report generated at %s", output_path)
    except Exception as e:
        logger.error("Failed to build PDF: %s", e)
        raise

    return output_path
