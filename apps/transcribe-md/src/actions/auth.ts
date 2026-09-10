'use server';

import { z } from 'zod';
import bcrypt from 'bcryptjs';
import { headers } from 'next/headers';

import prisma from '@meddoc/db';
import type { TransactionClient } from '@meddoc/db';
import { AuthTokenPurpose, PracticeRole, Product, UserRole } from '@prisma/client';
import { signIn as nextAuthSignIn } from '@/lib/nextauth';
import { requestHost } from '@/lib/practice-host';
import { createAuthToken } from '@/lib/auth-tokens';
import { isEmailDeliveryEnabled } from '@/lib/email-enabled';
import { isAutoConfirmDomain } from '@/lib/email-auto-confirm';
import { sendEmailVerification, sendAccountExistsEmail } from '@/lib/email';
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

// LoginSchema + SignupSchema live in ./auth-schemas so the unit
// tests can import them without pulling in this file's prisma +
// next-auth chain. Importable directly from '@/actions/auth-schemas'
// — not re-exported here because Next's "use server" boundary only
// allows async-function exports from a server-actions file.
import { LoginSchema, SignupSchema } from './auth-schemas';
import {
  INVITE_REJECTED_MESSAGE,
  checkInviteCode,
  consumeDbInviteCode,
} from '@/lib/signup-invite';
import { logAudit } from '@/lib/audit';
// B7 step 3c, door 1 of 3 — see the call site inside the signup transaction.
import { grantPromoCredit } from '@meddoc/ai';
import { recoveryHref } from '@/lib/recovery-href';

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
  /** Set when the account has mfaEnabled=true and the form has not
   *  yet supplied a totpToken / recoveryCode. The form switches to
   *  MFA mode (renders the 6-digit field + recovery-code link) and
   *  re-submits with the second factor included. The email + password
   *  are kept in `values` so the user doesn't retype. */
  mfaRequired?: boolean;
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

  // MFA preflight (closes shadow-audit HIPAA_FINDING_001). When the
  // user has mfaEnabled=true and the form has not supplied a second
  // factor, return mfaRequired so the client switches to the MFA
  // input and re-submits with the token. Re-runs the bcrypt check to
  // avoid letting an attacker enumerate "account exists with MFA" by
  // timing — every email path through here pays the bcrypt cost.
  const mfaUser = await prisma.user.findUnique({
    where: { email: parsed.data.email.trim().toLowerCase() },
    select: {
      passwordHash: true,
      mfaEnabled: true,
      isActive: true,
      lockedUntil: true,
    },
  });
  const credentialsValidForMfaCheck =
    !!mfaUser?.isActive &&
    (!mfaUser.lockedUntil || mfaUser.lockedUntil < new Date()) &&
    (await bcrypt.compare(parsed.data.password, mfaUser.passwordHash));
  if (credentialsValidForMfaCheck && mfaUser?.mfaEnabled) {
    if (!parsed.data.totpToken && !parsed.data.recoveryCode) {
      return {
        ok: false,
        errors: {},
        values: { email: parsed.data.email },
        mfaRequired: true,
      };
    }
  } else {
    // Equalize wall-clock for non-MFA paths — every login pays the
    // same bcrypt cost regardless of whether MFA is on.
    await bcrypt
      .compare(parsed.data.password, DUMMY_PASSWORD_HASH)
      .catch(() => false);
  }

  try {
    await nextAuthSignIn('credentials', {
      redirect: false,
      email: parsed.data.email,
      password: parsed.data.password,
      totpToken: parsed.data.totpToken ?? '',
      recoveryCode: parsed.data.recoveryCode ?? '',
    });
  } catch (err) {
    // ⚠️ #182(4) — A SESSION-TRACKING REFUSAL IS NOT A CREDENTIALS FAILURE, AND
    // SAYING SO WAS ACTIVELY HARMFUL. This `catch` used to swallow EVERY error
    // from `nextAuthSignIn` and report "Invalid email or password." — so when
    // #182(c) made the jwt callback refuse a sign-in whose UserSession insert
    // failed, a doctor with CORRECT credentials was told their password was
    // wrong. On the MFA path it was worse: they were told the recovery code was
    // invalid, and each retry burned another single-use code.
    //
    // The message is checked through the CAUSE CHAIN because Auth.js wraps the
    // error thrown by a callback; matching only `err.message` misses it.
    if (isSessionTrackingRefusal(err)) {
      return {
        ok: false,
        errors: {
          _form:
            "Sign-in couldn't be completed — session tracking failed. Your " +
            'credentials were accepted. Please try again.',
        },
        values: { email: parsed.data.email },
        // Keep the form in MFA mode if that is where they were, so a retry does
        // not send them back to the start of the flow.
        ...(credentialsValidForMfaCheck && mfaUser?.mfaEnabled
          ? { mfaRequired: true }
          : {}),
      };
    }

    // If MFA was required and we got here, the second factor is
    // wrong. Surface a specific message + keep the form in MFA mode.
    if (credentialsValidForMfaCheck && mfaUser?.mfaEnabled) {
      return {
        ok: false,
        errors: {
          _form: parsed.data.recoveryCode
            ? 'Invalid recovery code.'
            : 'Invalid 6-digit code. Try again.',
        },
        values: { email: parsed.data.email },
        mfaRequired: true,
      };
    }
    return {
      ok: false,
      errors: { _form: 'Invalid email or password.' },
      values: { email: parsed.data.email },
    };
  }

  return { ok: true, redirect: await postLoginRedirectFor() };
}

/**
 * Is this error the jwt callback's refusal to mint a session it could not
 * track — as opposed to a credentials failure?
 *
 * ⚠️ THE CAUSE CHAIN IS WALKED, NOT JUST `err.message`. Auth.js wraps an error
 * thrown from a callback, so the marker is one or more levels down. A check
 * that reads only the top-level message returns false for every real instance
 * and the truthful branch is never taken — a fix that compiles and does
 * nothing.
 */
function isSessionTrackingRefusal(err: unknown): boolean {
  let cur: unknown = err;
  for (let depth = 0; cur instanceof Error && depth < 8; depth += 1) {
    if (cur.message.includes('SESSION_TRACKING_FAILED')) return true;
    cur = (cur as { cause?: unknown }).cause;
  }
  return false;
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
    // ADMIN-2 — the Host header ONLY, through the one reader. This used to
    // prefer `x-forwarded-host`, which neither ingress hop sets and the trusted
    // Caddy hop passes through from the client (lib/practice-host.ts header).
    // For every honest request the two are equal, so this changes nothing but
    // a forged header's reach.
    const host = (await requestHost()) ?? '';
    if (host === 'admin.quillmd.com' || host?.startsWith('admin.')) {
      return '/admin';
    }
  } catch {
    // headers() outside a request context — fall through to the default
  }
  return recoveryHref();
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

  // ── INVITE GATE (2026-07-28) ─────────────────────────────────────────────
  //
  // Checked HERE, before the email lookup below, and the order is the point.
  // That lookup deliberately returns an identical response for an existing and
  // a new email (PR-F, below). Gating first means a prober without a code never
  // reaches it and learns nothing about which emails exist — the gate makes
  // enumeration strictly harder rather than opening a new oracle.
  //
  // The rejection message is the same for every reason (invalid / expired /
  // revoked / exhausted). Distinguishing them would tell a prober which codes
  // are real.
  const invite = await checkInviteCode(String(raw.inviteCode ?? ''));
  if (!invite.ok) {
    void logAudit({
      action: 'SIGNUP_REJECTED_NO_INVITE',
      targetType: 'User',
      targetId: null,
      userId: null,
      practiceId: null,
      success: false,
      // The REASON is recorded for the operator; the user is not told it.
      // No email address — a rejected signup is not an account, and logging
      // the address would build the very list the gate exists to prevent.
      metadata: { reason: invite.reason },
    });
    return {
      ok: false,
      errors: { inviteCode: INVITE_REJECTED_MESSAGE },
      values: { email: String(raw.email ?? ''), name: String(raw.name ?? '') },
    };
  }

  // Round 3 PR-F (A02-P1-001) — signup anti-enumeration.
  //
  // Pre-PR-F: existing-email path returned a UI-distinct error
  // ("An account with this email exists. Sign in instead.") which let
  // an attacker map every customer email by enumerating signups.
  //
  // Post-PR-F: existing-email path returns the SAME response shape as
  // the new-signup happy path (`ok: true` + `redirect: /check-email`)
  // and runs equivalent work (dummy bcrypt + send "account exists"
  // email to the real user) so an attacker probing for existing
  // accounts sees identical response body + similar wall-clock timing.
  // The real user gets a "you already have an account" nudge in their
  // inbox; the attacker gets nothing actionable.
  const existing = await prisma.user.findUnique({
    where: { email: emailLower },
    select: { id: true, name: true },
  });
  if (existing) {
    // Equalize wall-clock timing with the new-signup path. The
    // new-signup path runs:
    //   - bcrypt.hash(password, 12)             ~150ms
    //   - prisma.$transaction (practice + user) ~30ms
    //   - createAuthToken                       ~5ms
    //   - sendEmailVerification (Resend POST)   ~variable, fire-and-forget OK
    // Burning a bcrypt.hash of equivalent cost is the dominant
    // equalizer; the rest is sub-tens-of-ms noise.
    await bcrypt.hash(parsed.data.password, 12);

    // Send "you already have an account" email to the real user.
    // Fire-and-forget: same as new-signup verification email — a
    // Resend hiccup mustn't reveal an error path.
    void sendAccountExistsEmail({
      toEmail: emailLower,
      userName: existing.name ?? null,
      signInUrl: `${APP_URL}/login`,
    }).catch((err: unknown) => {
      console.error('[signup] account-exists email failed:', err);
    });

    return {
      ok: true,
      redirect: `/check-email?email=${encodeURIComponent(emailLower)}`,
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
  // ⚠️ B7 step 3c — CAPTURED INSIDE THE TRANSACTION, AUDITED AFTER IT COMMITS.
  // Writing the audit row inside the closure would record a grant that a later
  // statement in the same transaction can still roll back — the invite-race
  // throw below does exactly that. An audit row for a grant that does not exist
  // is worse than no row: it is a false record on the one table an operator
  // trusts to say what happened. `logAudit` is fire-and-forget, so it also
  // cannot participate in the rollback even if it were called here.
  let grantForAudit: {
    practiceId: string;
    amountMicroUsd: bigint;
    balanceAfter: bigint;
    seq: bigint;
  } | null = null;
  try {
    await prisma.$transaction(async (tx: TransactionClient) => {
      // ⚠️ T8 — AN INVITE MAY ADMIT INTO AN EXISTING PRACTICE.
      //
      // `membership` is non-null only when the code carries BOTH a practice and
      // a role; the database refuses them apart, so this branch cannot admit
      // somebody to a clinic without saying what they may do there.
      //
      // NULL is the LEGACY contract and it is unchanged: mint a fresh solo
      // practice and make the redeemer its OWNER. Every invite issued before T8
      // is in that state, and none were backfilled — there is no practice they
      // were "meant" to point at, so inventing one would be a guess wearing a
      // migration's authority.
      const membership = invite.source === 'db' ? invite.membership : null;
      const practice = membership
        ? await tx.practice.findUniqueOrThrow({
            where: { id: membership.practiceId },
            select: { id: true },
          })
        : await tx.practice.create({
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
          // ⚠️ T6 — REQUIRED IN PRACTICE, BY THE DATABASE. A signup mints its own
          // solo practice one statement above, so the new user owns it by
          // construction. Without this line the CHECK
          // `users_active_member_has_practice_role` refuses the row and EVERY
          // SIGNUP FAILS — the T3 shape, where the one site that mattered was
          // the real production path rather than the one CI happened to surface.
          // ⚠️ T8 — THE INVITE'S ROLE WINS, and OWNER is only the fallback for
          // the solo-practice path. Defaulting to OWNER here would have made
          // every invited CLINICIAN or TECH an owner of the clinic they joined,
          // which is the failure the both-or-neither CHECK exists to prevent —
          // and it would have been invisible, because the account would work.
          practiceRole: membership
            ? (membership.practiceRole as PracticeRole)
            : PracticeRole.OWNER,
          products: [Product.TRANSCRIBE_MD],
          emailVerified: nowForVerified,
        },
        select: { id: true },
      });
      createdUserId = user.id;

      // Spend the invite in the SAME transaction that creates the account, so
      // a code with one use left cannot be spent twice by concurrent signups.
      // `updateMany` with the limit in its WHERE lets the database decide the
      // race; count 0 means somebody else took the last use, and throwing here
      // rolls the practice and user back with it.
      if (invite.source === 'db') {
        const spent = await consumeDbInviteCode(tx, invite.inviteCodeId);
        if (!spent) throw new Error('INVITE_EXHAUSTED_RACE');
      }

      // ⚠️ B7 STEP 3c, DOOR 1 OF 3 — THE PROMO GRANT IS PART OF BECOMING A
      // PRACTICE, NOT AN EVENT THAT HAPPENED ONCE IN A BACKFILL.
      //
      // Without this, a practice created after the backfill holds no `grant`
      // row, so `readPracticeBalance` reports spendable 0, so `decideAdmission`
      // returns `insufficient_balance`, so `admitVisitOrThrow` throws — and the
      // FIRST VISIT OF EVERY NEW SIGNUP fails the moment `BILLING_ENFORCED` is
      // turned on. `billing-grant.ts`'s header records that chain in full; the
      // discovery channel would have been a real doctor's first recording.
      //
      // ⚠️ IT RUNS ONLY ON THE **CREATE** BRANCH, AND THAT IS A CORRECTNESS
      // REQUIREMENT RATHER THAN AN OPTIMISATION. A practice minted three
      // statements ago CANNOT already hold a grant, so this insert cannot
      // collide — which is the only way a grant is safe inside a transaction
      // that has to survive.
      //
      // ⚠️ THE FIRST VERSION RAN ON BOTH BRANCHES AND WOULD HAVE SILENTLY
      // DESTROYED SIGNUPS. The reasoning was that a T8 invite into an already
      // funded practice would collide on the global unique, be absorbed by
      // `grantPromoCredit`, and return `already_granted` — true of the
      // JavaScript, and worthless, because **a unique violation aborts the
      // whole Postgres transaction**. Catching the error in application code
      // does not recover it. Measured on QA, 2026-08-12:
      //
      //     INSERT … duplicate key value violates unique constraint
      //     SELECT  … current transaction is aborted, commands ignored
      //     COMMIT  → **ROLLBACK**
      //
      // Postgres converts `COMMIT` on an aborted transaction into `ROLLBACK`
      // and raises NOTHING. So the closure would return normally, Prisma would
      // commit, the database would roll back, and **the doctor's account would
      // silently not exist** — on the one path where an invited pilot doctor
      // signs up. It is the exact class `billing-grant.ts`'s own header warns
      // about: a stubbed error is a statement about what the author believes,
      // and only a real Postgres can disagree. It did, in the QA rehearsal
      // ruling #99 required before execution.
      //
      // The invite branch needs no grant: that practice already exists, so it
      // was either funded by the backfill or deliberately excluded from it.
      //
      // ⚠️ AND IT TAKES `tx`, DELIBERATELY. A grant that fails rolls the
      // practice and the user back with it. The alternative — granting after
      // the commit — can leave a practice that exists and is not funded, which
      // is precisely the state this step exists to make impossible.
      if (!membership) {
        const grant = await grantPromoCredit(practice.id, tx);
        if (grant.granted) {
          grantForAudit = {
            practiceId: practice.id,
            amountMicroUsd: grant.amountMicroUsd,
            balanceAfter: grant.balanceAfter,
            seq: grant.seq,
          };
        }
      }
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

  // ⚠️ B7 step 3c — ONE AUDIT ROW PER GRANT (ruling #99), emitted only now that
  // the transaction has COMMITTED. `grantForAudit` is null when the practice
  // already held its promo (a T8 invite into an existing clinic): that is the
  // ABSENCE of an event, and the schema comment records why it gets no row.
  //
  // Fire-and-forget like every other `logAudit` call — a failed audit write
  // must never fail a signup. That is also why the label needs its Postgres
  // migration and not merely the TypeScript union: without it the insert is
  // rejected and the rejection is discarded with no error anywhere.
  if (grantForAudit) {
    const g: {
      practiceId: string;
      amountMicroUsd: bigint;
      balanceAfter: bigint;
      seq: bigint;
    } = grantForAudit;
    void logAudit({
      action: 'PROMO_GRANT_CREDITED',
      targetType: 'Practice',
      targetId: g.practiceId,
      practiceId: g.practiceId,
      userId: createdUserId ?? undefined,
      metadata: {
        door: 'signup',
        bucket: 'promo',
        // BigInt is not JSON-serialisable; the metadata column is JSON.
        amountMicroUsd: g.amountMicroUsd.toString(),
        balanceAfter: g.balanceAfter.toString(),
        seq: g.seq.toString(),
      },
    });
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

  return { ok: true, redirect: recoveryHref() };
}
