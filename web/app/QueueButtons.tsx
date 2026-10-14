"use client";

import { useTransition } from "react";
import { resolveQueueItem } from "./actions";

const CHOICES: [string, string][] = [
  ["confirmation", "Applied"],
  ["oa", "OA"],
  ["interview", "Interview"],
  ["offer", "Offer"],
  ["rejection", "Rejected"],
];

export default function QueueButtons({ id }: { id: number }) {
  const [pending, start] = useTransition();
  return (
    <div className="btns">
      {CHOICES.map(([kind, label]) => (
        <button
          key={kind}
          disabled={pending}
          onClick={() => start(() => resolveQueueItem(id, kind))}
        >
          {label}
        </button>
      ))}
      <button
        className="dismiss"
        disabled={pending}
        onClick={() => start(() => resolveQueueItem(id, "dismiss"))}
      >
        Not a job
      </button>
    </div>
  );
}
