"""Template fingerprinting.

Two emails have the same fingerprint when they come from the same sender and
share the same boilerplate skeleton, once the personalized parts (company name,
your name, dates, numbers, urls) are stripped out. This is what lets the review
queue learn: "this rejection template again" collapses to one fingerprint.
"""
import hashlib
import re

# personalized / variable tokens we normalize away before hashing
_URL = re.compile(r"https?://\S+")
_EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
_NUM = re.compile(r"\d+")
_WS = re.compile(r"\s+")
_NONWORD = re.compile(r"[^a-z ]+")


def sender_domain(from_header: str) -> str:
    m = _EMAIL.search(from_header or "")
    if not m:
        return (from_header or "").strip().lower()
    return m.group(0).split("@", 1)[1].lower()


def _skeleton(text: str, strip_terms: list[str] | None = None) -> str:
    """Reduce a body to its reusable boilerplate skeleton.

    strip_terms are variable values (applicant name, company name) removed so
    that the same template addressed to different companies collapses to one
    fingerprint.
    """
    t = (text or "").lower()
    t = _URL.sub(" ", t)
    t = _EMAIL.sub(" ", t)
    for term in strip_terms or []:
        for part in (term or "").lower().split():
            if len(part) > 1:
                t = t.replace(part, " ")
    t = _NUM.sub(" ", t)
    t = _NONWORD.sub(" ", t)
    t = _WS.sub(" ", t).strip()
    # keep only the first ~60 significant words: templates diverge in the tail
    words = t.split(" ")[:60]
    return " ".join(words)


def compute(from_header: str, subject: str, body: str,
            strip_terms: list[str] | None = None) -> str:
    """Stable fingerprint for an email's template.

    Pass the applicant name and (once known) the company as strip_terms so the
    variable bits don't leak into the hash.
    """
    domain = sender_domain(from_header)
    subj_skel = _skeleton(subject, strip_terms)
    subj_skel = " ".join(subj_skel.split(" ")[:6])
    body_skel = _skeleton(body, strip_terms)
    raw = f"{domain}\n{subj_skel}\n{body_skel}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
