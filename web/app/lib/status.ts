// Pure constants + types, safe to import from client components
// (no better-sqlite3 / fs dependency).

export const STATUSES = [
  "wishlist",
  "applied",
  "oa",
  "interview",
  "offer",
  "rejected",
  "missed",
] as const;

// the active-tracking kanban columns (wishlist is its own tab, not a column;
// "missed" is a sub-status that renders inside the Rejected column)
export const PIPELINE = ["applied", "oa", "interview", "offer", "rejected"] as const;

export const STATUS_LABEL: Record<string, string> = {
  wishlist: "Wishlist",
  applied: "Applied",
  oa: "OA",
  interview: "Interview",
  offer: "Offer",
  rejected: "Rejected",
  missed: "Missed OA",
};

// an "applied" app with no activity for this many days is going cold
export const STALE_AFTER_DAYS = 42;

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
  contacts: Contact[];
};

export type Contact = {
  name: string;
  company: string;
  position: string | null;
  url: string | null;
  is_alum: number;
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
