# apptrack

A self-updating job and internship application tracker. You never manually mark
that you applied, got an OA, or got rejected. A background scanner reads your
Gmail, classifies each recruiting email with Claude, and keeps a board in sync.
It also sources fresh postings, blocks time on your calendar to actually do
assessments, and surfaces who you know at the companies you apply to.

Built for my own SWE internship search, so every feature earns its place.

## Architecture

Two processes, one SQLite file:

- `scanner/` Python, runs on a schedule via launchd. Reads Gmail (IMAP),
  classifies with the Claude API, writes SQLite, syncs Google Calendar + Tasks.
- `web/` Next.js board (tabbed: Pipeline / Wishlist / Review) plus a funnel and
  daily stats. Reads and writes the same SQLite file through better-sqlite3.
- `data/apptrack.db` shared SQLite database (git-ignored).
- `secrets/` Google OAuth client and token, Anthropic key (git-ignored).

Python fits the scraping and scheduling work; SQLite is language-agnostic so the
Next.js UI reads the exact same file with no API layer in between.

## Auto-updating from your inbox

1. The scanner pulls Gmail newer than the last run, server-side filtered via
   Gmail's `X-GM-RAW` search so it never downloads the whole inbox.
2. Each candidate is classified by Claude with a forced tool-call:
   `confirmation | rejection | oa | interview | offer | other`, plus the
   employer (not the ATS vendor), role, a confidence score, and any deadline /
   OA length / assessment platform.
3. Status only ever advances: a late "application received" email can't knock
   something back from OA. Offers and rejections are terminal.
4. High-confidence emails apply automatically; genuinely ambiguous ones land in
   a review queue.

### Self-learning review queue

Resolving a queued item records `(fingerprint, label)`, where the fingerprint is
the email's template skeleton with company/name/dates stripped out. After three
identical resolutions the rule is promoted and future matches skip the queue.
Correcting an auto-applied label demotes the rule, so nothing stays mislabeled
behind your back.

## Job sourcing to the wishlist

A second scanner pulls fresh Summer-internship postings into the Wishlist from:

- the SimplifyJobs / Pitt CSC community list (structured JSON, no scraping), and
- target companies' own ATS boards (Greenhouse / Lever / Ashby public APIs),
  auto-detecting which board each company uses.

Everything is filtered to active SWE internships in the US, deduped against what
you already track, and screened to drop defense/government contractors,
PhD-only roles, and non-US positions. When a confirmation email later arrives,
the matching wishlist card is promoted to Applied automatically.

## Calendar intelligence

OA and interview prep is time-blocked onto Google Calendar, and the scheduler is
the interesting part:

- **Availability-aware.** Free/busy is pulled across all of your calendars (via
  the FreeBusy API), not just the primary one.
- **Sleep-aware.** Sleep is not a calendar event, so it's inferred: an overnight
  (activity in the small hours) protects a sleep window afterward, bounded by
  your next real commitment.
- **Exam-aware.** If a quiz or exam is due that day (read from Google Tasks and
  matched to that course's class time), nothing is scheduled before it, because
  you'll be studying.
- **Deadline-guaranteed.** An OA block is never placed at or past its due time
  (with a safety buffer); if a deadline can't be detected it's treated as
  urgent, and anything that genuinely can't fit pings you instead of failing
  silently.
- **Serialized.** One OA per day, soonest-due first, skipping completed ones; an
  unfamiliar assessment platform gets a short practice block the first time you
  see it.

Reminders ride on Google Calendar and Tasks so they fire from Google's servers
whether or not the machine is on.

This whole half is **optional**. Set `APPTRACK_CALENDAR=0` to run inbox → board
only: the scanner, classification, and review queue work exactly the same, but
nothing is written to Google and no OAuth setup is needed. Leave it unset (or
`1`) for the full calendar integration.

## Referrals

Referrals convert far better than cold applications, so apptrack surfaces them:
import your own LinkedIn connections export (not scraping) and each company card
shows who you know there, flags fellow alumni, deep-links into LinkedIn's alumni
explorer for that company, and generates a ready-to-send connection note filled
in with the role, company, and the person's title.

## Daily digest

Once a day it writes an all-day calendar entry whose title is your running
counts (sent today / total) and whose body is a bullet summary: due soon, OAs to
do, upcoming interviews, and recent rejections.

## Stack

Python 3, Anthropic Claude API (forced tool-calls, prompt caching), SQLite,
Next.js 15 / React / TypeScript, better-sqlite3, Google Calendar + Tasks APIs,
Gmail over IMAP, launchd.

## Auth (split on purpose)

- **Gmail read = IMAP + app password.** `gmail.readonly` is a restricted OAuth
  scope that can't ship to production without a security assessment. IMAP with a
  Google app password sidesteps OAuth, consent, and token expiry entirely.
- **Calendar + Tasks = OAuth**, scopes `calendar.events`, `calendar.readonly`,
  and `tasks`, all merely sensitive, so the app publishes to production fine.

## Setup

1. Gmail app password (`myaccount.google.com/apppasswords`) into `scanner/.env`
   as `APPTRACK_APP_PASSWORD`, with `APPTRACK_EMAIL`. See `scanner/.env.example`.
2. Anthropic key in `scanner/.env` as `ANTHROPIC_API_KEY`.
3. *(Optional, for the calendar half.)* Google Cloud project: enable the
   Calendar and Tasks APIs, add the `calendar.events`, `calendar.readonly`, and
   `tasks` scopes, create a Desktop OAuth client, download it to
   `secrets/google_client.json`. To skip this entirely, set `APPTRACK_CALENDAR=0`
   and run inbox → board only.
4. `cd scanner && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt`
5. `.venv/bin/python scan.py --dry-run` to watch classification without writing.
6. `cd web && npm install && npm run dev` for the board on port 3737.
7. Install the launchd agents in `scanner/launchd/` to run it on a schedule.

## Note

This is a personal tool. The database holds real application data, and `data/`,
`secrets/`, and `.env` are git-ignored, so nothing personal lives in this repo.
