"use client";

import { useTransition } from "react";
import { generateWhyUs } from "./actions";
import CopyButton from "./CopyButton";
import { paragraphs, wordCount } from "./lib/text";

// "why us" blurb, rendered as readable paragraphs inside the detail drawer
export default function WhyUs({
  appId,
  company,
  blurb,
}: {
  appId: number;
  company: string;
  blurb: string | null;
}) {
  const [pending, start] = useTransition();
  const regen = () => start(() => generateWhyUs(appId));

  return (
    <section className="dsec">
      <div className="dsec-head">
        <h3>✍️ Why {company}</h3>
        {blurb && (
          <div className="dsec-tools">
            <span className="dmeta">{wordCount(blurb)} words</span>
            <CopyButton text={blurb} label="copy" />
            <button className="ghost" disabled={pending} onClick={regen}>
              {pending ? "writing…" : "↻ redo"}
            </button>
          </div>
        )}
      </div>
      {blurb ? (
        <div className={`quote${pending ? " dim" : ""}`}>
          {paragraphs(blurb).map((p, i) => (
            <p key={i}>{p}</p>
          ))}
        </div>
      ) : (
        <div className="dempty">
          <span>A short, specific answer for the "why this company" box.</span>
          <button className="primary" disabled={pending} onClick={regen}>
            {pending ? "writing…" : "Write it"}
          </button>
        </div>
      )}
    </section>
  );
}
