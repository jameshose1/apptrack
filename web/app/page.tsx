import { getApplications, getFunnel, getQueue } from "./lib/db";
import { PIPELINE, STATUS_LABEL } from "./lib/status";
import StatusSelect from "./StatusSelect";
import QueueButtons from "./QueueButtons";
import WishlistActions from "./WishlistActions";
import OaDone from "./OaDone";
import Referrals from "./Referrals";
import Tabs from "./Tabs";

export const dynamic = "force-dynamic";

function fmtDate(s: string | null) {
  if (!s) return "";
  return new Date(s).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
  });
}

const pct = (n: number) => `${Math.round(n * 100)}%`;

export default function Home() {
  const apps = getApplications();
  const queue = getQueue();
  const f = getFunnel();
  const wishlist = apps
    .filter((a) => a.status === "wishlist")
    .sort((a, b) => b.is_dream - a.is_dream);
  const reachedOa = f.oa + f.interview + f.offer;
  const reachedInterview = f.interview + f.offer;

  const pipeline = (
    <div className="board">
      {PIPELINE.map((s) => {
        const list = apps.filter((a) =>
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
            {list.map((a) => (
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
                  <span className="badge cold">
                    going cold · {a.days_idle}d quiet
                  </span>
                )}
                <Referrals company={a.company} role={a.role} status={a.status} contacts={a.contacts} />
              </div>
            ))}
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
          <Referrals company={a.company} role={a.role} status={a.status} contacts={a.contacts} />
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
    <div className="wrap">
      <div className="header">
        <h1>apptrack</h1>
        <span className="count">{apps.length - wishlist.length} tracked</span>
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
          Applied <b>{f.total}</b> → OA <b>{reachedOa}</b> → Interview{" "}
          <b>{reachedInterview}</b> → Offer <b>{f.offer}</b>
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
        ]}
      />
    </div>
  );
}
