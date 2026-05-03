'use server';

import { z } from 'zod';
import bcrypt from 'bcryptjs';
import { headers } from 'next/headers';

import prisma from '@meddoc/db';
import { AuthTokenPurpose, Product, UserRole } from '@prisma/client';
import { signIn as nextAuthSignIn } from '@/lib/nextauth';
import { createAuthToken } from '@/lib/auth-tokens';
import { isEmailDeliveryEnabled } from '@/lib/email-enabled';
import { isAutoConfirmDomain } from '@/lib/email-auto-confirm';
import { sendEmailVerification } from '@/lib/email';
import { APP_URL } from '@/lib/constants';
import {
  RATE_LIMITS,
  checkRateLimit,
  clientIpFromHeaders,
  type RateLimitRule,
} from '@/lib/rate-limit';

/** T-M18.3 A20: pre-computed dummy bcrypt hash, used to equalize the
 *  wall-clock time of loginAction paths that would otherwise skip the
 *  pre-check bcrypt.compare. Computed once at module load. */
const DUMMY_PASSWORD_HASH = bcrypt.hashSync(
  'timing-equalizer-never-matches',
  12
);

/** Server-action rate-limit helper. Unlike route handlers this can't
 *  return a NextResponse — we surface the 429 as a FormErrorState so
 *  the existing useActionState wiring shows it cleanly. */
async function actionRateLimitOrError(
  rule: RateLimitRule,
  values?: Record<string, string>
): Promise<FormErrorState | null> {
  const h = await headers();
  const ip = clientIpFromHeaders(h);
  const rl = checkRateLimit(rule, ip);
  if (rl.allowed) return null;
  const mins = Math.ceil(rl.retryAfterSec / 60);
  return {
    ok: false,
    errors: {
      _form: `Too many attempts. Try again in ${mins} minute${mins === 1 ? '' : 's'}.`,
    },
    values,
  };
}

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
  /** T-M16.2: signals that the credentials were correct but the
   *  account hasn't verified its email yet. The login form shows a
   *  "resend verification email" affordance when this is set. Holds
   *  the attempted email so the resend button knows what to ship. */
  needsVerificationFor?: string;
  /** Symmetric of CRM's `NO_MEDDOC_PRO_HAS_TRANSCRIBE` UX: when the
   *  user has MEDDOC_PRO but not TRANSCRIBE_MD, the form surfaces a
   *  one-click button to the CRM app instead of just saying "no
   *  access". Only set when the password was verified. */
  crossAppRedirect?: {
    message: string;
    url: string;
    buttonLabel: string;
  };
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
  const email = String(raw.email ?? '');

  const blocked = await actionRateLimitOrError(RATE_LIMITS.LOGIN, { email });
  if (blocked) return blocked;

  const parsed = LoginSchema.safeParse(raw);
  if (!parsed.success) {
    return {
      ok: false,
      errors: flattenZodErrors(parsed.error),
      values: {
        email,
      },
    };
  }

  // T-M16.2: pre-check the email-verification gate BEFORE handing off
  // to NextAuth. If credentials are correct but the account isn't
  // verified, we want to tell the user specifically rather than
  // showing the generic "invalid email or password" — otherwise they
  // have no way to discover the resend-verification link. When gate
  // is off (no RESEND) the check is skipped entirely.
  if (isEmailDeliveryEnabled()) {
    const preCheckUser = await prisma.user.findUnique({
      where: { email: parsed.data.email.trim().toLowerCase() },
      select: {
        id: true,
        passwordHash: true,
        emailVerified: true,
        isActive: true,
        lockedUntil: true,
      },
    });
    const isUnverifiedCandidate =
      !!preCheckUser?.isActive &&
      (!preCheckUser.lockedUntil || preCheckUser.lockedUntil < new Date()) &&
      preCheckUser.emailVerified === null;
    if (isUnverifiedCandidate && preCheckUser) {
      const pwOk = await bcrypt.compare(
        parsed.data.password,
        preCheckUser.passwordHash
      );
      if (pwOk) {
        // Password correct, email not verified — block and surface
        // the resend affordance.
        return {
          ok: false,
          errors: {
            _form: 'Please verify your email before signing in.',
          },
          values: { email: parsed.data.email },
          needsVerificationFor: parsed.data.email,
        };
      }
      // Wrong password — fall through to the generic error below so
      // we don't leak that the account is unverified.
    } else {
      // T-M18.3 A20: verified / missing / locked / inactive paths skip
      // the pre-check bcrypt above. Run a dummy compare here so the
      // wall-clock time of this block matches the unverified branch —
      // prevents an attacker from enumerating "email exists + unverified"
      // by measuring response time.
      await bcrypt
        .compare(parsed.data.password, DUMMY_PASSWORD_HASH)
        .catch(() => false);
    }
  }

  // F9-1 + product-separation: Pre-check product entitlement so the
  // form surfaces a specific "no access" message (and, if the user
  // has MEDDOC_PRO, a one-click cross-app redirect) instead of the
  // generic "invalid credentials" the authorize callback returns.
  // Authorize remains the authoritative security gate; this block is
  // purely UX. Always runs (not gated on email delivery) so the
  // message is consistent across envs.
  const entitlementUser = await prisma.user.findUnique({
    where: { email: parsed.data.email.trim().toLowerCase() },
    select: {
      passwordHash: true,
      products: true,
      isActive: true,
      lockedUntil: true,
    },
  });
  const isEntitlementCandidate =
    !!entitlementUser?.isActive &&
    (!entitlementUser.lockedUntil ||
      entitlementUser.lockedUntil < new Date()) &&
    !entitlementUser.products.includes(Product.TRANSCRIBE_MD) &&
    // Phase 1A: SUPER_ADMIN bypass — skip the "no entitlement" UX
    // message because the authorize() gate allows them through, and
    // the cross-app-redirect message would send them to the wrong
    // surface.
    !entitlementUser.products.includes(Product.SUPER_ADMIN);
  if (isEntitlementCandidate && entitlementUser) {
    const pwOk = await bcrypt.compare(
      parsed.data.password,
      entitlementUser.passwordHash
    );
    if (pwOk) {
      // Cross-app: if the user has MEDDOC_PRO but is missing
      // TRANSCRIBE_MD, send them to the CRM login. Symmetric with the
      // /api/auth/check-entitlement flow on the meddoc-pro side.
      if (entitlementUser.products.includes(Product.MEDDOC_PRO)) {
        const meddocProUrl =
          process.env.NEXT_PUBLIC_MEDDOC_PRO_APP_URL ??
          'https://pro.quillmd.com';
        return {
          ok: false,
          errors: {
            _form:
              'This account is for MedDoc Pro, not TranscribeMD. Continue to the right app:',
          },
          values: { email: parsed.data.email },
          crossAppRedirect: {
            message:
              'This account is for MedDoc Pro, not TranscribeMD. Continue to the right app:',
            url: `${meddocProUrl}/login`,
            buttonLabel: 'Go to MedDoc Pro',
          },
        };
      }
      return {
        ok: false,
        errors: {
          _form:
            'Your account does not have access to TranscribeMD. Contact your practice admin to enable it.',
        },
        values: { email: parsed.data.email },
      };
    }
    // Wrong password — fall through to the generic error so we don't
    // leak whether the email exists but lacks the product.
  } else {
    // Mirror the timing equalizer pattern from the email-verify block
    // so an attacker can't distinguish "account missing entitlement"
    // from "no such account" by response latency.
    await bcrypt
      .compare(parsed.data.password, DUMMY_PASSWORD_HASH)
      .catch(() => false);
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

  return { ok: true, redirect: await postLoginRedirectFor() };
}

/** Computes the post-login destination based on the request host. The
 *  app.quillmd.com flow lands on `/dashboard` (clinician home);
 *  admin.quillmd.com lands on `/admin` (the platform-admin overview).
 *  Without this branch a SUPER_ADMIN signing in via admin.quillmd.com
 *  would be sent to `/dashboard`, which the strict Caddy block on the
 *  admin host returns 404 for — leaving the user stuck on a blank
 *  page after a successful sign-in. */
async function postLoginRedirectFor(): Promise<string> {
  try {
    const h = await headers();
    const host = (h.get('x-forwarded-host') ?? h.get('host') ?? '')
      .toLowerCase()
      .split(':')[0];
    if (host === 'admin.quillmd.com' || host?.startsWith('admin.')) {
      return '/admin';
    }
  } catch {
    // headers() outside a request context — fall through to the default
  }
  return '/dashboard';
}

/** Signup: creates a synthetic Practice + User atomically, grants
 *  TRANSCRIBE_MD product, then signs in. */
export async function signupAction(
  _prev: AuthActionState,
  formData: FormData
): Promise<AuthActionState> {
  const raw = Object.fromEntries(formData.entries());
  const emailField = String(raw.email ?? '');
  const nameField = String(raw.name ?? '');

  const blocked = await actionRateLimitOrError(RATE_LIMITS.SIGNUP, {
    email: emailField,
    name: nameField,
  });
  if (blocked) return blocked;

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

  // T-M16.2: email-verification gate decides whether to stamp
  // emailVerified at create time. When RESEND is enabled we leave it
  // null and send a verify link (the user clicks → emailVerified set
  // → they can sign in). When RESEND is unavailable we stamp
  // createdAt so the unverified-login gate (also conditional on
  // isEmailDeliveryEnabled) doesn't block them.
  //
  // Phase 7-QA: QA-only bypass. If the email's domain is on the
  // EMAIL_AUTO_CONFIRM_DOMAINS allowlist (production: only
  // `quillmd-test.local`), treat it as if email delivery were disabled
  // — stamp emailVerified at create time, skip the verify-email
  // dispatch, auto-login via the no-verification path. Real-mail
  // domains are denylisted inside isAutoConfirmDomain as a defensive
  // safeguard against misconfiguration.
  const autoConfirm = isAutoConfirmDomain(emailLower);
  if (autoConfirm) {
    console.warn(
      `[QA-BYPASS] auto-confirmed email for ${emailLower} (domain on EMAIL_AUTO_CONFIRM_DOMAINS allowlist)`
    );
  }
  const verifyEnabled = isEmailDeliveryEnabled() && !autoConfirm;
  const nowForVerified = verifyEnabled ? null : new Date();

  // Synthetic Practice + User in one transaction so we don't orphan
  // Practice rows if the User insert fails.
  let createdUserId: string | null = null;
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
      const user = await tx.user.create({
        data: {
          email: emailLower,
          name: parsed.data.name,
          passwordHash,
          role: UserRole.DOCTOR,
          practiceId: practice.id,
          products: [Product.TRANSCRIBE_MD],
          emailVerified: nowForVerified,
        },
        select: { id: true },
      });
      createdUserId = user.id;
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

  // T-M16.2: verification-gate branch — mint token + send email,
  // DON'T auto-login. User lands on /check-email.
  if (verifyEnabled && createdUserId) {
    try {
      const { token } = await createAuthToken({
        userId: createdUserId,
        purpose: AuthTokenPurpose.EMAIL_VERIFICATION,
        expiresInMs: 24 * 60 * 60 * 1000,
      });
      const verifyUrl = `${APP_URL}/api/auth/verify-email?token=${encodeURIComponent(token)}`;
      await sendEmailVerification({
        toEmail: emailLower,
        verifyUrl,
        userName: parsed.data.name,
      });
    } catch (err) {
      // Verification email failed — account exists, user can request
      // a resend from /check-email. Don't roll back.
      console.error('[signup] verification email failed:', err);
    }
    return {
      ok: true,
      redirect: `/check-email?email=${encodeURIComponent(emailLower)}`,
    };
  }

  // No verification gate — original auto-login path.
  try {
    await nextAuthSignIn('credentials', {
      redirect: false,
      email: emailLower,
      password: parsed.data.password,
    });
  } catch (err) {
    console.error('[signup] auto-login failed:', err);
    return {
      ok: true,
      redirect: '/login',
      warning: 'Account created — please sign in to continue.',
    };
  }

  return { ok: true, redirect: '/dashboard' };
}
