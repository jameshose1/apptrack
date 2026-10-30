"""Import your LinkedIn connections so apptrack can flag who you know at the
companies you're tracking (referrals = 5-10x the conversion of cold applies).

ToS-safe: this reads the CSV LinkedIn gives YOU on request, not scraping.
  LinkedIn -> Settings -> Data Privacy -> Get a copy of your data ->
  "Connections" -> download -> drop Connections.csv at the path below.

    python3 import_contacts.py                       # reads data/linkedin_connections.csv
    python3 import_contacts.py ~/Downloads/Connections.csv
"""
import csv
import sys
from pathlib import Path

import config
import normalize
from db import connect, init_db

DEFAULT = Path(__file__).resolve().parent.parent / "data" / "linkedin_connections.csv"


def _rows(path):
    lines = Path(path).read_text(encoding="utf-8", errors="ignore").splitlines()
    # LinkedIn prepends a few notes lines before the real header
    start = next((i for i, l in enumerate(lines)
                  if l.lower().startswith("first name")), 0)
    yield from csv.DictReader(lines[start:])


def main(path=DEFAULT):
    path = Path(path)
    if not path.exists():
        print(f"no file at {path} — export your LinkedIn connections first "
              f"(see this script's header)")
        return
    init_db()
    conn = connect()
    added = 0
    for r in _rows(path):
        name = f"{(r.get('First Name') or '').strip()} " \
               f"{(r.get('Last Name') or '').strip()}".strip()
        company = (r.get("Company") or "").strip()
        if not name or not company:
            continue
        email = (r.get("Email Address") or "").strip()
        dom = email.rsplit("@", 1)[-1].lower() if "@" in email else ""
        is_alum = 1 if any(dom == d or dom.endswith("." + d)
                           for d in config.ALUMNI_EMAIL_DOMAINS) else 0
        cur = conn.execute(
            "INSERT OR IGNORE INTO contacts(name, company, company_key, position, "
            "url, email, source, connected_on, is_alum) "
            "VALUES(?,?,?,?,?,?,'linkedin',?,?)",
            (name, company, normalize.company_key(company),
             (r.get("Position") or "").strip(), (r.get("URL") or "").strip(),
             email, (r.get("Connected On") or "").strip(), is_alum),
        )
        added += cur.rowcount
    conn.commit()

    # if the LinkedIn archive's messages.csv is alongside (or passed), flag
    # everyone the user already has a conversation with so they're skipped.
    msgs = _find_messages(path)
    if msgs:
        flagged = _flag_already_messaged(conn, msgs)
        print(f"flagged {flagged} contact(s) as already in conversation "
              f"(from {msgs.name})")
    else:
        print("no messages.csv found alongside; skip the 'already messaging' "
              "filter (export the FULL LinkedIn archive to enable it)")

    total = conn.execute("SELECT count(*) FROM contacts").fetchone()[0]
    print(f"imported {added} new contact(s) ({total} total)")


def _norm_url(u):
    return (u or "").strip().rstrip("/").lower().split("?")[0]


def _find_messages(conn_path):
    """messages.csv passed as 2nd arg, or sitting next to the connections CSV."""
    if len(sys.argv) > 2 and Path(sys.argv[2]).exists():
        return Path(sys.argv[2])
    cand = Path(conn_path).parent / "messages.csv"
    return cand if cand.exists() else None


def _flag_already_messaged(conn, msgs_path):
    # collect every profile URL that appears as a sender or recipient
    convo_urls = set()
    for r in _rows(msgs_path):
        for col in ("SENDER PROFILE URL", "RECIPIENT PROFILE URLS"):
            val = r.get(col) or ""
            for u in val.replace(";", " ").replace(",", " ").split():
                if "linkedin.com/in/" in u.lower():
                    convo_urls.add(_norm_url(u))
    if not convo_urls:
        return 0
    flagged = 0
    for cid, url in conn.execute(
            "SELECT id, url FROM contacts WHERE url IS NOT NULL AND url != ''"):
        if _norm_url(url) in convo_urls:
            conn.execute("UPDATE contacts SET already_messaged = 1 WHERE id = ?",
                         (cid,))
            flagged += 1
    conn.commit()
    return flagged


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else DEFAULT)
