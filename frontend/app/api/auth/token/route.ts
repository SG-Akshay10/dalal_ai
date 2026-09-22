import { auth } from "@/lib/auth";
import { NextResponse } from "next/server";
import { SignJWT } from "jose";

/**
 * GET /api/auth/token
 *
 * Reads the NextAuth session server-side (decrypts the JWE cookie),
 * then mints a fresh plain HS256 JWT containing the user info.
 *
 * This plain JWT is what gets forwarded to FastAPI as a Bearer token.
 * FastAPI verifies it using the same AUTH_SECRET.
 *
 * Why not forward the raw NextAuth token?
 * NextAuth v5 uses JWE (encrypted JWT) by default. pyjwt in FastAPI
 * cannot decrypt JWE — it only handles plain signed JWTs (HS256/RS256).
 */
export async function GET() {
  const session = await auth();

  if (!session?.user?.id) {
    console.error(
      "[/api/auth/token] No session or user.id. session:",
      JSON.stringify({ hasSession: !!session, hasUser: !!session?.user, userId: session?.user?.id ?? null })
    );
    return NextResponse.json({ error: "Not authenticated" }, { status: 401 });
  }

  const secret = new TextEncoder().encode(process.env.AUTH_SECRET!);

  // Mint a plain HS256 JWT — FastAPI can verify this with pyjwt
  const token = await new SignJWT({
    sub: session.user.id,
    email: session.user.email ?? "",
    name: session.user.name ?? "",
  })
    .setProtectedHeader({ alg: "HS256" })
    .setIssuedAt()
    .setExpirationTime("1h")
    .sign(secret);

  return NextResponse.json({ token });
}
