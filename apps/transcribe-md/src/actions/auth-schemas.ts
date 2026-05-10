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
