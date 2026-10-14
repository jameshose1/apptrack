import { alumniSearchUrl, type Contact } from "./lib/status";
import CopyButton from "./CopyButton";

// a company is "applied-stage" once you've actually submitted, so the
// "I just applied" reach-out message is accurate
const APPLIED_STAGE = new Set(["applied", "oa", "interview", "offer"]);

function reachOut(contact: Contact, role: string | null, company: string) {
  const first = (contact.name || "").split(" ")[0] || contact.name;
  const where = contact.position
    ? ` and noticed you work as a ${contact.position} there`
    : "";
  return (
    `Hi ${first}, I just applied for the ${role || "open"} position at ` +
    `${company}${where}. I'd love to connect and hear a bit about your ` +
    `experience there sometime. Thanks!`
  );
}

// warm-intro paths for a company: people you know here (with a ready-to-send
// LinkedIn note once you've applied), plus a deep link into LinkedIn's alumni
// explorer pre-filtered to UMD alumni at this company.
export default function Referrals({
  company,
  role,
  status,
  contacts,
}: {
  company: string;
  role: string | null;
  status: string;
  contacts: Contact[];
}) {
  const applied = APPLIED_STAGE.has(status);
  const show = contacts.slice(0, applied ? 3 : 2);
  const more = contacts.length - show.length;
  return (
    <div className="refs">
      {contacts.length > 0 && (
        <div className="refs-known">
          🤝 {contacts.length} here
          {applied ? " (reach out):" : ":"}
          {show.map((c, i) => (
            <span key={i} className="ref-one">
              {c.is_alum ? "🎓" : ""}
              {c.url ? (
                <a href={c.url} target="_blank" rel="noreferrer">
                  {c.name}
                </a>
              ) : (
                c.name
              )}
              {applied && <CopyButton text={reachOut(c, role, company)} />}
            </span>
          ))}
          {more > 0 ? <span className="ref-more">+{more} more</span> : null}
        </div>
      )}
      {company && (
        <a
          className="refs-alum"
          href={alumniSearchUrl(company)}
          target="_blank"
          rel="noreferrer"
        >
          🎓 find Terps at {company}
        </a>
      )}
    </div>
  );
}
