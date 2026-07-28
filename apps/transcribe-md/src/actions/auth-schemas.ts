// Auth-input Zod schemas. Extracted from auth.ts so unit tests can
// import them without dragging in the prisma + next-auth runtime
// chain. The .max(254) caps mirror RFC 5321: keeps oversized rows
// out of the users.email column index and trips Resend's `to:`
// length pre-flight before send.
//
// Single source of truth for these definitions — auth.ts re-imports
// them so the action handlers stay in lock-step with what the tests
// pin.

import { z } from 'zod';

export const LoginSchema = z.object({
  email: z.string().email().max(254),
  password: z.string().min(1, 'Password is required'),
  // MFA — both optional. When the user has mfaEnabled=true,
  // loginAction requires one of these on the second submission.
  // Validated server-side; the client form decides when to send.
  totpToken: z.string().max(40).optional(),
  recoveryCode: z.string().max(40).optional(),
});

export const SignupSchema = z.object({
  email: z.string().email().max(254),
  /** Invite-only pilot (2026-07-28). Validated for SHAPE here; whether the code
   *  is real, live and unspent is decided server-side by checkInviteCode. */
  inviteCode: z.string().min(1, 'An invite code is required').max(64),
  password: z
    .string()
    .min(10, 'Password must be at least 10 characters')
    .regex(/[a-z]/, 'Password must contain a lowercase letter')
    .regex(/[A-Z]/, 'Password must contain an uppercase letter')
    .regex(/\d/, 'Password must contain a digit'),
  name: z.string().min(1, 'Name is required').max(120),
  acceptTerms: z.literal('on', {
    message: 'You must accept the terms of service',
  }),
});

/** Waitlist capture. Deliberately NOT a signup: no password, no terms
 *  acceptance, no account. The only required field is an email to reply to. */
export const WaitlistSchema = z.object({
  email: z.string().email().max(254),
  name: z.string().max(120).optional(),
  /** Free-text context the person volunteers (specialty, practice size).
   *  Capped short — this is a prospect note, and it must never become a place
   *  anyone types clinical detail. */
  note: z.string().max(500).optional(),
  source: z.string().max(60).optional(),
});
