"""
Checks the ENGINEERING-ONLY rules (Cyber Security + CSE-allied branches)
and the stream / sub-stream labels.
Run:  python -m tests.test_streams
"""
import os
import sys

os.environ.setdefault("FRESHER_BATCH_YEARS", "2025,2026,2027")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scrapers.fresher_filter import judge  # noqa: E402
from scrapers.job_classifier import classify  # noqa: E402

# (title, description, domain, should_be_accepted)
ENGG_CASES = [
    # ---------- KEEP: engineering roles in Cyber Security / CSE-allied branches
    ("Data Science Intern", "B.E/B.Tech in ISE, CSE or AI & DS, 2026 batch.", "cse", True),
    ("Graduate Engineer Trainee", "BE in Information Science or Computer Science, 2025 pass outs.", "cse", True),
    ("Software Engineer Trainee", "B.E/B.Tech/MCA freshers. Java and SQL.", "cse", True),
    ("Cyber Security Intern", "Final year B.Tech Cyber Security / CSE students.", "cse", True),
    ("Associate Software Engineer", "Freshers. Open to CSE, ECE, EEE and Mechanical branches.", "cse", True),
    ("Python Developer Fresher", "You will be working on our production servers. Freshers welcome.", "cse", True),
    ("Graduate Engineer Trainee - IT", "B.E/B.Tech CSE/IT 2026 pass outs.", "cse", True),
    ("ECIL GET Recruitment 2026", "B.E/B.Tech ECE, CSE, EEE, Mechanical. 2026 pass outs.", "govt", True),
    ("NIELIT Scientist B Recruitment", "B.E/B.Tech Computer Science / IT with GATE score.", "govt", True),
    # ---------- DROP: not engineering, or other branch
    ("IT Helpdesk Fresher", "Freshers welcome. Resolve laptop issues.", "cse", False),
    ("Data Entry Operator - Fresher", "Typing speed 30 wpm. Any graduate.", "cse", False),
    ("UI/UX Designer Intern", "Figma, user research. Internship.", "cse", False),
    ("Technical Support Associate (Voice)", "Freshers can apply. Night shift. Software product support.", "cse", False),
    ("Software Trainee", "BCA / B.Sc Computer Science freshers only.", "cse", False),
    ("Junior Python Developer", "Any graduate can apply. Freshers welcome.", "cse", False),
    ("VLSI Design Trainee", "Freshers B.E ECE. Verilog, RTL design, scripting in Python.", "cse", False),
    ("Graduate Engineer Trainee", "B.E/B.Tech Mechanical or Electrical freshers. AutoCAD and Python basics.", "cse", False),
    ("IOCL Apprentice Recruitment 2026", "Graduate apprentice. Diploma / B.E Mechanical, Civil, Electrical.", "govt", False),
    ("BHEL Engineer Trainee Recruitment", "Engineering graduates. Apply online.", "govt", False),
    ("Business Analyst Fresher", "Freshers. SQL and Excel.", "cse", False),
]

# (title, description, expected stream, expected sub-stream)
STREAM_CASES = [
    ("SOC Analyst Trainee", "Monitor SIEM alerts.", "Cyber Security", "SOC & Monitoring"),
    ("VAPT Intern", "Web application penetration testing.", "Cyber Security", "VAPT & Pentesting"),
    ("Cyber Security Intern", "Learn security basics.", "Cyber Security", "Cyber Security"),
    ("Graduate Engineer Trainee", "Work in our SOC: SIEM monitoring, incident response.", "Cyber Security", "SOC & Monitoring"),
    ("Data Science Intern", "Python, pandas.", "CSE & Allied", "Data Science & AI/ML"),
    ("AI/ML Engineering Intern", "PyTorch.", "CSE & Allied", "Data Science & AI/ML"),
    ("Cloud Support Engineer", "AWS basics.", "CSE & Allied", "Cloud & DevOps"),
    ("QA Engineer Fresher", "Selenium.", "CSE & Allied", "Testing & QA"),
    ("Java Developer", "Write unit testing and fix vulnerabilities. Deploy on AWS.", "CSE & Allied", "Software Development"),
    ("Graduate Engineer Trainee - IT", "Java, SQL.", "CSE & Allied", "Software Development"),
    ("Graduate Engineer Trainee - Security", "Entry level role for B.E graduates in our SOC.", "Cyber Security", "SOC & Monitoring"),
]


def test_engineering_rules():
    bad = []
    for title, desc, domain, expected in ENGG_CASES:
        v = judge(title, desc, domain=domain, strict=False if domain == "govt" else None)
        mark = "OK " if v.accepted == expected else "BAD"
        print(f"[{mark}] {'KEEP' if v.accepted else 'drop':4}  {title:40} -> {v.reason}")
        if v.accepted != expected:
            bad.append(title)
    assert not bad, f"Wrong verdicts: {bad}"


def test_streams():
    bad = []
    for title, desc, stream, sub in STREAM_CASES:
        got = classify(title, desc)
        mark = "OK " if got == (stream, sub) else "BAD"
        print(f"[{mark}] {title:32} -> {got[0]} / {got[1]}")
        if got != (stream, sub):
            bad.append((title, got))
    assert not bad, f"Wrong streams: {bad}"


if __name__ == "__main__":
    test_engineering_rules()
    print()
    test_streams()
    print("\nAll stream tests passed.")
