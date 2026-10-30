"use client";

import { useState, useTransition } from "react";
import { generateWhyUs } from "./actions";
import CopyButton from "./CopyButton";

export default function WhyUs({
  appId,
  blurb,
}: {
  appId: number;
  blurb: string | null;
}) {
  const [pending, start] = useTransition();
  const [open, setOpen] = useState(false);

  if (!blurb) {
    return (
      <div className="whyus">
        <button
          className="whyus-btn"
          disabled={pending}
          onClick={() => start(() => generateWhyUs(appId))}
        >
          {pending ? "writing…" : "✍️ why us"}
        </button>
      </div>
    );
  }

  return (
    <div className="whyus">
      <button className="whyus-toggle" onClick={() => setOpen((o) => !o)}>
        {open ? "▾" : "▸"} why-us blurb
      </button>
      {open && (
        <>
          <div className="whyus-text">{blurb}</div>
          <div className="whyus-actions">
            <CopyButton text={blurb} label="copy" />
            <button
              className="whyus-btn"
              disabled={pending}
              onClick={() => start(() => generateWhyUs(appId))}
            >
              {pending ? "writing…" : "regenerate"}
            </button>
          </div>
        </>
      )}
    </div>
  );
}
