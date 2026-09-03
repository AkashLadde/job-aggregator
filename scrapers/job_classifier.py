"""
Classifies a job as Cyber Security-focused or general CSE/allied-branch,
based on keyword matching against the title and eligibility/description text.
"""

CYBER_KEYWORDS = [
    "cyber security", "cybersecurity", "cyber-security", "infosec",
    "information security", "network security", "soc analyst",
    "penetration test", "pen test", "ethical hack", "vulnerability",
    "threat intel", "incident response", "security operations",
    "siem", "malware", "application security", "cloud security",
    "security engineer", "security analyst",
]


def is_cyber_security(job: dict) -> bool:
    text = f"{job.get('title', '')} {job.get('eligibility', '')} {job.get('sector', '')}".lower()
    return any(kw in text for kw in CYBER_KEYWORDS)
