'use server';

import { z } from 'zod';
import bcrypt from 'bcryptjs';

import prisma from '@meddoc/db';
import { Product, UserRole } from '@prisma/client';
import { signIn as nextAuthSignIn } from '@/lib/nextauth';

/** Strongly-typed login input. Passwords are NEVER echoed back in errors. */
const LoginSchema = z.object({
  email: z.string().email(),
  password: z.string().min(1, 'Password is required'),
});

/** Signup: stricter password policy + requires ToS.
 *
 *  T-M9: dropped the specialty field. The dropdown was captured but
 *  never persisted (no User.specialty column), so collecting it at
 *  signup was a UX no-op. Users pick specialty per-visit on
 *  /visits/new (which now defaults to the first specialty in the
 *  catalog so it's never empty). Future: if we add User.specialty,
 *  bring the field back and persist it. */
const SignupSchema = z.object({
  email: z.string().email(),
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

export interface FormErrorState {
  ok: false;
  errors: Record<string, string>;
  /** Preserves typed values between submissions so the user doesn't
   *  have to re-enter their form on a validation miss. */
  values?: Record<string, string>;
}
export interface FormOkState {
  ok: true;
  redirect: string;
  /** When set, the action technically succeeded (e.g., signup created
   *  the account) but a follow-up step (auto-login) didn't, so the
   *  caller should show a warning toast instead of the green
   *  success one. The email-bug lesson in T-M9: don't let a partial
   *  success toast as clean success. */
  warning?: string;
}

export type AuthActionState = FormOkState | FormErrorState | null;

function flattenZodErrors(err: z.ZodError): Record<string, string> {
  const out: Record<string, string> = {};
  for (const issue of err.issues) {
    const key = issue.path.join('.') || '_form';
    if (!out[key]) out[key] = issue.message;
  }
  return out;
}

/** Email + password login. On success returns `ok: true, redirect: '/dashboard'`
 *  so the client can router.push — we don't throw `redirect()` inside the
 *  action because NextAuth's internal signIn() redirect breaks the
 *  useActionState cycle in Next 16. */
export async function loginAction(
  _prev: AuthActionState,
  formData: FormData
): Promise<AuthActionState> {
  const raw = Object.fromEntries(formData.entries());
  const parsed = LoginSchema.safeParse(raw);
  if (!parsed.success) {
    return {
      ok: false,
      errors: flattenZodErrors(parsed.error),
      values: {
        email: String(raw.email ?? ''),
      },
    };
  }

  try {
    await nextAuthSignIn('credentials', {
      redirect: false,
      email: parsed.data.email,
      password: parsed.data.password,
    });
  } catch {
    return {
      ok: false,
      errors: { _form: 'Invalid email or password.' },
      values: { email: parsed.data.email },
    };
  }

  return { ok: true, redirect: '/dashboard' };
}

/** Signup: creates a synthetic Practice + User atomically, grants
 *  TRANSCRIBE_MD product, then signs in. */
export async function signupAction(
  _prev: AuthActionState,
  formData: FormData
): Promise<AuthActionState> {
  const raw = Object.fromEntries(formData.entries());
  const parsed = SignupSchema.safeParse(raw);
  if (!parsed.success) {
    return {
      ok: false,
      errors: flattenZodErrors(parsed.error),
      values: {
        email: String(raw.email ?? ''),
        name: String(raw.name ?? ''),
      },
    };
  }

  const emailLower = parsed.data.email.trim().toLowerCase();

  // Uniqueness check up front so we return a friendly error (rather than
  // surfacing a Prisma P2002). The race between this check and the
  // transaction is harmless — the `users.email` unique index catches it,
  // and the catch below rewrites it to the same friendly message.
  const existing = await prisma.user.findUnique({
    where: { email: emailLower },
    select: { id: true },
  });
  if (existing) {
    return {
      ok: false,
      errors: {
        email: 'An account with this email exists. Sign in instead.',
      },
      values: {
        email: emailLower,
        name: parsed.data.name,
      },
    };
  }

  const passwordHash = await bcrypt.hash(parsed.data.password, 12);

  // Synthetic Practice + User in one transaction so we don't orphan
  // Practice rows if the User insert fails.
  try {
    await prisma.$transaction(async (tx: typeof prisma) => {
      const practice = await tx.practice.create({
        data: {
          name: `Solo — ${parsed.data.name}`,
          // Random slug keeps it URL-safe and avoids a collision with
          // future "real" practice slugs. TranscribeMD UI never shows
          // the slug to the user.
          slug: `solo-${Math.random().toString(36).slice(2, 10)}-${Date.now().toString(36)}`,
        },
      });
      await tx.user.create({
        data: {
          email: emailLower,
          name: parsed.data.name,
          passwordHash,
          role: UserRole.DOCTOR,
          practiceId: practice.id,
          products: [Product.TRANSCRIBE_MD],
          emailVerified: null,
        },
      });
    });
  } catch (err) {
    console.error('[signup] create failed:', err);
    return {
      ok: false,
      errors: {
        _form: 'Could not create your account. Please try again.',
      },
      values: {
        email: emailLower,
        name: parsed.data.name,
      },
    };
  }

  // Auto sign-in. If this fails the account still exists and the user can
  // log in manually — we don't roll back on a transient auth error.
  try {
    await nextAuthSignIn('credentials', {
      redirect: false,
      email: emailLower,
      password: parsed.data.password,
    });
  } catch (err) {
    console.error('[signup] auto-login failed:', err);
    // Previously returned `{ ok: true, redirect: '/login' }` with no
    // marker, so the signup form fired its green success toast while
    // sending the user to the login page. Surface it as a warning so
    // the user understands why they landed on /login immediately
    // after "signing up".
    return {
      ok: true,
      redirect: '/login',
      warning: 'Account created — please sign in to continue.',
    };
  }

  return { ok: true, redirect: '/dashboard' };
}
