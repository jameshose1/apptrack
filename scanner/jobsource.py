"""Job posting source: the SimplifyJobs / Pitt CSC community internship list.

Downloads the structured listings JSON and yields normalized, relevant postings
(active, right term, software, US). No scraping — it's a public data file.
"""
import json
import re
import urllib.request
from datetime import datetime, timezone

import config
import normalize

# titles that aren't an undergrad summer internship: new-grad/full-time + PhD-only
_EXCLUDE_TITLE_RE = re.compile(
    r"new.?grad|new graduate|full.?time|entry.?level|\bph\.?\s?d\b|doctoral",
    re.I,
)

_US_STATES = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", "HI", "ID", "IL",
    "IN", "IA", "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN", "MS", "MO", "MT",
    "NE", "NV", "NH", "NJ", "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI",
    "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY", "DC",
}
_DREAM_KEYS = {normalize.company_key(c) for c in config.DREAM_COMPANIES}


def _is_us(locations) -> bool:
    for loc in locations or []:
        low = loc.strip().lower()
        if low in ("remote", "remote in usa", "united states"):
            return True
        tail = loc.split(",")[-1].strip()
        if tail in _US_STATES or tail in ("USA", "United States"):
            return True
    return False


def _is_dream(company: str) -> bool:
    # whole-word match on the normalized key so "Uberflip" != "Uber"
    return bool(set(normalize.company_key(company).split()) & _DREAM_KEYS)


def is_defense(company: str) -> bool:
    """Defense / gov-contractor / FFRDC employer (substring match on the name)."""
    if not config.EXCLUDE_DEFENSE:
        return False
    c = (company or "").lower()
    return any(kw in c for kw in config.DEFENSE_KEYWORDS)


def _excluded_title(title: str) -> bool:
    return config.EXCLUDE_NEW_GRAD and bool(_EXCLUDE_TITLE_RE.search(title or ""))


def _relevant(e) -> bool:
    return bool(
        e.get("active")
        and e.get("is_visible")
        and config.JOB_TERM in (e.get("terms") or [])
        and config.JOB_CATEGORY_MATCH in str(e.get("category", "")).lower()
        and _is_us(e.get("locations"))
        and not is_defense(e.get("company_name", ""))
        and not _excluded_title(e.get("title", ""))
    )


def fetch_postings():
    """Yield normalized relevant postings: dicts with id, company, role, url,
    location, posted_epoch, posted_iso, is_dream, source."""
    with urllib.request.urlopen(config.JOB_SIMPLIFY_URL, timeout=60) as r:
        data = json.load(r)
    for e in data:
        if not _relevant(e):
            continue
        locs = e.get("locations") or []
        epoch = e.get("date_posted") or 0
        yield {
            "id": str(e.get("id")),
            "company": e.get("company_name", "").strip(),
            "role": e.get("title", "").strip(),
            "url": e.get("url", "").strip(),
            "location": ", ".join(locs[:2]) if locs else "",
            "posted_epoch": epoch,
            "posted_iso": datetime.fromtimestamp(
                epoch, timezone.utc).date().isoformat() if epoch else None,
            "is_dream": _is_dream(e.get("company_name", "")),
            "source": "simplify",
        }
