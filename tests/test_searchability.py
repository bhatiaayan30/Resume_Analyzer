import pytest
from analyzer.utils import check_searchability

def test_check_searchability_passes_all():
    text = """
    Ayan Bhatia
    ayan@example.com | (555) 123-4567

    SUMMARY
    Experienced software engineer.

    EXPERIENCE
    Software Engineer at Tech Corp
    Jan 2020 - Present
    - Did some coding

    EDUCATION
    University of Somewhere
    2016 - 2020

    SKILLS
    Python, Django, React
    """
    checks = check_searchability(text)
    
    assert len(checks) == 3
    for check in checks:
        assert check["passed"] is True

def test_check_searchability_fails_contact():
    text = """
    Ayan Bhatia
    No contact info here.

    SUMMARY
    Experienced software engineer.
    
    EXPERIENCE
    2020 - 2022
    """
    checks = check_searchability(text)
    contact_check = next(c for c in checks if c["check_name"] == "Contact Information")
    assert contact_check["passed"] is False

def test_check_searchability_fails_date():
    text = """
    ayan@example.com | 555-123-4567
    EXPERIENCE
    Software Engineer
    I worked here for a while.
    SUMMARY
    """
    checks = check_searchability(text)
    date_check = next(c for c in checks if c["check_name"] == "Date Parseability")
    assert date_check["passed"] is False

def test_check_searchability_fails_headings():
    text = """
    ayan@example.com | 555-123-4567
    2020 - Present
    My Journey
    I worked here.
    My Learnings
    School
    """
    checks = check_searchability(text)
    headings_check = next(c for c in checks if c["check_name"] == "Standard Section Headings")
    assert headings_check["passed"] is False
