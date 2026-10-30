import { getApplications, getQueue, getContacts } from "./lib/db";
import Board from "./Board";

export const dynamic = "force-dynamic";

export default function Home() {
  const apps = getApplications();
  const queue = getQueue();
  const contacts = getContacts();
  const tracked = apps.filter((a) => a.status !== "wishlist").length;

  return (
    <div className="wrap">
      <div className="header">
        <h1>
          app<span style={{ color: "var(--accent)" }}>Track</span>
        </h1>
        <span className="count">{tracked} tracked</span>
      </div>
      <Board apps={apps} queue={queue} contacts={contacts} />
    </div>
  );
}
