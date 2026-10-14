"""Canonical company keys so name variants collapse to one application.

"MicroStrategy", "MicroStrategy Inc.", "Microstrategy India" -> "microstrategy".
The key is only for matching; the display name stays whatever the classifier
returned (cleaned).
"""
import re
import unicodedata

_SUFFIXES = {
    "inc", "llc", "ltd", "limited", "corp", "corporation", "co", "company",
    "gmbh", "plc", "pvt", "private", "lp", "llp", "sa", "ag", "nv", "bv",
    "group", "holdings", "technologies", "technology", "labs", "software",
    "solutions", "systems",
}
# regional qualifiers that shouldn't split a company into two rows
_REGIONS = {
    "india", "usa", "us", "uk", "emea", "apac", "global", "worldwide",
    "americas", "canada", "ireland", "europe",
}
_DROP = _SUFFIXES | _REGIONS

_PUNCT = re.compile(r"[^a-z0-9 ]+")
_WS = re.compile(r"\s+")

# Known-equivalent company keys (rebrands, common aliases) that no generic
# rule can catch. Maps variant key -> canonical key. Extend as you spot dupes.
ALIASES = {
    "strategy": "microstrategy",   # MicroStrategy rebranded to Strategy in 2025
}


def company_key(name: str) -> str:
    if not name:
        return ""
    t = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    t = t.lower()
    t = _PUNCT.sub(" ", t)
    t = _WS.sub(" ", t).strip()
    words = [w for w in t.split(" ") if w and w not in _DROP]
    key = " ".join(words) or t
    return ALIASES.get(key, key)
