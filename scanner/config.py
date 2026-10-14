"""Configuration and paths."""
import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent / ".env")
except ImportError:
    pass

ROOT = Path(__file__).resolve().parent.parent
SECRETS = ROOT / "secrets"

GOOGLE_CLIENT_FILE = SECRETS / "google_client.json"
GOOGLE_TOKEN_FILE = SECRETS / "google_token.json"

# Calendar (accountability hour) + Tasks (OA/interview deadlines, checkable).
# Gmail is read over IMAP (app password) to dodge the restricted-scope
# verification wall; both of these scopes are merely "sensitive" so the OAuth
# app publishes to production without a security assessment.
GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/calendar.events",   # create our events
    "https://www.googleapis.com/auth/calendar.readonly",  # freebusy across ALL cals
    "https://www.googleapis.com/auth/tasks",
]

# Google Tasks list to file deadlines in. "@default" is the built-in "My Tasks".
TASKLIST_ID = os.environ.get("APPTRACK_TASKLIST_ID", "@default")

# Gmail over IMAP with an app password (not OAuth, not the account password)
IMAP_HOST = os.environ.get("APPTRACK_IMAP_HOST", "imap.gmail.com")
IMAP_USER = os.environ.get("APPTRACK_EMAIL", "")
IMAP_APP_PASSWORD = os.environ.get("APPTRACK_APP_PASSWORD", "").replace(" ", "")

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
CLASSIFIER_MODEL = os.environ.get("APPTRACK_MODEL", "claude-haiku-4-5-20251001")
# model for interview-prep briefs (infrequent, so a stronger default is fine)
PREP_MODEL = os.environ.get("APPTRACK_PREP_MODEL", CLASSIFIER_MODEL)

# your name, used to strip personalized tokens out of fingerprints
APPLICANT_NAME = os.environ.get("APPTRACK_APPLICANT_NAME", "James Hose")

# email domains that mark a LinkedIn connection as a fellow UMD alum/student
ALUMNI_EMAIL_DOMAINS = [d.strip().lower() for d in os.environ.get(
    "APPTRACK_ALUMNI_DOMAINS", "umd.edu,terpmail.umd.edu").split(",") if d.strip()]

# how far back to look on the very first scan
INITIAL_LOOKBACK_DAYS = int(os.environ.get("APPTRACK_LOOKBACK_DAYS", "30"))

# confidence at/above which Claude's label is applied without review
AUTO_APPLY_CONFIDENCE = float(os.environ.get("APPTRACK_AUTO_CONF", "0.85"))

# daily accountability hour + OA work blocks share this local free-slot window
ACCOUNTABILITY_WINDOW_START = int(os.environ.get("APPTRACK_HOUR_START", "9"))   # 9am
ACCOUNTABILITY_WINDOW_END = int(os.environ.get("APPTRACK_HOUR_END", "23"))      # 11pm
ACCOUNTABILITY_SKIP_WEEKENDS = os.environ.get("APPTRACK_SKIP_WEEKENDS", "0") == "1"
ACCOUNTABILITY_MINUTES = int(os.environ.get("APPTRACK_HOUR_MINUTES", "60"))
# cascade: if the full hour doesn't fit that day, fall back to this shorter
# block; if even that doesn't fit, the day is voided (no block placed)
ACCOUNTABILITY_MIN_MINUTES = int(os.environ.get("APPTRACK_HOUR_MIN_MINUTES", "30"))
# scans run 9/13/18/22; the first run at/after this hour lays out TOMORROW's
# accountability block (the "night before"), earlier runs don't place one
ACCOUNTABILITY_NIGHT_BEFORE_HOUR = int(os.environ.get("APPTRACK_NIGHT_HOUR", "18"))

# OA work block: a timed event to actually sit and do the assessment before it's
# due. Length comes from the email when stated (oa_minutes), else this default.
OA_BLOCK_DEFAULT_MINUTES = int(os.environ.get("APPTRACK_OA_MINUTES", "90"))
# extra minutes added to an OA block the FIRST time its platform is seen
OA_PRACTICE_MINUTES = int(os.environ.get("APPTRACK_OA_PRACTICE_MIN", "30"))
# finish an OA block at least this long before its hard deadline (safety margin)
OA_DUE_BUFFER_MIN = int(os.environ.get("APPTRACK_OA_DUE_BUFFER", "60"))
# when an OA's deadline can't be detected, assume it's this many days from the
# invite so it's treated as urgent and scheduled ASAP (1 = the next day)
OA_ASSUMED_DEADLINE_DAYS = int(os.environ.get("APPTRACK_OA_ASSUMED_DAYS", "1"))

# explicit popup reminders (minutes before) so blocks notify the phone even if
# the Google Calendar default reminder is turned off. 1440 = the day before.
OA_REMINDERS = [1440, 60]
INTERVIEW_REMINDERS = [1440, 60]
ACCOUNTABILITY_REMINDERS = [10]

# daily digest: one all-day calendar entry per day (title = running counts,
# description = the bullet summary). Banana(5) keeps it distinct.
DIGEST_ENABLED = os.environ.get("APPTRACK_DIGEST", "1") == "1"
DIGEST_COLOR_ID = os.environ.get("APPTRACK_DIGEST_COLOR", "5")   # Banana

# free-slot search granularity (minutes)
SLOT_GRANULARITY_MIN = int(os.environ.get("APPTRACK_SLOT_GRAN", "30"))

# availability nuance: sleep isn't a calendar event, so infer it. If there's
# busy time in the small hours (an overnight shift), treat the stretch after it
# as sleep — lasting until the next real commitment that day, or MAX_SLEEP_HOURS
# if the next thing is far off / absent. Keeps blocks off hours you're asleep.
OVERNIGHT_EARLY_HOUR = int(os.environ.get("APPTRACK_OVERNIGHT_HOUR", "6"))
MAX_SLEEP_HOURS = int(os.environ.get("APPTRACK_MAX_SLEEP", "8"))
# merge adjacent overnight commitments (work 2-6am + gym 6-7am) into one run
SLEEP_MERGE_GAP_MIN = int(os.environ.get("APPTRACK_SLEEP_MERGE_GAP", "60"))
# breathing room padded around every commitment (and after waking). Applied on
# BOTH sides, so it costs 2x per gap — keep modest or dense days find no slot.
EVENT_BUFFER_MIN = int(os.environ.get("APPTRACK_BUFFER", "15"))

# on a day with a quiz/test/exam, assume the day is spent studying for it — no
# apply/OA block gets placed before that exam ends (matched on event title).
EXAM_KEYWORDS = [w.strip().lower() for w in os.environ.get(
    "APPTRACK_EXAM_WORDS", "quiz,quizzes,test,exam,midterm,final,finals"
).split(",") if w.strip()]

# when an interview email states an actual time, put the interview on the
# calendar as a real event + a prep block beforehand
INTERVIEW_MINUTES = int(os.environ.get("APPTRACK_INTERVIEW_MINUTES", "45"))
INTERVIEW_PREP_MINUTES = int(os.environ.get("APPTRACK_PREP_MINUTES", "60"))

# Google event colorIds (1..11). Sage=2, Grape=3 (purple ~ "amethyst"),
# Flamingo=4 (pink), Lavender=1.
ACCOUNTABILITY_COLOR_ID = os.environ.get("APPTRACK_APPLY_COLOR", "2")   # Sage
OA_BLOCK_COLOR_ID = os.environ.get("APPTRACK_OA_COLOR", "3")            # Grape
INTERVIEW_COLOR_ID = os.environ.get("APPTRACK_INTERVIEW_COLOR", "4")    # Flamingo
INTERVIEW_PREP_COLOR_ID = os.environ.get("APPTRACK_PREP_COLOR", "1")    # Lavender

CALENDAR_ID = os.environ.get("APPTRACK_CALENDAR_ID", "primary")
TIMEZONE = os.environ.get("APPTRACK_TIMEZONE", "America/New_York")

# --- job scanner (sources fresh internship postings into the wishlist) ---
# SimplifyJobs / Pitt CSC community list, structured JSON, updated daily.
JOB_SIMPLIFY_URL = os.environ.get(
    "APPTRACK_SIMPLIFY_URL",
    "https://raw.githubusercontent.com/SimplifyJobs/Summer2027-Internships/"
    "dev/.github/scripts/listings.json",
)
JOB_TERM = os.environ.get("APPTRACK_JOB_TERM", "Summer 2027")
JOB_CATEGORY_MATCH = os.environ.get("APPTRACK_JOB_CATEGORY", "software").lower()
JOB_MAX_PER_RUN = int(os.environ.get("APPTRACK_JOB_MAX", "40"))
# first run has no cursor: only pull postings this fresh so it doesn't dump 500
JOB_FIRST_LOOKBACK_DAYS = int(os.environ.get("APPTRACK_JOB_FIRST_LOOKBACK", "3"))
# dream companies: always surfaced + starred even if not brand-new (FAANG+big tech)
DREAM_COMPANIES = [c.strip() for c in os.environ.get(
    "APPTRACK_DREAM",
    "Google,Meta,Apple,Amazon,Netflix,Microsoft,Nvidia,Tesla,Adobe,Salesforce,"
    "Uber,Airbnb,Stripe,LinkedIn,Databricks,OpenAI,Snap,Pinterest,Roblox"
).split(",") if c.strip()]

# skip defense / gov-contractor / FFRDC employers (matched as substrings in the
# company name). Takes precedence over dream. Extend via APPTRACK_DEFENSE_WORDS.
EXCLUDE_DEFENSE = os.environ.get("APPTRACK_EXCLUDE_DEFENSE", "1") == "1"
DEFENSE_KEYWORDS = [w.strip().lower() for w in os.environ.get(
    "APPTRACK_DEFENSE_WORDS",
    "defense,defence,aerospace,raytheon,rtx,lockheed,northrop,grumman,"
    "general dynamics,bae systems,l3harris,leidos,booz allen,saic,caci,mitre,"
    "draper,anduril,peraton,mantech,parsons,sierra nevada,huntington ingalls,"
    "kbr,amentum,gdit,battelle,nightwing,palantir,general atomics,kratos,"
    "mercury systems,aerovironment,shield ai,rebellion defense,national laborator,"
    "lincoln laborator,applied physics laborator,sandia,los alamos,livermore,"
    "jet propulsion,iridium,honeywell,westinghouse,boeing,textron,collins aerospace,"
    "pratt & whitney,national security,missile,naval,warfare,space force,"
    "air force,army,dod,darpa,nsa,cia"
).split(",") if w.strip()]

# only internships / co-ops — drop new-grad / full-time postings by title
EXCLUDE_NEW_GRAD = os.environ.get("APPTRACK_INTERN_ONLY", "1") == "1"

# curated companies pulled DIRECTLY from their own ATS boards (Greenhouse/Lever/
# Ashby) — the ones Simplify barely covers. All their interns are surfaced +
# starred. Board tokens are auto-detected and cached.
TARGET_COMPANIES = [c.strip() for c in os.environ.get(
    "APPTRACK_TARGETS",
    "Anthropic,Perplexity,Anysphere,Mercury,Linear,Supabase,Modal,Baseten,"
    "Replit,Warp,Raycast,Clay,Together AI,Fireworks AI,Sierra,Decagon,Hex,Neon,"
    "Resend,Browserbase,Windsurf,Ramp,Vercel,Retool"
).split(",") if c.strip()]
