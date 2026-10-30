"""Draft LinkedIn outreach for one contact: a connection-request note (no ask)
and a follow-up chat ask (sent after they accept), in the user's voice, grounded
in his real background. Stored on the contact. The web UI shells here. He sends
both himself, nothing is automated against LinkedIn.

    python3 outreach.py <contact_id>
"""
import re
import sys

from anthropic import Anthropic

import config
from db import connect


def _no_dashes(t):
    t = re.sub(r"\s*—\s*", ", ", t)
    t = re.sub(r"\s*–\s*", " - ", t)
    return t.replace(" ,", ",").replace(",,", ",").replace(", .", ".")


SYSTEM = (
    "You draft a LinkedIn DIRECT MESSAGE for a University of Maryland Computer "
    "Science student who is networking (looking for internships and genuine "
    "industry conversations), writing in HIS first-person voice. The recipient "
    "is ALREADY a first-degree connection, so this is a message, not a "
    "connection request. Write ONE message:\n"
    "- Three to four sentences. Open warmly and specifically: reference "
    "something real about them (their role, their company, or a shared "
    "University of Maryland background if they are a student or alum).\n"
    "- Then make a specific, low-friction ask for a short (15 minute) chat about "
    "their path or their work, framed around genuine curiosity and easy to say "
    "yes to.\n"
    "Rules: ground any claim about him in the background below, never invent "
    "experience. First person, sound like a real person, not a template. No "
    "corporate filler, no flattery he could not back up. NEVER use em dashes or "
    "en dashes."
)

TOOL = {
    "name": "outreach",
    "description": "The drafted direct message for this contact.",
    "input_schema": {
        "type": "object",
        "properties": {
            "message": {
                "type": "string",
                "description": "A LinkedIn direct message to an existing connection: a warm, specific opener plus a 15-minute chat ask.",
            },
        },
        "required": ["message"],
    },
}


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
    user = (who + f"\nMy background (resume):\n{experience[:3500]}\n\n"
            + (f"Match this writing voice (samples of how I write):\n{style[:2500]}\n\n"
               if style else "")
            + "Draft the two messages.")

    client = Anthropic(api_key=config.ANTHROPIC_API_KEY)
    resp = client.messages.create(
        model=config.PREP_MODEL, max_tokens=700,
        system=[{"type": "text", "text": SYSTEM,
                 "cache_control": {"type": "ephemeral"}}],
        tools=[TOOL], tool_choice={"type": "tool", "name": "outreach"},
        messages=[{"role": "user", "content": user}],
    )
    msg = ""
    for b in resp.content:
        if b.type == "tool_use":
            msg = _no_dashes((b.input.get("message") or "").strip())
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
