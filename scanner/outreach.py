"""Draft a LinkedIn direct message for one contact, in the user's voice, grounded
in his real background. Stored on the contact. The web UI shells here. He sends
it himself, nothing is automated against LinkedIn.

    python3 outreach.py <contact_id>
"""
import sys

import voice
from db import connect

TASK = (
    "You draft ONE LinkedIn direct message from James, a Computer Science student at "
    "the University of Maryland who is looking for internships and real conversations "
    "with people in the industry. The recipient is ALREADY a first-degree connection.\n"
    "- Three or four sentences. Open with something real about them from the details "
    "given: their role, their company, or a shared UMD background.\n"
    "- Then ask for a 15 minute chat about their path or their work, specific and easy "
    "to say yes to.\n"
    "- Only claim what his background states, and nothing about them beyond the "
    "details given. No flattery he couldn't back up."
)


def main(cid):
    conn = connect()
    c = conn.execute(
        "SELECT name, company, position, is_alum FROM contacts WHERE id = ?",
        (cid,)).fetchone()
    if not c:
        print(f"no contact {cid}")
        return
    prof = {r["key"]: r["value"] for r in
            conn.execute("SELECT key, value FROM profile").fetchall()}
    experience = prof.get("experience") or "(no resume on file)"
    style = prof.get("style")
    first = (c["name"] or "there").split()[0]
    who = (f"Contact first name: {first}\n"
           f"Contact full name: {c['name']}\n"
           f"Their company: {c['company'] or 'unknown'}\n"
           f"Their role or title: {c['position'] or 'unknown'}\n"
           f"Shared UMD background: "
           f"{'yes' if c['is_alum'] else 'possibly (both connected to University of Maryland)'}\n")
    user = (who + f"\nMy background (resume):\n{experience}\n\n"
            + (f"Samples of how I write:\n{style}\n\n"
               if style else "")
            + "Draft the message.")

    msg = voice.write(TASK, user, facts=experience + who, words=(35, 110))
    # store the single direct message in connect_note; chat_ask unused (existing
    # connections are DM'd directly, no separate accept step)
    conn.execute("UPDATE contacts SET connect_note = ?, chat_ask = NULL WHERE id = ?",
                 (msg, cid))
    conn.commit()
    print(f"drafted message for {c['name']} ({len(msg)} chars)")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)
    main(int(sys.argv[1]))
