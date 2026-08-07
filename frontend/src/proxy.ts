import { NextRequest, NextResponse } from "next/server";

const protectedPrefixes = ["/create", "/history", "/task", "/assets", "/admin"];

export function proxy(request: NextRequest) {
  const path = request.nextUrl.pathname;
  const hasSession = Boolean(request.cookies.get("h3_session")?.value);
  const isProtected = protectedPrefixes.some(
    (prefix) => path === prefix || path.startsWith(`${prefix}/`),
  );
  if (isProtected && !hasSession) {
    return NextResponse.redirect(new URL("/login", request.url));
  }
  if (path === "/login" && hasSession) {
    return NextResponse.redirect(new URL("/create", request.url));
  }
  return NextResponse.next();
}

export const config = {
  matcher: ["/login", "/create/:path*", "/history/:path*", "/task/:path*", "/assets/:path*", "/admin/:path*"],
};
