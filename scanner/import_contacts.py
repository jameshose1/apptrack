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
    total = conn.execute("SELECT count(*) FROM contacts").fetchone()[0]
    print(f"imported {added} new contact(s) ({total} total)")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else DEFAULT)
