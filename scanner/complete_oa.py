"""Mark an application's OA as completed, then re-serialize OA blocks so the
next-soonest OA gets scheduled. The web UI shells out to this (keeps calendar
access + the queue logic in one place).

    python3 complete_oa.py <application_id>          # mark done
    python3 complete_oa.py <application_id> --undo    # unmark
"""
import sys

import google_client as gc
from calendar_sync import sync_oa_blocks
from db import connect


def main(app_id, undo=False):
    conn = connect()
    if undo:
        conn.execute("UPDATE applications SET oa_completed_at = NULL, "
                     "updated_at = datetime('now') WHERE id = ?", (app_id,))
    else:
        conn.execute("UPDATE applications SET oa_completed_at = "
                     "COALESCE(oa_completed_at, date('now')), "
                     "updated_at = datetime('now') WHERE id = ?", (app_id,))
    conn.commit()
    sync_oa_blocks(gc.calendar(), gc.tasks(), conn)
    print(f"OA {'uncompleted' if undo else 'completed'} + rescheduled for {app_id}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    main(int(sys.argv[1]), undo="--undo" in sys.argv)
