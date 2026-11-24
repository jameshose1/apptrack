// tiny text shapers so model prose renders as structure instead of one blob

// split prose into sentences without breaking on "e.g." / decimals / "U.S."
export function sentences(s: string | null | undefined): string[] {
  if (!s) return [];
  return s
    .replace(/\s+/g, " ")
    .trim()
    .split(/(?<=[.!?])\s+(?=[A-Z"(])/)
    .map((x) => x.trim())
    .filter(Boolean);
}

// group sentences into short paragraphs (~2 sentences each) for easy reading
export function paragraphs(s: string | null | undefined, per = 2): string[] {
  const sents = sentences(s);
  if (sents.length <= per) return sents.length ? [sents.join(" ")] : [];
  const out: string[] = [];
  for (let i = 0; i < sents.length; i += per) out.push(sents.slice(i, i + per).join(" "));
  return out;
}

// "gaps" comes back either as a ; list or as sentences; normalize to items
export function listItems(s: string | null | undefined): string[] {
  if (!s) return [];
  const t = s.replace(/\s+/g, " ").trim();
  const parts =
    t.includes(";") ? t.split(/;\s*/) : sentences(t);
  return parts
    .map((p) => p.replace(/^(and|or)\s+/i, "").replace(/[.;]\s*$/, "").trim())
    .filter(Boolean)
    .map((p) => p[0].toUpperCase() + p.slice(1));
}

export const wordCount = (s: string | null | undefined) =>
  s ? s.trim().split(/\s+/).length : 0;

// only render plain web links; listing URLs come from outside sources and
// React 18 still renders javascript: hrefs (audit 2026-11-21 APP-08)
export function safeHref(u: string | null | undefined): string | undefined {
  return u && /^https?:\/\//i.test(u.trim()) ? u.trim() : undefined;
}
