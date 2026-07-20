import "server-only";

import { getToken } from "next-auth/jwt";
import { authConfig } from "@meddoc/auth";

export interface SignedSessionAuthority {
  cookiePresent: boolean;
  sessionId: string | null;
  userId: string | null;
}

const secureCookie = process.env.NODE_ENV === "production";
const sessionCookieName = secureCookie
  ? "__Secure-authjs.session-token"
  : "authjs.session-token";

function hasSessionCookie(headers: Headers): boolean {
  const cookieHeader = headers.get("cookie");
  if (!cookieHeader) return false;
  return cookieHeader.split(";").some((entry) => {
    const name = entry.trim().split("=", 1)[0];
    return name === sessionCookieName || name?.startsWith(`${sessionCookieName}.`);
  });
}

function nonEmptyString(value: unknown): string | null {
  return typeof value === "string" && value.trim().length > 0 ? value : null;
}

/**
 * Decode only the signed Auth.js cookie. This intentionally does not call
 * auth(), the JWT callback, Prisma, or the current-session validator: logout
 * must still be able to identify and revoke its durable row during a database
 * validation outage, before any local cookie is cleared.
 */
export async function readSignedSessionAuthority(
  headers: Headers,
): Promise<SignedSessionAuthority> {
  const cookiePresent = hasSessionCookie(headers);
  if (!cookiePresent) {
    return { cookiePresent: false, sessionId: null, userId: null };
  }
  const secret = authConfig.secret;
  if (!secret) {
    return { cookiePresent: true, sessionId: null, userId: null };
  }
  const token = await getToken({
    req: { headers },
    cookieName: sessionCookieName,
    secureCookie,
    secret,
  });
  if (!token) {
    return { cookiePresent: true, sessionId: null, userId: null };
  }
  const tokenId = nonEmptyString(token.id);
  const subject = nonEmptyString(token.sub);
  const userId = tokenId && subject && tokenId !== subject ? null : tokenId ?? subject;
  return {
    cookiePresent: true,
    sessionId: nonEmptyString(token.sessionId),
    userId,
  };
}
