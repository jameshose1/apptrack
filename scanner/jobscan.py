"""Job scanner entrypoint. Pulls fresh internship postings into the wishlist.

    python3 jobscan.py            # add fresh + target-company postings
    python3 jobscan.py --dry-run  # print what it would add, write nothing

Two sources: the SimplifyJobs community list (fresh + FAANG postings) and target
companies' own ATS boards (all their interns). Runs on a schedule via launchd.
Everything is deduped against the board and against postings already seen (so
dismissed cards never come back).
"""
import sys
import time

import atssource
import config
import jobsource
import normalize
from db import connect, get_meta, init_db, set_meta


def _already_on_board(conn, company_key, role, url):
    return bool(conn.execute(
        "SELECT 1 FROM applications WHERE url = ? OR "
        "(company_key = ? AND lower(role) = lower(?)) LIMIT 1",
        (url, company_key, role),
    ).fetchone())


def _seen(conn, source_id):
    return bool(conn.execute("SELECT 1 FROM job_seen WHERE source_id = ?",
                             (source_id,)).fetchone())


def _board_cache(conn):
    def get(name):
        row = conn.execute("SELECT ats, token FROM ats_board WHERE company = ?",
                           (name,)).fetchone()
        return (row["ats"], row["token"]) if row else None

    def save(name, ats, token):
        conn.execute(
            "INSERT OR REPLACE INTO ats_board(company, ats, token, resolved_at) "
            "VALUES(?, ?, ?, datetime('now'))", (name, ats, token))
        conn.commit()
    return get, save


def run(dry=False):
    init_db()
    conn = connect()

    last = get_meta(conn, "last_job_scan_epoch")
    baseline = int(last) if last else int(
        time.time() - config.JOB_FIRST_LOOKBACK_DAYS * 86400)

    # target companies' own boards: every intern is wanted (curated list)
    get_board, save_board = _board_cache(conn)
    ats = [p for p in atssource.fetch_target_postings(get_board, save_board)
           if p["id"] and not _seen(conn, p["id"])]
    ats.sort(key=lambda p: p["posted_epoch"], reverse=True)

    # Simplify: not seen, and dream (FAANG) or posted since the last run
    simplify = [p for p in jobsource.fetch_postings()
                if p["id"] and not _seen(conn, p["id"])
                and (p["is_dream"] or p["posted_epoch"] >= baseline)]
    simplify.sort(key=lambda p: (p["is_dream"], p["posted_epoch"]), reverse=True)

    added = 0
    for p in ats + simplify:            # curated targets first, then Simplify
        if added >= config.JOB_MAX_PER_RUN:
            break
        ckey = normalize.company_key(p["company"])
        if _already_on_board(conn, ckey, p["role"], p["url"]):
            if not dry:
                conn.execute("INSERT OR IGNORE INTO job_seen(source_id) VALUES(?)",
                             (p["id"],))
                conn.commit()
            continue
        star = "*" if p["is_dream"] else " "
        print(f"  {star} [{p['source']}] {p['company']} — {p['role']} "
              f"({p['location']})")
        if not dry:
            conn.execute(
                "INSERT INTO applications(company, company_key, role, url, "
                "source, location, status, posted_at, is_dream) "
                "VALUES(?,?,?,?,?,?,'wishlist',?,?)",
                (p["company"], ckey, p["role"], p["url"], p["source"],
                 p["location"], p["posted_iso"], 1 if p["is_dream"] else 0),
            )
            conn.execute("INSERT OR IGNORE INTO job_seen(source_id) VALUES(?)",
                         (p["id"],))
            conn.commit()
        added += 1

    if not dry:
        set_meta(conn, "last_job_scan_epoch", str(int(time.time())))
    conn.close()
    print(f"jobscan: {'would add' if dry else 'added'} {added} posting(s) "
          f"({len(ats)} target + {len(simplify)} simplify candidates)")


if __name__ == "__main__":
    run(dry="--dry-run" in sys.argv)
