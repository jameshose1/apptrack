# apptrack Morning Report

**Date:** Tuesday, October 28, 2026
**Project:** apptrack, your self-updating job and internship tracker
**Status:** Fully live and healthy

---

## The one-minute summary

apptrack is running clean. The email scanner ran last night, the board is current, and the newest feature (tailored resume plus cover letter generation) is finished and verified. You have **55 live applications** out of 147 total tracked, almost all CS internships. The single biggest untapped lever right now is the networking pipeline: 89 connections are imported but zero outreach has started, and your 324-connection re-import is still pending. That is the highest-value thing to unblock this week.

---

## The numbers

**Pipeline (non-wishlist, 69 tracked):**

| Stage | Count |
|---|---|
| Applied | 55 |
| Online assessment | 3 |
| Interview | 1 |
| Offer | 0 |
| Rejected | 8 |
| Missed OA | 2 |

- Response rate (moved past "applied"): about **20%** (14 of 69)
- Positive rate (reached OA or further): about **6%** (4 of 69)
- Wishlist queued by the job scanner: **78**, all CS internships
- Future deadlines synced to calendar: **5**

**Mix:** 65 of 69 tracked are CS internships. Only 4 are non-CS or full-time (1 non-CS internship, 3 jobs). The field/track tagging is working as intended, your CS internship search is not getting polluted by other mail.

---

## System health

| Component | State |
|---|---|
| Email scanner (com.apptrack.scan) | Loaded, runs 9am / 1pm / 6pm / 10pm. Last run Oct 27 22:01, completed (19 read, 11 classified). |
| Job scanner (com.apptrack.jobscan) | Loaded, runs 8am daily. Pulls Simplify plus your ATS targets. |
| Web board (com.apptrack.web) | Running, port 3737, persistent. |
| Review queue | 3 items pending your confirmation. |
| Learned rules | 0 promoted yet (needs 3 same-template confirms to form one). |

**Minor issues worth a glance, none breaking:**

1. The email scan error log shows a broken-pipe IMAP socket error. The scan still completed, so this is a transient network hiccup, not a failure. Worth a reconnect/retry guard eventually.
2. The job scan error log shows a DNS error (nodename not known), which happens when the Mac is asleep or offline at 8am. Transient, but noisy.
3. Two OAs (Roblox and IBM) have deadlines that already passed and were never scheduled. They should be marked "missed" so the funnel stays honest.

---

## What shipped recently

- **Tailored resume plus cover letter generator (finished).** Hit "tailor" on any card: it auto-pulls the job description from the posting (Greenhouse API plus plain fetch), regenerates your resume in your exact format (centered header, uppercase section rules, Projects / Experience / Leadership order, bold right-aligned dates, filled-dot bullets), re-angles only the bullet contents to the role, and generates a matching cover letter. Both render to one-page PDFs linked on the card. Zero fabrication, hard bullet caps keep it one page.
- **Networking pipeline (built, awaiting data).** Contacts table, outreach status tracking, AI-drafted messages, peer and already-messaging filters. 89 contacts imported. Waiting on your fresh 324-connection export to populate it fully.
- **Funnel tab (Sankey diagram).** Dark-themed d3-sankey flow of applications through stages, filterable by CS/internship.

---

## Short-term roadmap (this week)

Ordered by leverage.

1. **Re-import your 324 LinkedIn connections.** This is the top priority. The networking machinery is built and idle. Referrals convert 5 to 10 times better than cold applications, and right now you have 89 contacts with no outreach started. Once the export lands I unzip it and run the importer (additive, keeps any statuses).
2. **Clear the 3 review-queue items.** Keeps the board accurate and starts training learned rules so the scanner asks you less over time.
3. **Clean up the 2 passed OAs** (Roblox, IBM): mark them missed so the funnel and response-rate numbers are truthful.
4. **Upgrade the writing model.** Right now resume, cover letter, and "why us" generation all run on Haiku (same as the classifier). Bumping just the writing path to Sonnet would noticeably improve quality on the highest-value outputs, at trivial cost since you generate these rarely. One config line.
5. **Make tailoring a habit.** Only 3 tailored resumes exist so far. Generate one for every dream-company application and every serious wishlist target.

---

## Long-term roadmap (weeks to months)

Grouped by theme. The first three are already designed as feature ideas and extend patterns you already have.

**Close the application loop:**
- **Follow-up and thank-you email drafter.** Post-OA and post-interview notes, grounded in your resume and the role. High ROI, low effort, reuses the tailor and why-us scaffolding.
- **Application-question answerer.** Paste any supplemental prompt ("Why do you want to work here", "Describe a project") and get a tailored draft in your voice, grounded in your real resume.

**Apply smarter, not just more:**
- **Wishlist fit-ranking.** Score each of the 78 wishlist postings against your profile so you apply to the best-fit roles first instead of top-of-list.
- **Keyword and skills coverage.** Aggregate the recurring skills across your target JDs and surface the ones you are missing, so prep is data-driven.

**Harden and observe:**
- **Scanner resilience.** IMAP reconnect on broken pipe, job-scan retry when offline. Removes the noisy transient errors.
- **Response-rate trends.** You have the Funnel tab, add week-over-week trend and breakdown by source so you can see what actually converts.
- **Activate the weekly digest.** A `digest.py` already exists in the scanner. Verify it and schedule a Monday morning summary email so you get this report automatically.

**Stretch / later:**
- Interview-prep assistant (per company: likely questions plus talking points drawn from your projects).
- Offer comparison, once offers start arriving.

---

## Bottom line

The core system is solid and the tailoring feature is a strong new asset. This week is about **execution, not building**: get the 324 connections in and start referral outreach, keep the board clean, and bump the writing model. The build backlog (follow-up drafter, fit-ranking, keyword coverage) is well-scoped and ready whenever you want to extend.
