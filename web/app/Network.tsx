"use client";

import { useMemo, useState, useTransition } from "react";
import {
  OUTREACH_STATUSES,
  OUTREACH_LABEL,
  ROLE_LABEL,
  type NetContact,
} from "./lib/status";
import { setOutreachStatus, draftOutreach } from "./actions";
import CopyButton from "./CopyButton";

const DAILY_TARGET = 15; // a sane daily pace so you don't blast everyone at once

function OutreachSelect({ id, status }: { id: number; status: string }) {
  const [pending, start] = useTransition();
  return (
    <select
      className={`ostatus st-${status}`}
      value={status}
      disabled={pending}
      onChange={(e) => start(() => setOutreachStatus(id, e.target.value))}
    >
      {OUTREACH_STATUSES.map((s) => (
        <option key={s} value={s}>
          {OUTREACH_LABEL[s]}
        </option>
      ))}
    </select>
  );
}

function DraftBtn({ id, has }: { id: number; has: boolean }) {
  const [pending, start] = useTransition();
  return (
    <button
      className="draftbtn"
      disabled={pending}
      onClick={() => start(() => draftOutreach(id))}
    >
      {pending ? "drafting…" : has ? "✍️ regenerate" : "✍️ draft messages"}
    </button>
  );
}

type Seg = "all" | "recruiter" | "engineer" | "other";

export default function Network({ contacts }: { contacts: NetContact[] }) {
  const [seg, setSeg] = useState<Seg>("all");
  const [stat, setStat] = useState("active");
  const [q, setQ] = useState("");
  const [showPeers, setShowPeers] = useState(false);

  const today = new Date().toISOString().slice(0, 10);
  const messagedToday = contacts.filter(
    (c) => c.outreach_status === "messaged" && (c.outreach_updated || "").slice(0, 10) === today
  ).length;
  // excluded by default: people you already talk to, and same-age peers
  const alreadyCount = contacts.filter((c) => c.already_messaged).length;
  const peerCount = contacts.filter((c) => c.is_peer && !c.already_messaged).length;

  // base pool everything else filters from (drops already-messaged + peers)
  const pool = useMemo(
    () => contacts.filter((c) => !c.already_messaged && (showPeers || !c.is_peer)),
    [contacts, showPeers]
  );

  const rows = useMemo(() => {
    let list = pool.filter((c) => {
      if (seg !== "all" && c.role !== seg) return false;
      if (stat === "active") {
        if (c.outreach_status === "skip" || c.outreach_status === "chatted") return false;
      } else if (stat !== "all" && c.outreach_status !== stat) return false;
      if (q.trim()) {
        const n = q.toLowerCase();
        return (
          (c.name || "").toLowerCase().includes(n) ||
          (c.company || "").toLowerCase().includes(n) ||
          (c.position || "").toLowerCase().includes(n)
        );
      }
      return true;
    });
    const roleRank: Record<string, number> = { recruiter: 0, engineer: 1, other: 2 };
    // surface people to act on: replied first (follow up), then fresh to-reach,
    // then already-messaged (waiting on them), chatted/skip last
    const statRank: Record<string, number> = {
      replied: 0, todo: 1, messaged: 2, chatted: 9, skip: 9,
    };
    return [...list].sort((a, b) => {
      if (a.at_company !== b.at_company) return a.at_company ? -1 : 1;
      if (roleRank[a.role] !== roleRank[b.role]) return roleRank[a.role] - roleRank[b.role];
      return (statRank[a.outreach_status] ?? 5) - (statRank[b.outreach_status] ?? 5);
    });
  }, [pool, seg, stat, q]);

  const segCount = (r: Seg) =>
    pool.filter(
      (c) =>
        (r === "all" || c.role === r) &&
        c.outreach_status !== "skip" &&
        c.outreach_status !== "chatted"
    ).length;

  return (
    <>
      <div className="net-bar">
        <div className="seg">
          {(["all", "recruiter", "engineer", "other"] as Seg[]).map((s) => (
            <button
              key={s}
              className={`seg-b${s === seg ? " on" : ""}`}
              onClick={() => setSeg(s)}
            >
              {s === "all" ? "All" : ROLE_LABEL[s]}
              <span className="tabn">{segCount(s)}</span>
            </button>
          ))}
        </div>
        <div className="controls">
          <input
            className="search"
            placeholder="search name / company / title"
            value={q}
            onChange={(e) => setQ(e.target.value)}
          />
          <select className="statfilter" value={stat} onChange={(e) => setStat(e.target.value)}>
            <option value="active">Active</option>
            <option value="all">All</option>
            {OUTREACH_STATUSES.map((s) => (
              <option key={s} value={s}>
                {OUTREACH_LABEL[s]}
              </option>
            ))}
          </select>
          <button
            className={`peertoggle${showPeers ? " on" : ""}`}
            onClick={() => setShowPeers((v) => !v)}
            title="Peers are students/interns around your age, hidden by default"
          >
            {showPeers ? "hiding peers" : `show peers (${peerCount})`}
          </button>
          <span className={`pace${messagedToday >= DAILY_TARGET ? " over" : ""}`}>
            {messagedToday} messaged today
          </span>
        </div>
      </div>
      {alreadyCount > 0 && (
        <div className="net-hidden">
          {alreadyCount} connection{alreadyCount === 1 ? "" : "s"} you already
          talk to are hidden{!showPeers && peerCount > 0 ? `, plus ${peerCount} same-stage peers` : ""}.
        </div>
      )}

      <div className="net-list">
        {rows.length === 0 && (
          <div className="empty">
            No contacts here. Export your LinkedIn connections and run
            import_contacts.py to populate this.
          </div>
        )}
        {rows.map((c) => (
          <div className="ncard" key={c.id}>
            <div className="nmain">
              <div className="nhead">
                {c.url ? (
                  <a href={c.url} target="_blank" rel="noreferrer" className="nname">
                    {c.name}
                  </a>
                ) : (
                  <span className="nname">{c.name}</span>
                )}
                {c.at_company && <span className="nbadge warm">your target</span>}
                <span className={`nbadge role role-${c.role}`}>{ROLE_LABEL[c.role]}</span>
                {c.is_alum === 1 && <span className="nbadge alum">🎓 Terp</span>}
              </div>
              <div className="nsub">
                {c.position}
                {c.company ? ` · ${c.company}` : ""}
              </div>
              <div className="nactions">
                <DraftBtn id={c.id} has={!!c.connect_note} />
                {c.url && (
                  <a className="apply" href={c.url} target="_blank" rel="noreferrer">
                    Open ↗
                  </a>
                )}
              </div>
              {c.connect_note && (
                <details className="ndraft">
                  <summary>▸ message</summary>
                  <div className="dmsg">
                    <div className="dlabel">Direct message</div>
                    <div className="dtext">{c.connect_note}</div>
                    <CopyButton text={c.connect_note} label="copy message" />
                  </div>
                </details>
              )}
            </div>
            <div className="nstatus">
              <OutreachSelect id={c.id} status={c.outreach_status} />
            </div>
          </div>
        ))}
      </div>
    </>
  );
}
