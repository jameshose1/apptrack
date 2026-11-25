"use server";

import { execFile } from "child_process";
import path from "path";
import { promisify } from "util";
import { revalidatePath } from "next/cache";
import { db } from "./lib/db";
import { STATUSES, FIELDS, TRACKS, OUTREACH_STATUSES } from "./lib/status";

// --- input guards (audit 2026-11-21 APP-01/APP-11): every action is reachable
// by anything that can talk to the server, so validate rather than trust ---
function id(n: unknown): number {
  if (typeof n !== "number" || !Number.isSafeInteger(n) || n <= 0)
    throw new Error("bad id");
  return n;
}
function oneOf<T extends string>(v: unknown, allowed: readonly T[]): T {
  if (typeof v !== "string" || !(allowed as readonly string[]).includes(v))
    throw new Error("bad value");
  return v as T;
}
const QUEUE_KINDS = ["confirmation", "oa", "interview", "team_match", "offer", "rejection", "dismiss"] as const;
const JD_MAX = 30_000;

// Claude/Chrome-backed actions are paid and heavy; never run more than 2 at once
let running = 0;
async function limited<T>(fn: () => Promise<T>): Promise<T> {
  if (running >= 2) throw new Error("busy, try again in a moment");
  running++;
  try {
    return await fn();
  } finally {
    running--;
  }
}

const pexec = promisify(execFile);
const SCANNER = path.join(process.cwd(), "..", "scanner");
const PY = path.join(SCANNER, ".venv", "bin", "python");

// Resolve a review-queue item via resolve.py so the self-learning rule logic
// (confirm -> promote after 3) stays in one place.
export async function resolveQueueItem(qid: number, kind: string) {
  id(qid);
  oneOf(kind, QUEUE_KINDS);
  await pexec(PY, [path.join(SCANNER, "resolve.py"), String(qid), kind], {
    cwd: SCANNER,
  });
  revalidatePath("/");
}

// Manual board override (the status dropdown). Selecting "Missed OA" runs the
// full teardown (calendar blocks, deadline/alert tasks) via miss_oa.py.
export async function setStatus(appId: number, status: string) {
  id(appId);
  oneOf(status, STATUSES);
  if (status === "missed") {
    await markOaMissed(appId);
    return;
  }
  db()
    .prepare(
      "UPDATE applications SET status = ?, updated_at = datetime('now') WHERE id = ?"
    )
    .run(status, appId);
  revalidatePath("/");
}

// Mark an OA completed (and reschedule the next one) via the scanner CLI so the
// calendar + queue logic stays in one place.
export async function markOaDone(appId: number) {
  id(appId);
  await pexec(PY, [path.join(SCANNER, "complete_oa.py"), String(appId)], {
    cwd: SCANNER,
  });
  revalidatePath("/");
}

export async function undoOaDone(appId: number) {
  id(appId);
  await pexec(
    PY,
    [path.join(SCANNER, "complete_oa.py"), String(appId), "--undo"],
    { cwd: SCANNER }
  );
  revalidatePath("/");
}

// Missed OA deadline: tear down its calendar artifacts and move it to rejected.
export async function markOaMissed(appId: number) {
  id(appId);
  await pexec(PY, [path.join(SCANNER, "miss_oa.py"), String(appId)], {
    cwd: SCANNER,
  });
  revalidatePath("/");
}

// Manual override of the two card tags (CS/Non-CS, Internship/Job) when the
// classifier guessed wrong. Plain SQLite write, no scanner needed.
export async function setFieldTrack(
  appId: number,
  field: string,
  track: string
) {
  id(appId);
  oneOf(field, FIELDS);
  oneOf(track, TRACKS);
  db()
    .prepare(
      "UPDATE applications SET field = ?, track = ?, updated_at = datetime('now') WHERE id = ?"
    )
    .run(field, track, appId);
  revalidatePath("/");
}

// Wishlist -> applied (stamps the application date).
export async function applyToWishlist(appId: number) {
  id(appId);
  db()
    .prepare(
      "UPDATE applications SET status = 'applied', date_applied = date('now'), " +
        "updated_at = datetime('now') WHERE id = ?"
    )
    .run(appId);
  revalidatePath("/");
}

// Generate a tailored "why I want to work here" blurb (Claude, via the scanner
// which holds the API key + the user's profile).
export async function generateWhyUs(appId: number) {
  id(appId);
  await limited(() =>
    pexec(PY, [path.join(SCANNER, "why_us.py"), String(appId)], { cwd: SCANNER })
  );
  revalidatePath("/");
}

// Remove a wishlist posting the user isn't interested in. job_seen keeps its
// source id, so the scanner won't re-add it.
export async function dismissApp(appId: number) {
  id(appId);
  db().prepare("DELETE FROM applications WHERE id = ?").run(appId);
  revalidatePath("/");
}

// --- networking pipeline ---

// Advance a contact's outreach status (plain SQLite write, no scanner needed).
export async function setOutreachStatus(contactId: number, status: string) {
  id(contactId);
  oneOf(status, OUTREACH_STATUSES);
  db()
    .prepare(
      "UPDATE contacts SET outreach_status = ?, outreach_updated = datetime('now') WHERE id = ?"
    )
    .run(status, contactId);
  revalidatePath("/");
}

// Draft the connection note + follow-up chat ask (Claude, via the scanner which
// holds the API key + the user's profile/voice).
export async function draftOutreach(contactId: number) {
  id(contactId);
  await limited(() =>
    pexec(PY, [path.join(SCANNER, "outreach.py"), String(contactId)], { cwd: SCANNER })
  );
  revalidatePath("/");
}

function saveJd(appId: number, jd: unknown) {
  if (jd === undefined) return;
  if (typeof jd !== "string" || jd.length > JD_MAX) throw new Error("bad jd");
  db()
    .prepare(
      "INSERT INTO tailoring(application_id, jd) VALUES(?, ?) " +
        "ON CONFLICT(application_id) DO UPDATE SET jd = excluded.jd"
    )
    .run(appId, jd);
}

// Answer "what makes you an ideal candidate" from the job description. ideal.py
// exits 3 when there's no description to read, so the card can ask for one.
export async function generateIdeal(appId: number, jd?: string): Promise<"ok" | "no_jd"> {
  id(appId);
  saveJd(appId, jd);
  try {
    await limited(() =>
      pexec(PY, [path.join(SCANNER, "ideal.py"), String(appId)], { cwd: SCANNER })
    );
  } catch (e) {
    if ((e as { code?: unknown }).code === 3) return "no_jd";
    throw e;
  }
  revalidatePath("/");
  return "ok";
}

// Tailor an application to its role: saves the (optional) pasted job description,
// then runs tailor.py (Claude) for the fit read + tailored bullets + gaps.
export async function generateTailor(appId: number, jd?: string) {
  id(appId);
  saveJd(appId, jd);
  await limited(() =>
    pexec(PY, [path.join(SCANNER, "tailor.py"), String(appId)], { cwd: SCANNER })
  );
  revalidatePath("/");
}

// --- Wellfound "why this company" ---

const WF_NOTES_MAX = 14_000;

// wellfound.py reads its request as JSON on stdin (pasted notes can be long)
function runWellfound(req: object): Promise<{ code: number; out: string }> {
  return new Promise((resolve) => {
    const child = execFile(
      PY,
      [path.join(SCANNER, "wellfound.py")],
      { cwd: SCANNER, timeout: 240_000 },
      (err, stdout) =>
        resolve({ code: err ? Number((err as { code?: unknown }).code ?? 1) : 0, out: stdout })
    );
    child.stdin?.end(JSON.stringify(req));
  });
}

export async function writeWellfound(
  company: string,
  url: string,
  notes: string
): Promise<"ok" | "not_found"> {
  if (typeof company !== "string" || !company.trim() || company.length > 80)
    throw new Error("bad company");
  if (typeof url !== "string" || url.length > 300) throw new Error("bad url");
  if (typeof notes !== "string" || notes.length > WF_NOTES_MAX) throw new Error("bad notes");
  const r = await limited(() => runWellfound({ company, url, notes }));
  if (r.code === 3) return "not_found";
  if (r.code !== 0) throw new Error("wellfound.py failed");
  revalidatePath("/");
  return "ok";
}

export async function deleteWellfound(answerId: number) {
  id(answerId);
  db().prepare("DELETE FROM wellfound_answers WHERE id = ?").run(answerId);
  revalidatePath("/");
}
