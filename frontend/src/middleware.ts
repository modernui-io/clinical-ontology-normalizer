/**
 * Next.js Middleware for Route Protection
 *
 * This middleware:
 * - Protects authenticated routes by checking for auth cookie
 * - Redirects unauthenticated users to login
 * - Allows access to public routes (login, register, etc.)
 * - Supports SMART on FHIR launch flows
 */

import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

// Routes that don't require authentication
const PUBLIC_PATHS = [
  "/",
  "/landing",
  "/login",
  "/register",
  "/forgot-password",
  "/reset-password",
  "/smart/launch",
  "/smart/callback",
  "/smart/authorize",
];

// Static assets and API routes to skip
const SKIP_PATHS = [
  "/_next",
  "/api",
  "/favicon.ico",
  "/images",
  "/fonts",
];

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Skip static assets and API routes
  if (SKIP_PATHS.some((path) => pathname.startsWith(path))) {
    return NextResponse.next();
  }

  // Allow public paths
  const isPublicPath =
    PUBLIC_PATHS.some((path) => (path === "/" ? pathname === "/" : pathname.startsWith(path)));

  if (isPublicPath) {
    return NextResponse.next();
  }

  // Check for dev auth bypass
  if (process.env.NEXT_PUBLIC_AUTH_BYPASS === "true") {
    return NextResponse.next();
  }

  // Check for auth cookie (set by use-auth.tsx on login)
  const hasAuth = request.cookies.get("has_auth");

  if (!hasAuth || hasAuth.value !== "true") {
    // Store the requested URL for redirect after login
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("redirect", pathname);
    return NextResponse.redirect(loginUrl);
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    /*
     * Match all request paths except for the ones starting with:
     * - _next/static (static files)
     * - _next/image (image optimization files)
     * - favicon.ico (favicon file)
     */
    "/((?!_next/static|_next/image|favicon.ico).*)",
  ],
};
