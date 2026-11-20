"use client";

import { useState, useTransition } from "react";
import { generateTailor } from "./actions";
import { sentences, listItems } from "./lib/text";

// tailored resume + cover letter + honest fit read, laid out as sections
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
  const [jd, setJd] = useState("");
  const tailored = !!resume || !!fit;
  const run = () => start(() => generateTailor(appId, jd.trim() || undefined));

  const fitS = sentences(fit);
  const gapItems = listItems(gaps);

  return (
    <section className="dsec">
      <div className="dsec-head">
        <h3>✨ Tailored resume</h3>
        {tailored && (
          <div className="dsec-tools">
            {hasJd ? <span className="pill ok">JD pulled</span> : <span className="pill">no JD</span>}
            <button className="ghost" disabled={pending} onClick={run}>
              {pending ? "generating…" : "↻ redo"}
            </button>
          </div>
        )}
      </div>

      {!tailored && (
        <div className="dempty">
          <span>Builds a resume + cover letter aimed at this posting, plus an honest fit read.</span>
          <button className="primary" disabled={pending} onClick={run}>
            {pending ? "generating… (~30s)" : "Generate"}
          </button>
        </div>
      )}

      {(resume || cover) && (
        <div className="files">
          {resume && (
            <a className="file" href={resume} target="_blank" rel="noreferrer">
              <span className="file-ico">📄</span>
              <span>
                <b>Resume</b>
                <small>tailored PDF</small>
              </span>
            </a>
          )}
          {cover && (
            <a className="file" href={cover} target="_blank" rel="noreferrer">
              <span className="file-ico">✉️</span>
              <span>
                <b>Cover letter</b>
                <small>tailored PDF</small>
              </span>
            </a>
          )}
        </div>
      )}

      {fitS.length > 0 && (
        <div className="fit">
          <div className="sublbl">Fit</div>
          <p className="fit-lead">{fitS[0]}</p>
          {fitS.length > 1 && <p className="fit-rest">{fitS.slice(1).join(" ")}</p>}
        </div>
      )}

      {gapItems.length > 0 && (
        <div className="gaps">
          <div className="sublbl">Gaps to address</div>
          <ul>
            {gapItems.map((g, i) => (
              <li key={i}>{g}</li>
            ))}
          </ul>
        </div>
      )}

      <details className="jd-override">
        <summary>Paste a job description instead</summary>
        <textarea
          className="jdbox"
          placeholder="Only needed if the auto-pulled JD is wrong or missing"
          value={jd}
          onChange={(e) => setJd(e.target.value)}
          rows={5}
        />
        <button className="primary" disabled={pending || !jd.trim()} onClick={run}>
          {pending ? "generating…" : "Generate with this JD"}
        </button>
      </details>
    </section>
  );
}
