"""Google Calendar sync: deadline events + the daily accountability hour.

All day-boundary and free-slot logic runs in the configured local timezone so
the accountability hour lands where you actually have a free hour.
"""
import re
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import config
import google_client as gc
import prep

TZ = ZoneInfo(config.TIMEZONE)

# match a quiz/test/exam by whole word in an event title (so "contest",
# "testing", "finalize" don't trip it)
_EXAM_RE = re.compile(
    r"\b(" + "|".join(re.escape(w) for w in config.EXAM_KEYWORDS) + r")\b",
    re.IGNORECASE,
) if config.EXAM_KEYWORDS else None


def _plausible(due_at: str) -> bool:
    """Reject empty, past, or absurdly-far deadlines (hallucinated dates)."""
    try:
        due = datetime.fromisoformat(due_at.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return False
    now = datetime.now(due.tzinfo) if due.tzinfo else datetime.now()
    return now - timedelta(hours=12) <= due <= now + timedelta(days=365)


def sync_deadline(tasks_svc, conn, application_id: int, kind: str, due_at: str):
    """Create a checkable Google Task for an OA/interview deadline if not already
    synced. The task's id is stored in the deadlines.gcal_event_id column."""
    if not _plausible(due_at):
        return None
    existing = conn.execute(
        "SELECT id, gcal_event_id FROM deadlines "
        "WHERE application_id = ? AND kind = ? AND due_at = ?",
        (application_id, kind, due_at),
    ).fetchone()
    if existing and existing["gcal_event_id"]:
        return existing["gcal_event_id"]

    app = conn.execute(
        "SELECT company, role FROM applications WHERE id = ?", (application_id,)
    ).fetchone()
    label = f"{kind.upper()} due: {app['company']}" if app else f"{kind.upper()} due"
    day = datetime.fromisoformat(due_at).astimezone(TZ).date()
    task_id = gc.create_task(
        tasks_svc, label, day.isoformat(),
        notes=f"apptrack: {app['role'] if app else ''}",
    )
    conn.execute(
        "INSERT INTO deadlines(application_id, kind, due_at, gcal_event_id) "
        "VALUES(?, ?, ?, ?)",
        (application_id, kind, due_at, task_id),
    )
    conn.commit()
    return task_id


def _ceil_to_gran(dt: datetime) -> datetime:
    """Round a datetime UP to the next SLOT_GRANULARITY_MIN boundary."""
    g = config.SLOT_GRANULARITY_MIN
    dt = dt.replace(second=0, microsecond=0)
    rem = (dt.minute % g)
    return dt if rem == 0 else dt + timedelta(minutes=g - rem)


def _first_gap(day_start: datetime, busy: list, minutes: int,
               not_before: datetime, hard_end: datetime = None):
    """Earliest start on `day_start`'s date where a `minutes` block fits inside
    the local window without overlapping any busy interval, or None."""
    win_start = day_start.replace(hour=config.ACCOUNTABILITY_WINDOW_START)
    win_end = day_start.replace(hour=config.ACCOUNTABILITY_WINDOW_END)
    if hard_end:
        win_end = min(win_end, hard_end)
    step = timedelta(minutes=config.SLOT_GRANULARITY_MIN)
    block = timedelta(minutes=minutes)
    cand = _ceil_to_gran(max(win_start, not_before))
    while cand + block <= win_end:
        end = cand + block
        if not any(cand < b_end and end > b_start for b_start, b_end in busy):
            return cand
        cand += step
    return None


def _infer_sleep(intervals, day_start):
    """Infer a sleep interval to treat as unavailable, or None. If any busy time
    falls in the small hours (before OVERNIGHT_EARLY_HOUR), the user was up
    overnight; sleep starts when that overnight run ends and lasts until the next
    commitment that day, capped at MAX_SLEEP_HOURS. `intervals` are tz-aware
    (start, end) busy tuples for the day."""
    intervals = sorted(intervals)
    early_cut = day_start + timedelta(hours=config.OVERNIGHT_EARLY_HOUR)
    if not any(s < early_cut and e > day_start for s, e in intervals):
        return None  # nothing in the small hours -> a normal day, no daytime sleep
    merge_gap = timedelta(minutes=config.SLEEP_MERGE_GAP_MIN)
    run_end = None
    for s, e in intervals:
        if run_end is None:
            if s < early_cut:
                run_end = e
        elif s <= run_end + merge_gap:
            run_end = max(run_end, e)
        else:
            break
    if run_end is None:
        return None
    nxt = next((s for s, _ in intervals if s > run_end), None)
    cap = run_end + timedelta(hours=config.MAX_SLEEP_HOURS)
    sleep_end = min(nxt, cap) if nxt else cap
    return (run_end, sleep_end) if sleep_end > run_end else None


def _unavailable(busy_raw, day_start):
    """Busy intervals for the day plus an inferred sleep block, each padded by
    EVENT_BUFFER_MIN so blocks never butt right against a commitment or wake-up."""
    intervals = list(busy_raw)
    sleep = _infer_sleep(intervals, day_start)
    if sleep:
        intervals.append(sleep)
    buf = timedelta(minutes=config.EVENT_BUFFER_MIN)
    return [(s - buf, e + buf) for s, e in intervals]


def _exam_courses(tasks_svc, target_date):
    """Course tokens (e.g. 'cmsc250') with a quiz/test/exam Google Task due on
    target_date. Exams live in Tasks, not calendar events; the task names the
    course, the calendar supplies the time."""
    if _EXAM_RE is None or tasks_svc is None:
        return set()
    want = target_date.isoformat()
    tokens, page = set(), None
    while True:
        res = tasks_svc.tasks().list(tasklist=config.TASKLIST_ID,
                                     showCompleted=False, maxResults=100,
                                     pageToken=page).execute()
        for t in res.get("items", []):
            if (t.get("due") or "")[:10] != want:
                continue
            title = t.get("title", "") or ""
            if _EXAM_RE.search(title) and title.split():
                tokens.add(title.split()[0].rstrip(":").lower())
        page = res.get("nextPageToken")
        if not page:
            return tokens


def _study_wall(cal, tasks_svc, day_start, cal_ids):
    """Datetime nothing should be scheduled before, because there's an in-class
    exam that day (studying up to it). Finds exam Tasks due that day, then the
    matching course's class meeting; walls up to the latest such class's end.
    None if no exam, or the exam's course has no class that day (e.g. an online
    quiz), which by design does not wall the day."""
    tokens = _exam_courses(tasks_svc, day_start.date())
    if not tokens:
        return None
    win_end = day_start.replace(hour=config.ACCOUNTABILITY_WINDOW_END)
    day_end = (day_start + timedelta(days=1)).isoformat()
    latest = None
    for cid in cal_ids:
        try:
            events = gc.list_events_between(cal, day_start.isoformat(),
                                            day_end, calendar_id=cid)
        except Exception:
            continue  # a calendar we can see freebusy for but not events
        for e in events:
            title = (e.get("summary", "") or "").lower()
            if not any(tok in title for tok in tokens):
                continue
            dt = e.get("end", {}).get("dateTime")
            end = datetime.fromisoformat(dt) if dt else win_end
            if latest is None or end > latest:
                latest = end
    return latest


def place_accountability_hour(cal, tasks_svc, target_date: date = None) -> str | None:
    """Book the daily 'Job Application Time' block on target_date (default
    today). Cascade: try the full hour, then the shorter fallback; if neither
    fits, void the day (book nothing). Deduped by summary for that day."""
    target_date = target_date or datetime.now(TZ).date()
    if config.ACCOUNTABILITY_SKIP_WEEKENDS and target_date.weekday() >= 5:
        return None
    day_start = datetime(target_date.year, target_date.month, target_date.day,
                         tzinfo=TZ)
    day_end = day_start + timedelta(days=1)
    for e in gc.list_events_between(cal, day_start.isoformat(),
                                    day_end.isoformat()):
        if e.get("summary") == "Job Application Time":
            return e["id"]
    cal_ids = gc.list_calendar_ids(cal)
    busy = _unavailable(
        gc.busy_between(cal, day_start.isoformat(), day_end.isoformat(),
                        calendar_ids=cal_ids),
        day_start)
    wall = _study_wall(cal, tasks_svc, day_start, cal_ids)
    not_before = max(day_start, wall) if wall else day_start
    for minutes in (config.ACCOUNTABILITY_MINUTES, config.ACCOUNTABILITY_MIN_MINUTES):
        slot = _first_gap(day_start, busy, minutes, not_before)
        if slot:
            return gc.create_event(
                cal, "Job Application Time", slot.isoformat(),
                (slot + timedelta(minutes=minutes)).isoformat(),
                description="apptrack accountability block",
                color_id=config.ACCOUNTABILITY_COLOR_ID,
                reminders=config.ACCOUNTABILITY_REMINDERS,
            )
    return None  # day voided: no free slot even for the short fallback


def _book_before(cal, tasks_svc, conn, application_id, kind, label, notes,
                 horizon, minutes, color_id):
    """Book the earliest free `minutes` slot from today up to `horizon`
    (respecting busy + inferred sleep + exam wall), record it in time_blocks
    under `kind`, and return the event id. Deduped per (application_id, kind)."""
    existing = conn.execute(
        "SELECT gcal_event_id FROM time_blocks "
        "WHERE application_id = ? AND kind = ?",
        (application_id, kind),
    ).fetchone()
    if existing and existing["gcal_event_id"]:
        return existing["gcal_event_id"]

    span = (config.ACCOUNTABILITY_WINDOW_END - config.ACCOUNTABILITY_WINDOW_START) * 60
    minutes = max(config.SLOT_GRANULARITY_MIN, min(int(minutes), span))
    now = datetime.now(TZ)
    cal_ids = gc.list_calendar_ids(cal)  # enumerate once, reuse each day
    day = now.date()
    while day <= horizon.date():
        day_start = datetime(day.year, day.month, day.day, tzinfo=TZ)
        busy = _unavailable(
            gc.busy_between(cal, day_start.isoformat(),
                            (day_start + timedelta(days=1)).isoformat(),
                            calendar_ids=cal_ids),
            day_start)
        not_before = now + timedelta(minutes=90) if day == now.date() else day_start
        wall = _study_wall(cal, tasks_svc, day_start, cal_ids)
        if wall and wall > not_before:
            not_before = wall
        hard_end = horizon if day == horizon.date() else None
        slot = _first_gap(day_start, busy, minutes, not_before, hard_end)
        if slot:
            eid = gc.create_event(
                cal, label, slot.isoformat(),
                (slot + timedelta(minutes=minutes)).isoformat(),
                description=notes, color_id=color_id,
            )
            conn.execute(
                "INSERT OR IGNORE INTO time_blocks(application_id, kind, "
                "start_at, minutes, gcal_event_id) VALUES(?, ?, ?, ?, ?)",
                (application_id, kind, slot.isoformat(), minutes, eid),
            )
            conn.commit()
            return eid
        day += timedelta(days=1)
    return None


def schedule_oa_block(cal, tasks_svc, conn, application_id: int, due_at: str,
                      minutes: int = 0) -> str | None:
    """Book a timed block to actually DO an OA before it's due (earliest free
    slot up to the deadline, or a 3-day horizon if none)."""
    minutes = int(minutes) if minutes else config.OA_BLOCK_DEFAULT_MINUTES
    now = datetime.now(TZ)
    due = None
    if due_at:
        try:
            due = datetime.fromisoformat(due_at).astimezone(TZ)
        except (ValueError, TypeError):
            due = None
    horizon = due if (due and due > now) else now + timedelta(days=3)
    app = conn.execute(
        "SELECT company, role FROM applications WHERE id = ?", (application_id,)
    ).fetchone()
    label = f"Do OA: {app['company']}" if app else "Do OA"
    notes = f"apptrack: do the assessment before it's due ({app['role'] if app else ''})"
    return _book_before(cal, tasks_svc, conn, application_id, "oa", label,
                        notes, horizon, minutes, config.OA_BLOCK_COLOR_ID)


def sync_oa_blocks(cal, tasks_svc, conn):
    """Serialize OA work blocks: schedule INCOMPLETE OAs one per day in due-date
    order starting tomorrow, each before its deadline. Completed/past OAs get no
    block. Idempotent: only rewrites the calendar when the plan actually changes
    (so repeated scans don't churn events)."""
    rows = conn.execute(
        "SELECT a.id, a.company, a.role, a.oa_minutes, a.oa_practice, "
        "a.oa_platform, a.oa_no_deadline_alerted, "
        "(SELECT MIN(due_at) FROM deadlines d WHERE d.application_id = a.id "
        " AND d.kind = 'oa') AS due, "
        "(SELECT MIN(received_at) FROM email_events e WHERE e.application_id = a.id "
        " AND e.kind = 'oa') AS oa_received "
        "FROM applications a "
        "WHERE a.status = 'oa' AND a.oa_completed_at IS NULL"
    ).fetchall()

    existing = {r["application_id"]: dict(r) for r in conn.execute(
        "SELECT application_id, start_at, minutes, gcal_event_id, "
        "practice_event_id FROM time_blocks WHERE kind = 'oa'")}

    now = datetime.now(TZ)
    today = now.date()
    tomorrow = today + timedelta(days=1)
    cal_ids = gc.list_calendar_ids(cal)

    def _day(iso):
        return datetime.fromisoformat(iso).astimezone(TZ).date()

    # resolve each OA's block length + buffered deadline (finish this long before
    # the real due); anything already past its deadline can't be scheduled
    jobs, missed = [], []
    for r in rows:
        minutes = int(r["oa_minutes"] or 0) or config.OA_BLOCK_DEFAULT_MINUTES
        if r["oa_practice"]:   # unfamiliar platform -> tack on practice time
            minutes += config.OA_PRACTICE_MINUTES
        span = (config.ACCOUNTABILITY_WINDOW_END
                - config.ACCOUNTABILITY_WINDOW_START) * 60
        minutes = max(config.SLOT_GRANULARITY_MIN, min(minutes, span))
        due = None
        if r["due"]:
            try:
                due = datetime.fromisoformat(r["due"]).astimezone(TZ)
            except (ValueError, TypeError):
                due = None
        if due:
            deadline = due - timedelta(minutes=config.OA_DUE_BUFFER_MIN)
            hard = True       # a real, stated deadline — never schedule past it
            if deadline <= now:
                missed.append((r["company"], "deadline already passed"))
                continue
        else:
            # deadline unknown -> assume urgency from the invite date so the OA
            # is still scheduled soon (OAs usually expire within a week)
            try:
                recv = datetime.fromisoformat(r["oa_received"]).astimezone(TZ)
            except (ValueError, TypeError):
                recv = now
            deadline = recv + timedelta(days=config.OA_ASSUMED_DEADLINE_DAYS)
            hard = False      # soft target — schedule soon but don't drop it
            # ping the user once: we couldn't detect this OA's real deadline
            if not r["oa_no_deadline_alerted"] and tasks_svc is not None:
                role = f": {r['role']}" if r["role"] else ""
                gc.create_task(
                    tasks_svc,
                    f"⚠️ Set OA deadline — {r['company']}{role}",
                    today.isoformat(),
                    notes="apptrack couldn't detect this OA's deadline from the "
                          "email. Check it and set the due date so it schedules "
                          "correctly (it's assumed urgent for now).")
                conn.execute("UPDATE applications SET oa_no_deadline_alerted = 1 "
                             "WHERE id = ?", (r["id"],))
                conn.commit()
        jobs.append((r, minutes, deadline, hard))
    jobs.sort(key=lambda j: j[2])   # soonest (real or assumed) deadline first

    plan = {}          # app_id -> (slot datetime, minutes)
    used = set()       # days already claimed this pass

    # PASS 1: keep an existing block that's still valid (today-or-future and
    # fits before the deadline) so a scheduled OA doesn't slide forward daily
    pending = []
    for r, minutes, deadline, hard in jobs:
        b = existing.get(r["id"])
        if b and b["start_at"]:
            bstart = datetime.fromisoformat(b["start_at"]).astimezone(TZ)
            bend = bstart + timedelta(minutes=b["minutes"])
            if (bstart.date() >= today and bstart.date() not in used
                    and (not hard or bend <= deadline)):
                plan[r["id"]] = (bstart, b["minutes"])
                used.add(bstart.date())
                continue
        pending.append((r, minutes, deadline, hard))

    # PASS 2: schedule the rest into the earliest free day before the deadline,
    # starting TODAY (if a slot remains after now) so the soonest OA can land
    # today rather than always being pushed to tomorrow; soonest-due first
    for r, minutes, deadline, hard in pending:
        horizon = (deadline.date() if hard
                   else max(deadline.date(), today + timedelta(days=2)))
        day, placed = today, False
        while day <= horizon:
            if day not in used:
                ds = datetime(day.year, day.month, day.day, tzinfo=TZ)
                busy = _unavailable(gc.busy_between(
                    cal, ds.isoformat(), (ds + timedelta(days=1)).isoformat(),
                    calendar_ids=cal_ids), ds)
                wall = _study_wall(cal, tasks_svc, ds, cal_ids)
                not_before = now + timedelta(minutes=60) if day == today else ds
                if wall and wall > not_before:
                    not_before = wall
                hard_end = deadline if (hard and deadline.date() == day) else None
                slot = _first_gap(ds, busy, minutes, not_before, hard_end)
                if slot:
                    plan[r["id"]] = (slot, minutes)
                    used.add(day)
                    placed = True
                    break
            day += timedelta(days=1)
        if not placed:
            missed.append((r["company"], "no free slot before the deadline"
                           if hard else "no free slot in the next few days"))

    for company, why in missed:  # surfaced in scan.log; deadline Task still stands
        print(f"  [!] OA '{company}' not scheduled: {why} "
              f"(its deadline reminder task remains)")

    # compare plan to existing; no-op when already correct (avoids churn).
    # a today-or-future existing block counts as current (not stale)
    want = {aid: (slot.date(), m) for aid, (slot, m) in plan.items()}
    eligible = {r["id"] for r in rows}
    have = {aid: (_day(b["start_at"]), b["minutes"]) for aid, b in existing.items()
            if aid in eligible and _day(b["start_at"]) >= today}
    stale = [aid for aid, b in existing.items()
             if aid not in eligible or _day(b["start_at"]) < today]
    if have == want and not stale:
        return

    for aid, b in existing.items():       # clear and rebuild (both events)
        for ev in (b["gcal_event_id"], b["practice_event_id"]):
            if ev:
                try:
                    gc.delete_event(cal, ev)
                except Exception:
                    pass
    conn.execute("DELETE FROM time_blocks WHERE kind = 'oa'")
    conn.commit()
    for aid, (slot, minutes) in plan.items():
        app = conn.execute(
            "SELECT company, role, oa_practice, oa_platform "
            "FROM applications WHERE id = ?", (aid,)).fetchone()
        company = app["company"] if app else ""
        practice = bool(app and app["oa_practice"])
        plat = (app["oa_platform"] if app else "") or "the platform"
        # a new platform gets a separate warm-up block right before the OA
        practice_id, oa_start = None, slot
        if practice:
            p_end = slot + timedelta(minutes=config.OA_PRACTICE_MINUTES)
            practice_id = gc.create_event(
                cal, f"OA practice: {company}" if company else "OA practice",
                slot.isoformat(), p_end.isoformat(),
                description=f"apptrack: warm up on {plat} before the OA "
                            f"(first time on this platform).",
                color_id=config.OA_BLOCK_COLOR_ID)
            oa_start = p_end
        oa_id = gc.create_event(
            cal, f"Do OA: {company}" if company else "Do OA",
            oa_start.isoformat(), (slot + timedelta(minutes=minutes)).isoformat(),
            description=f"apptrack: do the assessment before it's due "
                        f"({app['role'] if app else ''})",
            color_id=config.OA_BLOCK_COLOR_ID, reminders=config.OA_REMINDERS,
        )
        conn.execute(
            "INSERT INTO time_blocks(application_id, kind, start_at, minutes, "
            "gcal_event_id, practice_event_id) VALUES(?, 'oa', ?, ?, ?, ?)",
            (aid, slot.isoformat(), minutes, oa_id, practice_id))
        conn.commit()


def schedule_interview(cal, tasks_svc, conn, application_id: int, when_iso: str,
                       minutes: int = 0) -> str | None:
    """Put a real interview EVENT on the calendar at the stated time, plus a
    prep block beforehand. Deduped per application (kind='interview')."""
    existing = conn.execute(
        "SELECT gcal_event_id FROM time_blocks "
        "WHERE application_id = ? AND kind = 'interview'",
        (application_id,),
    ).fetchone()
    if existing and existing["gcal_event_id"]:
        return existing["gcal_event_id"]
    try:
        when = datetime.fromisoformat(when_iso).astimezone(TZ)
    except (ValueError, TypeError):
        return None
    if when <= datetime.now(TZ):
        return None
    minutes = int(minutes) if minutes else config.INTERVIEW_MINUTES
    app = conn.execute(
        "SELECT company, role FROM applications WHERE id = ?", (application_id,)
    ).fetchone()
    label = f"Interview: {app['company']}" if app else "Interview"
    # a ready-to-study prep brief, dropped into both the interview + prep events
    brief = prep.interview_brief(app["company"] if app else "",
                                 app["role"] if app else "")
    desc = f"{brief}\n\n— apptrack" if brief else \
        f"apptrack interview ({app['role'] if app else ''})"
    eid = gc.create_event(
        cal, label, when.isoformat(),
        (when + timedelta(minutes=minutes)).isoformat(),
        description=desc, color_id=config.INTERVIEW_COLOR_ID,
        reminders=config.INTERVIEW_REMINDERS,
    )
    conn.execute(
        "INSERT OR IGNORE INTO time_blocks(application_id, kind, start_at, "
        "minutes, gcal_event_id) VALUES(?, 'interview', ?, ?, ?)",
        (application_id, when.isoformat(), minutes, eid),
    )
    conn.commit()
    # prep block sometime before it, carrying the same brief
    prep_label = f"Prep: {app['company']} interview" if app else "Interview prep"
    _book_before(cal, tasks_svc, conn, application_id, "prep", prep_label,
                 brief or "apptrack: prep for the interview", when,
                 config.INTERVIEW_PREP_MINUTES, config.INTERVIEW_PREP_COLOR_ID)
    return eid
