"use client";

import { useState, useTransition } from "react";
import { writeWellfound, deleteWellfound } from "./actions";
import CopyButton from "./CopyButton";
import { type WellfoundAnswer } from "./lib/status";
import { paragraphs, safeHref, wordCount } from "./lib/text";

// type a startup's name, get an answer to Wellfound's "why this company?"
export default function Wellfound({ answers }: { answers: WellfoundAnswer[] }) {
  const [pending, start] = useTransition();
  const [company, setCompany] = useState("");
  const [url, setUrl] = useState("");
  const [notes, setNotes] = useState("");
  const [problem, setProblem] = useState<"not_found" | "failed" | null>(null);

  const run = () =>
    start(async () => {
      setProblem(null);
      try {
        const r = await writeWellfound(company.trim(), url.trim(), notes.trim());
        if (r === "not_found") setProblem("not_found");
        else {
          setCompany("");
          setUrl("");
          setNotes("");
        }
      } catch {
        setProblem("failed");
      }
    });

  return (
    <div className="wf">
      <form
        className="wf-form"
        onSubmit={(e) => {
          e.preventDefault();
          if (company.trim() && !pending) run();
        }}
      >
        <div className="wf-row">
          <input
            className="jdbox"
            placeholder="Startup name"
            value={company}
            maxLength={80}
            onChange={(e) => setCompany(e.target.value)}
          />
          <input
            className="jdbox"
            placeholder="Website (optional, helps with common names)"
            value={url}
            maxLength={300}
            onChange={(e) => setUrl(e.target.value)}
          />
          <button className="primary" type="submit" disabled={pending || !company.trim()}>
            {pending ? "writing… (~50s)" : "Why this company"}
          </button>
        </div>
        <details open={problem === "not_found" || undefined}>
          <summary>Paste their Wellfound blurb or the job (optional)</summary>
          <textarea
            className="jdbox"
            rows={5}
            placeholder="Anything from their Wellfound page. Makes the answer more specific."
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
          />
        </details>
        {problem === "not_found" && (
          <p className="dwarn">
            Couldn't find that company. Add its website or paste its Wellfound blurb above.
          </p>
        )}
        {problem === "failed" && <p className="dwarn">That didn't work. Try again in a minute.</p>}
      </form>

      {answers.length === 0 && <p className="dmeta">No answers yet.</p>}
      {answers.map((a) => (
        <section key={a.id} className="dsec">
          <div className="dsec-head">
            <h3>
              {a.url && safeHref(a.url) ? (
                <a href={safeHref(a.url)!} target="_blank" rel="noreferrer">
                  {a.company}
                </a>
              ) : (
                a.company
              )}
            </h3>
            <div className="dsec-tools">
              <span className="dmeta">
                {wordCount(a.text)} words · {a.created_at.slice(0, 10)}
              </span>
              <CopyButton text={a.text} label="copy" />
              <button className="ghost" onClick={() => start(() => deleteWellfound(a.id))}>
                ✕
              </button>
            </div>
          </div>
          <div className="quote">
            {paragraphs(a.text).map((p, i) => (
              <p key={i}>{p}</p>
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}
