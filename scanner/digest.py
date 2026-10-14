"""Daily summary: one all-day calendar entry per day whose title carries the
running sent-counts and whose description is the bullet digest (due soon, OAs to
do, recent rejections, interviews). One per day => scrolling the calendar back
is a running count-per-day view. Refreshed on each scan; past days stay as-is.
"""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import config
import google_client as gc
from db import get_meta, set_meta

TZ = ZoneInfo(config.TIMEZONE)


def _count(conn, sql, *args):
    return conn.execute(sql, args).fetchone()[0]


def build(conn, today):
    """Return (title, body) for today's digest."""
    base = "SELECT count(*) FROM applications WHERE status != 'wishlist'"
    total = _count(conn, base)
    sent_today = _count(conn, base + " AND date_applied = ?", today.isoformat())
    sent_week = _count(conn, base + " AND date_applied >= ?",
                       (today - timedelta(days=6)).isoformat())
    title = f"\U0001F4CB apptrack: {sent_today} sent today · {total} total"

    lines = [f"Applications sent: {sent_today} today · {sent_week} this "
             f"week · {total} total", ""]

    soon = conn.execute(
        "SELECT a.company, d.kind, d.due_at FROM deadlines d "
        "JOIN applications a ON a.id = d.application_id "
        "WHERE d.due_at >= datetime('now') AND d.due_at <= datetime('now','+7 days') "
        "AND NOT (d.kind = 'oa' AND a.oa_completed_at IS NOT NULL) "
        "ORDER BY d.due_at").fetchall()
    if soon:
        lines.append("Due within 7 days:")
        lines += [f"  • {r['kind'].upper()} – {r['company']} "
                  f"({r['due_at'][:10]})" for r in soon]
        lines.append("")

    oas = conn.execute(
        "SELECT company FROM applications WHERE status = 'oa' "
        "AND oa_completed_at IS NULL ORDER BY company").fetchall()
    if oas:
        lines.append("OAs to do: " + ", ".join(r["company"] for r in oas))
        lines.append("")

    interviews = conn.execute(
        "SELECT company FROM applications WHERE status = 'interview' "
        "ORDER BY company").fetchall()
    if interviews:
        lines.append("Interviews: "
                     + ", ".join(r["company"] for r in interviews))
        lines.append("")

    rej = conn.execute(
        "SELECT company FROM applications WHERE status = 'rejected' "
        "AND updated_at >= datetime('now','-7 days') ORDER BY updated_at DESC"
    ).fetchall()
    if rej:
        lines.append("Rejections this week: "
                     + ", ".join(r["company"] for r in rej))

    return title, "\n".join(lines).strip()


def post_daily_digest(cal, conn):
    """Create/refresh today's all-day digest event. Past days are left intact."""
    if not config.DIGEST_ENABLED:
        return
    today = datetime.now(TZ).date()
    title, body = build(conn, today)
    eid = get_meta(conn, "digest_event_id")
    if get_meta(conn, "digest_date") == today.isoformat() and eid:
        try:
            gc.update_event(cal, eid, summary=title, description=body)
            return
        except Exception:
            pass  # event was deleted -> fall through and make a new one
    eid = gc.create_event(
        cal, title, today.isoformat(), (today + timedelta(days=1)).isoformat(),
        description=body, all_day=True, color_id=config.DIGEST_COLOR_ID)
    set_meta(conn, "digest_event_id", eid)
    set_meta(conn, "digest_date", today.isoformat())
