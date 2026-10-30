"use client";

import { sankey, sankeyLinkHorizontal, sankeyJustify } from "d3-sankey";
import { type Application } from "./lib/status";

// A classic job-hunt Sankey (SankeyArt style): light theme, green = advancing,
// gray = no reply, red = rejected. Applications fan in from their source
// channel, then flow through the funnel. Built with d3-sankey so multiple
// sources can converge into shared No-reply / Rejected pools. Derived from each
// app's current status + discovery source.
export default function Funnel({ apps }: { apps: Application[] }) {
  if (apps.length === 0)
    return <div className="empty">No applications yet to chart.</div>;

  const srcLabel = (s: string | null) =>
    s === "simplify" ? "Simplify" : s === "ats" ? "Company boards" : "Email / direct";

  // per-source outcome counts + OA-stage sub-counts
  const bySource = new Map<string, { noReply: number; rejected: number; oa: number; total: number }>();
  let interviewCt = 0, inProgressCt = 0, missedCt = 0;
  for (const a of apps) {
    const sl = srcLabel(a.source);
    const rec = bySource.get(sl) || { noReply: 0, rejected: 0, oa: 0, total: 0 };
    rec.total++;
    if (a.status === "applied") rec.noReply++;
    else if (a.status === "rejected") rec.rejected++;
    else {
      rec.oa++; // reached the OA stage (oa/interview/team_match/offer/missed)
      if (a.status === "oa") inProgressCt++;
      else if (a.status === "missed") missedCt++;
      else interviewCt++; // interview / team_match / offer
    }
    bySource.set(sl, rec);
  }

  const GREEN = "green", GRAY = "gray", RED = "red";
  const nodes: { name: string; cat: string }[] = [];
  const idx = new Map<string, number>();
  const node = (name: string, cat: string) => {
    if (!idx.has(name)) { idx.set(name, nodes.length); nodes.push({ name, cat }); }
    return idx.get(name)!;
  };
  const links: { source: number; target: number; value: number; cat: string }[] = [];
  const link = (s: number, t: number, v: number, cat: string) => {
    if (v > 0) links.push({ source: s, target: t, value: v, cat });
  };

  const nApplied = node("Applied", GREEN);
  const nNoReply = node("No reply", GRAY);
  const nOA = node("Online assessment", GREEN);
  const nRejected = node("Rejected", RED);
  const nInProg = node("In progress", GREEN);
  const nInterview = node("Interview", GREEN);

  // sources sorted biggest-first for a tidy stack
  for (const [sl, rec] of [...bySource.entries()].sort((a, b) => b[1].total - a[1].total)) {
    const ns = node(sl, GREEN);
    link(nApplied, ns, rec.total, GREEN);
    link(ns, nNoReply, rec.noReply, GRAY);
    link(ns, nOA, rec.oa, GREEN);
    link(ns, nRejected, rec.rejected, RED);
  }
  link(nOA, nInterview, interviewCt, GREEN);
  link(nOA, nInProg, inProgressCt, GREEN);
  link(nOA, nRejected, missedCt, RED);

  // layout
  const VW = 1040, VH = 560, MT = 56, MB = 28, ML = 96, MR = 124;
  const graph = sankey<any, any>()
    .nodeWidth(15)
    .nodePadding(17)
    .nodeAlign(sankeyJustify)
    .extent([[ML, MT], [VW - MR, VH - MB]])({
      nodes: nodes.map((d) => ({ ...d })),
      links: links.map((d) => ({ ...d })),
    });
  const linkPath = sankeyLinkHorizontal();
  const midX = VW / 2;
  // per-stage palette (matches the board's status colors); sources default blue
  const PAL: Record<string, string> = {
    Applied: "#6b9bff", "No reply": "#737a8a", "Online assessment": "#f2b84b",
    Rejected: "#ff6b6b", "In progress": "#c7a2ff", Interview: "#a978ff",
    Offer: "#3ecf8e",
  };
  const col = (name: string) => PAL[name] || "#5b8cff";

  return (
    <div className="funnel-wrap">
      <svg viewBox={`0 0 ${VW} ${VH}`} className="sankey" role="img">
        <text x={VW / 2} y={32} textAnchor="middle" fontSize={21} fontWeight={800} fill="#8aa6ff">
          Internship Applications
        </text>

        {graph.links!.map((l: any, i: number) => (
          <path key={i} d={linkPath(l) || undefined} fill="none" stroke={col(l.target.name)}
            strokeOpacity={0.4} strokeWidth={Math.max(1.4, l.width)} />
        ))}

        {graph.nodes!.map((n: any, i: number) => {
          const right = n.x0 < midX;
          const lx = right ? n.x1 + 8 : n.x0 - 8;
          return (
            <g key={i}>
              <rect x={n.x0} y={n.y0} width={n.x1 - n.x0} height={Math.max(n.y1 - n.y0, 1)} rx={2} fill={col(n.name)} />
              <text x={lx} y={(n.y0 + n.y1) / 2} textAnchor={right ? "start" : "end"}
                dominantBaseline="central" fontSize={12.5} fill="#e6e9ef" fontWeight={600}>
                <tspan x={lx} dy="-3">{n.name}</tspan>
                <tspan x={lx} dy="15" fill="#9aa2b1" fontWeight={700}>{n.value}</tspan>
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}
