"""Mark an OA as MISSED: tear down its calendar blocks + deadline/alert tasks,
move the application to 'rejected' (a missed OA is a dead end, kept as a record),
and re-serialize the remaining OAs. The web UI shells out to this.

    python3 miss_oa.py <application_id>
"""
import sys

import config
import google_client as gc
from calendar_sync import sync_oa_blocks
from db import connect


def main(app_id):
    conn = connect()
    cal, tsk = gc.calendar(), gc.tasks()
    row = conn.execute("SELECT company FROM applications WHERE id = ?",
                       (app_id,)).fetchone()
    company = row["company"] if row else ""

    # 1. remove the OA work/practice calendar events
    for b in conn.execute(
        "SELECT gcal_event_id, practice_event_id FROM time_blocks "
        "WHERE application_id = ? AND kind = 'oa'", (app_id,)).fetchall():
        for ev in (b["gcal_event_id"], b["practice_event_id"]):
            if ev:
                try:
                    gc.delete_event(cal, ev)
                except Exception:
                    pass
    conn.execute("DELETE FROM time_blocks WHERE application_id = ? AND kind = 'oa'",
                 (app_id,))

    # 2. remove the OA deadline Google Tasks
    for d in conn.execute(
        "SELECT gcal_event_id FROM deadlines WHERE application_id = ? "
        "AND kind = 'oa'", (app_id,)).fetchall():
        if d["gcal_event_id"]:
            try:
                gc.delete_task(tsk, d["gcal_event_id"])
            except Exception:
                pass
    conn.execute("DELETE FROM deadlines WHERE application_id = ? AND kind = 'oa'",
                 (app_id,))

    # 3. clean up any "Set OA deadline" alert task for this company
    try:
        for t in tsk.tasks().list(tasklist=config.TASKLIST_ID,
                                  showCompleted=False, maxResults=100
                                  ).execute().get("items", []):
            title = t.get("title", "")
            if "Set OA deadline" in title and company and company in title:
                tsk.tasks().delete(tasklist=config.TASKLIST_ID,
                                   task=t["id"]).execute()
    except Exception:
        pass

    # 4. a missed OA is a dead end -> 'missed' (renders in the Rejected column)
    conn.execute(
        "UPDATE applications SET status = 'missed', notes = 'missed OA deadline', "
        "updated_at = datetime('now') WHERE id = ?", (app_id,))
    conn.commit()

    sync_oa_blocks(cal, tsk, conn)   # let the freed day go to the next OA
    print(f"marked OA missed -> rejected + cleaned up ({company}, id {app_id})")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)
    main(int(sys.argv[1]))
