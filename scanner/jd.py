"""Fetch the text of a job posting from its URL.

Tries, in order: the job board's own JSON API (Greenhouse, Workday, Ashby,
Lever, Oracle, UltiPro), the schema.org JobPosting block most career sites embed for Google
Jobs, then the visible page text. Whatever comes back has to read like a job
description, so cookie banners, login walls and app shells count as a miss.

Posting URLs come from community lists, so every fetch is limited to public
hosts (audit 2026-11-21 APP-08). Callers must treat the text as untrusted.
"""
import html
import ipaddress
import json
import re
import socket
import urllib.parse

import requests

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36")
MAX_CHARS = 14000
_HEADERS = {"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"}

_NONTEXT = re.compile(r"<(script|style|head|nav|footer|svg)\b[^>]*>.*?</\1>", re.S | re.I)
_LDJSON = re.compile(
    r"<script[^>]*type=[\"']?application/ld\+json[^>]*>(.*?)</script>", re.S | re.I)
_JD_WORDS = re.compile(
    r"responsibilit|qualification|requirement|you will|you'll|what you|who you are|"
    r"experience (?:with|in)|pursuing|degree|skills|about the (?:role|job|team)", re.I)


def html_to_text(h):
    h = _NONTEXT.sub(" ", h)
    h = re.sub(r"<(br|/p|/div|/li|/h[1-6]|/tr)[^>]*>", "\n", h, flags=re.I)
    h = re.sub(r"<[^>]+>", " ", h)
    h = html.unescape(h)
    h = re.sub(r"[ \t\r\xa0]+", " ", h)
    return re.sub(r"\n\s*\n+", "\n", h).strip()


def looks_like_jd(t):
    return len(t or "") >= 300 and len({m.lower() for m in _JD_WORDS.findall(t)}) >= 2


def public_url(url):
    """Only http(s) URLs whose host resolves to public IPs (no LAN, loopback,
    link-local, metadata)."""
    try:
        u = urllib.parse.urlsplit(url)
        if u.scheme not in ("http", "https") or not u.hostname:
            return False
        infos = socket.getaddrinfo(u.hostname, u.port or (443 if u.scheme == "https" else 80))
        for info in infos:
            ip = ipaddress.ip_address(info[4][0])
            if (ip.is_private or ip.is_loopback or ip.is_link_local
                    or ip.is_reserved or ip.is_multicast or ip.is_unspecified):
                return False
        return True
    except Exception:
        return False


def get_public(url, **kw):
    """requests.get that re-checks every redirect hop with public_url."""
    kw.setdefault("headers", _HEADERS)
    kw.setdefault("timeout", 20)
    for _ in range(6):
        if not public_url(url):
            return None
        r = requests.get(url, allow_redirects=False, **kw)
        if r.is_redirect or r.status_code in (301, 302, 303, 307, 308):
            loc = r.headers.get("location")
            if not loc:
                return r
            url = urllib.parse.urljoin(url, loc)
            continue
        return r
    return None


def _json(url):
    r = get_public(url, headers={**_HEADERS, "Accept": "application/json"})
    return r.json() if r is not None and r.status_code == 200 else None


def _greenhouse(url, company):
    m = re.search(r"greenhouse\.io/(?:embed/job_app\?for=)?([^/?]+)/jobs/(\d+)", url)
    if m:
        tokens, jid = [m.group(1)], m.group(2)
    else:
        g = re.search(r"[?&]gh_jid=(\d+)", url)
        if not g:
            return ""
        jid = g.group(1)
        words = (company or "").lower().split()
        tokens = [re.sub(r"[^a-z0-9]", "", "".join(words)),
                  re.sub(r"[^a-z0-9]", "", words[0]) if words else ""]
    for tok in dict.fromkeys(t for t in tokens if t):
        data = _json(f"https://boards-api.greenhouse.io/v1/boards/{tok}/jobs/{jid}")
        if data:
            txt = html_to_text(html.unescape(data.get("content") or ""))
            if txt:
                return f"{data.get('title', '')}\n{txt}"
    return ""


def _workday(url, _company):
    u = urllib.parse.urlsplit(url)
    if not (u.hostname or "").endswith(".myworkdayjobs.com"):
        return ""
    m = re.match(r"/(?:[a-z]{2}-[A-Z]{2}/)?([^/]+)/job/(.+?)(?:/apply.*)?$", u.path)
    if not m:
        return ""
    tenant = u.hostname.split(".")[0]
    data = _json(f"https://{u.hostname}/wday/cxs/{tenant}/{m.group(1)}/job/{m.group(2)}")
    info = (data or {}).get("jobPostingInfo") or {}
    return f"{info.get('title', '')}\n{html_to_text(info.get('jobDescription') or '')}".strip()


def _ashby(url, _company):
    m = re.search(r"jobs\.ashbyhq\.com/([^/?#]+)/([0-9a-f-]{36})", url)
    if not m:
        return ""
    data = _json(f"https://api.ashbyhq.com/posting-api/job-board/{m.group(1)}") or {}
    for j in data.get("jobs", []):
        if j.get("id") == m.group(2):
            return f"{j.get('title', '')}\n{j.get('descriptionPlain') or ''}"
    return ""


def _oracle(url, _company):
    m = re.search(r"//([\w.-]+\.oraclecloud\.com)/.*?/sites/([\w-]+)/.*?job/(\d+)", url)
    if not m:
        return ""
    host, site, jid = m.groups()
    data = _json(f"https://{host}/hcmRestApi/resources/latest/recruitingCEJobRequisitionDetails"
                 f"?expand=all&onlyData=true&finder=ById;Id=%22{jid}%22,siteNumber={site}") or {}
    item = (data.get("items") or [{}])[0]
    parts = [item.get("Title")] + [
        html_to_text(item.get(k) or "") for k in
        ("ExternalDescriptionStr", "ExternalResponsibilitiesStr", "ExternalQualificationsStr")]
    return "\n".join(p for p in parts if p)


def _lever(url, _company):
    m = re.search(r"jobs\.lever\.co/([^/?#]+)/([0-9a-f-]{36})", url)
    if not m:
        return ""
    d = _json(f"https://api.lever.co/v0/postings/{m.group(1)}/{m.group(2)}?mode=json") or {}
    parts = [d.get("text"), d.get("descriptionPlain")]
    for sec in d.get("lists") or []:
        parts += [sec.get("text"), html_to_text(sec.get("content") or "")]
    return "\n".join(p for p in parts if p)


def _ultipro(url, _company):
    if not (urllib.parse.urlsplit(url).hostname or "").endswith(".ultipro.com"):
        return ""
    r = get_public(url)
    m = re.search(r"CandidateOpportunityDetail\((\{)", r.text) if r is not None else None
    if not m:
        return ""
    d, _ = json.JSONDecoder().raw_decode(r.text, m.start(1))
    return f"{d.get('Title', '')}\n{html_to_text(d.get('Description') or '')}"


def _postings(node):
    """Every JobPosting object inside a parsed ld+json value."""
    if isinstance(node, list):
        for n in node:
            yield from _postings(n)
    elif isinstance(node, dict):
        t = node.get("@type")
        if t == "JobPosting" or (isinstance(t, list) and "JobPosting" in t):
            yield node
        for v in node.values():
            if isinstance(v, (dict, list)):
                yield from _postings(v)


def _ldjson(page):
    for raw in _LDJSON.findall(page):
        try:
            data = json.loads(raw.strip(), strict=False)
        except ValueError:
            continue
        for p in _postings(data):
            parts = [p.get("title")]
            for k in ("description", "responsibilities", "qualifications", "skills"):
                v = p.get(k)
                if isinstance(v, str):
                    # descriptions are often entity-escaped HTML, sometimes twice
                    parts.append(html_to_text(html.unescape(html.unescape(v))))
            txt = "\n".join(x for x in parts if isinstance(x, str) and x)
            if looks_like_jd(txt):
                return txt
    return ""


def _page(url, _company):
    r = get_public(url)
    if r is None or r.status_code != 200:
        return ""
    ld = _ldjson(r.text)
    if ld:
        return ld
    txt = html_to_text(r.text)
    low = txt[:700].lower()
    if (txt.startswith(("{", "[")) or "{{companyname}}" in low
            or "enable javascript" in low or "verify you are human" in low
            or "are you a robot" in low):
        return ""
    return txt


def fetch_jd(url, company=""):
    """Posting text, or "" when nothing that reads like a JD could be pulled."""
    if not url or not public_url(url):
        return ""
    for source in (_greenhouse, _workday, _ashby, _lever, _oracle, _ultipro, _page):
        try:
            txt = source(url, company)
        except Exception:
            continue
        if looks_like_jd(txt):
            return txt[:MAX_CHARS]
    return ""


def for_application(conn, app_id):
    """Job description for an application: the stored one (pasted or pulled
    before), else pulled from the posting now and stored for next time."""
    row = conn.execute("SELECT jd FROM tailoring WHERE application_id = ?",
                       (app_id,)).fetchone()
    if row and (row["jd"] or "").strip():
        return row["jd"]
    app = conn.execute("SELECT company, url FROM applications WHERE id = ?",
                       (app_id,)).fetchone()
    text = fetch_jd(app["url"], app["company"]) if app and app["url"] else ""
    if text:
        conn.execute(
            "INSERT INTO tailoring(application_id, jd) VALUES(?, ?) "
            "ON CONFLICT(application_id) DO UPDATE SET jd = excluded.jd",
            (app_id, text))
        conn.commit()
    return text
