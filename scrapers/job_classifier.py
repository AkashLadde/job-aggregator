"""
Puts every job into one of the two streams the digest covers, plus a
sub-stream shown in the email/PDF:

  Cyber Security   -> SOC & Monitoring | VAPT & Pentesting | AppSec & Cloud Security | Cyber Security
  CSE & Allied     -> Data Science & AI/ML | Cloud & DevOps | Testing & QA | Networking | Software Development
                      | Govt / PSU (CSE/IT) for government notifications

Non-engineering "security" titles (Security Guard/Officer) never get here - the
fresher filter drops them first.

The TITLE decides first. The description only decides "Cyber Security" when
it mentions at least two different security topics (so a developer ad that
says "fix vulnerabilities" once stays in CSE & Allied).
"""
import re

CYBER = "Cyber Security"
CSE = "CSE & Allied"

CYBER_TITLE = re.compile(
    r"(cyber|infosec|\bsecurity\b|\bsoc\b|siem|vapt|penetration|pen[\s-]?test|ethical\s+hack|red\s+team|"
    r"blue\s+team|threat|incident\s+response|malware|forensic|appsec|application\s+security|cloud\s+security|"
    r"network\s+security|\bgrc\b|\biam\b|identity\s+and\s+access)",
    re.I,
)
CYBER_DESC_TOPICS = {
    "soc": r"\bsoc\b|security\s+operations",
    "siem": r"siem|splunk|qradar|sentinel",
    "pentest": r"vapt|penetration|pen[\s-]?test|ethical\s+hack|burp",
    "threat": r"threat\s+(?:intel|hunting|detection)|incident\s+response",
    "malware": r"malware|forensic",
    "vuln": r"vulnerabilit",
    "certs": r"ceh\b|security\+|oscp|cissp|comptia\s+security",
    "general": r"cyber\s*-?\s*security|information\s+security|infosec",
}

CYBER_SUB = [
    ("SOC & Monitoring", r"\bsoc\b|siem|monitor|incident|threat|blue\s+team|security\s+operations"),
    ("VAPT & Pentesting", r"vapt|penetration|pen[\s-]?test|ethical\s+hack|red\s+team|offensive"),
    ("AppSec & Cloud Security", r"appsec|application\s+security|cloud\s+security|devsecops|product\s+security"),
]
CSE_SUB = [
    ("Data Science & AI/ML", r"data\s+(?:scien|analy|engineer)|machine\s+learning|\bml\b|\bai\b|artificial\s+intelligence|"
                             r"deep\s+learning|\bnlp\b|computer\s+vision|gen\s?ai|\bllm|analytics|power\s+bi|tableau"),
    ("Cloud & DevOps", r"cloud|devops|\baws\b|azure|\bgcp\b|\bsre\b|site\s+reliability|kubernetes|platform\s+engineer"),
    ("Testing & QA", r"\bqa\b|quality\s+assurance|\btest(?:er|ing)?\b|sdet"),
    ("Networking", r"network\s+(?:engineer|admin|trainee|intern)|\bccna\b|networking"),
]
GOVT_SUB = "Govt / PSU (CSE/IT)"


SOFTWARE_TITLE = re.compile(
    r"developer|software|\bsde\b|\bswe\b|programmer|full[\s-]?stack|front[\s-]?end|back[\s-]?end|\bweb\b|"
    r"java|python|\.net|react|node|android|ios|mobile|application\s+engineer|system\s+engineer",
    re.I,
)


def classify(title: str, description: str = "") -> tuple[str, str]:
    """Return (stream, sub_stream) for a job."""
    title = title or ""
    desc = description or ""
    topics = sum(1 for p in CYBER_DESC_TOPICS.values() if re.search(p, desc, re.I))
    is_cyber = bool(CYBER_TITLE.search(title)) or topics >= 2

    stream = CYBER if is_cyber else CSE
    subs = CYBER_SUB if is_cyber else CSE_SUB
    for name, pattern in subs:               # title decides first
        if re.search(pattern, title, re.I):
            return stream, name
    # A clear developer title is Software Development even if the ad mentions "testing" or "AWS".
    if not is_cyber and SOFTWARE_TITLE.search(title):
        return CSE, "Software Development"
    for name, pattern in subs:               # otherwise look at the description
        if re.search(pattern, desc, re.I):
            return stream, name
    return (CYBER, "Cyber Security") if is_cyber else (CSE, "Software Development")


def is_cyber_security(job: dict) -> bool:
    """Kept for compatibility: uses the stream set by the scraper if present."""
    if job.get("stream"):
        return job["stream"] == CYBER
    return classify(job.get("title", ""), job.get("eligibility", ""))[0] == CYBER
