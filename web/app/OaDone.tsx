"use client";

import { useTransition } from "react";
import { markOaDone, markOaMissed, undoOaDone } from "./actions";

export default function OaDone({ id, done }: { id: number; done: boolean }) {
  const [pending, start] = useTransition();
  if (done) {
    return (
      <span className="oa-done">
        OA done ✓{" "}
        <button
          className="linkbtn"
          disabled={pending}
          onClick={() => start(() => undoOaDone(id))}
        >
          undo
        </button>
      </span>
    );
  }
  return (
    <>
      <button
        className="oa-btn"
        disabled={pending}
        onClick={() => start(() => markOaDone(id))}
      >
        Mark OA done
      </button>
      <button
        className="oa-btn missed"
        disabled={pending}
        onClick={() => start(() => markOaMissed(id))}
        title="Missed the deadline — remove it"
      >
        Missed
      </button>
    </>
  );
}
