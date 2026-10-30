// Pure constants + types, safe to import from client components
// (no better-sqlite3 / fs dependency).

export const STATUSES = [
  "wishlist",
  "applied",
  "oa",
  "interview",
  "team_match",
  "offer",
  "rejected",
  "missed",
] as const;

// the active-tracking kanban columns (wishlist is its own tab, not a column;
// "missed" is a sub-status that renders inside the Rejected column)
export const PIPELINE = [
  "applied",
  "oa",
  "interview",
  "team_match",
  "offer",
  "rejected",
] as const;

export const STATUS_LABEL: Record<string, string> = {
  wishlist: "Wishlist",
  applied: "Applied",
  oa: "OA",
  interview: "Interview",
  team_match: "Team Match",
  offer: "Offer",
  rejected: "Rejected",
  missed: "Missed OA",
};

// an "applied" app with no activity for this many days is going cold
export const STALE_AFTER_DAYS = 42;

// two orthogonal tags → 4 card types (CS/Non-CS × Internship/Job)
export const FIELDS = ["cs", "other"] as const;
export const TRACKS = ["internship", "job"] as const;
export const FIELD_LABEL: Record<string, string> = { cs: "CS", other: "Non-CS" };
export const TRACK_LABEL: Record<string, string> = {
  internship: "Internship",
  job: "Job",
};

export type Application = {
  id: number;
  company: string;
  role: string | null;
  url: string | null;
  source: string | null;
  location: string | null;
  status: string;
  date_applied: string | null;
  notes: string | null;
  updated_at: string;
  next_due: string | null;
  next_kind: string | null;
  last_activity: string | null;
  days_idle: number;
  stale: boolean;
  posted_at: string | null;
  is_dream: number;
  oa_completed_at: string | null;
  field: string;
  track: string;
  round: number;
  contacts: Contact[];
  blurb: string | null;
  tailor_fit: string | null;
  tailor_resume: string | null; // url to the generated tailored-resume PDF
  tailor_cover: string | null; // url to the generated tailored cover-letter PDF
  tailor_gaps: string | null;
  tailor_hasjd: number;
};

export type Contact = {
  name: string;
  company: string;
  position: string | null;
  url: string | null;
  is_alum: number;
};

// networking pipeline: outreach progress per LinkedIn contact
// these are existing 1st-degree connections, so no connection request step,
// just: message them -> they reply -> you have a chat
export const OUTREACH_STATUSES = [
  "todo",
  "messaged",
  "replied",
  "chatted",
  "skip",
] as const;

export const OUTREACH_LABEL: Record<string, string> = {
  todo: "To reach",
  messaged: "Messaged",
  replied: "Replied",
  chatted: "Chatted",
  skip: "Skip",
};

// segment a contact by their role (who's worth reaching first)
export function roleType(position: string | null): "recruiter" | "engineer" | "other" {
  const p = (position || "").toLowerCase();
  if (/recruit|talent acquisition|sourcer|\bhr\b|people ops|people team|university relations/.test(p))
    return "recruiter";
  if (/engineer|developer|\bswe\b|\bsde\b|software|programmer|full.?stack|back.?end|front.?end|data scien|machine learning|\bml\b|research/.test(p))
    return "engineer";
  return "other";
}

export const ROLE_LABEL: Record<string, string> = {
  recruiter: "Recruiter",
  engineer: "Engineer",
  other: "Other",
};

// a connection who is likely the user's own age/stage (student, intern, etc.),
// so not a network-up target. "senior" is seniority, not a peer signal.
export function isPeer(position: string | null): boolean {
  const p = (position || "").toLowerCase();
  return /\bstudent\b|\bintern(ship)?\b|\bundergrad|teaching assistant|\bt\.?a\.?\b|research assistant|\bco-?op\b|\bincoming\b|class of 20\d\d|\bapprentice|\baspiring\b|\bfreshman\b|\bsophomore\b/.test(
    p
  );
}

export type NetContact = {
  id: number;
  name: string;
  company: string | null;
  position: string | null;
  url: string | null;
  is_alum: number;
  outreach_status: string;
  outreach_updated: string | null;
  connect_note: string | null;
  chat_ask: string | null;
  already_messaged: number; // already in a LinkedIn conversation
  role: string; // derived
  is_peer: boolean; // derived: student/intern/same-stage
  at_company: boolean; // applied to / dream company
};

// LinkedIn alumni explorer, used to deep-link "find UMD alumni at <company>"
export const LINKEDIN_SCHOOL = "university-of-maryland";
export const alumniSearchUrl = (company: string) =>
  `https://www.linkedin.com/school/${LINKEDIN_SCHOOL}/people/?keywords=${encodeURIComponent(
    company
  )}`;

export type Funnel = {
  total: number;
  applied: number;
  oa: number;
  interview: number;
  offer: number;
  rejected: number;
  responseRate: number;
  positiveRate: number;
  appliedToday: number;
  appliedThisWeek: number;
  stale: number;
};

export type QueueItem = {
  id: number;
  sender: string;
  subject: string;
  snippet: string;
  received_at: string;
  proposed_kind: string;
  proposed_company: string;
  proposed_role: string;
  confidence: number;
};
