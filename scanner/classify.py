"""Classify a recruiting email with Claude.

Returns a structured verdict: kind, company, role, confidence, plus an optional
deadline if the email carries an OA/interview due date. Uses a forced tool call
so the output is always valid JSON, and caches the system prompt.
"""
import json

from anthropic import Anthropic

import config

_client = None

SYSTEM = (
    "You classify emails for a personal job-application tracker. Decide whether "
    "an email is about the applicant's OWN job/internship application and, if "
    "so, what stage it signals. Ignore marketing, job-board digests, newsletters "
    "and recruiter cold-outreach for roles not yet applied to. Be conservative: "
    "if you are unsure it concerns a real application the applicant submitted, "
    "return kind='other' with low confidence.\n\n"
    "COMPANY is ALWAYS the employer the applicant applied to, NEVER the "
    "assessment or applicant-tracking vendor. Emails often come FROM a vendor "
    "(HackerRank, CodeSignal, Canditech, HackerEarth, Codility, Workday, "
    "Greenhouse, Lever, Ashby, iCIMS, SmartRecruiters, Workable) on behalf of "
    "the real employer. In those cases the employer is named in the subject or "
    "body, extract THAT, not the vendor. Return the company's common short name "
    "with no legal suffix (Inc, LLC, Ltd) and no regional qualifier: "
    "'MicroStrategy', not 'MicroStrategy India Pvt Ltd'. Use the exact same "
    "name for the same company every time."
)

CLASSIFY_TOOL = {
    "name": "record_classification",
    "description": "Record the classification of one email.",
    "input_schema": {
        "type": "object",
        "properties": {
            "kind": {
                "type": "string",
                "enum": ["confirmation", "rejection", "oa", "interview",
                         "team_match", "offer", "other"],
                "description": "confirmation=application received; oa=online "
                               "assessment/coding test; interview=interview "
                               "invite/scheduling; team_match=team/host matching "
                               "(being matched to a team, manager, or host after "
                               "passing interviews, before or around an offer); "
                               "offer=offer; rejection=turned down; other=not a "
                               "real application update.",
            },
            "company": {
                "type": "string",
                "description": "The EMPLOYER applied to, canonical short form. "
                               "Never the assessment/ATS vendor the email came "
                               "from.",
            },
            "role": {"type": "string"},
            "confidence": {
                "type": "number",
                "description": "0..1 that kind is correct AND this is the "
                               "applicant's own application.",
            },
            "deadline_iso": {
                "type": "string",
                "description": "Full ISO datetime (with year) of an OA/interview "
                               "due date ONLY if an explicit ABSOLUTE date is "
                               "stated (e.g. 'by October 12, 2026'). Do NOT guess "
                               "and never invent a year. Empty if the email gives "
                               "only a relative window (use deadline_days for "
                               "that) or no deadline.",
            },
            "deadline_days": {
                "type": "number",
                "description": "If the email gives a RELATIVE window to complete "
                               "an OA/interview ('within 5 days', 'complete in 72 "
                               "hours', 'one week', 'by end of the week'), the "
                               "number of DAYS from when the email was received "
                               "(convert hours to days: 72 hours = 3). 0 if no "
                               "deadline or if you set deadline_iso instead.",
            },
            "interview_round": {
                "type": "number",
                "description": "For an INTERVIEW email ONLY: which interview round "
                               "this is if the email indicates it (phone "
                               "screen/first round = 1, second round = 2, and so "
                               "on; final/onsite/superday = the highest number "
                               "stated, else your best estimate). 0 if not an "
                               "interview or the round is not indicated.",
            },
            "oa_minutes": {
                "type": "number",
                "description": "For an OA/assessment ONLY: how long the test "
                               "takes to COMPLETE once started, in minutes, if the "
                               "email states it ('you will have 90 minutes', "
                               "'approximately 1 hour', 'a 45-minute assessment'). "
                               "Convert hours to minutes. 0 if not an OA or the "
                               "duration is not stated. This is the test length, "
                               "NOT the deadline window.",
            },
            "oa_completed": {
                "type": "boolean",
                "description": "True ONLY if this email confirms the applicant "
                               "already COMPLETED/SUBMITTED an online assessment "
                               "('thank you for completing the assessment', 'we "
                               "received your submission', 'your assessment is "
                               "complete'). False for an INVITE to take one, a "
                               "reminder, or anything else.",
            },
            "oa_platform": {
                "type": "string",
                "description": "For an OA/assessment ONLY: the TESTING platform "
                               "it runs on if identifiable (e.g. HackerRank, "
                               "CodeSignal, Codility, HackerEarth, CoderPad, "
                               "Karat, Canditech, Woven, Qualified, Byteboard). "
                               "This is the assessment platform, NOT the employer "
                               "and NOT an ATS like Workday/Greenhouse/Lever. "
                               "Empty string if not an OA or not identifiable.",
            },
            "is_internship": {
                "type": "boolean",
                "description": "True if the role is an INTERNSHIP or co-op "
                               "(temporary, student-focused). False if it is a "
                               "regular full-time or part-time job (consulting "
                               "analyst, new-grad SWE, a remote part-time gig, "
                               "etc). If you cannot tell from the email, infer "
                               "from the role title.",
            },
            "is_cs": {
                "type": "boolean",
                "description": "True if the role is a COMPUTER-SCIENCE / software "
                               "/ technical engineering role (software engineer, "
                               "developer, data, ML/AI, security, IT, QA, systems, "
                               "robotics, etc). False for non-technical roles "
                               "(consulting, finance, marketing, sales, "
                               "operations, general business). Infer from the role "
                               "title if the email does not say outright.",
            },
        },
        "required": ["kind", "company", "role", "confidence"],
    },
}


def _get_client():
    global _client
    if _client is None:
        _client = Anthropic(api_key=config.ANTHROPIC_API_KEY)
    return _client


def classify(email: dict) -> dict:
    """email: {sender, subject, body/snippet}. Returns the tool input dict."""
    body = (email.get("body") or email.get("snippet") or "")[:6000]
    user = (
        f"From: {email.get('sender','')}\n"
        f"Subject: {email.get('subject','')}\n\n"
        f"{body}"
    )
    resp = _get_client().messages.create(
        model=config.CLASSIFIER_MODEL,
        max_tokens=400,
        system=[{"type": "text", "text": SYSTEM,
                 "cache_control": {"type": "ephemeral"}}],
        tools=[CLASSIFY_TOOL],
        tool_choice={"type": "tool", "name": "record_classification"},
        messages=[{"role": "user", "content": user}],
    )
    for block in resp.content:
        if block.type == "tool_use":
            out = dict(block.input)
            out.setdefault("company", "")
            out.setdefault("role", "")
            out.setdefault("confidence", 0.0)
            out.setdefault("deadline_iso", "")
            out.setdefault("deadline_days", 0)
            out.setdefault("interview_round", 0)
            out.setdefault("oa_minutes", 0)
            out.setdefault("oa_completed", False)
            out.setdefault("oa_platform", "")
            # None (not a fixed bool) so scan.py falls back to the title heuristic
            out.setdefault("is_internship", None)
            out.setdefault("is_cs", None)
            return out
    return {"kind": "other", "company": "", "role": "", "confidence": 0.0,
            "deadline_iso": "", "deadline_days": 0, "interview_round": 0,
            "oa_minutes": 0, "oa_completed": False, "oa_platform": "",
            "is_internship": None, "is_cs": None}
