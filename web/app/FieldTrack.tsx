"use client";

import { useTransition } from "react";
import { setFieldTrack } from "./actions";
import { FIELDS, TRACKS, FIELD_LABEL, TRACK_LABEL } from "./lib/status";

// Two tiny selects to correct a card's type when the classifier guessed wrong.
export default function FieldTrack({
  appId,
  field,
  track,
}: {
  appId: number;
  field: string;
  track: string;
}) {
  const [pending, start] = useTransition();
  return (
    <div className="fieldtrack" title="card type">
      <select
        className="ft"
        value={field}
        disabled={pending}
        onChange={(e) => start(() => setFieldTrack(appId, e.target.value, track))}
      >
        {FIELDS.map((f) => (
          <option key={f} value={f}>
            {FIELD_LABEL[f]}
          </option>
        ))}
      </select>
      <select
        className="ft"
        value={track}
        disabled={pending}
        onChange={(e) => start(() => setFieldTrack(appId, field, e.target.value))}
      >
        {TRACKS.map((t) => (
          <option key={t} value={t}>
            {TRACK_LABEL[t]}
          </option>
        ))}
      </select>
    </div>
  );
}
