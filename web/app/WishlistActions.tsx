"use client";

import { useTransition } from "react";
import { applyToWishlist, dismissApp } from "./actions";

export default function WishlistActions({ id }: { id: number }) {
  const [pending, start] = useTransition();
  return (
    <div className="wish-btns">
      <button
        disabled={pending}
        onClick={() => start(() => applyToWishlist(id))}
        title="Mark as applied"
      >
        Applied
      </button>
      <button
        className="dismiss"
        disabled={pending}
        onClick={() => start(() => dismissApp(id))}
        title="Not interested"
      >
        Dismiss
      </button>
    </div>
  );
}
