import { NextResponse, type NextRequest } from "next/server";

// The board is a personal, unauthenticated app bound to loopback. Reject any
// request whose Host isn't loopback, which blocks DNS-rebinding pages (and,
// because Next's server-action CSRF check compares Origin to Host, it closes
// that path too). Audit 2026-11-21, APP-01/APP-02.
const ALLOWED_HOSTS = new Set([
  "localhost:3737",
  "127.0.0.1:3737",
  "[::1]:3737",
]);

export function middleware(req: NextRequest) {
  const host = (req.headers.get("host") || "").toLowerCase();
  if (!ALLOWED_HOSTS.has(host)) {
    return new NextResponse("forbidden", { status: 403 });
  }
  // server actions: Origin, when present, must also be loopback
  const origin = req.headers.get("origin");
  if (origin && req.method !== "GET") {
    let oh = "";
    try {
      oh = new URL(origin).host.toLowerCase();
    } catch {}
    if (!ALLOWED_HOSTS.has(oh)) {
      return new NextResponse("forbidden", { status: 403 });
    }
  }
  return NextResponse.next();
}

export const config = { matcher: "/:path*" };
