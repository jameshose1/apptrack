"""Tailor the user's application to a specific role: regenerate his resume with
re-angled bullet points (keeping his exact resume layout, entries, and facts)
AND draft a tailored cover letter, both rendered to PDF. The job description is
auto-pulled from the posting URL when possible (Greenhouse API + plain fetch),
else it tailors to the company + role. Grounded in his real resume, never
invents anything.

    python3 tailor.py <application_id>
"""
import html
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

import requests
from anthropic import Anthropic

import config
from db import connect

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
PUBLIC = Path(__file__).resolve().parent.parent / "web" / "public" / "resumes"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36")
# his real profile links (his resume renders them as the words LinkedIn / GitHub)
LINKEDIN_URL = "https://www.linkedin.com/in/james-hose-58b6b432b"
GITHUB_URL = "https://github.com/jameshose1"


def _no_dashes(t):
    t = re.sub(r"\s*—\s*", ", ", t or "")
    t = re.sub(r"\s*–\s*", " - ", t)
    return t.replace(" ,", ",").replace(",,", ",").replace(", .", ".")


def _slug(s):
    return re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")[:60] or "resume"


def _esc(s):
    return html.escape(s or "")


def _rich(s):
    """Escape, then turn **bold** markers into <b> (his resume bolds key metrics)."""
    return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", _esc(s))


_NONTEXT = re.compile(r"<(script|style|head|nav|footer|svg)[^>]*>.*?</\1>", re.S | re.I)


def _html_to_text(h):
    h = _NONTEXT.sub(" ", h)
    h = re.sub(r"<(br|/p|/div|/li|/h[1-6]|/tr)[^>]*>", "\n", h, flags=re.I)
    h = re.sub(r"<[^>]+>", " ", h)
    h = html.unescape(h)
    h = re.sub(r"[ \t]+", " ", h)
    return re.sub(r"\n\s*\n+", "\n", h).strip()


def _greenhouse_jd(url, company):
    m = re.search(r"greenhouse\.io/(?:embed/job_app\?for=)?([^/?]+)/jobs/(\d+)", url)
    if m:
        tokens, jid = [m.group(1)], m.group(2)
    else:
        g = re.search(r"[?&]gh_jid=(\d+)", url)
        if not g:
            return ""
        jid = g.group(1)
        c = re.sub(r"[^a-z0-9]", "", (company or "").lower())
        c1 = re.sub(r"[^a-z0-9]", "", (company or "").lower().split()[0]) if company else ""
        tokens = [c, c1]
    for tok in dict.fromkeys(t for t in tokens if t):
        try:
            r = requests.get(
                f"https://boards-api.greenhouse.io/v1/boards/{tok}/jobs/{jid}",
                headers={"User-Agent": UA}, timeout=15)
            if r.status_code == 200:
                data = r.json()
                txt = _html_to_text(html.unescape(data.get("content") or ""))
                if len(txt) >= 300:
                    return ((data.get("title", "") + "\n" + txt).strip())[:7000]
        except Exception:
            pass
    return ""


def _fetch_jd(url, company=""):
    if not url or not url.startswith("http"):
        return ""
    gh = _greenhouse_jd(url, company)
    if gh:
        return gh
    try:
        r = requests.get(url, headers={"User-Agent": UA,
                                       "Accept-Language": "en-US,en;q=0.9"},
                         timeout=20, allow_redirects=True)
    except Exception:
        return ""
    if r.status_code != 200:
        return ""
    txt = _html_to_text(r.text)
    low = txt.lower()[:700]
    if (len(txt) < 400 or "enable javascript" in low
            or "verify you are human" in low or "are you a robot" in low):
        return ""
    return txt[:7000]


# ---------------------------------------------------------------- resume ----

RESUME_SYSTEM = (
    "You tailor a University of Maryland Computer Science student's resume to ONE "
    "internship role. You are given his EXACT real resume. Your job is NOT to "
    "redesign it: keep the same sections, the same education, the same skills, "
    "the same projects / jobs / activities, and the same titles, organizations, "
    "and dates. The ONLY thing you rewrite is the BULLET POINT text, re-angling "
    "each bullet to emphasize what THIS role cares about, using the role's "
    "language where it is honestly true of him. You may reorder bullets, and "
    "reorder projects so the most relevant one is first, but never invent or "
    "change a fact, number, tool, or outcome. Keep every real metric.\n"
    "Each bullet is one or two lines, starts with a strong verb, and wraps the "
    "single most important metric or keyword in **double asterisks** so it "
    "renders bold (exactly like his resume does). STRICT bullet caps so it fits "
    "ONE page: at most 3 bullets per project, at most 2 per job, at most 1 per "
    "leadership/activity item. Keep bullets to one line where you can. Cut the "
    "weakest bullets rather than padding, no filler like 'demonstrating X' or "
    "'showing ability to'. NEVER use em dashes or en dashes. Copy education and "
    "skills through verbatim from his resume (do not tailor those)."
)

RESUME_TOOL = {
    "name": "resume",
    "description": "The tailored resume in his exact layout, plus a fit note and gaps.",
    "input_schema": {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "phone": {"type": "string"},
            "email": {"type": "string"},
            "education": {
                "type": "object",
                "properties": {
                    "org": {"type": "string", "description": "e.g. University of Maryland | College Park, MD"},
                    "gpa": {"type": "string", "description": "only if present in his resume, else empty"},
                    "date": {"type": "string", "description": "graduation, e.g. May 2028"},
                    "degree": {"type": "string", "description": "e.g. B.S. in Computer Science"},
                    "coursework": {"type": "string", "description": "the relevant coursework list, verbatim"},
                    "honors": {"type": "string", "description": "honors line, verbatim, else empty"},
                },
                "required": ["org", "degree"],
            },
            "skills": {
                "type": "object",
                "properties": {
                    "languages": {"type": "string"},
                    "tools": {"type": "string"},
                },
                "required": ["languages", "tools"],
            },
            "projects": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "stack": {"type": "string"},
                        "date": {"type": "string"},
                        "subtitle": {"type": "string", "description": "e.g. Personal Project"},
                        "bullets": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["name", "bullets"],
                },
            },
            "experience": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "org": {"type": "string", "description": "org | location"},
                        "date": {"type": "string"},
                        "role": {"type": "string", "description": "job title, italic subtitle"},
                        "bullets": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["org", "role", "bullets"],
                },
            },
            "leadership": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "org": {"type": "string", "description": "org | location"},
                        "date": {"type": "string"},
                        "role": {"type": "string"},
                        "bullets": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["org", "role", "bullets"],
                },
            },
            "fit": {"type": "string", "description": "2-3 honest sentences on fit + what he leads with"},
            "gaps": {"type": "string", "description": "skills/keywords to study or surface, honest"},
        },
        "required": ["name", "education", "skills", "projects", "experience", "fit", "gaps"],
    },
}

# replicates his typical resume: centered header, uppercase section titles with a
# full-width rule, bold right-aligned dates, italic subtitles, filled-dot bullets.
RESUME_CSS = """
@page { size: letter; margin: 0.45in 0.55in; }
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: 'Cambria','Georgia','Times New Roman',serif; color: #000; font-size: 10.3pt; line-height: 1.2; }
.name { text-align: center; font-size: 18pt; font-weight: 700; margin-bottom: 1px; }
.contact { text-align: center; font-size: 10pt; margin-bottom: 5px; }
.contact a { color: #1155cc; text-decoration: underline; }
h2 { font-size: 11pt; font-weight: 700; text-transform: uppercase; border-bottom: 1.1px solid #000;
     margin: 6px 0 2px; padding-bottom: 1px; }
.entry { margin-bottom: 3px; }
.head { display: flex; justify-content: space-between; align-items: baseline; }
.head .t { font-weight: 700; }
.head .d { font-weight: 700; white-space: nowrap; padding-left: 14px; }
.sub { font-style: italic; }
.line { margin: 1px 0; }
ul { list-style: none; margin: 1px 0 0; padding: 0; }
li { position: relative; padding-left: 15px; margin: 1px 0; line-height: 1.22; }
li::before { content: "\\25CF"; position: absolute; left: 2px; top: -0.06em; font-size: 7pt; }
"""


def _head(title, date_):
    return (f'<div class="head"><span class="t">{title}</span>'
            f'<span class="d">{_esc(date_)}</span></div>')


def _bullets(items):
    bl = "".join(f"<li>{_rich(b)}</li>" for b in (items or []) if b)
    return f"<ul>{bl}</ul>" if bl else ""


def _entry(org, date_, role, bullets, org_rich=False):
    t = org if org_rich else _esc(org)
    return (f'<div class="entry">{_head(t, date_)}'
            + (f'<div class="sub">{_esc(role)}</div>' if role else "")
            + _bullets(bullets) + "</div>")


def _render_resume_html(d):
    contact = " | ".join(filter(None, [
        _esc(d.get("phone")),
        _esc(d.get("email")),
        f'<a href="{LINKEDIN_URL}">LinkedIn</a>',
        f'<a href="{GITHUB_URL}">GitHub</a>',
    ]))

    ed = d.get("education", {}) or {}
    ed_left = " | ".join(filter(None, [ed.get("org"), ed.get("gpa")]))
    ed_bul = []
    if ed.get("coursework"):
        ed_bul.append(f'<b>Relevant Coursework:</b> {_esc(ed["coursework"])}')
    if ed.get("honors"):
        ed_bul.append(f'<b>Honors:</b> {_esc(ed["honors"])}')
    education = (f'<div class="entry">{_head(_esc(ed_left), ed.get("date"))}'
                 f'<div class="sub">{_esc(ed.get("degree"))}</div>'
                 + ("<ul>" + "".join(f"<li>{b}</li>" for b in ed_bul) + "</ul>" if ed_bul else "")
                 + "</div>")

    sk = d.get("skills", {}) or {}
    skills = ""
    if sk.get("languages"):
        skills += f'<div class="line"><b>Languages:</b> {_esc(sk["languages"])}</div>'
    if sk.get("tools"):
        skills += f'<div class="line"><b>Frameworks & Tools:</b> {_esc(sk["tools"])}</div>'

    projects = "".join(
        _entry(_rich(p.get("name")) + (f' | {_esc(p.get("stack"))}' if p.get("stack") else ""),
               p.get("date"), p.get("subtitle") or "Personal Project", p.get("bullets"),
               org_rich=True)
        for p in d.get("projects", []))
    experience = "".join(
        _entry(e.get("org"), e.get("date"), e.get("role"), e.get("bullets"))
        for e in d.get("experience", []))
    leadership = "".join(
        _entry(e.get("org"), e.get("date"), e.get("role"), e.get("bullets"))
        for e in d.get("leadership", []))

    return (f"<!doctype html><html><head><meta charset='utf-8'><style>{RESUME_CSS}</style></head><body>"
            f'<div class="name">{_esc(d.get("name"))}</div>'
            f'<div class="contact">{contact}</div>'
            f'<h2>Education</h2>{education}'
            f'<h2>Technical Skills</h2>{skills}'
            + (f'<h2>Projects</h2>{projects}' if projects else "")
            + (f'<h2>Experience</h2>{experience}' if experience else "")
            + (f'<h2>Leadership</h2>{leadership}' if leadership else "")
            + "</body></html>")


# ------------------------------------------------------------ cover letter --

COVER_SYSTEM = (
    "Write a cover letter for a University of Maryland Computer Science student "
    "applying to a specific internship, in HIS first-person voice. Ground every "
    "claim in his real resume, NEVER invent experience. Three short paragraphs, "
    "about 230 to 280 words total: (1) which role and company and a genuine, "
    "specific reason he is drawn to it; (2) 1 to 2 concrete things he has built "
    "(from his resume) that map directly to what this role needs, with real "
    "detail; (3) a brief, confident close. Sound like a sharp real student, not "
    "a template, no cliches, no 'I am writing to express my interest', no "
    "flattery he could not back up. Output ONLY the body paragraphs separated by "
    "a blank line, no greeting and no signature. NEVER use em dashes or en dashes."
)

COVER_CSS = """
@page { size: letter; margin: 0.9in 1in; }
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: 'Cambria','Georgia','Times New Roman',serif; color: #000; font-size: 11pt; line-height: 1.5; }
.name { font-size: 17pt; font-weight: 700; }
.contact { font-size: 9.5pt; margin: 2px 0 20px; border-bottom: 1px solid #ccc; padding-bottom: 10px; }
.contact a { color: #1155cc; text-decoration: underline; }
.date, .greet { margin-bottom: 14px; }
p { margin-bottom: 12px; }
.sign { margin-top: 18px; }
"""


def _render_cover_html(name, phone, email, company, body):
    contact = " | ".join(filter(None, [
        _esc(phone), _esc(email),
        f'<a href="{LINKEDIN_URL}">LinkedIn</a>',
        f'<a href="{GITHUB_URL}">GitHub</a>',
    ]))
    paras = "".join(f"<p>{_esc(p.strip())}</p>" for p in re.split(r"\n\s*\n", body) if p.strip())
    today = date.today().strftime("%B %-d, %Y")
    return (f"<!doctype html><html><head><meta charset='utf-8'><style>{COVER_CSS}</style></head><body>"
            f'<div class="name">{_esc(name)}</div>'
            f'<div class="contact">{contact}</div>'
            f'<div class="date">{today}</div>'
            f'<div class="greet">Dear {_esc(company)} Hiring Team,</div>'
            f'{paras}'
            f'<div class="sign">Sincerely,<br>{_esc(name)}</div>'
            "</body></html>")


# ------------------------------------------------------------------- render --

def _to_pdf(html_str, pdf_path):
    PUBLIC.mkdir(parents=True, exist_ok=True)
    html_path = pdf_path.with_suffix(".html")
    html_path.write_text(html_str, encoding="utf-8")
    subprocess.run(
        [CHROME, "--headless=new", "--disable-gpu", "--no-sandbox",
         "--no-pdf-header-footer", "--user-data-dir=/tmp/apptrack-chrome-pdf",
         f"--print-to-pdf={pdf_path}", f"file://{html_path}"],
        capture_output=True, timeout=90)
    return pdf_path.exists()


def main(app_id):
    conn = connect()
    app = conn.execute("SELECT company, role, url FROM applications WHERE id = ?",
                       (app_id,)).fetchone()
    if not app:
        print(f"no application {app_id}")
        return
    row = conn.execute("SELECT jd FROM tailoring WHERE application_id = ?",
                       (app_id,)).fetchone()
    jd = (row["jd"] if row else "") or ""
    if not jd.strip() and app["url"]:
        fetched = _fetch_jd(app["url"], app["company"])
        if fetched:
            jd = fetched
            print(f"pulled job description from the posting ({len(jd)} chars)")
        else:
            print("could not pull the posting (JS/login-walled?), tailoring to "
                  "company + role")

    prof = {r["key"]: r["value"] for r in
            conn.execute("SELECT key, value FROM profile").fetchall()}
    experience = prof.get("experience") or "(no resume on file)"
    role = app["role"] or "Software Engineer Intern"
    jd_block = (f"Job description:\n{jd[:6000]}\n\n" if jd.strip()
                else "No job description, tailor to the company and role.\n\n")
    client = Anthropic(api_key=config.ANTHROPIC_API_KEY)

    def clean(x):
        if isinstance(x, str):
            return _no_dashes(x)
        if isinstance(x, list):
            return [clean(i) for i in x]
        if isinstance(x, dict):
            return {k: clean(v) for k, v in x.items()}
        return x

    # ----- resume (same layout + entries, only bullets re-angled) -----
    resp = client.messages.create(
        model=config.PREP_MODEL, max_tokens=2400,
        system=[{"type": "text", "text": RESUME_SYSTEM, "cache_control": {"type": "ephemeral"}}],
        tools=[RESUME_TOOL], tool_choice={"type": "tool", "name": "resume"},
        messages=[{"role": "user", "content":
                   f"Company: {app['company']}\nRole: {role}\n\n{jd_block}"
                   f"My exact resume (keep the layout, entries, titles, dates, "
                   f"education, and skills identical, only re-angle the bullets):\n"
                   f"{experience[:5000]}\n\nProduce the tailored resume."}],
    )
    data = next((b.input for b in resp.content if b.type == "tool_use"), None)
    if not data:
        print("no resume produced")
        return
    data = clean(data)
    slug = f"{_slug(app['company'])}-{_slug(role)}"
    resume_pdf = PUBLIC / f"{slug}.pdf"
    resume_ok = _to_pdf(_render_resume_html(data), resume_pdf)
    resume_url = f"/resumes/{slug}.pdf" if resume_ok else None

    # ----- cover letter -----
    cresp = client.messages.create(
        model=config.PREP_MODEL, max_tokens=700,
        system=[{"type": "text", "text": COVER_SYSTEM, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content":
                   f"Company: {app['company']}\nRole: {role}\n\n{jd_block}"
                   f"My real resume:\n{experience[:4500]}\n\nWrite the cover letter body."}],
    )
    body = _no_dashes("".join(b.text for b in cresp.content if b.type == "text").strip())
    cover_pdf = PUBLIC / f"{slug}-cover.pdf"
    cover_ok = _to_pdf(_render_cover_html(data.get("name", "James Hose"),
                                          data.get("phone"), data.get("email"),
                                          app["company"], body), cover_pdf)
    cover_url = f"/resumes/{slug}-cover.pdf" if cover_ok else None

    conn.execute(
        "INSERT INTO tailoring(application_id, jd, fit, gaps, resume_path, cover_path, created_at) "
        "VALUES(?, ?, ?, ?, ?, ?, datetime('now')) "
        "ON CONFLICT(application_id) DO UPDATE SET jd=excluded.jd, fit=excluded.fit, "
        "gaps=excluded.gaps, resume_path=excluded.resume_path, cover_path=excluded.cover_path, "
        "created_at=datetime('now')",
        (app_id, jd, data.get("fit", ""), data.get("gaps", ""), resume_url, cover_url))
    conn.commit()
    print(f"tailored {app['company']}: resume={'ok' if resume_ok else 'FAIL'}, "
          f"cover={'ok' if cover_ok else 'FAIL'} (jd={'yes' if jd.strip() else 'no'})")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)
    main(int(sys.argv[1]))
