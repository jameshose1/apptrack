"""SQLite schema and helpers. Shared with the Next.js UI (same file)."""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "apptrack.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS applications (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    company       TEXT NOT NULL,
    company_key   TEXT,                 -- normalized key for dedup matching
    role          TEXT,
    url           TEXT,
    source        TEXT,                 -- linkedin, handshake, referral, ...
    location      TEXT,
    salary        TEXT,
    contact       TEXT,                 -- referral / recruiter name
    status        TEXT NOT NULL DEFAULT 'applied',
                                        -- wishlist|applied|oa|interview|offer|rejected
    date_applied  TEXT,                 -- ISO date
    notes         TEXT,
    created_at    TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

-- every recruiting-relevant email we've processed, linked to an application
CREATE TABLE IF NOT EXISTS email_events (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    application_id INTEGER REFERENCES applications(id) ON DELETE SET NULL,
    gmail_msg_id   TEXT UNIQUE NOT NULL,
    gmail_thread_id TEXT,
    kind           TEXT,                -- confirmation|rejection|oa|interview|offer|other
    sender         TEXT,
    subject        TEXT,
    snippet        TEXT,
    received_at    TEXT,
    fingerprint    TEXT,
    confidence     REAL,
    created_at     TEXT NOT NULL DEFAULT (datetime('now'))
);

-- OA / interview deadlines, mirrored into Google Calendar
CREATE TABLE IF NOT EXISTS deadlines (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    application_id    INTEGER REFERENCES applications(id) ON DELETE CASCADE,
    kind              TEXT,             -- oa|interview
    due_at            TEXT,             -- ISO datetime
    gcal_event_id     TEXT,
    created_at        TEXT NOT NULL DEFAULT (datetime('now'))
);

-- timed work blocks booked on the calendar (e.g. sit-down time to do an OA)
CREATE TABLE IF NOT EXISTS time_blocks (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    application_id    INTEGER REFERENCES applications(id) ON DELETE CASCADE,
    kind              TEXT,             -- oa
    start_at          TEXT,             -- ISO datetime (local)
    minutes           INTEGER,
    gcal_event_id     TEXT,
    created_at        TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(application_id, kind)
);

-- ambiguous emails awaiting a human decision
CREATE TABLE IF NOT EXISTS review_queue (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    gmail_msg_id     TEXT UNIQUE NOT NULL,
    sender           TEXT,
    subject          TEXT,
    snippet          TEXT,
    received_at      TEXT,
    fingerprint      TEXT,
    proposed_kind    TEXT,
    proposed_company TEXT,
    proposed_role    TEXT,
    confidence       REAL,
    status           TEXT NOT NULL DEFAULT 'pending',  -- pending|resolved|dismissed
    resolved_kind    TEXT,
    created_at       TEXT NOT NULL DEFAULT (datetime('now')),
    resolved_at      TEXT
);

-- learned rules: fingerprint -> label, promoted after N confirmations
CREATE TABLE IF NOT EXISTS learned_rules (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    fingerprint    TEXT NOT NULL,
    label          TEXT NOT NULL,
    confirm_count  INTEGER NOT NULL DEFAULT 0,
    active         INTEGER NOT NULL DEFAULT 0,   -- promoted once confirm_count >= 3
    created_at     TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at     TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(fingerprint, label)
);

-- people the user knows (from their own LinkedIn connections export), used to
-- surface warm-intro / referral paths at companies they're tracking
CREATE TABLE IF NOT EXISTS contacts (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT,
    company       TEXT,
    company_key   TEXT,                 -- normalized, matches applications
    position      TEXT,
    url           TEXT,
    email         TEXT,
    source        TEXT,                 -- linkedin | umd_alum
    connected_on  TEXT,
    is_alum       INTEGER DEFAULT 0,    -- known UMD alum (e.g. umd.edu email)
    created_at    TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(name, company)
);

-- scanner state (last history id / scan cursor, misc key-value)
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);

-- job-scanner: postings already considered, so they're never re-added even
-- after the user dismisses them from the wishlist
CREATE TABLE IF NOT EXISTS job_seen (
    source_id   TEXT PRIMARY KEY,     -- Simplify listing id / ats:<co>:<jobid>
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

-- OA platforms the applicant has already encountered (first OA on a new
-- platform gets +30min practice time; later ones on it don't)
CREATE TABLE IF NOT EXISTS seen_platforms (
    platform    TEXT PRIMARY KEY,
    first_seen  TEXT NOT NULL DEFAULT (datetime('now'))
);

-- resolved ATS board per target company (so we don't re-detect every run)
CREATE TABLE IF NOT EXISTS ats_board (
    company     TEXT PRIMARY KEY,
    ats         TEXT,                 -- greenhouse | lever | ashby | none
    token       TEXT,
    resolved_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""

# columns added after the initial schema shipped (CREATE TABLE IF NOT EXISTS
# won't alter an existing table, so ALTER them in idempotently)
_MIGRATIONS = [
    "ALTER TABLE applications ADD COLUMN posted_at TEXT",       # job posting date
    "ALTER TABLE applications ADD COLUMN is_dream INTEGER DEFAULT 0",
    "ALTER TABLE applications ADD COLUMN oa_completed_at TEXT",  # OA done (date)
    "ALTER TABLE applications ADD COLUMN oa_minutes INTEGER",    # OA length, mins
    "ALTER TABLE applications ADD COLUMN oa_platform TEXT",      # assessment platform
    "ALTER TABLE applications ADD COLUMN oa_practice INTEGER DEFAULT 0",  # +practice
    "ALTER TABLE time_blocks ADD COLUMN practice_event_id TEXT",  # split practice block
    "ALTER TABLE applications ADD COLUMN oa_no_deadline_alerted INTEGER DEFAULT 0",
    "ALTER TABLE contacts ADD COLUMN is_alum INTEGER DEFAULT 0",
]


def connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = connect()
    conn.executescript(SCHEMA)
    for stmt in _MIGRATIONS:
        try:
            conn.execute(stmt)
        except sqlite3.OperationalError:
            pass  # column already exists
    conn.commit()
    conn.close()


def get_meta(conn, key, default=None):
    row = conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else default


def set_meta(conn, key, value):
    conn.execute(
        "INSERT INTO meta(key, value) VALUES(?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, str(value)),
    )
    conn.commit()


if __name__ == "__main__":
    init_db()
    print(f"initialized {DB_PATH}")
