"use client";

import { useState, useTransition } from "react";
import { generateTailor } from "./actions";

export default function Tailor({
  appId,
  fit,
  resume,
  cover,
  gaps,
  hasJd,
}: {
  appId: number;
  fit: string | null;
  resume: string | null;
  cover: string | null;
  gaps: string | null;
  hasJd: number;
}) {
  const [pending, start] = useTransition();
  const [open, setOpen] = useState(false);
  const [jd, setJd] = useState("");
  const tailored = !!resume || !!fit;

  const run = () => start(() => generateTailor(appId, jd.trim() || undefined));

  if (!tailored && !open) {
    return (
      <div className="tailor">
        <button className="tailor-toggle" onClick={() => setOpen(true)}>
          ✨ tailor resume
        </button>
      </div>
    );
  }

  return (
    <div className="tailor">
      <button className="tailor-toggle" onClick={() => setOpen((o) => !o)}>
        {open ? "▾" : "▸"} {tailored ? "tailored resume" : "tailor resume"}
        {hasJd ? " · JD" : ""}
      </button>
      {open && (
        <div className="tailor-body">
          <textarea
            className="jdbox"
            placeholder="auto-pulls the JD from the posting link; paste one here only to override"
            value={jd}
            onChange={(e) => setJd(e.target.value)}
            rows={3}
          />
          <button className="tailor-btn" disabled={pending} onClick={run}>
            {pending ? "generating…" : tailored ? "re-generate" : "generate resume"}
          </button>

          {(resume || cover) && (
            <div className="tailor-files">
              {resume && (
                <a className="resume-link" href={resume} target="_blank" rel="noreferrer">
                  📄 resume PDF
                </a>
              )}
              {cover && (
                <a className="resume-link" href={cover} target="_blank" rel="noreferrer">
                  ✉️ cover letter PDF
                </a>
              )}
            </div>
          )}
          {fit && (
            <div className="t-sec">
              <div className="t-lbl">Fit</div>
              <div className="t-text">{fit}</div>
            </div>
          )}
          {gaps && (
            <div className="t-sec">
              <div className="t-lbl">Gaps to address</div>
              <div className="t-text gap">{gaps}</div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
