"""Read Gmail over IMAP with an app password.

Filtering is pushed to Gmail server-side via the X-GM-RAW search extension so we
only download recruiting mail, not the whole inbox. Yields message dicts:
{id, thread_id, sender, subject, snippet, body, received_at}. `id` is the stable
Message-ID header so dedup survives across scans. Never marks mail as read.
"""
import html as _html
import re
from datetime import date, datetime, timedelta, timezone

from imap_tools import MailBox

import config

_TAG = re.compile(r"<[^>]+>")
# <style>/<script>/<head> CONTENTS are not visible text — strip them whole, or
# their CSS/JS leaks in as body text and buries the real content (e.g. deadlines)
_NONTEXT = re.compile(r"<(style|script|head)\b[^>]*>.*?</\1>", re.I | re.S)

# Gmail search (no embedded double-quotes so it can be wrapped for X-GM-RAW).
# category:primary drops the Promotions/marketing tab where deal spam lives,
# leaving real recruiting mail. Terms stay broad; Claude does the fine sorting.
RECRUITING_TERMS = (
    "category:primary (application OR applied OR interview OR assessment "
    "OR offer OR unfortunately OR candidacy OR recruiter OR hackerrank "
    "OR codesignal OR internship OR position)"
)


def _html_to_text(html: str) -> str:
    if not html:
        return ""
    s = _NONTEXT.sub(" ", html)      # drop style/script/head blocks first
    s = _TAG.sub(" ", s)             # then remaining tags
    s = _html.unescape(s)            # &nbsp; &amp; etc. -> real chars
    return re.sub(r"\s+", " ", s).strip()


def _msg_id(msg) -> str:
    hdr = msg.headers.get("message-id")
    if hdr and hdr[0]:
        return hdr[0].strip()
    return f"uid:{msg.uid}"


def _criteria(since: date) -> str:
    after = since.strftime("%Y/%m/%d")
    return f'X-GM-RAW "after:{after} {RECRUITING_TERMS}"'


def fetch_since(since: date):
    """Yield candidate recruiting messages received on/after `since`."""
    with MailBox(config.IMAP_HOST).login(
        config.IMAP_USER, config.IMAP_APP_PASSWORD, initial_folder="INBOX"
    ) as mb:
        for msg in mb.fetch(_criteria(since), reverse=True, bulk=False,
                            mark_seen=False):
            body = msg.text or _html_to_text(msg.html)
            received = msg.date.isoformat() if msg.date else datetime.now(timezone.utc).isoformat()
            yield {
                "id": _msg_id(msg),
                "thread_id": None,
                "sender": msg.from_ or "",
                "subject": msg.subject or "",
                "snippet": (body or "")[:200],
                "body": body or "",
                "received_at": received,
            }


def since_from_epoch(epoch: str | None) -> date:
    if not epoch:
        return (datetime.now(timezone.utc) - timedelta(days=config.INITIAL_LOOKBACK_DAYS)).date()
    # step back a day so a same-day boundary email is never missed (dedup catches dups)
    return (datetime.fromtimestamp(int(epoch), timezone.utc) - timedelta(days=1)).date()
