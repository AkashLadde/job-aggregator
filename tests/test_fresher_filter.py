"""
Checks the fresher filter against realistic job ads.
Run:  python -m tests.test_fresher_filter      (from the project folder)
"""
import os
import sys

os.environ.setdefault("FRESHER_BATCH_YEARS", "2025,2026,2027")
os.environ.setdefault("FRESHER_STRICT", "true")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scrapers.fresher_filter import judge, min_experience_years  # noqa: E402

# (title, description, should_be_accepted)
CASES = [
    # ---------- should be ACCEPTED
    ("Software Engineering Intern", "6 month internship in our Bengaluru office. Python, Git.", True),
    ("Graduate Engineer Trainee - IT", "B.E/B.Tech CSE/IT 2026 pass outs with 60% aggregate.", True),
    ("Associate Software Engineer", "Freshers from 2025 batch. Strong Java fundamentals.", True),
    ("Python Developer", "Experience: 0-1 years. Freshers can apply. Django, REST APIs.", True),
    ("SOC Analyst", "Entry level role in our 24x7 SOC. CompTIA Security+ a plus.", True),
    ("Data Analyst", "We are hiring freshers! SQL, Excel, Power BI. 0 to 2 years experience.", True),
    ("Cloud Support Engineer", "Recent graduates welcome. AWS basics. 4 years B.Tech degree required.", True),
    ("Junior Web Developer", "React, HTML, CSS. Training will be provided.", True),
    ("Cyber Security Apprentice", "Apprenticeship under NATS for B.E CSE graduates.", True),
    ("Java Developer", "1-3 years experience preferred; freshers are also welcome to apply.", True),

    # ---------- should be REJECTED
    ("Senior Software Engineer", "8+ years of experience building distributed systems.", False),
    ("Lead Data Scientist", "Lead a team of ML engineers.", False),
    ("Software Engineer", "Minimum 3 years of experience in Java and Spring Boot.", False),
    ("Python Developer", "Experience: 2-5 years in Python programming.", False),
    ("Security Guard", "Freshers can apply. Night shift at IT park.", False),
    ("Sales Executive - Software Products", "Freshers welcome, good communication.", False),
    ("DevOps Engineer", "We need experienced candidates only. Kubernetes, Terraform.", False),
    ("Software Developer Trainee", "Only 2021 and 2022 batch pass outs eligible.", False),
    ("Engineering Manager", "Manage a team of 10 developers.", False),
    ("Full Stack Developer", "MERN stack, building SaaS dashboards.", False),  # no signal -> strict reject
    ("Machine Learning Engineer II", "Build recommendation models with PyTorch.", False),
    ("Mechanical Engineer Fresher", "Diploma/B.E Mechanical freshers for plant maintenance.", False),
]


def test_cases():
    failures = []
    for title, desc, expected in CASES:
        v = judge(title, desc)
        mark = "OK " if v.accepted == expected else "BAD"
        print(f"[{mark}] {'ACCEPT' if v.accepted else 'reject':6}  {title:40} -> {v.reason} {v.tags}")
        if v.accepted != expected:
            failures.append(title)
    assert not failures, f"Wrong verdicts: {failures}"


def test_experience_parser():
    assert min_experience_years("Minimum 3 years of experience") == 3
    assert min_experience_years("Experience: 0-2 yrs") == 0
    assert min_experience_years("4 years B.Tech degree required") is None
    assert min_experience_years("Age 18 years and above. Experience not required") is None
    assert min_experience_years("3+ years of experience in programming") == 3
    assert min_experience_years("6 months internship") is None


if __name__ == "__main__":
    test_experience_parser()
    test_cases()
    print("\nAll fresher-filter tests passed.")
