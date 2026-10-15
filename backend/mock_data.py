"""Labelled SAMPLE data for mock mode (no API key / MOCK=1) and for offline tests.

Every scheme here carries ``"sample": True`` and the UI shows a "Sample" badge.
Names and portals are real and well known; amounts, limits and especially
*deadlines* are indicative placeholders set relative to today so the demo
always shows open, closing-soon and closed states. Always verify on the portal.
"""
from __future__ import annotations

import json
import time
from datetime import date, timedelta
from urllib.parse import quote
from typing import Any, Iterator

from matcher import Profile, document_checklist, rank


def _d(days: int) -> str:
    return (date.today() + timedelta(days=days)).strftime("%d %b %Y")


def sample_schemes() -> list[dict[str, Any]]:
    return [
        {
            "name": "Post-Matric Scholarship for SC students (Telangana ePASS)",
            "provider": "Government of Telangana · SC Development Dept.",
            "source_type": "government",
            "amount": "Full tuition fee reimbursement + maintenance allowance",
            "deadline": _d(38),
            "eligibility": {
                "states": ["Telangana"], "gender": "All", "categories": ["Scheduled Caste"],
                "course_levels": ["Post Matric"], "income_limit": "₹2 lakh per annum",
                "min_marks_current": "Pass in previous year", "years_of_study": "",
            },
            "documents_required": ["Income certificate", "Caste certificate", "Aadhaar card", "Bank passbook",
                                   "Bonafide certificate", "Previous year marks memo", "Ration card"],
            "application_url": "https://telanganaepass.cgg.gov.in/",
            "source_url": "https://telanganaepass.cgg.gov.in/",
            "notes": "Apply through the Telangana ePASS portal; college verifies the application.",
            "sample": True,
        },
        {
            "name": "AICTE Pragati Scholarship for Girls",
            "provider": "AICTE / Ministry of Education (via National Scholarship Portal)",
            "source_type": "government",
            "amount": "₹50,000 per year",
            "deadline": _d(24),
            "eligibility": {
                "states": "All India", "gender": "Girls", "categories": "All",
                "course_levels": ["Diploma", "UG"], "streams": ["Engineering / Technical"],
                "income_limit": "₹8 lakh per annum", "years_of_study": "1, 2",
            },
            "documents_required": ["Aadhaar card", "Income certificate", "Class 10 marksheet", "Class 12 marksheet",
                                   "Admission letter", "Tuition fee receipt", "Bank passbook",
                                   "Category certificate (if applicable)", "Parent's declaration"],
            "application_url": "https://scholarships.gov.in/",
            "source_url": "https://www.aicte-india.org/schemes/students-development-schemes/Pragati",
            "notes": "Up to two girl children per family; AICTE-approved institutions only.",
            "sample": True,
        },
        {
            "name": "Kotak Kanya Scholarship",
            "provider": "Kotak Education Foundation (CSR)",
            "source_type": "private",
            "amount": "₹1.5 lakh per year for the full course",
            "deadline": _d(9),
            "eligibility": {
                "states": "All India", "gender": "Female", "categories": "All", "course_levels": ["UG"],
                "streams": ["Engineering", "Medicine", "Law", "Management", "Architecture"],
                "income_limit": "₹3.2 lakh per annum", "min_marks_12": "85%", "years_of_study": "1",
            },
            "documents_required": ["Class 12 marksheet", "Income proof", "Aadhaar card", "Admission proof",
                                   "Fee receipt", "Bank account details", "Passport-size photograph"],
            "application_url": "https://kotakeducation.org/kotak-kanya-scholarship/",
            "source_url": "https://kotakeducation.org/kotak-kanya-scholarship/",
            "notes": "Merit-cum-means; for girls entering professional courses at premier institutes.",
            "sample": True,
        },
        {
            "name": "Central Sector Scheme of Scholarship for College & University Students (CSSS)",
            "provider": "Dept. of Higher Education, Ministry of Education (NSP)",
            "source_type": "government",
            "amount": "₹12,000 per year (UG) · ₹20,000 per year (PG)",
            "deadline": _d(31),
            "eligibility": {
                "states": "All India", "gender": "All", "categories": "All", "course_levels": ["UG", "PG"],
                "income_limit": "₹4.5 lakh per annum", "min_marks_12": "80%",
            },
            "documents_required": ["Class 12 marksheet", "Income certificate", "Aadhaar card", "Bank passbook",
                                   "Bonafide certificate", "Passport-size photograph"],
            "application_url": "https://scholarships.gov.in/",
            "source_url": "https://scholarships.gov.in/",
            "notes": "Top 20 percentile of the Class 12 board; regular courses only.",
            "sample": True,
        },
        {
            "name": "PM YASASVI Post-Matric Scholarship (OBC / EBC / DNT)",
            "provider": "Ministry of Social Justice & Empowerment (NSP)",
            "source_type": "government",
            "amount": "Academic allowance ₹5,000–₹20,000 per year + fee support",
            "deadline": _d(44),
            "eligibility": {
                "states": "All India", "gender": "All", "categories": ["OBC", "EBC", "DNT"],
                "course_levels": ["Post Matric"], "income_limit": "₹2.5 lakh per annum",
            },
            "documents_required": ["Caste certificate", "Income certificate", "Aadhaar card", "Bank passbook",
                                   "Previous year marksheet", "Bonafide certificate", "Domicile certificate"],
            "application_url": "https://scholarships.gov.in/",
            "source_url": "https://socialjustice.gov.in/",
            "notes": "Applications are verified by the institute and then the state nodal officer.",
            "sample": True,
        },
        {
            "name": "Bihar Post-Matric Scholarship for BC / EBC students",
            "provider": "Government of Bihar · BC & EBC Welfare Dept. (PMS Online)",
            "source_type": "government",
            "amount": "Course fee reimbursement up to ₹15,000 per year (varies by course)",
            "deadline": _d(50),
            "eligibility": {
                "states": ["Bihar"], "gender": "All", "categories": ["Other Backward Classes", "EBC"],
                "course_levels": ["Post Matric"], "income_limit": "₹3 lakh per annum",
            },
            "documents_required": ["Caste certificate", "Income certificate", "Residence certificate", "Aadhaar card",
                                   "Bank passbook", "Previous year marksheet", "Fee receipt", "Bonafide certificate"],
            "application_url": "https://pmsonline.bih.nic.in/",
            "source_url": "https://pmsonline.bih.nic.in/",
            "notes": "Students studying inside or outside Bihar can apply if domiciled in Bihar.",
            "sample": True,
        },
        {
            "name": "Rajarshi Chhatrapati Shahu Maharaj Shikshan Shulkh Shishyavrutti (MahaDBT)",
            "provider": "Government of Maharashtra · Higher & Technical Education",
            "source_type": "government",
            "amount": "50% of tuition and exam fees reimbursed",
            "deadline": _d(60),
            "eligibility": {
                "states": ["Maharashtra"], "gender": "All", "categories": ["General", "OBC", "EWS"],
                "course_levels": ["UG", "PG"], "streams": ["Professional courses"],
                "income_limit": "₹8 lakh per annum",
            },
            "documents_required": ["Domicile certificate", "Income certificate", "Aadhaar card", "Class 12 marksheet",
                                   "Admission / CAP allotment letter", "Fee receipt", "Bank passbook"],
            "application_url": "https://mahadbt.maharashtra.gov.in/",
            "source_url": "https://mahadbt.maharashtra.gov.in/",
            "notes": "Apply on MahaDBT; the college forwards the application.",
            "sample": True,
        },
        {
            "name": "Post-Matric Scholarship for Minority Communities",
            "provider": "Ministry of Minority Affairs (NSP)",
            "source_type": "government",
            "amount": "Admission + tuition fee up to ₹10,000 per year + maintenance allowance",
            "deadline": _d(29),
            "eligibility": {
                "states": "All India", "gender": "All", "categories": "All", "minority_only": True,
                "course_levels": ["Post Matric"], "income_limit": "₹2 lakh per annum", "min_marks_current": "50%",
            },
            "documents_required": ["Self-declaration of community", "Income certificate", "Aadhaar card",
                                   "Bank passbook", "Previous year marksheet", "Bonafide certificate"],
            "application_url": "https://scholarships.gov.in/",
            "source_url": "https://scholarships.gov.in/",
            "notes": "30% of scholarships are earmarked for girl students.",
            "sample": True,
        },
        {
            "name": "HDFC Bank Parivartan's ECSS Programme",
            "provider": "HDFC Bank (CSR)",
            "source_type": "private",
            "amount": "Up to ₹75,000 (UG) · up to ₹1 lakh (professional)",
            "deadline": _d(19),
            "eligibility": {
                "states": "All India", "gender": "All", "categories": "All", "course_levels": ["Diploma", "UG", "PG"],
                "income_limit": "₹2.5 lakh per annum", "min_marks_current": "55%",
            },
            "documents_required": ["Previous year marksheet", "Income proof", "Aadhaar card", "Bank passbook",
                                   "Fee receipt", "Passport-size photograph", "Admission proof"],
            "application_url": "https://www.hdfcbank.com/personal/about-us/corporate-social-responsibility",
            "source_url": "https://www.hdfcbank.com/personal/about-us/corporate-social-responsibility",
            "notes": "Need-based; students facing a family crisis get priority.",
            "sample": True,
        },
        {
            "name": "Post-Matric Scholarship for Students with Disabilities",
            "provider": "Dept. of Empowerment of Persons with Disabilities (NSP)",
            "source_type": "government",
            "amount": "Maintenance allowance + course fee up to ₹1.5 lakh per year",
            "deadline": _d(35),
            "eligibility": {
                "states": "All India", "gender": "All", "categories": "All", "pwd_only": True,
                "course_levels": ["Post Matric"], "income_limit": "₹2.5 lakh per annum",
            },
            "documents_required": ["Disability certificate (40%+)", "Income certificate", "Aadhaar card",
                                   "Bank passbook", "Previous year marksheet", "Bonafide certificate"],
            "application_url": "https://scholarships.gov.in/",
            "source_url": "https://disabilityaffairs.gov.in/",
            "notes": "Benchmark disability of 40% or more.",
            "sample": True,
        },
        {
            "name": "Reliance Foundation Undergraduate Scholarship",
            "provider": "Reliance Foundation (CSR)",
            "source_type": "private",
            "amount": "Up to ₹2 lakh over the course",
            "deadline": _d(-6),
            "eligibility": {
                "states": "All India", "gender": "All", "categories": "All", "course_levels": ["UG"],
                "income_limit": "₹15 lakh per annum", "min_marks_12": "60%", "years_of_study": "1",
            },
            "documents_required": ["Class 12 marksheet", "Income proof", "Aadhaar card", "Admission proof",
                                   "Passport-size photograph"],
            "application_url": "https://scholarships.reliancefoundation.org/",
            "source_url": "https://scholarships.reliancefoundation.org/",
            "notes": "Merit-cum-means; includes an aptitude test.",
            "sample": True,
        },
        {
            "name": "Sitaram Jindal Foundation Scholarship",
            "provider": "Sitaram Jindal Foundation (trust)",
            "source_type": "private",
            "amount": "₹500–₹3,200 per month depending on course",
            "deadline": "Rolling — applications accepted throughout the year",
            "eligibility": {
                "states": "All India", "gender": "All", "categories": "All",
                "course_levels": ["School", "Diploma", "UG", "PG"], "income_limit": "₹4 lakh per annum",
                "min_marks_current": "60%",
            },
            "documents_required": ["Previous year marksheet", "Income certificate", "Bonafide certificate",
                                   "Bank passbook", "Passport-size photograph"],
            "application_url": "https://www.sitaramjindalfoundation.org/scholarships-for-students-in-bangalore.php",
            "source_url": "https://www.sitaramjindalfoundation.org/",
            "notes": "Applications by post; separate marks criteria for boys and girls.",
            "sample": True,
        },
    ]


SAMPLE_STUDENTS = {
    "telangana_sc_btech": {
        "label": "Priya · Telangana · SC · B.Tech yr 2",
        "name": "Priya", "state": "Telangana", "domicile_state": "Telangana", "gender": "Female", "category": "SC",
        "minority": False, "pwd": False, "course_level": "UG", "course": "B.Tech", "branch": "CSE", "year": 2,
        "marks_10": 92, "marks_12": 88, "marks_current": 81, "family_income": 180000,
        "institution_type": "government", "single_girl_child": False,
    },
    "bihar_obc_ba": {
        "label": "Rahul · Bihar · OBC · B.A. yr 1",
        "name": "Rahul", "state": "Bihar", "domicile_state": "Bihar", "gender": "Male", "category": "OBC",
        "minority": False, "pwd": False, "course_level": "UG", "course": "B.A.", "branch": "History", "year": 1,
        "marks_10": 71, "marks_12": 68, "marks_current": None, "family_income": 220000,
        "institution_type": "government", "single_girl_child": False,
    },
    "maharashtra_general_mbbs": {
        "label": "Sneha · Maharashtra · General · MBBS yr 3 · ₹2.5L",
        "name": "Sneha", "state": "Maharashtra", "domicile_state": "Maharashtra", "gender": "Female",
        "category": "General", "minority": False, "pwd": False, "course_level": "UG", "course": "MBBS", "branch": "",
        "year": 3, "marks_10": 94, "marks_12": 91, "marks_current": 76, "family_income": 250000,
        "institution_type": "government", "single_girl_child": True,
    },
}


# --------------------------------------------------------------------------- #
# Fake pipelines (same event shapes as the live ones)
# --------------------------------------------------------------------------- #

def _sleep(seconds: float) -> None:
    if seconds > 0:
        time.sleep(seconds)


def mock_discover_events(profile: Profile, delay: float = 0.35) -> Iterator[dict[str, Any]]:
    schemes = sample_schemes()
    queries = [f"[sample] post matric scholarship {profile.domicile_state or 'India'} {profile.category}".strip(),
               f"[sample] {profile.course} scholarship {profile.gender} 2026-27".strip()]
    yield {"stage": "searching", "queries": queries, "message": f"Searching {len(queries)} queries (sample data)"}
    _sleep(delay)
    yield {"stage": "found", "count": 23, "message": "Found 23 pages (sample)"}
    _sleep(delay)
    yield {"stage": "kept", "count": len(schemes), "message": f"Kept {len(schemes)} scholarship pages (sample)"}
    ranked_so_far = []
    for i, scheme in enumerate(schemes, 1):
        _sleep(delay)
        ranked_so_far = rank(profile, schemes[:i])
        just = next(r for r in ranked_so_far if r["name"] == scheme["name"])
        yield {"stage": "extracting", "done": i, "total": len(schemes), "name": scheme["name"],
               "cache_hit": False, "scheme": just, "message": f"Extracted {i}/{len(schemes)}: {scheme['name']}"}
    final = rank(profile, schemes)
    yield {"stage": "ranked", "results": final, "checklist": document_checklist(final),
           "meta": {"mode": "mock", "sample": True, "queries": queries, "agent_runs": 0, "credits_used": 0,
                    "cache_hits": 0, "seconds": round(delay * (len(schemes) + 3), 1)},
           "message": f"Ranked {len(final)} schemes"}


def mock_prefill_events(fields: list[dict[str, str]], url: str, delay: float = 0.6) -> Iterator[dict[str, Any]]:
    """Mirrors STARTED -> STREAMING_URL -> PROGRESS... -> COMPLETE from the TinyFish SDK."""
    yield {"type": "STARTED", "run_id": "mock-run-0001", "message": "Agent started (sample run)"}
    _sleep(delay)
    preview = "/demo-form?preview=1&f=" + quote(json.dumps(fields))
    yield {"type": "STREAMING_URL", "run_id": "mock-run-0001", "streaming_url": preview,
           "message": "Live browser connected (sample preview — simulated typing)"}
    _sleep(delay)
    yield {"type": "PROGRESS", "message": f"Opening {url}"}
    _sleep(delay)
    yield {"type": "PROGRESS", "message": "Reading the form: found sections Personal, Academic, Bank, Documents, Declaration"}
    filled, manual = [], []
    for f in fields:
        _sleep(delay * 0.6)
        yield {"type": "PROGRESS", "message": f"Typing {f['field']} → {f['value']}"}
        filled.append({"field": f["field"], "value": f["value"]})
    for f in ("Aadhaar number", "Mobile OTP", "Bank account number", "Upload: income certificate",
              "Upload: caste certificate", "Declaration checkbox"):
        manual.append({"field": f, "reason": "Sensitive — the agent never enters IDs, OTPs, bank numbers or uploads files"})
    _sleep(delay)
    yield {"type": "PROGRESS", "message": "Reached the Declaration section. Submit button is visible — STOPPING as instructed."}
    _sleep(delay)
    yield {"type": "COMPLETE", "run_id": "mock-run-0001", "status": "COMPLETED",
           "result": {"filled": filled, "needs_manual_input": manual,
                      "stopped_before": "Declaration & Submit — the student must review and submit themselves"},
           "message": "Done (sample run)"}
