"""Load the applicant profile the 'why us' generator writes from:
  - experience: your resume text (pass a path, or defaults to the HTML resume)
  - style: a prose writing sample so blurbs sound like you (data/writing_sample.txt)

    python3 import_profile.py [resume.html|.txt]
    # drop a paragraph you wrote into data/writing_sample.txt for voice-matching
"""
import html
import re
import sys
from pathlib import Path

from db import connect, init_db

HOME = Path.home()
DEFAULT_RESUME = next((p for p in [
    HOME / "Downloads" / "James_Hose_Resume_2026-09.html",
    HOME / "Downloads" / "James_Hose_Resume_2026-09.txt",
] if p.exists()), None)
SAMPLE = Path(__file__).resolve().parent.parent / "data" / "writing_sample.txt"


def _text(path: Path) -> str:
    raw = path.read_text(errors="ignore")
    if path.suffix.lower() in (".html", ".htm"):
        raw = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", raw, flags=re.S | re.I)
        raw = html.unescape(re.sub(r"<[^>]+>", " ", raw))
    return re.sub(r"\s+", " ", raw).strip()


def _set(conn, key, value):
    conn.execute("INSERT INTO profile(key, value) VALUES(?, ?) "
                 "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                 (key, value))


def main(resume=None):
    init_db()
    conn = connect()
    resume = Path(resume) if resume else DEFAULT_RESUME
    if resume and resume.exists():
        _set(conn, "experience", _text(resume))
        print(f"experience set from {resume.name} ({len(_text(resume))} chars)")
    else:
        print("no resume found — pass a path, or add one; experience unset")
    if SAMPLE.exists() and SAMPLE.read_text().strip():
        _set(conn, "style", SAMPLE.read_text().strip())
        print(f"style set from writing_sample.txt")
    else:
        print("no data/writing_sample.txt yet — blurbs use a neutral voice until "
              "you add a paragraph you wrote there")
    conn.commit()


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)
