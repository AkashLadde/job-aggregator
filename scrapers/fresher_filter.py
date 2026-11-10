"""
Decides whether a job is genuinely meant for FRESHERS (students / recent
graduates with 0 years of experience), and whether it belongs to the
CSE / allied-branch domain.

Why this exists: Adzuna's keyword search matches words anywhere in the ad,
so "fresher ... engineer" also returns "Senior Engineer, 8+ years". Every
job must pass this filter before it is saved or emailed.

How a job is judged (in this order):
  1. Not CSE / IT related                         -> rejected
  2. Senior word in the title (Senior, Lead ...)  -> rejected
  3. Says "no freshers" / "experienced only"      -> rejected
  4. Asks for 1+ years of experience              -> rejected
     (unless it also clearly says freshers can apply)
  5. Mentions only old batches (e.g. 2021 batch)  -> rejected
  6. Has a fresher signal (Intern, Trainee, Fresher, Entry level,
     0-1 years, 2026 batch ...)                    -> ACCEPTED
  7. No signal either way                          -> rejected in strict mode
                                                     (FRESHER_STRICT=true, default)

Every decision carries a short human-readable reason, shown in the PDF/email
so you can see WHY a job was listed.

Settings (environment variables, all optional):
  FRESHER_STRICT          true/false  (default true)
  FRESHER_BATCH_YEARS     e.g. "2025,2026,2027" (default: last year .. next year)
  FRESHER_MAX_EXPERIENCE  max "minimum years" a job may ask for (default 0)
"""
import os
import re
import html
import datetime
from dataclasses import dataclass, field

# ---------------------------------------------------------------- settings

def _env_bool(name: str, default: bool) -> bool:
    raw = (os.getenv(name) or "").strip()   # unset GitHub variables arrive as ""
    return default if not raw else raw.lower() in ("1", "true", "yes", "y")


def _batch_years() -> set[int]:
    raw = (os.getenv("FRESHER_BATCH_YEARS") or "").strip()
    years = {int(y) for y in re.findall(r"\b(?:19|20)\d{2}\b", raw)}
    if years:
        return years
    y = datetime.date.today().year
    return {y - 1, y, y + 1}


STRICT = _env_bool("FRESHER_STRICT", True)
MAX_EXPERIENCE = float((os.getenv("FRESHER_MAX_EXPERIENCE") or "0") or 0)
BATCH_YEARS = _batch_years()

# ---------------------------------------------------------------- keywords

# Words in the TITLE that mean the role is for experienced people.
SENIOR_TITLE = re.compile(
    r"\b(senior|sr\.?|snr|lead|leader|principal|staff|manager|mgr|head|director|"
    r"architect|vp|vice president|chief|cto|cio|ciso|expert|experienced|"
    r"professor|dean|registrar|controller|superintendent|commissioner|deputy|"
    r"specialist\s+(?:ii|iii)|level\s*[2-9]|l[3-9]|(?:engineer|developer|analyst)\s+(?:ii|iii|iv|2|3|4))\b",
    re.I,
)

# Strong fresher signals in the TITLE.
FRESHER_TITLE = re.compile(
    r"\b(intern|interns|internship|trainee|trainees|fresher|freshers|graduate|grad|"
    r"new\s+grad|entry[\s-]?level|junior|jr\.?|apprentice|apprenticeship|campus|"
    r"associate\s+(?:software|engineer|developer|data|analyst|consultant|security)|"
    r"(?:software|systems?|data|security|cloud|network)\s+engineer\s+(?:i|1)\b|"
    r"student|early\s+career|0\s*[-–to]+\s*1\s*(?:yr|year))",
    re.I,
)

# Fresher signals in the DESCRIPTION.
FRESHER_DESC = re.compile(
    r"\b(freshers?\b|entry[\s-]?level|no\s+(?:prior\s+)?experience\s+(?:is\s+)?(?:required|needed)|"
    r"recent\s+graduates?|new\s+graduates?|graduate\s+(?:trainee|program(?:me)?|scheme)|"
    r"final[\s-]year\s+students?|pass[\s-]?outs?|passed\s+out|internship|"
    r"campus\s+(?:hiring|drive|recruitment)|0\s*(?:-|–|to)\s*[12]\s*(?:years?|yrs?)|"
    r"(?:19|20)\d{2}\s+(?:batch|pass(?:[\s-]?out)?|graduates?))",
    re.I,
)

# Phrases that explicitly exclude freshers.
NO_FRESHERS = re.compile(
    r"(freshers?\s+(?:need\s+not|should\s+not|please\s+don'?t|do\s+not)\s+apply|"
    r"no\s+freshers|not\s+(?:suitable\s+)?for\s+freshers|experienced\s+(?:candidates|professionals)\s+only|"
    r"only\s+experienced)",
    re.I,
)

# Phrases saying freshers are welcome even though some experience is mentioned.
FRESHERS_WELCOME = re.compile(
    r"(freshers?\s+(?:can|may|are\s+(?:also\s+)?(?:welcome|eligible|encouraged))|"
    r"freshers?\s+(?:also\s+)?(?:can\s+)?apply|freshers?\s+and\s+experienced|"
    r"(?:fresher|0)\s*(?:/|or)\s*experienced)",
    re.I,
)

# "2-4 years", "3+ yrs", "minimum 2 years" ... near the word experience.
EXP_RANGE = re.compile(
    r"(\d+(?:\.\d+)?)\s*\+?\s*(?:-|–|to)\s*(\d+(?:\.\d+)?)\s*\+?\s*(?:years?|yrs?)", re.I
)
EXP_SINGLE = re.compile(r"(\d+(?:\.\d+)?)\s*\+?\s*(?:years?|yrs?)", re.I)
EXP_CONTEXT = re.compile(r"experience|exp\b|expertise|work(?:ing)?\s+history", re.I)
# Words right AFTER "N years" that mean it's NOT about work experience
# ("4 years B.Tech", "2 years bond", "18 years of age", "1 year internship").
NOT_EXPERIENCE = re.compile(
    r"^\s*(?:of\s+)?(?:age|old|bond|service\s+agreement|degree|b\.?\s?tech|b\.?\s?e\b|diploma|course|"
    r"programme|program\b|duration|contract|warranty|internship|apprenticeship|training)",
    re.I,
)

# "2025 batch", "2024, 2025 & 2026 pass outs", "2026 graduates"
BATCH_MENTION = re.compile(
    r"\b((?:(?:19|20)\d{2}\s*(?:,|/|&|and|or|-)\s*)*(?:19|20)\d{2})\s*(?:batch|pass(?:[\s-]?out)?|graduat)",
    re.I,
)
BATCH_LIST = re.compile(r"\b(?:batch(?:es)?|pass[\s-]?outs?|graduat\w*)\s*(?:of|:|-)?\s*((?:(?:19|20)\d{2}\s*(?:,|/|&|and|or|-)?\s*)+)", re.I)

# CSE / allied-branch domain.
CSE_DOMAIN = re.compile(
    r"\b(software|developer|programmer|programming|coding|sde|swe|full[\s-]?stack|front[\s-]?end|"
    r"back[\s-]?end|web\s+develop|mobile\s+app|android|ios\s+develop|python|java|javascript|"
    r"react|node\.?js|\.net|c\+\+|golang|sql|database|data\s+(?:science|scientist|analyst|analytics|engineer)|"
    r"machine\s+learning|deep\s+learning|artificial\s+intelligence|\bai\b|\bml\b|nlp|computer\s+vision|"
    r"gen\s?ai|llm|cyber|infosec|information\s+security|network\s+(?:security|engineer)|"
    r"soc\b|penetration|ethical\s+hack|vapt|security\s+(?:analyst|engineer|operations)|"
    r"cloud|devops|aws|azure|gcp|kubernetes|linux|"
    r"(?:qa|test|automation)\s+(?:engineer|analyst)|software\s+test|"
    r"it\s+(?:intern|trainee|analyst|engineer)|computer\s+science|computer\s+engineering|\bcse\b|\bise\b|"
    r"information\s+science|information\s+technology|blockchain|iot|embedded\s+software)",
    re.I,
)

# ---------------------------------------------------------------- engineering streams
# The user wants ONLY engineering roles in Cyber Security and CSE-allied branches
# (CSE, ISE, IT, AI/ML, AI & DS, Data Science, Cyber Security, Computer Engg).

# Engineering degrees. "B.E"/"BE"/"M.E" must be capitals (the word "be" is everywhere).
ENGG_DEGREE = re.compile(
    r"(\bb\.?\s?tech\b|\bm\.?\s?tech\b|engineering\s+(?:graduates?|degree|students?|freshers?|background|"
    r"discipline|branch)|bachelor'?s?\s+(?:degree\s+)?(?:of|in)\s+(?:engineering|technology)|graduate\s+engineer)",
    re.I,
)
ENGG_DEGREE_CAPS = re.compile(r"\b(?:B\.\s?E|BE|M\.\s?E)\b\.?(?=[\s/,)(-]|$)")
# Non-engineering qualifications. An ad that lists ONLY these is dropped.
NON_ENGG_DEGREE = re.compile(
    r"(\bbca\b|\bmca\b|\bb\.?\s?sc\b|\bm\.?\s?sc\b|\bbba\b|\bmba\b|\bb\.?\s?com\b|\bm\.?\s?com\b|\bb\.?a\.?(?=[\s/,)])|"
    r"\bdiploma\b|\b(?:10|12)th\b|\biti\b|\bsslc\b|\bpuc\b|any\s+graduate|graduates?\s+(?:in|of|from)\s+any\s+(?:stream|discipline))",
    re.I,
)
# CSE family of branches
CSE_BRANCH = re.compile(
    r"(computer\s+science|computer\s+engineering|\bcse\b|information\s+science|\bise\b|"
    r"information\s+technology|data\s+science|artificial\s+intelligence|\bai\s*(?:&|and|-)\s*(?:ml|ds)\b|"
    r"\baiml\b|\baids\b|machine\s+learning|cyber\s*-?\s*security|"
    r"circuit\s+branch(?:es)?|all\s+(?:engineering\s+)?(?:branches|disciplines|streams)|"
    r"any\s+(?:engineering\s+)?(?:branch|discipline|stream))",
    re.I,
)
# "IT" / "CS" / "ISE" must be capitals so we don't match the word "it".
CSE_BRANCH_CAPS = re.compile(r"(?<![A-Za-z])(?:IT|CS|ISE)(?![A-Za-z])")
# Other engineering branches - only looked for NEXT TO degree words
# ("B.E Mechanical", "branches: EEE/ECE"), so "production server" doesn't count.
OTHER_BRANCH = re.compile(
    r"(mechanical|\bmech\b|civil|electrical|\beee\b|\bece\b|\bee\b|electronics(?:\s*(?:&|and)\s*\w+)?|"
    r"chemical|automobile|automotive|production\s+engineering|industrial\s+engineering|instrumentation|"
    r"metallurgy|metallurgical|mining|aeronautical|aerospace|textile|petroleum|bio[\s-]?tech\w*|biomedical|"
    r"marine|agricultur\w*|mechatronics)",
    re.I,
)
DEGREE_CONTEXT = re.compile(
    r"(\bb\.?\s?tech|\bm\.?\s?tech|\bB\.?\s?E\b|\bdiploma|engineering|branch(?:es)?|disciplines?|"
    r"streams?|speciali[sz]ation|degree\s+in|graduates?\s+in|qualification|eligib)",
    re.I,
)


def _degree_windows(text: str) -> str:
    """Text near degree / branch words - where an ad says WHO can apply."""
    parts = [text[max(0, m.start() - 40): m.end() + 90] for m in DEGREE_CONTEXT.finditer(text)]
    return " | ".join(parts)


# Roles that are NOT engineering work even if they say "IT" / "tech".
NON_ENGG_ROLE = re.compile(
    r"\b(help\s*desk|desktop\s+support|technical\s+support|tech\s+support|it\s+support|service\s+desk|"
    r"customer\s+support|non[\s-]?voice|voice\s+process|chat\s+process|back\s+office|kpo|data\s+entry|"
    r"computer\s+operator|content\s+writer|copywriter|seo|digital\s+marketing|social\s+media|graphic|"
    r"video\s+editor|animator|ui\s*/?\s*ux|ux\s+designer|ui\s+designer|product\s+designer|web\s+designer|"
    r"business\s+analyst|operations\s+executive|mis\s+executive|admin\s+executive|typist|stenographer|clerk|"
    r"lab\s+assistant|computer\s+teacher|computer\s+instructor|trainer)\b",
    re.I,
)
# Title says it's for another branch / hardware ("VLSI Trainee", "Mechanical GET").
OTHER_BRANCH_TITLE = re.compile(
    r"\b(mechanical|civil|electrical|\beee\b|\bece\b|chemical|automobile|production|instrumentation|metallurgy|"
    r"mining|aeronautical|textile|petroleum|vlsi|rtl|asic|fpga|pcb|analog|rf\b|hardware\s+(?:design|engineer)|"
    r"electronics\s+engineer|plc|scada|hvac|autocad|solidworks)\b",
    re.I,
)
ENGINEERING_ONLY = _env_bool("ENGINEERING_ONLY", True)


def has_cse_branch(text: str) -> bool:
    return bool(CSE_BRANCH.search(text) or CSE_BRANCH_CAPS.search(text))


def engineering_check(title: str, desc: str, domain: str = "cse") -> str | None:
    """
    Return a rejection reason if the job isn't an engineering role in the
    Cyber Security / CSE-allied streams, else None.
    """
    full = f"{title}. {desc}"
    if NON_ENGG_ROLE.search(title):
        return f"Non-engineering role ({NON_ENGG_ROLE.search(title).group(0)})"
    if OTHER_BRANCH_TITLE.search(title):
        return f"Other branch ({OTHER_BRANCH_TITLE.search(title).group(0)})"
    engg = bool(ENGG_DEGREE.search(full) or ENGG_DEGREE_CAPS.search(full))
    if NON_ENGG_DEGREE.search(full) and not engg:
        return "Not for B.E/B.Tech graduates"
    cse = has_cse_branch(full)
    if not cse and OTHER_BRANCH.search(_degree_windows(full)):
        return "Only for other engineering branches"
    if domain == "govt" and not cse:
        # Govt notifications must name a CSE-family branch (or "all branches").
        return "Govt post - no CSE/IT branch mentioned"
    return None


# Clearly non-CSE roles that sneak in through words like "security" or "graduate".
NON_CSE_TITLE = re.compile(
    r"\b(security\s+(?:guard|officer|supervisor)|guard|driver|telecaller|tele[\s-]?sales|bpo|"
    r"sales|marketing|business\s+development|recruiter|hr\b|human\s+resources|teacher|tutor|"
    r"faculty|nurse|pharmac|accountant|accounts|finance|civil|mechanical|electrical\s+engineer|"
    r"chef|cook|delivery|warehouse|receptionist|customer\s+(?:care|service)|call\s+cent)",
    re.I,
)


# ---------------------------------------------------------------- helpers

@dataclass
class Verdict:
    accepted: bool
    reason: str
    tags: list[str] = field(default_factory=list)


def _clean(text: str) -> str:
    """Strip HTML tags/entities so regexes see plain text."""
    text = html.unescape(text or "")
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def min_experience_years(text: str) -> float | None:
    """
    Smallest 'minimum years of experience' the ad asks for, or None if it
    doesn't mention any. Only counts numbers that sit near the word
    'experience', so '4 years B.Tech' or '6 month internship' are ignored.
    """
    found: list[float] = []
    spans: list[tuple[int, int]] = []

    def near_experience(start: int, end: int) -> bool:
        window = text[max(0, start - 60): end + 60]
        if not EXP_CONTEXT.search(window):
            return False
        # ignore '4 years degree', '2 years bond', 'age 18 years' etc.
        tail = text[end: end + 30]
        head = text[max(0, start - 15): start]
        return not NOT_EXPERIENCE.search(tail) and not re.search(r"\b(?:age|aged)\b", head, re.I)

    for m in EXP_RANGE.finditer(text):
        if near_experience(m.start(), m.end()):
            found.append(float(m.group(1)))
            spans.append(m.span())
    for m in EXP_SINGLE.finditer(text):
        if any(s <= m.start() < e for s, e in spans):
            continue  # already counted as part of a range
        if near_experience(m.start(), m.end()):
            val = float(m.group(1))
            if val <= 30:  # ignore '1998 years' style garbage
                found.append(val)
    return min(found) if found else None


def mentioned_batch_years(text: str) -> set[int]:
    years: set[int] = set()
    for m in BATCH_MENTION.finditer(text):
        years.update(int(y) for y in re.findall(r"(?:19|20)\d{2}", m.group(1)))
    for m in BATCH_LIST.finditer(text):
        years.update(int(y) for y in re.findall(r"(?:19|20)\d{2}", m.group(1)))
    # keep only plausible graduation years
    this_year = datetime.date.today().year
    return {y for y in years if this_year - 10 <= y <= this_year + 4}


def is_cse_related(title: str, description: str, domain: str = "cse") -> bool:
    if NON_CSE_TITLE.search(title or ""):
        return False
    text = f"{title} {description}"
    if CSE_DOMAIN.search(text):
        return True
    return domain == "govt" and has_cse_branch(text)


# ---------------------------------------------------------------- main API

def judge(title: str, description: str, domain: str = "cse", strict: bool | None = None) -> Verdict:
    """
    Return a Verdict saying whether this job is a fresher CSE opportunity.
    domain="govt" also accepts general technical posts (Engineer, Apprentice, Scientist).
    strict=None uses FRESHER_STRICT; government notifications use strict=False because
    they list eligibility (degree, age) rather than the word "fresher".
    """
    strict = STRICT if strict is None else strict
    title = _clean(title)
    desc = _clean(description)
    full = f"{title}. {desc}"

    if not is_cse_related(title, desc, domain):
        return Verdict(False, "Not a CSE/IT role")

    if ENGINEERING_ONLY:
        why_not = engineering_check(title, desc, domain)
        if why_not:
            return Verdict(False, why_not)

    if SENIOR_TITLE.search(title) and not FRESHER_TITLE.search(title):
        return Verdict(False, f"Senior title ({SENIOR_TITLE.search(title).group(0)})")

    if NO_FRESHERS.search(full):
        return Verdict(False, "Ad says freshers not eligible")

    welcome = bool(FRESHERS_WELCOME.search(full))
    min_exp = min_experience_years(full)
    if min_exp is not None and min_exp > MAX_EXPERIENCE and not welcome:
        return Verdict(False, f"Needs {min_exp:g}+ years experience")

    batches = mentioned_batch_years(full)
    if batches and not (batches & BATCH_YEARS):
        return Verdict(False, f"Only for batch {', '.join(map(str, sorted(batches)))}")

    tags: list[str] = []
    t = title.lower()
    if re.search(r"\bintern|internship", t):
        tags.append("Internship")
    elif re.search(r"apprentic", t):
        tags.append("Apprenticeship")
    elif re.search(r"trainee", t):
        tags.append("Trainee")
    if batches & BATCH_YEARS:
        tags.append("Batch " + "/".join(map(str, sorted(batches & BATCH_YEARS))))
    if min_exp is not None and min_exp <= MAX_EXPERIENCE:
        tags.append("0 yrs exp OK")
    if welcome:
        tags.append("Freshers welcome")

    title_hit = FRESHER_TITLE.search(title)
    desc_hit = FRESHER_DESC.search(desc)
    if title_hit:
        return Verdict(True, f"Title: '{title_hit.group(0).strip()}'", tags)
    if desc_hit or welcome or (min_exp is not None and min_exp <= MAX_EXPERIENCE) or (batches & BATCH_YEARS):
        signal = desc_hit.group(0).strip() if desc_hit else ("freshers welcome" if welcome else "0 yrs experience")
        return Verdict(True, f"Ad mentions '{signal}'", tags)

    if strict:
        return Verdict(False, "No fresher signal (strict mode)")
    if domain == "govt":
        return Verdict(True, "Govt post, no experience asked", tags + ["Check eligibility"])
    return Verdict(True, "Unverified - no experience mentioned", tags + ["Unverified"])
