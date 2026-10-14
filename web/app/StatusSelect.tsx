"use client";

import { useTransition } from "react";
import { setStatus } from "./actions";
import { STATUSES, STATUS_LABEL } from "./lib/status";

export default function StatusSelect({
  appId,
  status,
}: {
  appId: number;
  status: string;
}) {
  const [pending, start] = useTransition();
  return (
    <select
      value={status}
      disabled={pending}
      onChange={(e) => start(() => setStatus(appId, e.target.value))}
    >
      {STATUSES.map((s) => (
        <option key={s} value={s}>
          {STATUS_LABEL[s]}
        </option>
      ))}
    </select>
  );
}
