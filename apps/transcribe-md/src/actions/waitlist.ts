'use server';

// ============================================================================
// Waitlist capture — and NOT a signup.
// ----------------------------------------------------------------------------
// The marketing CTA used to point at /signup, which created a real account with
// a practice, a role and a product entitlement. Behind the invite gate that
// would just fail, so the CTA now lands here instead.
//
// THE POINT OF THIS FILE IS WHAT IT DOES NOT DO. It writes one row to
// waitlist_entries. It does not create a User, a Practice, a session, an auth
// token, or a product grant. There is nothing here to sign in with, which is
// why an open endpoint is acceptable where open signup was not.
//
// `use server` files may export ONLY async functions — a shared constant or a
// type export here is a build error, so the schema lives in ./auth-schemas.
// ============================================================================

import prisma from '@meddoc/db';

import { headers } from 'next/headers';

import { logAudit } from '@/lib/audit';
import { RATE_LIMITS, checkRateLimit, clientIpFromHeaders } from '@/lib/rate-limit';

import { WaitlistSchema } from './auth-schemas';

export interface WaitlistState {
  ok: boolean;
  message?: string;
  errors?: Record<string, string>;
}

export async function joinWaitlistAction(
  _prev: WaitlistState,
  formData: FormData,
): Promise<WaitlistState> {
  const raw = Object.fromEntries(formData.entries());

  // Same per-IP budget as signup. It is not the primary defence — there is
  // nothing here worth farming — but an unbounded write endpoint is still an
  // unbounded write endpoint.
  const rl = checkRateLimit(RATE_LIMITS.SIGNUP, clientIpFromHeaders(await headers()));
  if (!rl.allowed) {
    const mins = Math.ceil(rl.retryAfterSec / 60);
    return {
      ok: false,
      errors: { email: `Too many attempts. Try again in ${mins} minute${mins === 1 ? '' : 's'}.` },
    };
  }

  const parsed = WaitlistSchema.safeParse(raw);
  if (!parsed.success) {
    return { ok: false, errors: { email: 'Enter a valid email address.' } };
  }

  const email = parsed.data.email.trim().toLowerCase();

  try {
    // Idempotent by email. Asking twice is not an error, and telling someone
    // "you are already on the list" would leak who is on it.
    await prisma.waitlistEntry.upsert({
      where: { email },
      create: {
        email,
        name: parsed.data.name?.trim() || null,
        note: parsed.data.note?.trim() || null,
        source: parsed.data.source?.trim() || null,
      },
      update: {
        name: parsed.data.name?.trim() || undefined,
        note: parsed.data.note?.trim() || undefined,
      },
    });

    void logAudit({
      action: 'WAITLIST_JOINED',
      targetType: 'WaitlistEntry',
      targetId: null,
      userId: null,
      practiceId: null,
      success: true,
      // Field names only, per the audit contract. No email in metadata.
      metadata: { source: parsed.data.source ?? 'unknown' },
    });
  } catch (err) {
    console.error('[waitlist] write failed:', err);
    // Fail SOFT. A waitlist row is a nicety; telling a prospective customer
    // their details broke something is worse than quietly retrying later.
    return {
      ok: true,
      message: "Thanks — we'll be in touch when there's room.",
    };
  }

  return { ok: true, message: "Thanks — we'll be in touch when there's room." };
}
