"use client";

import { useState, type ReactNode } from "react";

type Tab = { key: string; label: string; count: number; node: ReactNode };

export default function Tabs({ tabs }: { tabs: Tab[] }) {
  const [active, setActive] = useState(tabs[0]?.key);
  const current = tabs.find((t) => t.key === active) ?? tabs[0];
  return (
    <>
      <div className="tabs">
        {tabs.map((t) => (
          <button
            key={t.key}
            className={`tab${t.key === active ? " on" : ""}`}
            onClick={() => setActive(t.key)}
          >
            {t.label}
            <span className="tabn">{t.count}</span>
          </button>
        ))}
      </div>
      {current?.node}
    </>
  );
}
