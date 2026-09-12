import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

// Public paths that do not require authentication
const PUBLIC_PATHS = ["/auth"];

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Allow Next.js internals, static files, favicon, etc.
  if (
    pathname.startsWith("/_next") ||
    pathname.startsWith("/api") ||
    pathname.startsWith("/static") ||
    pathname.endsWith(".ico") ||
    pathname.endsWith(".svg") ||
    pathname.endsWith(".png") ||
    pathname.endsWith(".jpg") ||
    pathname.endsWith(".webp")
  ) {
    return NextResponse.next();
  }

  // Check if route is public
  const isPublic = PUBLIC_PATHS.some(
    (p) => pathname === p || pathname.startsWith(`${p}/`)
  );

  // Check for auth cookie
  const token = request.cookies.get("stockportfolio_token")?.value;

  // If unauthenticated and accessing a protected route -> redirect to /auth
  if (!token && !isPublic) {
    const authUrl = new URL("/auth", request.url);
    if (pathname !== "/") {
      authUrl.searchParams.set("redirect", pathname);
    }
    return NextResponse.redirect(authUrl);
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    /*
     * Match all request paths except static files and images:
     */
    "/((?!_next/static|_next/image|favicon.ico).*)",
  ],
};
