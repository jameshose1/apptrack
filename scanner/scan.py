"""Main scan entrypoint. Run on a schedule via launchd.

    python3 scan.py            # normal incremental scan
    python3 scan.py --dry-run  # classify + print, write nothing

Flow per email: fetch -> prefilter -> classify -> fingerprint -> route
(learned rule | high-confidence auto-apply | review queue) -> update board ->
sync calendar. Finishes by placing today's accountability hour.
"""
import re
import sys
import time
from datetime import datetime, timedelta

import classify as classifier
import config
import digest
import fingerprint as fp
import google_client as gc
import imap_client
import learning
import normalize
from calendar_sync import (place_accountability_hour, schedule_interview,
                           sync_deadline, sync_oa_blocks)
from db import connect, get_meta, init_db, set_meta

# maps a classification kind -> board status
KIND_TO_STATUS = {
    "confirmation": "applied",
    "oa": "oa",
    "interview": "interview",
    "team_match": "team_match",
    "offer": "offer",
    "rejection": "rejected",
}

# pipeline order; status only advances (a late-arriving "application received"
# must never knock something back from oa/interview). offer/rejected are
# terminal outcomes that win regardless of current stage.
STAGE_RANK = {"wishlist": 0, "applied": 1, "oa": 2, "interview": 3,
              "team_match": 4, "offer": 5, "rejected": 5, "missed": 5}
_TERMINAL = {"offer", "rejected", "missed"}


def _should_set_status(new, current):
    if not current:
        return True
    if new in _TERMINAL:
        return True
    return STAGE_RANK.get(new, 0) > STAGE_RANK.get(current, 0)

# Volume is cut server-side by Gmail's X-GM-RAW search in imap_client, so
# everything reaching here is already a recruiting candidate.


# generic words shared by nearly every SWE-intern title; the DISTINCTIVE tokens
# (backend, robotics, ios, ml, ...) are what tell two roles at one company apart
_ROLE_STOP = {
    "software", "engineer", "engineering", "intern", "internship", "interns",
    "developer", "development", "dev", "summer", "fall", "winter", "spring",
    "2026", "2027", "2028", "co", "op", "coop", "the", "and", "of", "for",
    "new", "grad", "program", "early", "career", "swe", "technical",
    "technology", "tech", "full", "time", "student", "university", "college",
}


def _role_tokens(role):
    return {t for t in re.split(r"[^a-z0-9]+", (role or "").lower())
            if t and len(t) > 1 and t not in _ROLE_STOP}


def _role_match(a, b):
    """True if two roles share a distinctive token. False when either is generic
    (only stop-words) — then we can't tell the roles apart by title alone."""
    ta, tb = _role_tokens(a), _role_tokens(b)
    return bool(ta and tb and (ta & tb))


# two orthogonal tags that split the board: CS vs non-CS, internship vs job.
# The classifier sets them when it can; otherwise fall back to the role title.
_INTERN_RE = re.compile(r"\b(intern|internship|interns|co-?op)\b", re.I)
_CS_RE = re.compile(
    r"\b(software|develop\w*|engineer\w*|program\w*|data|machine.?learning|"
    r"\bml\b|\bai\b|backend|back.?end|frontend|front.?end|full.?stack|devops|"
    r"\bsre\b|security|computer|\bit\b|\bqa\b|test\w*|mobile|ios|android|web|"
    r"cloud|platform|systems?|robotics|firmware|embedded|infrastructure|network)\b",
    re.I,
)


def _field_track(verdict):
    """(field, track) for an application from the classifier verdict, with a
    role-title fallback when the model left a flag unset (None)."""
    role = verdict.get("role") or ""
    intern = verdict.get("is_internship")
    if intern is None:
        intern = bool(_INTERN_RE.search(role))
    cs = verdict.get("is_cs")
    if cs is None:
        cs = bool(_CS_RE.search(role))
    return ("cs" if cs else "other"), ("internship" if intern else "job")


def _find_or_create_application(conn, company, role, status, dry,
                                field="cs", track="internship"):
    """Attach an email to the right application row (creating one if needed).

    Prefers a role match at the company so a confirmation email PROMOTES the
    matching wishlist card the user forgot to mark applied. Falls back to an
    existing pipeline row, then a lone wishlist card; only makes a brand-new row
    when nothing sensible matches.
    """
    company = (company or "").strip()
    if not company:
        return None
    key = normalize.company_key(company)
    rows = conn.execute(
        "SELECT id, role, status FROM applications WHERE company_key = ? "
        "ORDER BY id DESC", (key,),
    ).fetchall()
    chosen = None
    if rows:
        matches = [r for r in rows if _role_match(role, r["role"])]
        if matches:  # same role — prefer a wishlist card so it gets promoted
            wl = [r for r in matches if r["status"] == "wishlist"]
            chosen = (wl or matches)[0]["id"]
        else:
            pipeline = [r for r in rows if r["status"] != "wishlist"]
            wl = [r for r in rows if r["status"] == "wishlist"]
            if pipeline:
                chosen = pipeline[0]["id"]           # already-tracked row
            elif len(wl) == 1 and status and status != "wishlist":
                chosen = wl[0]["id"]                  # lone wishlist -> promote
            # else ambiguous (multiple wishlist, unknown role) -> new row below
    if chosen is not None:
        return chosen
    if dry:
        return None
    cur = conn.execute(
        "INSERT INTO applications(company, company_key, role, status, "
        "date_applied, field, track) "
        "VALUES(?, ?, ?, 'applied', date('now'), ?, ?)",
        (company, key, role or "", field, track),
    )
    conn.commit()
    return cur.lastrowid


def _plausible_due(iso):
    """Keep an absolute due only if it's sane: not already past and within a
    year. Guards against mis-extracted years (e.g. '2025' from branding)."""
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None
    now = datetime.now(dt.tzinfo) if dt.tzinfo else datetime.now()
    return iso if now - timedelta(days=1) <= dt <= now + timedelta(days=365) else None


def _due_from_verdict(verdict, received_at):
    """Resolve an OA/interview due datetime (ISO) or None.

    Absolute date wins (if plausible); otherwise a relative window is measured
    from when the email HIT THE INBOX (received_at), never from scan time.
    """
    iso = (verdict.get("deadline_iso") or "").strip()
    if iso and _plausible_due(iso):
        return iso
    days = verdict.get("deadline_days") or 0
    try:
        days = float(days)
    except (TypeError, ValueError):
        days = 0
    if days > 0:
        try:
            base = datetime.fromisoformat(received_at)
        except (ValueError, TypeError):
            return None
        return (base + timedelta(days=days)).isoformat()
    return None


def _platform_key(p):
    return re.sub(r"[^a-z0-9]", "", (p or "").lower())


def _has_clock_time(iso) -> bool:
    """True if an ISO datetime carries an actual time of day (a scheduled
    interview), not just a bare date / midnight."""
    try:
        dt = datetime.fromisoformat((iso or "").strip())
    except (ValueError, TypeError):
        return False
    return dt.hour != 0 or dt.minute != 0


def _apply_label(conn, cal, tasks_svc, msg, verdict, print_only):
    kind = verdict["kind"]
    status = KIND_TO_STATUS.get(kind)
    due = _due_from_verdict(verdict, msg["received_at"]) if kind in ("oa", "interview") else None
    oa_done = kind == "oa" and bool(verdict.get("oa_completed"))
    field, track = _field_track(verdict)
    app_id = _find_or_create_application(
        conn, verdict.get("company"), verdict.get("role"), status, print_only,
        field, track,
    )
    if print_only:
        extra = f" | due {due[:10]}" if due else ""
        if kind == "oa":
            extra += " | OA COMPLETED" if oa_done else \
                f" | oa {verdict.get('oa_minutes') or 'default'}min"
        print(f"  -> AUTO {kind} ({verdict['confidence']:.2f}) "
              f"[{field}/{track}] "
              f"{verdict.get('company')} / {verdict.get('role')}{extra}")
        return
    if app_id:
        # keep the two tags current to the latest classification (self-corrects a
        # row first created from a vaguer email); never flip a sourced wishlist's
        # tags here since sourcing sets them explicitly
        conn.execute(
            "UPDATE applications SET field = ?, track = ? WHERE id = ? "
            "AND status != 'wishlist'", (field, track, app_id))
        cur = conn.execute("SELECT status FROM applications WHERE id = ?",
                           (app_id,)).fetchone()
        # status only advances (a late "received" email can't undo oa/interview)
        if status and _should_set_status(status, cur["status"] if cur else None):
            conn.execute(
                "UPDATE applications SET status = ?, "
                "date_applied = COALESCE(date_applied, date('now')), "
                "updated_at = datetime('now') WHERE id = ?",
                (status, app_id),
            )
        if kind == "interview":
            # track the furthest interview round reached (at least 1 for any
            # interview email); the classifier guesses the round when stated
            rnd = int(verdict.get("interview_round") or 0) or 1
            conn.execute(
                "UPDATE applications SET round = MAX(COALESCE(round, 0), ?) "
                "WHERE id = ?", (rnd, app_id))
        if kind == "oa":
            mins = int(verdict.get("oa_minutes") or 0)
            if mins:
                conn.execute(
                    "UPDATE applications SET oa_minutes = ? WHERE id = ? "
                    "AND (oa_minutes IS NULL OR oa_minutes = 0)", (mins, app_id))
            # +30m practice the FIRST time a platform is seen
            plat = _platform_key(verdict.get("oa_platform"))
            if plat:
                conn.execute(
                    "UPDATE applications SET oa_platform = ? WHERE id = ? AND "
                    "(oa_platform IS NULL OR oa_platform = '')", (plat, app_id))
                new_platform = not conn.execute(
                    "SELECT 1 FROM seen_platforms WHERE platform = ?",
                    (plat,)).fetchone()
                if new_platform and not oa_done:
                    conn.execute("UPDATE applications SET oa_practice = 1 "
                                 "WHERE id = ?", (app_id,))
                conn.execute("INSERT OR IGNORE INTO seen_platforms(platform) "
                             "VALUES(?)", (plat,))
            if oa_done:  # an "assessment complete" email auto-marks it done
                conn.execute(
                    "UPDATE applications SET oa_completed_at = "
                    "COALESCE(oa_completed_at, date('now')) WHERE id = ?",
                    (app_id,))
    conn.execute(
        "INSERT OR IGNORE INTO email_events(application_id, gmail_msg_id, "
        "gmail_thread_id, kind, sender, subject, snippet, received_at, "
        "fingerprint, confidence) VALUES(?,?,?,?,?,?,?,?,?,?)",
        (app_id, msg["id"], msg["thread_id"], kind, msg["sender"],
         msg["subject"], msg["snippet"], msg["received_at"],
         msg["_fp"], verdict.get("confidence", 0.0)),
    )
    conn.commit()
    # an interview email with an actual clock time becomes a real calendar event
    # + prep block; an uncompleted OA/interview due date becomes a checkable Task
    if kind == "interview" and app_id and _has_clock_time(verdict.get("deadline_iso")):
        schedule_interview(cal, tasks_svc, conn, app_id, due)
    elif due and not oa_done:
        sync_deadline(tasks_svc, conn, app_id, kind, due)
    # NB: OA work blocks are booked by the serialized queue (sync_oa_blocks) at
    # the end of the scan, not here, so only the soonest-due incomplete OA is
    # scheduled and no two land on the same day.


def _queue(conn, msg, verdict, print_only):
    if print_only:
        print(f"  -> QUEUE {verdict['kind']} ({verdict['confidence']:.2f}) "
              f"{verdict.get('company')}")
        return
    conn.execute(
        "INSERT OR IGNORE INTO review_queue(gmail_msg_id, sender, subject, "
        "snippet, received_at, fingerprint, proposed_kind, proposed_company, "
        "proposed_role, confidence) VALUES(?,?,?,?,?,?,?,?,?,?)",
        (msg["id"], msg["sender"], msg["subject"], msg["snippet"],
         msg["received_at"], msg["_fp"], verdict["kind"],
         verdict.get("company", ""), verdict.get("role", ""),
         verdict.get("confidence", 0.0)),
    )
    conn.commit()


def _already_seen(conn, msg_id) -> bool:
    a = conn.execute("SELECT 1 FROM email_events WHERE gmail_msg_id = ?",
                     (msg_id,)).fetchone()
    b = conn.execute("SELECT 1 FROM review_queue WHERE gmail_msg_id = ?",
                     (msg_id,)).fetchone()
    return bool(a or b)


def run(dry=False):
    init_db()
    conn = connect()
    cal = None if dry else gc.calendar()
    tasks_svc = None if dry else gc.tasks()

    since = imap_client.since_from_epoch(get_meta(conn, "last_scan_epoch"))
    print(f"scan: reading INBOX since {since}")

    seen = classified = 0
    for msg in imap_client.fetch_since(since):
        seen += 1
        if _already_seen(conn, msg["id"]):
            continue
        classified += 1
        print(f"  . [{classified}] {msg['subject'][:55]}", flush=True)
        verdict = classifier.classify(msg)
        msg["_fp"] = fp.compute(
            msg["sender"], msg["subject"], msg["body"],
            strip_terms=[config.APPLICANT_NAME, verdict.get("company", "")],
        )

        if verdict["kind"] == "other":
            continue

        print(f"[{msg['subject'][:60]}]")
        learned = learning.matching_rule(conn, msg["_fp"])
        if learned:
            verdict["kind"] = learned
            _apply_label(conn, cal, tasks_svc, msg, verdict, dry)
        elif verdict["confidence"] >= config.AUTO_APPLY_CONFIDENCE:
            _apply_label(conn, cal, tasks_svc, msg, verdict, dry)
        else:
            _queue(conn, msg, verdict, dry)

    if not dry:
        cal = cal or gc.calendar()
        # serialize OA work blocks (soonest-due first, one/day, skip completed)
        sync_oa_blocks(cal, tasks_svc, conn)
        digest.post_daily_digest(cal, conn)   # today's summary + running counts
        # lay out TOMORROW's job-application hour on the evening ("night before")
        # run; the first run at/after the night hour books it, later ones no-op
        if datetime.now().hour >= config.ACCOUNTABILITY_NIGHT_BEFORE_HOUR:
            tomorrow = (datetime.now() + timedelta(days=1)).date()
            place_accountability_hour(cal, tasks_svc, tomorrow)
        set_meta(conn, "last_scan_epoch", str(int(time.time())))
    conn.close()
    print(f"scan: done ({seen} read, {classified} classified)")


if __name__ == "__main__":
    run(dry="--dry-run" in sys.argv)
