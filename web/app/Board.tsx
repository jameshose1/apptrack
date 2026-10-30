"use client";

import { useMemo, useState } from "react";
import {
  PIPELINE,
  STATUS_LABEL,
  FIELD_LABEL,
  TRACK_LABEL,
  type Application,
  type QueueItem,
  type NetContact,
} from "./lib/status";
import StatusSelect from "./StatusSelect";
import QueueButtons from "./QueueButtons";
import WishlistActions from "./WishlistActions";
import OaDone from "./OaDone";
import Referrals from "./Referrals";
import WhyUs from "./WhyUs";
import Tailor from "./Tailor";
import FieldTrack from "./FieldTrack";
import Funnel from "./Funnel";
import Network from "./Network";
import Tabs from "./Tabs";

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

  // apply the two orthogonal filters to everything downstream (board + stats)
  const shown = useMemo(
    () =>
      apps.filter(
        (a) =>
          (field === "all" || a.field === field) &&
          (track === "all" || a.track === track)
      ),
    [apps, field, track]
  );

  const wishlist = shown
    .filter((a) => a.status === "wishlist")
    .sort((a, b) => b.is_dream - a.is_dream);
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

  const card = (a: Application) => (
    <div className={`card${a.stale ? " stale" : ""}`} key={a.id}>
      <div className="co">
        {a.url ? (
          <a href={a.url} target="_blank" rel="noreferrer">
            {a.company}
          </a>
        ) : (
          a.company
        )}
      </div>
      {a.role && <div className="role">{a.role}</div>}
      <div className="meta">
        <span>Applied {fmtDate(a.date_applied)}</span>
        <StatusSelect appId={a.id} status={a.status} />
      </div>
      {a.next_due && (
        <div className="due">
          {STATUS_LABEL[a.next_kind ?? ""] ?? a.next_kind} due{" "}
          {fmtDate(a.next_due)}
        </div>
      )}
      {a.status === "oa" && (
        <div className="oa-row">
          <OaDone id={a.id} done={!!a.oa_completed_at} />
        </div>
      )}
      {a.stale && (
        <span className="badge cold">going cold · {a.days_idle}d quiet</span>
      )}
      <Referrals
        company={a.company}
        role={a.role}
        status={a.status}
        contacts={a.contacts}
      />
      {a.status !== "rejected" && a.status !== "missed" && (
        <>
          <WhyUs appId={a.id} blurb={a.blurb} />
          <Tailor
            appId={a.id}
            fit={a.tailor_fit}
            resume={a.tailor_resume}
            cover={a.tailor_cover}
            gaps={a.tailor_gaps}
            hasJd={a.tailor_hasjd}
          />
        </>
      )}
      <FieldTrack appId={a.id} field={a.field} track={a.track} />
    </div>
  );

  const pipeline = (
    <div className="board">
      {PIPELINE.map((s) => {
        const list = tracked.filter((a) =>
          s === "rejected"
            ? a.status === "rejected" || a.status === "missed"
            : a.status === s
        );
        return (
          <div className="col" key={s}>
            <div className="col-head">
              <span>
                <span className="dot" style={{ background: `var(--${s})` }} />
                {STATUS_LABEL[s]}
              </span>
              <span className="n">{list.length}</span>
            </div>
            {list.map(card)}
            {list.length === 0 && <div className="empty">—</div>}
          </div>
        );
      })}
    </div>
  );

  const wishlistGrid = (
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
          <Referrals
            company={a.company}
            role={a.role}
            status={a.status}
            contacts={a.contacts}
          />
          <WhyUs appId={a.id} blurb={a.blurb} />
          <Tailor
            appId={a.id}
            fit={a.tailor_fit}
            resume={a.tailor_resume}
            cover={a.tailor_cover}
            gaps={a.tailor_gaps}
            hasJd={a.tailor_hasjd}
          />
          <div className="wactions">
            <a
              className="apply"
              href={a.url ?? "#"}
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
    </>
  );
}
