"""Generate a tailored "why I want to work at <company>" blurb for one
application, grounded in the user's real resume and the posting. Stores it in the blurbs table. The web UI shells here.

    python3 why_us.py <application_id>
"""
import sys

import jd as jobs
import voice
from db import connect
from trust import clean_name

TASK = (
    "You write James's short answer to \"why do you want to work here?\" on a job "
    "application. He is a Computer Science student at the University of Maryland.\n"
    "- 80 to 110 words, one paragraph, first person.\n"
    "- Make one or two specific, credible links between what he has built and what "
    "this company or role does. Use the posting for what they do, if there is one. "
    "Without one, stick to what the company is plainly known for.\n"
    "- Only claim what the background states. No flattery he couldn't back up, and "
    "no history with the company or its product unless the background gives one.\n"
    "- Say what a project does in plain words instead of pasting resume phrasing."
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

    company = clean_name(app["company"])
    role = clean_name(app["role"], 90) or "Software Engineer Intern"
    user = (f"Company: {company}\nRole: {role}\n\n"
            + voice.posting(jobs.for_application(conn, app_id))
            + f"My background (everything you may claim about me):\n{experience}\n\n"
            + (f"Samples of how I write:\n{style}\n\n" if style else "")
            + "Write the answer.")
    text = voice.write(TASK, user, facts=f"{experience}\n{company} {role}",
                       words=(70, 120))
    conn.execute(
        "INSERT OR REPLACE INTO blurbs(application_id, text, created_at) "
        "VALUES(?, ?, datetime('now'))", (app_id, text))
    conn.commit()
    print(f"generated blurb for {company} ({len(text)} chars)")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)
    main(int(sys.argv[1]))
