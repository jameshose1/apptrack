"""Google Calendar auth + write (OAuth). Gmail is handled separately over IMAP.

First run opens a browser for consent and caches the token in
secrets/google_token.json. Subsequent runs are silent.
"""
from datetime import datetime

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

import config


def _creds():
    creds = None
    if config.GOOGLE_TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(
            str(config.GOOGLE_TOKEN_FILE), config.GOOGLE_SCOPES
        )
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                str(config.GOOGLE_CLIENT_FILE), config.GOOGLE_SCOPES
            )
            creds = flow.run_local_server(port=0)
        config.GOOGLE_TOKEN_FILE.write_text(creds.to_json())
    return creds


def calendar():
    return build("calendar", "v3", credentials=_creds(), cache_discovery=False)


def tasks():
    return build("tasks", "v1", credentials=_creds(), cache_discovery=False)


def create_task(svc, title, due_date, notes="", tasklist_id=None):
    """Create a checkable Google Task due on `due_date` (YYYY-MM-DD). Tasks
    only honor the date part of `due`; it renders as an all-day, checkable item
    in Google Calendar's Tasks layer. Returns the task id."""
    tasklist_id = tasklist_id or config.TASKLIST_ID
    body = {"title": title, "notes": notes, "due": f"{due_date}T00:00:00.000Z"}
    created = svc.tasks().insert(tasklist=tasklist_id, body=body).execute()
    return created["id"]


def delete_task(svc, task_id, tasklist_id=None):
    tasklist_id = tasklist_id or config.TASKLIST_ID
    svc.tasks().delete(tasklist=tasklist_id, task=task_id).execute()


def create_event(svc, summary, start, end, description="",
                 calendar_id=None, all_day=False, color_id=None, reminders=None):
    """Create an event. Timed by default; all_day=True makes an all-day banner
    (start/end are then plain YYYY-MM-DD dates; Google treats end.date as
    exclusive, so a single-day event needs end = start + 1 day). color_id is a
    Google event colorId string (1..11). reminders is a list of minutes-before
    to fire popup notifications (explicit, so it pings regardless of the
    calendar's default-reminder setting); None = use the calendar default."""
    calendar_id = calendar_id or config.CALENDAR_ID
    if all_day:
        when = {"start": {"date": start}, "end": {"date": end}}
    else:
        when = {
            "start": {"dateTime": start, "timeZone": config.TIMEZONE},
            "end": {"dateTime": end, "timeZone": config.TIMEZONE},
        }
    event = {"summary": summary, "description": description, **when}
    if color_id:
        event["colorId"] = str(color_id)
    if reminders is not None:
        event["reminders"] = {
            "useDefault": False,
            "overrides": [{"method": "popup", "minutes": m} for m in reminders],
        }
    created = svc.events().insert(calendarId=calendar_id, body=event).execute()
    return created["id"]


def delete_event(svc, event_id, calendar_id=None):
    calendar_id = calendar_id or config.CALENDAR_ID
    svc.events().delete(calendarId=calendar_id, eventId=event_id).execute()


def update_event(svc, event_id, summary=None, description=None, calendar_id=None):
    calendar_id = calendar_id or config.CALENDAR_ID
    body = {}
    if summary is not None:
        body["summary"] = summary
    if description is not None:
        body["description"] = description
    svc.events().patch(calendarId=calendar_id, eventId=event_id,
                       body=body).execute()


def list_calendar_ids(svc):
    """Every calendar the user can at least see free/busy for (their whole
    aggregated view: primary + school + subscribed + shared)."""
    ids, page = [], None
    while True:
        resp = svc.calendarList().list(
            pageToken=page, showHidden=False, minAccessRole="freeBusyReader"
        ).execute()
        ids += [c["id"] for c in resp.get("items", [])]
        page = resp.get("nextPageToken")
        if not page:
            return ids


def busy_between(svc, start_iso, end_iso, calendar_ids=None):
    """Merged (start, end) busy intervals across ALL the user's calendars in the
    range, via the FreeBusy API. Times are tz-aware (UTC). All-day events don't
    count as busy, matching how the calendar UI shows availability."""
    ids = calendar_ids if calendar_ids is not None else list_calendar_ids(svc)
    resp = svc.freebusy().query(body={
        "timeMin": start_iso, "timeMax": end_iso,
        "items": [{"id": i} for i in ids],
    }).execute()
    out = []
    for cal in resp.get("calendars", {}).values():
        for b in cal.get("busy", []):
            out.append((
                datetime.fromisoformat(b["start"].replace("Z", "+00:00")),
                datetime.fromisoformat(b["end"].replace("Z", "+00:00")),
            ))
    return out


def list_events_between(svc, start_iso, end_iso, calendar_id=None):
    calendar_id = calendar_id or config.CALENDAR_ID
    resp = (
        svc.events()
        .list(
            calendarId=calendar_id,
            timeMin=start_iso,
            timeMax=end_iso,
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
    )
    return resp.get("items", [])
