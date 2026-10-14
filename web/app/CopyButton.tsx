"use client";

import { useState } from "react";

export default function CopyButton({
  text,
  label = "copy note",
}: {
  text: string;
  label?: string;
}) {
  const [done, setDone] = useState(false);
  return (
    <button
      className="copybtn"
      title={text}
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(text);
          setDone(true);
          setTimeout(() => setDone(false), 1500);
        } catch {}
      }}
    >
      {done ? "copied ✓" : label}
    </button>
  );
}
