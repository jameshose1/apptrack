"""Pull internships straight from target companies' own ATS job boards.

Greenhouse / Lever / Ashby all expose public, embeddable JSON board endpoints.
For each TARGET_COMPANY we auto-detect which board it uses (cached in ats_board)
and yield normalized SWE-intern postings in the same shape jobsource emits.
"""
import json
import re
import urllib.request
from datetime import datetime, timezone

import config
import normalize

_UA = {"User-Agent": "Mozilla/5.0 (apptrack job scanner)"}
# whole-word intern/co-op, so "International" / "Internal" don't match
_INTERN_RE = re.compile(r"\bintern(?:ship)?s?\b|\bco-?op\b", re.I)
_SWE_RE = re.compile(
    r"software|engineer|developer|\bswe\b|programming|full.?stack|"
    r"back.?end|front.?end|machine learning|\bml\b|infrastructure", re.I)
# a year other than 2027 in the title (drops leftover 2026 / 2025 postings)
_OTHER_YEAR_RE = re.compile(r"20(2[0-6]|2[89]|[3-9]\d)")
# wrong season (user wants Summer)
_OFFSEASON_RE = re.compile(r"\b(winter|fall|autumn|spring)\b", re.I)
_US_NAMES = {"united states", "usa", "us", "united states of america",
             "u.s.", "u.s.a.", "america"}
# location keywords that mark a posting as clearly outside the US
_FOREIGN = (
    "united kingdom", "london", " uk", "canada", "toronto", "vancouver",
    "ontario", "india", "bangalore", "bengaluru", "hyderabad", "pune", "noida",
    "gurgaon", "europe", "germany", "berlin", "munich", "france", "paris",
    "ireland", "dublin", "singapore", "australia", "sydney", "melbourne",
    "israel", "tel aviv", "netherlands", "amsterdam", "spain", "poland",
    "brazil", "mexico", "japan", "tokyo", "korea", "china", "emea", "apac",
    "latam", "zurich", "switzerland",
)


def _get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=_UA),
                                timeout=30) as r:
        return json.load(r)


def _epoch(val):
    if not val:
        return 0
    if isinstance(val, (int, float)):
        return int(val / 1000 if val > 1e12 else val)  # ms vs s
    try:
        s = str(val).replace("Z", "+00:00")
        return int(datetime.fromisoformat(s).timestamp())
    except (ValueError, TypeError):
        return 0


def _is_foreign(loc: str) -> bool:
    return any(f in (loc or "").lower() for f in _FOREIGN)


def _is_us(location: str, country: str) -> bool:
    """Prefer the explicit country when the board gives one; otherwise infer
    from the location string (not clearly foreign)."""
    c = (country or "").strip().lower()
    if c:
        return c in _US_NAMES
    return not _is_foreign(location)


# --- per-ATS board fetchers: return list of raw job dicts, or None if no board
def _greenhouse(slug):
    return _get(f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"
                ).get("jobs") or None


def _ashby(slug):
    return _get(f"https://api.ashbyhq.com/posting-api/job-board/{slug}"
                ).get("jobs") or None


def _lever(slug):
    return _get(f"https://api.lever.co/v0/postings/{slug}?mode=json") or None


_ATS = {"greenhouse": _greenhouse, "ashby": _ashby, "lever": _lever}


def _slugs(name: str):
    base = re.sub(r"\(.*?\)", "", name).strip().lower()
    alnum = re.sub(r"[^a-z0-9]", "", base)
    first = re.sub(r"[^a-z0-9]", "", base.split()[0]) if base.split() else alnum
    return [s for s in dict.fromkeys([alnum, first]) if s]


def resolve_board(name):
    """(ats, token) for a company's board, trying slug + ATS combos, or (None,None)."""
    for slug in _slugs(name):
        for ats, fn in _ATS.items():
            try:
                if fn(slug):
                    return ats, slug
            except Exception:
                pass
    return None, None


# --- normalize each ATS's job shape to (title, url, location, country, epoch)
def _norm(ats, j):
    if ats == "greenhouse":
        return (j.get("title", ""), j.get("absolute_url", ""),
                (j.get("location") or {}).get("name", ""), "",
                _epoch(j.get("updated_at")))
    if ats == "ashby":
        addr = (j.get("address") or {}).get("postalAddress") or {}
        loc = (j.get("location") or addr.get("addressLocality")
               or ("Remote" if j.get("isRemote") else ""))
        return (j.get("title", ""), j.get("jobUrl") or j.get("applyUrl", ""),
                loc, addr.get("addressCountry", ""),
                _epoch(j.get("publishedAt")))
    cats = j.get("categories") or {}
    return (j.get("text", ""), j.get("hostedUrl") or j.get("applyUrl", ""),
            cats.get("location", ""), cats.get("country", ""),
            _epoch(j.get("createdAt")))


def _wanted(title, location, country):
    if not _INTERN_RE.search(title) or not _SWE_RE.search(title):
        return False
    if _OFFSEASON_RE.search(title):
        return False  # wrong season (want Summer)
    if _OTHER_YEAR_RE.search(title) and "2027" not in title:
        return False  # a different cycle's leftover
    return _is_us(location, country)


def fetch_target_postings(get_board, save_board):
    """Yield normalized intern postings for every TARGET_COMPANY. get_board(name)
    returns a cached (ats, token) or None; save_board(name, ats, token) caches a
    freshly resolved one."""
    for name in config.TARGET_COMPANIES:
        cached = get_board(name)
        if cached is None:
            ats, token = resolve_board(name)
            save_board(name, ats or "none", token or "")
        else:
            ats, token = cached
        if not ats or ats == "none":
            continue
        try:
            jobs = _ATS[ats](token) or []
        except Exception:
            continue
        for j in jobs:
            title, url, location, country, epoch = _norm(ats, j)
            if not url or not _wanted(title, location, country):
                continue
            jid = str(j.get("id") or url)
            yield {
                "id": f"ats:{normalize.company_key(name)}:{jid}",
                "company": re.sub(r"\s*\(.*?\)", "", name).strip(),
                "role": title.strip(),
                "url": url.strip(),
                "location": location.strip(),
                "posted_epoch": epoch,
                "posted_iso": datetime.fromtimestamp(
                    epoch, timezone.utc).date().isoformat() if epoch else None,
                "is_dream": True,   # curated target -> always surfaced + starred
                "source": "ats",
            }
