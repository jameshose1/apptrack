"""The self-learning layer over the review queue.

A rule is (fingerprint -> label). Every time you resolve a queued email the
same way, its confirm_count ticks up. At PROMOTE_THRESHOLD it goes active and
future matching emails skip the queue entirely. Correcting an auto-applied
label demotes the rule so it asks again.
"""

PROMOTE_THRESHOLD = 3


def matching_rule(conn, fingerprint: str):
    """Return an active rule's label for this fingerprint, or None."""
    if not fingerprint:
        return None
    row = conn.execute(
        "SELECT label FROM learned_rules "
        "WHERE fingerprint = ? AND active = 1 "
        "ORDER BY confirm_count DESC LIMIT 1",
        (fingerprint,),
    ).fetchone()
    return row["label"] if row else None


def confirm(conn, fingerprint: str, label: str) -> bool:
    """Record a human confirmation. Returns True if the rule is now active."""
    conn.execute(
        "INSERT INTO learned_rules(fingerprint, label, confirm_count, active) "
        "VALUES(?, ?, 1, 0) "
        "ON CONFLICT(fingerprint, label) DO UPDATE SET "
        "  confirm_count = confirm_count + 1, "
        "  updated_at = datetime('now')",
        (fingerprint, label),
    )
    row = conn.execute(
        "SELECT confirm_count FROM learned_rules "
        "WHERE fingerprint = ? AND label = ?",
        (fingerprint, label),
    ).fetchone()
    active = row["confirm_count"] >= PROMOTE_THRESHOLD
    if active:
        conn.execute(
            "UPDATE learned_rules SET active = 1, updated_at = datetime('now') "
            "WHERE fingerprint = ? AND label = ?",
            (fingerprint, label),
        )
    conn.commit()
    return active


def demote(conn, fingerprint: str, label: str):
    """A correction: deactivate and reset this rule so it asks again."""
    conn.execute(
        "UPDATE learned_rules SET active = 0, confirm_count = 0, "
        "  updated_at = datetime('now') "
        "WHERE fingerprint = ? AND label = ?",
        (fingerprint, label),
    )
    conn.commit()
