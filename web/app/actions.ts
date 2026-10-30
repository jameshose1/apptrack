"use server";

import { execFile } from "child_process";
import path from "path";
import { promisify } from "util";
import { revalidatePath } from "next/cache";
import { db } from "./lib/db";

const pexec = promisify(execFile);
const SCANNER = path.join(process.cwd(), "..", "scanner");
const PY = path.join(SCANNER, ".venv", "bin", "python");

// Resolve a review-queue item via resolve.py so the self-learning rule logic
// (confirm -> promote after 3) stays in one place.
export async function resolveQueueItem(id: number, kind: string) {
  await pexec(PY, [path.join(SCANNER, "resolve.py"), String(id), kind], {
    cwd: SCANNER,
  });
  revalidatePath("/");
}

// Manual board override (the status dropdown). Selecting "Missed OA" runs the
// full teardown (calendar blocks, deadline/alert tasks) via miss_oa.py.
export async function setStatus(appId: number, status: string) {
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
  await pexec(PY, [path.join(SCANNER, "complete_oa.py"), String(appId)], {
    cwd: SCANNER,
  });
  revalidatePath("/");
}

export async function undoOaDone(appId: number) {
  await pexec(
    PY,
    [path.join(SCANNER, "complete_oa.py"), String(appId), "--undo"],
    { cwd: SCANNER }
  );
  revalidatePath("/");
}

// Missed OA deadline: tear down its calendar artifacts and move it to rejected.
export async function markOaMissed(appId: number) {
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
  db()
    .prepare(
      "UPDATE applications SET field = ?, track = ?, updated_at = datetime('now') WHERE id = ?"
    )
    .run(field, track, appId);
  revalidatePath("/");
}

// Wishlist -> applied (stamps the application date).
export async function applyToWishlist(appId: number) {
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
  await pexec(PY, [path.join(SCANNER, "why_us.py"), String(appId)], {
    cwd: SCANNER,
  });
  revalidatePath("/");
}

// Remove a wishlist posting the user isn't interested in. job_seen keeps its
// source id, so the scanner won't re-add it.
export async function dismissApp(appId: number) {
  db().prepare("DELETE FROM applications WHERE id = ?").run(appId);
  revalidatePath("/");
}

// --- networking pipeline ---

// Advance a contact's outreach status (plain SQLite write, no scanner needed).
export async function setOutreachStatus(contactId: number, status: string) {
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
  await pexec(PY, [path.join(SCANNER, "outreach.py"), String(contactId)], {
    cwd: SCANNER,
  });
  revalidatePath("/");
}

// Tailor an application to its role: saves the (optional) pasted job description,
// then runs tailor.py (Claude) for the fit read + tailored bullets + gaps.
export async function generateTailor(appId: number, jd?: string) {
  if (typeof jd === "string") {
    db()
      .prepare(
        "INSERT INTO tailoring(application_id, jd) VALUES(?, ?) " +
          "ON CONFLICT(application_id) DO UPDATE SET jd = excluded.jd"
      )
      .run(appId, jd);
  }
  await pexec(PY, [path.join(SCANNER, "tailor.py"), String(appId)], {
    cwd: SCANNER,
  });
  revalidatePath("/");
}
