"""Generate a concise interview-prep brief with Claude, dropped into the
interview calendar event + prep block so each scheduled interview arrives with a
ready study sheet. Fails soft (empty string) so scheduling never breaks."""
import re

import voice
from trust import clean_name

TASK = (
    "You write tight, skimmable interview-prep briefs for a University of "
    "Maryland CS undergraduate interviewing for software-engineering "
    "INTERNSHIPS. Given a company and role, output PLAIN TEXT (no markdown, no "
    "bold, no headers symbols), under ~220 words, in these labeled parts:\n"
    "Company: 1-2 sentences on what they actually build.\n"
    "Format: the likely interview rounds for a SWE intern there (online "
    "assessment, 1-2 technical/coding rounds, behavioral), realistic for that "
    "company's tier; say plainly if you're unsure.\n"
    "Practice: 4-5 representative things to drill (mix of DS&A topics and "
    "anything role-specific).\n"
    "Tips: 2-3 concrete, company-specific pointers.\n"
    "Be practical. Never invent specifics you're unsure of; keep those "
    "generic. No preamble, start at 'Company:'."
)


_URL = re.compile(r"(https?://\S+|www\.\S+|\b[\w-]+\.(com|net|org|io|co|app|xyz|ru|dev|link|ly)(/\S*)?)", re.I)


def _strip_links(t):
    """The brief lands in a trusted calendar event; never let it carry links
    (company/role are email-derived, audit 2026-11-21 APP-04)."""
    return _URL.sub("[link removed]", t)


def interview_brief(company: str, role: str) -> str:
    company, role = clean_name(company), clean_name(role, 90)
    if not company:
        return ""
    try:
        return _strip_links(voice.write(
            TASK, f"Company: {company}\nRole: {role or 'Software Engineer Intern'}",
            kind="doc", max_tokens=900))
    except Exception:
        return ""  # scheduling must not fail because a brief couldn't be written
