"""Generate a tailored "why I want to work at <company>" blurb for one
application, grounded in the user's real resume and matching their writing voice
if a sample is on file. Stores it in the blurbs table. The web UI shells here.

    python3 why_us.py <application_id>
"""
import re
import sys

from anthropic import Anthropic

import config
from db import connect


def _no_dashes(t):
    """Strip em/en dashes (the user hates them): em -> comma, en -> hyphen."""
    t = re.sub(r"\s*—\s*", ", ", t)   # — em dash
    t = re.sub(r"\s*–\s*", " - ", t)  # – en dash
    return t.replace(" ,", ",").replace(",,", ",").replace(", .", ".")

SYSTEM = (
    "You write a short 'why I want to work here' blurb for a University of "
    "Maryland CS student's job application, in HIS first-person voice. Rules:\n"
    "- Ground it in his REAL background below; make 1-2 specific, credible links "
    "between what he's built and what this company/role does. Never invent "
    "experience he doesn't have.\n"
    "- 80-110 words, one paragraph, first person. Specific and genuine, no "
    "cliches, no 'I am passionate about', no corporate filler, no flattery he "
    "couldn't back up.\n"
    "- If a writing sample is provided, match its tone, rhythm, and vocabulary. "
    "If not, write plainly and naturally, like a sharp student, not a brochure.\n"
    "- NEVER use em dashes or en dashes. Use commas, colons, or hyphens.\n"
    "- Output ONLY the blurb text, no preamble, no quotes."
)


def main(app_id):
    conn = connect()
    app = conn.execute("SELECT company, role FROM applications WHERE id = ?",
                       (app_id,)).fetchone()
    if not app:
        print(f"no application {app_id}")
        return
    prof = {r["key"]: r["value"] for r in
            conn.execute("SELECT key, value FROM profile").fetchall()}
    experience = prof.get("experience") or "(no resume on file)"
    style = prof.get("style")

    user = (f"Company: {app['company']}\nRole: {app['role'] or 'Software Engineer Intern'}\n\n"
            f"My background (resume):\n{experience[:4000]}\n\n"
            + (f"Match this writing voice (samples of how I write):\n{style[:3500]}\n\n"
               if style else "")
            + "Write the blurb.")

    client = Anthropic(api_key=config.ANTHROPIC_API_KEY)
    resp = client.messages.create(
        model=config.PREP_MODEL, max_tokens=400,
        system=[{"type": "text", "text": SYSTEM,
                 "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": user}],
    )
    text = _no_dashes("".join(b.text for b in resp.content
                              if b.type == "text").strip())
    conn.execute(
        "INSERT OR REPLACE INTO blurbs(application_id, text, created_at) "
        "VALUES(?, ?, datetime('now'))", (app_id, text))
    conn.commit()
    print(f"generated blurb for {app['company']} ({len(text)} chars)")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)
    main(int(sys.argv[1]))
