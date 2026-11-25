"use client";

import { useMemo, useState, type MouseEvent } from "react";
import {
  PIPELINE,
  STATUS_LABEL,
  FIELD_LABEL,
  TRACK_LABEL,
  type Application,
  type QueueItem,
  type NetContact,
} from "./lib/status";
import QueueButtons from "./QueueButtons";
import WishlistActions from "./WishlistActions";
import OaDone from "./OaDone";
import StatusSelect from "./StatusSelect";
import Detail from "./Detail";
import Funnel from "./Funnel";
import Network from "./Network";
import Tabs from "./Tabs";
import { safeHref } from "./lib/text";

function fmtDate(s: string | null) {
  if (!s) return "";
  return new Date(s).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
  });
}
const pct = (n: number) => `${Math.round(n * 100)}%`;

type Seg = { key: string; label: string };

function Segmented({
  options,
  value,
  onChange,
}: {
  options: Seg[];
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <div className="seg">
      {options.map((o) => (
        <button
          key={o.key}
          className={`seg-b${o.key === value ? " on" : ""}`}
          onClick={() => onChange(o.key)}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

export default function Board({
  apps,
  queue,
  contacts,
}: {
  apps: Application[];
  queue: QueueItem[];
  contacts: NetContact[];
}) {
  const [field, setField] = useState("all");
  const [track, setTrack] = useState("all");
  const [wlSort, setWlSort] = useState("dream");
  const [q, setQ] = useState("");
  const [openId, setOpenId] = useState<number | null>(null);
  const openApp = openId == null ? null : apps.find((a) => a.id === openId) ?? null;

  // apply the two orthogonal filters to everything downstream (board + stats)
  const shown = useMemo(
    () =>
      apps.filter(
        (a) =>
          (field === "all" || a.field === field) &&
          (track === "all" || a.track === track) &&
          (!q.trim() ||
            `${a.company} ${a.role ?? ""}`.toLowerCase().includes(q.trim().toLowerCase()))
      ),
    [apps, field, track, q]
  );

  const postedTime = (s: string | null) => (s ? new Date(s).getTime() : 0);
  const wishlist = shown
    .filter((a) => a.status === "wishlist")
    .sort((a, b) =>
      wlSort === "recent"
        ? postedTime(b.posted_at) - postedTime(a.posted_at)
        : b.is_dream - a.is_dream ||
          postedTime(b.posted_at) - postedTime(a.posted_at)
    );
  const tracked = shown.filter((a) => a.status !== "wishlist");

  // funnel + stats recomputed over the filtered set so they match the view
  const f = useMemo(() => {
    const by = (s: string) => tracked.filter((a) => a.status === s).length;
    const oa = by("oa"),
      interview = by("interview"),
      offer = by("offer"),
      rejected = by("rejected") + by("missed");
    const total = tracked.length;
    const responded = oa + interview + offer + rejected;
    const now = Date.now();
    const today = new Date().toISOString().slice(0, 10);
    return {
      total,
      offer,
      reachedOa: oa + interview + offer,
      reachedInterview: interview + offer,
      responseRate: total ? responded / total : 0,
      positiveRate: total ? (oa + interview + offer) / total : 0,
      appliedToday: tracked.filter(
        (a) => a.date_applied && a.date_applied.slice(0, 10) === today
      ).length,
      appliedThisWeek: tracked.filter(
        (a) =>
          a.date_applied &&
          now - Date.parse(a.date_applied + "T00:00:00Z") < 7 * 86_400_000
      ).length,
      stale: tracked.filter((a) => a.stale).length,
    };
  }, [tracked]);

  const ago = (d: string | null) => {
    if (!d) return "";
    const n = Math.floor((Date.now() - Date.parse(d.slice(0, 10) + "T00:00:00Z")) / 86_400_000);
    return n <= 0 ? "today" : `${n}d`;
  };

  // little indicators for prep that's already done, so the card stays one glance
  const prep = (a: Application) => (
    <span className="prep">
      {a.blurb && <span title="why-us written">✍️</span>}
      {a.ideal && <span title="ideal candidate answer written">🎯</span>}
      {(a.tailor_resume || a.tailor_fit) && <span title="resume tailored">✨</span>}
      {a.contacts.length > 0 && <span title="people you know here">🤝{a.contacts.length}</span>}
    </span>
  );

  // stop clicks on controls inside a card from also opening the drawer
  const keep = (e: MouseEvent) => e.stopPropagation();

  const card = (a: Application) => {
    const closed = a.status === "rejected" || a.status === "missed";
    if (closed)
      return (
        <div className="card mini" key={a.id} onClick={() => setOpenId(a.id)}>
          <div className="mini-main">
            <span className="co">{a.company}</span>
            {a.role && <span className="role">{a.role}</span>}
          </div>
          <span className="when" onClick={keep}>
            <StatusSelect appId={a.id} status={a.status} />
          </span>
        </div>
      );
    return (
      <div
        className={`card${a.stale ? " stale" : ""}`}
        key={a.id}
        onClick={() => setOpenId(a.id)}
      >
        <div className="card-top">
          <span className="co">{a.company}</span>
          {a.is_dream ? <span className="star">★</span> : null}
        </div>
        {a.role && <div className="role">{a.role}</div>}
        <div className="meta">
          <span>
            {fmtDate(a.date_applied)}
            {a.date_applied ? ` · ${ago(a.date_applied)}` : ""} {prep(a)}
          </span>
          <span onClick={keep}>
            <StatusSelect appId={a.id} status={a.status} />
          </span>
        </div>
        {a.next_due && (
          <div className="due">
            {STATUS_LABEL[a.next_kind ?? ""] ?? a.next_kind} due {fmtDate(a.next_due)}
          </div>
        )}
        {a.status === "oa" && (
          <div className="oa-row" onClick={keep}>
            <OaDone id={a.id} done={!!a.oa_completed_at} />
          </div>
        )}
        {a.stale && <span className="badge cold">going cold · {a.days_idle}d quiet</span>}
      </div>
    );
  };

  const pipeline = (
    <div className="board">
      {PIPELINE.map((s) => {
        const list = tracked.filter((a) =>
          s === "rejected"
            ? a.status === "rejected" || a.status === "missed"
            : a.status === s
        );
        return (
          <div
            className={`col${list.length === 0 ? " slim" : ""}${s === "applied" ? " wide" : ""}`}
            key={s}
          >
            <div className="col-head">
              <span>
                <span className="dot" style={{ background: `var(--${s})` }} />
                {STATUS_LABEL[s]}
              </span>
              <span className="n">{list.length}</span>
            </div>
            <div className="col-body">
              {list.map(card)}
              {list.length === 0 && <div className="empty">none yet</div>}
            </div>
          </div>
        );
      })}
    </div>
  );

  const wishlistGrid = (
    <>
    <div className="wishlist-sort">
      <Segmented
        options={[
          { key: "dream", label: "Dream first" },
          { key: "recent", label: "Recently posted" },
        ]}
        value={wlSort}
        onChange={setWlSort}
      />
    </div>
    <div className="wishlist-grid">
      {wishlist.map((a) => (
        <div className={`wcard${a.is_dream ? " dream" : ""}`} key={a.id}>
          <div className="whead">
            {a.is_dream ? <span className="star">★</span> : null}
            <span className="wco">{a.company}</span>
          </div>
          {a.role && <div className="wrole">{a.role}</div>}
          {(a.location || a.posted_at) && (
            <div className="wmeta">
              {a.location}
              {a.location && a.posted_at ? " · " : ""}
              {a.posted_at ? `posted ${fmtDate(a.posted_at)}` : ""}
            </div>
          )}
          <div className="wactions">
            <button className="prepbtn" onClick={() => setOpenId(a.id)}>
              Prep {prep(a)}
            </button>
            <a
              className="apply"
              href={safeHref(a.url) ?? "#"}
              target="_blank"
              rel="noreferrer"
            >
              Apply ↗
            </a>
            <WishlistActions id={a.id} />
          </div>
        </div>
      ))}
      {wishlist.length === 0 && (
        <div className="empty">Nothing here yet. The job scanner runs daily.</div>
      )}
    </div>
    </>
  );

  const review = (
    <div className="queue">
      {queue.length === 0 && (
        <div className="empty">Nothing to review. The scanner is caught up.</div>
      )}
      {queue.map((q) => (
        <div className="qitem" key={q.id}>
          <div className="top">
            <div>
              <div className="subj">{q.subject}</div>
              <div className="snip">{q.snippet}</div>
              <div className="from">
                {q.sender} · proposed: {q.proposed_kind}
                {q.proposed_company ? ` · ${q.proposed_company}` : ""}
              </div>
            </div>
            <div className="conf">{Math.round(q.confidence * 100)}%</div>
          </div>
          <QueueButtons id={q.id} />
        </div>
      ))}
    </div>
  );

  return (
    <>
      <div className="filters">
        <Segmented
          value={field}
          onChange={setField}
          options={[
            { key: "all", label: "All" },
            { key: "cs", label: FIELD_LABEL.cs },
            { key: "other", label: FIELD_LABEL.other },
          ]}
        />
        <Segmented
          value={track}
          onChange={setTrack}
          options={[
            { key: "all", label: "All" },
            { key: "internship", label: TRACK_LABEL.internship },
            { key: "job", label: TRACK_LABEL.job },
          ]}
        />
        <input
          className="search"
          placeholder="Search company or role…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
      </div>

      <div className="stats">
        <div className="stat">
          <span className="k">{f.appliedToday}</span>
          <span className="l">sent today</span>
        </div>
        <div className="stat">
          <span className="k">{f.appliedThisWeek}</span>
          <span className="l">this week</span>
        </div>
        <div className="stat">
          <span className="k">{f.total}</span>
          <span className="l">total sent</span>
        </div>
        <div className="stat">
          <span className="k">{pct(f.responseRate)}</span>
          <span className="l">response rate</span>
        </div>
        <div className="stat">
          <span className="k">{pct(f.positiveRate)}</span>
          <span className="l">OA+ rate</span>
        </div>
        {f.stale > 0 && (
          <div className="stat warn">
            <span className="k">{f.stale}</span>
            <span className="l">going cold</span>
          </div>
        )}
        <div className="funnel">
          Applied <b>{f.total}</b> → OA <b>{f.reachedOa}</b> → Interview{" "}
          <b>{f.reachedInterview}</b> → Offer <b>{f.offer}</b>
        </div>
      </div>

      <Tabs
        tabs={[
          { key: "pipeline", label: "Pipeline", count: f.total, node: pipeline },
          {
            key: "wishlist",
            label: "Wishlist",
            count: wishlist.length,
            node: wishlistGrid,
          },
          { key: "review", label: "Review", count: queue.length, node: review },
          {
            key: "funnel",
            label: "Funnel",
            count: f.total,
            node: <Funnel apps={tracked} />,
          },
          {
            key: "network",
            label: "Network",
            count: contacts.filter(
              (c) => c.outreach_status !== "skip" && c.outreach_status !== "chatted"
            ).length,
            node: <Network contacts={contacts} />,
          },
        ]}
      />
      {openApp && <Detail app={openApp} onClose={() => setOpenId(null)} />}
    </>
  );
}
