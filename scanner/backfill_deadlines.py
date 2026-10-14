"""One-off: recompute deadlines + OA work blocks for OA/interview emails already
on record (from before relative-deadline/OA-block support). Re-fetches recent
bodies, re-classifies, syncs the deadline Task, and books the OA sit-down block.
Does NOT change board status.

    python3 backfill_deadlines.py            # sync
    python3 backfill_deadlines.py --dry-run  # classify + print only
"""
import sys
from datetime import date, timedelta

import classify
import google_client as gc
import imap_client
from calendar_sync import schedule_oa_block, sync_deadline
from db import connect
from scan import _due_from_verdict


def main(lookback_days=7, dry=False):
    conn = connect()
    tasks_svc = None if dry else gc.tasks()
    cal = None if dry else gc.calendar()
    targets = {
        r["gmail_msg_id"]: r["application_id"]
        for r in conn.execute(
            "SELECT gmail_msg_id, application_id FROM email_events "
            "WHERE kind IN ('oa', 'interview')"
        ).fetchall()
    }
    if not targets:
        print("no OA/interview emails on record")
        return
    print(f"{len(targets)} OA/interview email(s) on record; re-fetching last "
          f"{lookback_days} days")
    since = date.today() - timedelta(days=lookback_days)
    matched = 0
    for msg in imap_client.fetch_since(since):
        if msg["id"] not in targets:
            continue
        matched += 1
        v = classify.classify(msg)
        due = _due_from_verdict(v, msg["received_at"])
        print(f"- {msg['subject'][:50]}")
        print(f"    kind={v.get('kind')} iso={v.get('deadline_iso') or '-'} "
              f"days={v.get('deadline_days')} oa_min={v.get('oa_minutes')} "
              f"-> due={due or '-'}")
        if dry:
            continue
        app_id = targets[msg["id"]]
        if due and v["kind"] in ("oa", "interview"):
            tid = sync_deadline(tasks_svc, conn, app_id, v["kind"], due)
            print("    deadline synced" if tid else "    deadline skipped")
        if v["kind"] == "oa":
            bid = schedule_oa_block(cal, tasks_svc, conn, app_id, due,
                                    v.get("oa_minutes", 0))
            print(f"    oa block {'booked' if bid else 'none free'}")
    print(f"done ({matched}/{len(targets)} target emails re-fetched)")


if __name__ == "__main__":
    main(dry="--dry-run" in sys.argv)
