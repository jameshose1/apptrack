# apptrack web UI (not built yet)

Next.js board + review queue, reads/writes `../data/apptrack.db` (the same
SQLite file the Python scanner writes).

Planned:
- Board: columns Wishlist / Applied / OA / Interview / Offer / Rejected, cards
  per application, drag between columns (manual override of the scanner).
- Review queue: pending items with the proposed label; buttons to confirm as
  confirmation/oa/interview/offer/rejection or dismiss. Resolving shells out to
  `../scanner/resolve.py <id> <kind>` so the self-learning rule logic stays in
  one place.
- Application detail: all fields (company, role, url, source, location, salary,
  contact, notes, dates) plus the linked email timeline from `email_events`.

Suggested stack: Next.js App Router + better-sqlite3 for direct DB access
(single local user, no API layer needed). Scaffold with:

    npx create-next-app@latest . --ts --app --no-tailwind

Nothing here yet on purpose: the scanner backend is the hard part and it's
built + verified. Build this once you've done the Google OAuth setup and seen a
real scan populate the board.
