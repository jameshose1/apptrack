"""Answer "what makes you an ideal candidate for this role?" for one
application: reads the job description, picks what it asks for, and answers from
the resume on file. Needs a real job description (pulled from the posting, or
pasted on the card); without one it exits 3 instead of writing something generic.

    python3 ideal.py <application_id>
"""
import sys

import jd as jobs
import voice
from db import connect
from trust import clean_name

NO_JD = 3

TASK = (
    "You write James's answer to the application question \"What makes you an ideal "
    "candidate for this role?\" He is a Computer Science student at the University of "
    "Maryland. You are given the job posting and his real background.\n"
    "First work out, without writing it down, which two or three things this posting "
    "most needs from an intern, and which parts of his background are the most direct "
    "evidence for each. Then write the answer:\n"
    "- 120 to 170 words, first person, one or two paragraphs, no heading.\n"
    "- Open with his strongest evidence for what the job centers on. No throat "
    "clearing, no restating the question, no company flattery.\n"
    "- Match the posting's needs to specific things he built or did, named, with the "
    "real detail. Cover the need that matters most in more depth than the others, "
    "and leave out projects that only pad the list.\n"
    "- It has to answer for THIS job: at least twice, say in plain words which part "
    "of the posted work the thing he did carries over to, naming that work "
    "specifically (the system, the stack, the kind of problem).\n"
    "- Put it the way he'd explain it to a recruiter who has never heard of the "
    "project. Say what a thing does before how it works, and don't paste resume "
    "phrasing like 'deterministic, idempotent settlement engine' or "
    "'money-conservation invariant'. One or two numbers is plenty.\n"
    "- Only claim what the background states. If the posting wants a tool he hasn't "
    "used, don't claim it or imply it. You may name the closest real thing he has "
    "done, and one honest gap is fine when the posting makes it central.\n"
    "- Every number comes from his background, never from the posting.\n"
    "- Don't end on a sentence about being a great fit or excited for the opportunity."
)


def main(app_id):
    conn = connect()
    app = conn.execute("SELECT company, role, url FROM applications WHERE id = ?",
                       (app_id,)).fetchone()
    if not app:
        print(f"no application {app_id}")
        return 1
    jd = jobs.for_application(conn, app_id)
    if not jd:
        print("no job description: couldn't pull the posting and none was pasted")
        return NO_JD
    prof = {r["key"]: r["value"] for r in
            conn.execute("SELECT key, value FROM profile").fetchall()}
    experience, style = prof.get("experience"), prof.get("style")
    if not experience:
        print("no resume on file (run import_profile.py)")
        return 1
    company = clean_name(app["company"])
    role = clean_name(app["role"], 90) or "Software Engineer Intern"

    user = (f"Company: {company}\nRole: {role}\n\n{voice.posting(jd)}"
            f"My background (everything you may claim about me):\n{experience}\n\n"
            + (f"Samples of how I write:\n{style}\n\n" if style else "")
            + "Write the answer.")
    text = voice.write(TASK, user, facts=f"{experience}\n{company} {role}",
                       words=(105, 185))
    conn.execute(
        "INSERT OR REPLACE INTO ideal_answers(application_id, text, created_at) "
        "VALUES(?, ?, datetime('now'))", (app_id, text))
    conn.commit()
    print(f"answered for {company} ({len(text.split())} words)")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)
    sys.exit(main(int(sys.argv[1])))
