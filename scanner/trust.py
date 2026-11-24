"""Decide whether a classifier verdict may be auto-applied (audit 2026-11-21 APP-03/04).

The classifier reads attacker-controllable email, so its verdict is untrusted.
A verdict only auto-applies when:
  1. Gmail authenticated the From domain (DMARC pass, or a DKIM pass aligned
     with the From domain), AND
  2. the From domain plausibly belongs to the company or to a known
     ATS / assessment vendor (skipped for a learned template rule, whose
     fingerprint already pins the sender domain), AND
  3. the verdict doesn't hide existing work (a rejection of an app already at
     OA/interview or later) without a human look.
Anything else goes to the review queue. Also sanitizes the company/role strings
that later reach calendar titles and the prep-brief LLM.
"""
from __future__ import annotations

import re

import normalize
from fingerprint import sender_domain

FREEMAIL = {
    "gmail.com", "googlemail.com", "outlook.com", "hotmail.com", "live.com",
    "yahoo.com", "icloud.com", "me.com", "aol.com", "proton.me",
    "protonmail.com", "gmx.com", "mail.com", "zoho.com", "yandex.com",
}

# hiring platforms that send on a company's behalf (match on the registrable
# suffix, e.g. "us.greenhouse-mail.io" matches "greenhouse-mail.io")
VENDORS = {
    "greenhouse.io", "greenhouse-mail.io", "lever.co", "ashbyhq.com",
    "myworkday.com", "workday.com", "myworkdayjobs.com", "smartrecruiters.com",
    "icims.com", "jobvite.com", "taleo.net", "successfactors.com",
    "oraclecloud.com", "eightfold.ai", "avature.net", "workable.com",
    "recruitee.com", "breezy.hr", "bamboohr.com", "jazzhr.com", "applytojob.com",
    "rippling.com", "gem.com", "beamery.com", "phenompeople.com", "paradox.ai",
    "joinhandshake.com", "linkedin.com", "indeed.com", "indeedemail.com",
    "simplify.jobs", "wellfound.com", "hackerrank.com", "hackerrankforwork.com",
    "codesignal.com", "codility.com", "hirevue.com", "karat.com", "karat.io",
    "modernhire.com", "pymetrics.com", "pymetrics.ai", "harver.com",
    "shl.com", "criteriacorp.com", "testgorilla.com", "coderpad.io",
    "goodtime.io", "calendly.com", "ripplematch.com", "paylocity.com",
    "ukg.com", "ultipro.com", "adp.com", "dayforcehcm.com", "teamtailor.com",
    "personio.de", "pinpointhq.com", "comeet.co", "hireology.com",
    "oracle.com", "brassring.com", "kenexa.com", "dover.com", "otta.com",
}

# words too generic to identify a company by themselves
_GENERIC = {
    "inc", "llc", "ltd", "corp", "corporation", "company", "group", "the",
    "technologies", "technology", "tech", "labs", "systems", "solutions",
    "consulting", "services", "global", "international", "holdings", "partners",
    "energy", "capital", "health", "financial", "software", "digital", "data",
    "america", "american", "united", "national", "first", "general", "boston",
}

_RISKY_STAGES = {"oa", "interview", "team_match", "offer"}


def _registrable_match(domain: str, suffixes: set[str]) -> bool:
    return any(domain == s or domain.endswith("." + s) for s in suffixes)


def authenticated(auth_results: str, domain: str) -> bool:
    """True if Gmail's Authentication-Results shows the From domain verified."""
    if not auth_results or not domain:
        return False
    a = auth_results.lower()
    # DMARC pass is checked against the From header domain
    m = re.search(r"dmarc=pass[^;]*header\.from=([a-z0-9.-]+)", a)
    if m and (domain == m.group(1) or domain.endswith("." + m.group(1))):
        return True
    # otherwise a DKIM pass whose signing domain aligns with the From domain
    for d in re.findall(r"dkim=pass[^;]*?header\.(?:i=@?|d=)([a-z0-9.-]+)", a):
        if domain == d or domain.endswith("." + d) or d.endswith("." + domain):
            return True
    return False


def plausible(domain: str, company: str) -> bool:
    """From domain belongs to the company or a hiring vendor."""
    if not domain or domain in FREEMAIL:
        return False
    if _registrable_match(domain, VENDORS):
        return True
    labels = re.sub(r"[^a-z0-9.]", "", domain).split(".")
    host = "".join(labels[:-1]) if len(labels) > 1 else labels[0]
    key = normalize.company_key(company or "")
    compact = re.sub(r"[^a-z0-9]", "", key)
    if len(compact) >= 3 and compact in host:
        return True
    words = [w for w in re.findall(r"[a-z0-9]+", (company or "").lower())
             if len(w) >= 4 and w not in _GENERIC]
    return any(w in host for w in words)


def hides_work(conn, verdict: dict) -> bool:
    """A rejection that would bury an application already past applied."""
    if verdict.get("kind") != "rejection":
        return False
    key = normalize.company_key(verdict.get("company") or "")
    if not key:
        return False
    row = conn.execute(
        "SELECT 1 FROM applications WHERE company_key = ? AND status IN "
        f"({','.join('?' * len(_RISKY_STAGES))}) LIMIT 1",
        (key, *sorted(_RISKY_STAGES)),
    ).fetchone()
    return bool(row)


def gate(conn, msg: dict, verdict: dict, learned: bool) -> str | None:
    """None if the verdict may auto-apply, else a short reason to queue it."""
    domain = sender_domain(msg.get("sender", ""))
    if not authenticated(msg.get("auth", ""), domain):
        return f"sender {domain or '?'} not authenticated"
    if domain in FREEMAIL:
        return f"freemail sender {domain}"
    if not learned and not plausible(domain, verdict.get("company", "")):
        return f"sender {domain} doesn't match {verdict.get('company')!r}"
    if hides_work(conn, verdict):
        return "rejection for an app already past applied"
    return None


_SAFE = re.compile(r"[^A-Za-z0-9 &.,'()/+\-]")
_URLISH = re.compile(r"(https?://\S+|www\.\S+|\b[a-z0-9-]+(\.[a-z0-9-]+)*\.[a-z]{2,}(/\S*)?)", re.I)


def clean_name(s: str | None, cap: int = 60) -> str:
    """Company/role text that ends up in calendar titles and LLM prompts:
    no URLs, no odd characters, bounded length."""
    # full links vanish; a bare domain keeps only its first word, so
    # "Booking.com" -> "Booking" but no clickable/typeable link survives
    s = _URLISH.sub(lambda m: "" if re.match(r"(https?://|www\.)", m.group(0), re.I)
                    else m.group(0).split(".")[0], s or "")
    s = _SAFE.sub("", s)
    s = re.sub(r"\s+", " ", s).strip(" .,-")
    return s[:cap].rstrip()


def safe_log(s: str | None, cap: int = 60) -> str:
    """Email subjects are attacker text; log them inert (APP-10)."""
    s = re.sub(r"[^\w .,:#()&'/-]", "", s or "")
    return repr(s[:cap])
