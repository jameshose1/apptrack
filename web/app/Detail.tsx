"use client";

import { useEffect } from "react";
import { STATUS_LABEL, type Application } from "./lib/status";
import StatusSelect from "./StatusSelect";
import OaDone from "./OaDone";
import Referrals from "./Referrals";
import WhyUs from "./WhyUs";
import Tailor from "./Tailor";
import FieldTrack from "./FieldTrack";
import WishlistActions from "./WishlistActions";
import { safeHref } from "./lib/text";

function fmt(s: string | null) {
  if (!s) return "";
  return new Date(s).toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

// slide-over panel with everything about one application, so board cards stay small
export default function Detail({
  app: a,
  onClose,
}: {
  app: Application;
  onClose: () => void;
}) {
  useEffect(() => {
    const k = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", k);
    return () => window.removeEventListener("keydown", k);
  }, [onClose]);

  const closed = a.status === "rejected" || a.status === "missed";
  const st = a.status === "missed" ? "rejected" : a.status;

  return (
    <div className="drawer-bg" onClick={onClose}>
      <aside className="drawer" onClick={(e) => e.stopPropagation()}>
        <header className="dhead" style={{ borderTopColor: `var(--${st})` }}>
          <div className="dtitle">
            <div>
              <h2 className="dco">
                {a.is_dream ? <span className="star">★ </span> : null}
                {safeHref(a.url) ? (
                  <a href={safeHref(a.url)} target="_blank" rel="noreferrer">
                    {a.company} ↗
                  </a>
                ) : (
                  a.company
                )}
              </h2>
              {a.role && <div className="drole">{a.role}</div>}
            </div>
            <button className="xbtn" onClick={onClose} aria-label="close">
              ✕
            </button>
          </div>
          <div className="dfacts">
            <span className="pill" style={{ color: `var(--${st})` }}>
              ● {STATUS_LABEL[a.status] ?? a.status}
            </span>
            {a.date_applied && <span>applied {fmt(a.date_applied)}</span>}
            {a.posted_at && a.status === "wishlist" && <span>posted {fmt(a.posted_at)}</span>}
            {a.location && <span>{a.location}</span>}
            {a.next_due && (
              <span className="due">
                {STATUS_LABEL[a.next_kind ?? ""] ?? a.next_kind} due {fmt(a.next_due)}
              </span>
            )}
            {a.stale && <span className="badge cold">going cold · {a.days_idle}d quiet</span>}
          </div>
          <div className="dctl">
            {a.status === "wishlist" ? (
              <WishlistActions id={a.id} />
            ) : (
              <StatusSelect appId={a.id} status={a.status} />
            )}
            {a.status === "oa" && <OaDone id={a.id} done={!!a.oa_completed_at} />}
            <FieldTrack appId={a.id} field={a.field} track={a.track} />
          </div>
        </header>

        <div className="dbody">
          {!closed && (
            <>
              <WhyUs appId={a.id} company={a.company} blurb={a.blurb} />
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
          <section className="dsec">
            <div className="dsec-head">
              <h3>🤝 People</h3>
            </div>
            <Referrals company={a.company} role={a.role} status={a.status} contacts={a.contacts} />
          </section>
          {a.notes && (
            <section className="dsec">
              <div className="dsec-head">
                <h3>📝 Notes</h3>
              </div>
              <p className="dnotes">{a.notes}</p>
            </section>
          )}
        </div>
      </aside>
    </div>
  );
}
