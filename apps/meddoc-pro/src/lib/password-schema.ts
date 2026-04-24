import { z } from 'zod';

// Mirror of apps/transcribe-md/src/app/api/settings/change-password/route.ts
// PasswordSchema so both apps apply the same policy. 10 chars + one of
// each character class. If you change this, change the transcribe-md
// equivalent too — the two flows share user records.
export const PasswordSchema = z
  .string()
  .min(10, 'Password must be at least 10 characters')
  .regex(/[a-z]/, 'Password must contain a lowercase letter')
  .regex(/[A-Z]/, 'Password must contain an uppercase letter')
  .regex(/\d/, 'Password must contain a digit');

export function validatePassword(
  raw: unknown
): { ok: true } | { ok: false; error: string } {
  const parsed = PasswordSchema.safeParse(raw);
  if (parsed.success) return { ok: true };
  return { ok: false, error: parsed.error.issues[0]?.message ?? 'Invalid password' };
}
