import Database from "better-sqlite3";
import path from "path";
import {
  STALE_AFTER_DAYS,
  type Application,
  type Contact,
  type Funnel,
  type QueueItem,
} from "./status";

// scanner and web share one SQLite file
const DB_PATH = path.join(process.cwd(), "..", "data", "apptrack.db");

let _db: Database.Database | null = null;
export function db(): Database.Database {
  if (!_db) {
    _db = new Database(DB_PATH, { fileMustExist: false });
    _db.pragma("journal_mode = WAL");
  }
  return _db;
}

// SQLite datetime('now') is space-separated UTC; normalize so Date.parse is UTC
function parseTime(s: string | null): number {
  if (!s) return NaN;
  const iso = s.includes("T") ? s : s.replace(" ", "T") + "Z";
  return Date.parse(iso);
}

// company_key tokens are already normalized (suffixes/regions stripped); drop
// the few generic words that can survive so matches are on the brand token
const _TOK_STOP = new Set(["web", "services", "global", "international",
  "worldwide", "group", "labs", "the"]);
function _sigTokens(key: string): string[] {
  return (key || "")
    .split(/\s+/)
    .filter((t) => t.length >= 3 && !_TOK_STOP.has(t));
}

// token -> contacts index, so each tracked company can find who the user knows
function contactsByToken(): Map<string, Contact[]> {
  const idx = new Map<string, Contact[]>();
  let rows: any[] = [];
  try {
    rows = db()
      .prepare(
        "SELECT name, company, company_key, position, url, is_alum FROM contacts"
      )
      .all() as any[];
  } catch {
    return idx; // contacts table not created yet (no import run)
  }
  for (const c of rows) {
    for (const t of _sigTokens(c.company_key)) {
      (idx.get(t) ?? idx.set(t, []).get(t)!).push(c);
    }
  }
  return idx;
}

function matchContacts(
  companyKey: string,
  idx: Map<string, Contact[]>
): Contact[] {
  const seen = new Set<string>();
  const out: Contact[] = [];
  for (const t of _sigTokens(companyKey)) {
    for (const c of idx.get(t) ?? []) {
      const k = `${c.name}@${c.company}`;
      if (!seen.has(k)) {
        seen.add(k);
        out.push(c);
      }
    }
  }
  return out;
}

export function getApplications(): Application[] {
  const rows = db()
    .prepare(
      "SELECT a.*, " +
        "(SELECT due_at FROM deadlines d WHERE d.application_id = a.id " +
        " AND d.due_at >= datetime('now') ORDER BY d.due_at LIMIT 1) AS next_due, " +
        "(SELECT kind FROM deadlines d WHERE d.application_id = a.id " +
        " AND d.due_at >= datetime('now') ORDER BY d.due_at LIMIT 1) AS next_kind, " +
        "(SELECT MAX(received_at) FROM email_events e WHERE e.application_id = a.id) " +
        " AS last_email " +
        "FROM applications a ORDER BY updated_at DESC"
    )
    .all() as any[];
  const now = Date.now();
  const cIdx = contactsByToken();
  return rows.map((r) => {
    const times = [r.date_applied, r.last_email, r.updated_at]
      .map(parseTime)
      .filter((n) => !isNaN(n));
    const last = times.length ? Math.max(...times) : now;
    const daysIdle = Math.floor((now - last) / 86_400_000);
    return {
      ...r,
      last_activity: new Date(last).toISOString(),
      days_idle: daysIdle,
      stale: r.status === "applied" && daysIdle >= STALE_AFTER_DAYS,
      contacts: matchContacts(r.company_key, cIdx),
    } as Application;
  });
}

// funnel + response metrics; note stage counts are CUMULATIVE (an app now at
// "interview" also counts as having reached "oa")
export function getFunnel(): Funnel {
  const apps = getApplications().filter((a) => a.status !== "wishlist");
  const by = (s: string) => apps.filter((a) => a.status === s).length;
  const applied = by("applied"),
    oa = by("oa"),
    interview = by("interview"),
    offer = by("offer"),
    rejected = by("rejected") + by("missed"); // missed OA counts as a dead end
  const total = apps.length;
  const responded = oa + interview + offer + rejected; // moved past "applied"
  const now = Date.now();
  const todayStr = new Date().toISOString().slice(0, 10);
  const appliedToday = apps.filter(
    (a) => a.date_applied && a.date_applied.slice(0, 10) === todayStr
  ).length;
  const appliedThisWeek = apps.filter(
    (a) => a.date_applied && now - parseTime(a.date_applied) < 7 * 86_400_000
  ).length;
  return {
    total,
    applied,
    oa,
    interview,
    offer,
    rejected,
    responseRate: total ? responded / total : 0,
    positiveRate: total ? (oa + interview + offer) / total : 0,
    appliedToday,
    appliedThisWeek,
    stale: apps.filter((a) => a.stale).length,
  };
}

export function getQueue(): QueueItem[] {
  return db()
    .prepare(
      "SELECT id, sender, subject, snippet, received_at, proposed_kind, " +
        "proposed_company, proposed_role, confidence FROM review_queue " +
        "WHERE status = 'pending' ORDER BY received_at DESC"
    )
    .all() as QueueItem[];
}
