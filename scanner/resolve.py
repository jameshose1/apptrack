"""Resolve a review-queue item. Applies the label, records the confirmation
for the self-learning layer, and promotes a rule once it hits the threshold.

    python3 resolve.py <queue_id> <kind>      # confirm as kind
    python3 resolve.py <queue_id> dismiss      # not a real application update

The Next.js UI can shell out to this so the learning logic lives in one place.
"""
import sys

import learning
from db import connect
from scan import KIND_TO_STATUS, _find_or_create_application, _should_set_status


def resolve(queue_id: int, kind: str):
    conn = connect()
    item = conn.execute(
        "SELECT * FROM review_queue WHERE id = ?", (queue_id,)
    ).fetchone()
    if not item:
        print(f"no queue item {queue_id}")
        return

    if kind == "dismiss":
        conn.execute(
            "UPDATE review_queue SET status='dismissed', "
            "resolved_at=datetime('now') WHERE id = ?",
            (queue_id,),
        )
        conn.commit()
        print(f"dismissed {queue_id}")
        return

    status = KIND_TO_STATUS.get(kind)
    app_id = _find_or_create_application(
        conn, item["proposed_company"], item["proposed_role"], status, False
    )
    if app_id and status:
        # Guard against regressing a more-advanced stage when resolving a stale
        # queued email (e.g. confirming an old "application received" for an app
        # already at 'interview'). Mirrors scan.py's STAGE_RANK rule.
        current = conn.execute(
            "SELECT status FROM applications WHERE id = ?", (app_id,)
        ).fetchone()
        if _should_set_status(status, current["status"] if current else None):
            conn.execute(
                "UPDATE applications SET status=?, "
                "date_applied=COALESCE(date_applied, date('now')), "
                "updated_at=datetime('now') WHERE id = ?",
                (status, app_id),
            )
        else:
            conn.execute(
                "UPDATE applications SET "
                "date_applied=COALESCE(date_applied, date('now')), "
                "updated_at=datetime('now') WHERE id = ?",
                (app_id,),
            )
    conn.execute(
        "INSERT OR IGNORE INTO email_events(application_id, gmail_msg_id, "
        "kind, sender, subject, snippet, received_at, fingerprint, confidence) "
        "VALUES(?,?,?,?,?,?,?,?,?)",
        (app_id, item["gmail_msg_id"], kind, item["sender"], item["subject"],
         item["snippet"], item["received_at"], item["fingerprint"],
         item["confidence"]),
    )
    conn.execute(
        "UPDATE review_queue SET status='resolved', resolved_kind=?, "
        "resolved_at=datetime('now') WHERE id = ?",
        (kind, queue_id),
    )
    conn.commit()

    promoted = learning.confirm(conn, item["fingerprint"], kind)
    conn.close()
    print(f"resolved {queue_id} as {kind}"
          + (" (rule now active, will auto-apply)" if promoted else ""))


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(1)
    resolve(int(sys.argv[1]), sys.argv[2])
