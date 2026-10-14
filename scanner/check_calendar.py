"""One-off: run the OAuth consent flow and prove a calendar write round-trip.
Creates a test event tomorrow, reads it back, deletes it."""
from datetime import datetime, timedelta

import google_client as gc


def main():
    cal = gc.calendar()
    start = (datetime.now() + timedelta(days=1)).replace(
        hour=15, minute=0, second=0, microsecond=0
    )
    end = start + timedelta(hours=1)
    eid = gc.create_event(
        cal, "apptrack test (safe to ignore)",
        start.isoformat(), end.isoformat(), "created by apptrack setup check",
    )
    print("created event:", eid)
    items = gc.list_events_between(
        cal, start.isoformat() + "Z", (end + timedelta(hours=1)).isoformat() + "Z"
    )
    print("read back:", [i.get("summary") for i in items])
    cal.events().delete(calendarId="primary", eventId=eid).execute()
    print("deleted test event -> calendar write works")


if __name__ == "__main__":
    main()
