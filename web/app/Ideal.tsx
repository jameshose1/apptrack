"use client";

import { useState, useTransition } from "react";
import { generateIdeal } from "./actions";
import CopyButton from "./CopyButton";
import { paragraphs, wordCount } from "./lib/text";

// "what makes you an ideal candidate" answer, written from the job description
export default function Ideal({ appId, answer }: { appId: number; answer: string | null }) {
  const [pending, start] = useTransition();
  const [jd, setJd] = useState("");
  const [problem, setProblem] = useState<"no_jd" | "failed" | null>(null);
  const run = (pasted?: string) =>
    start(async () => {
      setProblem(null);
      try {
        const r = await generateIdeal(appId, pasted);
        if (r === "no_jd") setProblem("no_jd");
        else setJd("");
      } catch {
        setProblem("failed");
      }
    });

  return (
    <section className="dsec">
      <div className="dsec-head">
        <h3>🎯 Ideal candidate</h3>
        {answer && (
          <div className="dsec-tools">
            <span className="dmeta">{wordCount(answer)} words</span>
            <CopyButton text={answer} label="copy" />
            <button className="ghost" disabled={pending} onClick={() => run()}>
              {pending ? "writing…" : "↻ redo"}
            </button>
          </div>
        )}
      </div>

      {answer ? (
        <div className={`quote${pending ? " dim" : ""}`}>
          {paragraphs(answer).map((p, i) => (
            <p key={i}>{p}</p>
          ))}
        </div>
      ) : (
        <div className="dempty">
          <span>Reads the job description and answers "what makes you an ideal candidate?"</span>
          <button className="primary" disabled={pending} onClick={() => run()}>
            {pending ? "writing… (~40s)" : "Write it"}
          </button>
        </div>
      )}

      {problem === "failed" && <p className="dwarn">That didn't work. Try again in a minute.</p>}
      {problem === "no_jd" && (
        <p className="dwarn">Couldn't read this posting. Paste the job description below.</p>
      )}
      <details className="jd-override" open={problem === "no_jd" || undefined}>
        <summary>Paste a job description instead</summary>
        <textarea
          className="jdbox"
          placeholder="Only needed if the posting can't be read, or is the wrong one"
          value={jd}
          onChange={(e) => setJd(e.target.value)}
          rows={5}
        />
        <button className="primary" disabled={pending || !jd.trim()} onClick={() => run(jd.trim())}>
          {pending ? "writing…" : "Write with this JD"}
        </button>
      </details>
    </section>
  );
}
