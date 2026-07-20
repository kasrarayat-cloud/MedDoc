"use server";

import { randomInt } from "node:crypto";

import { z } from "zod";
import bcrypt from "bcryptjs";
import { headers } from "next/headers";

import prisma from "@meddoc/db";
import {
  AuthEmailPurpose,
  Product,
  UserRole,
  type Prisma,
} from "@prisma/client";
import { signIn as nextAuthSignIn } from "@/lib/nextauth";
import { isAdminRequestHost } from "@/lib/admin-host";
import {
  isLoginRequestAllowed,
  isSignupRequestAllowed,
} from "@/lib/auth-surface";
import {
  isEmailDeliveryEnabled,
  isEmailVerificationRequired,
} from "@/lib/email-enabled";
import { isAutoConfirmDomain } from "@/lib/email-auto-confirm";
import { hasCompleteMfaEnrollment } from "@/lib/mfa-enrollment-state";
import { enqueueAuthEmailRequestInTransaction } from "@/lib/auth-email-outbox";
import {
  TEMPLATE_TWIN_STATIC_ASSET_ADMIN_PATH,
  templateTwinAdminLandingPath,
} from "@/lib/template-twin/admin-app-service";
import {
  RATE_LIMITS,
  checkSharedRateLimit,
  clientIpFromHeaders,
  type RateLimitRule,
} from "@/lib/rate-limit";

/** T-M18.3 A20: pre-computed dummy bcrypt hash, used to equalize the
 *  wall-clock time of loginAction paths that would otherwise skip the
 *  pre-check bcrypt.compare. Computed once at module load. */
const DUMMY_PASSWORD_HASH = bcrypt.hashSync(
  "timing-equalizer-never-matches",
  12,
);

const SIGNUP_RESPONSE_FLOOR_MS = 650;

async function waitForSignupResponseFloor(startedAtMs: number): Promise<void> {
  if (process.env.NODE_ENV === "test") return;
  const targetMs = SIGNUP_RESPONSE_FLOOR_MS + randomInt(0, 101);
  const remainingMs = targetMs - (Date.now() - startedAtMs);
  if (remainingMs > 0) {
    await new Promise<void>((resolve) => setTimeout(resolve, remainingMs));
  }
}

function isUniqueConstraintError(error: unknown): boolean {
  return (
    typeof error === "object" &&
    error !== null &&
    "code" in error &&
    (error as { code?: unknown }).code === "P2002"
  );
}

/** Server-action rate-limit helper. Unlike route handlers this can't
 *  return a NextResponse — we surface the 429 as a FormErrorState so
 *  the existing useActionState wiring shows it cleanly. */
async function actionRateLimitOrError(
  rule: RateLimitRule,
  values?: Record<string, string>,
): Promise<FormErrorState | null> {
  const h = await headers();
  const ip = clientIpFromHeaders(h);
  const rl = await checkSharedRateLimit(rule, ip);
  if (rl.allowed) return null;
  const mins = Math.ceil(rl.retryAfterSec / 60);
  return {
    ok: false,
    errors: {
      _form: `Too many attempts. Try again in ${mins} minute${mins === 1 ? "" : "s"}.`,
    },
    values,
  };
}

// LoginSchema + SignupSchema live in ./auth-schemas so the unit
// tests can import them without pulling in this file's prisma +
// next-auth chain. Importable directly from '@/actions/auth-schemas'
// — not re-exported here because Next's "use server" boundary only
// allows async-function exports from a server-actions file.
import { LoginSchema, SignupSchema } from "./auth-schemas";

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
    const key = issue.path.join(".") || "_form";
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
  formData: FormData,
): Promise<AuthActionState> {
  const requestHeaders = await headers().catch(() => null);
  if (!requestHeaders || !isLoginRequestAllowed(requestHeaders)) {
    return {
      ok: false,
      errors: { _form: "Sign in is unavailable on this host." },
    };
  }
  const raw = Object.fromEntries(formData.entries());
  const email = String(raw.email ?? "");

  const blocked = await actionRateLimitOrError(RATE_LIMITS.LOGIN_PREFLIGHT, {
    email,
  });
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

  // Resolve the optional UX hints from one account snapshot and one bcrypt
  // comparison. Unknown accounts compare against the same-cost dummy hash;
  // known accounts compare against their current hash. Reusing that result
  // across verification, entitlement, and MFA hints prevents any one UX path
  // from gaining an extra password-hash operation. Auth.js still rechecks all
  // security predicates and credentials at the authoritative issuance gate.
  const preflightUser = await prisma.user
    .findUnique({
      where: { email: parsed.data.email.trim().toLowerCase() },
      select: {
        id: true,
        passwordHash: true,
        emailVerified: true,
        products: true,
        role: true,
        mfaEnabled: true,
        mfaSecret: true,
        mfaVerifiedAt: true,
        isActive: true,
        lockedUntil: true,
      },
    })
    .catch(() => null);
  const passwordMatches = await bcrypt
    .compare(
      parsed.data.password,
      preflightUser?.passwordHash ?? DUMMY_PASSWORD_HASH,
    )
    .catch(() => false);
  const credentialsValidForPreflight =
    !!preflightUser?.isActive &&
    (!preflightUser.lockedUntil || preflightUser.lockedUntil < new Date()) &&
    passwordMatches;

  // Verification policy remains active in production even while delivery is
  // unavailable: a provider outage must never authenticate an unverified
  // account. The specific UX is shown only after the password is proved.
  if (
    isEmailVerificationRequired() &&
    credentialsValidForPreflight &&
    preflightUser?.emailVerified === null
  ) {
    return {
      ok: false,
      errors: {
        _form: "Please verify your email before signing in.",
      },
      values: { email: parsed.data.email },
      needsVerificationFor: parsed.data.email,
    };
  }

  // F9-1 + product-separation: Pre-check product entitlement so the
  // form surfaces a specific "no access" message (and, if the user
  // has MEDDOC_PRO, a one-click cross-app redirect) instead of the
  // generic "invalid credentials" the authorize callback returns.
  // Authorize remains the authoritative security gate; this block is
  // purely UX. Always runs (not gated on email delivery) so the
  // message is consistent across envs.
  const isEntitlementCandidate =
    credentialsValidForPreflight &&
    !!preflightUser &&
    !preflightUser.products.includes(Product.TRANSCRIBE_MD) &&
    // Phase 1A: SUPER_ADMIN bypass — skip the "no entitlement" UX
    // message because the authorize() gate allows them through, and
    // the cross-app-redirect message would send them to the wrong
    // surface.
    !preflightUser.products.includes(Product.SUPER_ADMIN);
  if (isEntitlementCandidate && preflightUser) {
    // Cross-app: if the user has MEDDOC_PRO but is missing TRANSCRIBE_MD,
    // send them to the CRM login. Symmetric with the entitlement flow on the
    // MedDoc Pro side.
    if (preflightUser.products.includes(Product.MEDDOC_PRO)) {
      const meddocProUrl =
        process.env.NEXT_PUBLIC_MEDDOC_PRO_APP_URL ?? "https://pro.quillmd.com";
      return {
        ok: false,
        errors: {
          _form:
            "This account is for MedDoc Pro, not TranscribeMD. Continue to the right app:",
        },
        values: { email: parsed.data.email },
        crossAppRedirect: {
          message:
            "This account is for MedDoc Pro, not TranscribeMD. Continue to the right app:",
          url: `${meddocProUrl}/login`,
          buttonLabel: "Go to MedDoc Pro",
        },
      };
    }
    return {
      ok: false,
      errors: {
        _form:
          "Your account does not have access to TranscribeMD. Contact your practice admin to enable it.",
      },
      values: { email: parsed.data.email },
    };
  }

  // MFA preflight (closes shadow-audit HIPAA_FINDING_001). When the
  // user has mfaEnabled=true and the form has not supplied a second
  // factor, return mfaRequired so the client switches to the MFA
  // input and re-submits with the token. The one preflight password result
  // above is reused here; this branch never adds a second bcrypt operation.
  const credentialsValidForMfaCheck = credentialsValidForPreflight;
  const hasConfiguredMfaChallenge =
    preflightUser !== null && hasCompleteMfaEnrollment(preflightUser);
  if (
    credentialsValidForMfaCheck &&
    preflightUser?.mfaEnabled === true &&
    !hasConfiguredMfaChallenge
  ) {
    return {
      ok: false,
      errors: {
        _form:
          "MFA configuration requires controlled repair. Sign out and contact your security administrator.",
      },
      values: { email: parsed.data.email },
    };
  }
  if (credentialsValidForMfaCheck && hasConfiguredMfaChallenge) {
    if (!parsed.data.totpToken && !parsed.data.recoveryCode) {
      return {
        ok: false,
        errors: {},
        values: { email: parsed.data.email },
        mfaRequired: true,
      };
    }
  }

  try {
    await nextAuthSignIn("credentials", {
      redirect: false,
      email: parsed.data.email,
      password: parsed.data.password,
      totpToken: parsed.data.totpToken ?? "",
      recoveryCode: parsed.data.recoveryCode ?? "",
    });
  } catch {
    // If MFA was required and we got here, the second factor is
    // wrong. Surface a specific message + keep the form in MFA mode.
    if (credentialsValidForMfaCheck && hasConfiguredMfaChallenge) {
      return {
        ok: false,
        errors: {
          _form: parsed.data.recoveryCode
            ? "Invalid recovery code."
            : "Invalid 6-digit code. Try again.",
        },
        values: { email: parsed.data.email },
        mfaRequired: true,
      };
    }
    return {
      ok: false,
      errors: { _form: "Invalid email or password." },
      values: { email: parsed.data.email },
    };
  }

  return {
    ok: true,
    redirect: await postLoginRedirectFor(
      preflightUser
        ? {
            role: preflightUser.role,
            products: preflightUser.products,
            mfaEnabled: preflightUser.mfaEnabled,
            mfaSecret: preflightUser.mfaSecret,
            mfaVerifiedAt: preflightUser.mfaVerifiedAt,
          }
        : null,
    ),
  };
}

/** Computes the post-login destination based on the request host. The
 *  physician host lands on `/dashboard`; the admin host lands on one of the
 *  two exact isolated surfaces selected by current role/product authority.
 *  No successful admin-process login is routed through the broad `/admin`
 *  physician upstream. */
async function postLoginRedirectFor(
  currentUser: {
    role: string;
    products: readonly string[];
    mfaEnabled?: boolean;
    mfaSecret?: string | null;
    mfaVerifiedAt?: Date | null;
  } | null,
): Promise<string> {
  try {
    const h = await headers();
    if (isAdminRequestHost(h)) {
      return currentUser
        ? (templateTwinAdminLandingPath(currentUser) ??
            TEMPLATE_TWIN_STATIC_ASSET_ADMIN_PATH)
        : TEMPLATE_TWIN_STATIC_ASSET_ADMIN_PATH;
    }
  } catch {
    // headers() outside a request context — fall through to the default
  }
  return "/dashboard";
}

/** Signup creates a solo Practice + physician atomically. Production accounts
 * remain unverified until the durable dispatcher delivers and the physician
 * redeems a verification link. Only the explicit synthetic-domain policy may
 * stamp verification and auto-sign in. */
export async function signupAction(
  _prev: AuthActionState,
  formData: FormData,
): Promise<AuthActionState> {
  // Next server functions are addressed by action identity and execute on the
  // POST route carrying that identity. A crafted POST to an allowlisted admin
  // auth page must not turn this same-image process into public registration.
  // Keep this before rate limiting, parsing, email lookup, hashing, or writes.
  const requestHeaders = await headers().catch(() => null);
  if (!requestHeaders || !isSignupRequestAllowed(requestHeaders)) {
    return {
      ok: false,
      errors: { _form: "Public registration is unavailable on this host." },
    };
  }
  const responseBudgetStartedAt = Date.now();
  const raw = Object.fromEntries(formData.entries());
  const emailField = String(raw.email ?? "");
  const nameField = String(raw.name ?? "");

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
        email: String(raw.email ?? ""),
        name: String(raw.name ?? ""),
      },
    };
  }

  const emailLower = parsed.data.email.trim().toLowerCase();
  const passwordHash = await bcrypt.hash(parsed.data.password, 12);
  const autoConfirm = isAutoConfirmDomain(emailLower);
  if (autoConfirm) {
    console.warn("[QA-BYPASS] signup email auto-confirmed by synthetic policy");
  }
  const deliveryEnabled = isEmailDeliveryEnabled();
  if (!deliveryEnabled && !autoConfirm) {
    return {
      ok: false,
      errors: {
        _form:
          "Account registration is temporarily unavailable. Try again later.",
      },
      values: { email: emailLower, name: parsed.data.name },
    };
  }

  type SignupDisposition = "existing" | "created-pending" | "created-confirmed";
  let disposition: SignupDisposition;
  try {
    disposition = await prisma.$transaction(
      async (tx: Prisma.TransactionClient): Promise<SignupDisposition> => {
        const existing = await tx.user.findUnique({
          where: { email: emailLower },
          select: { id: true },
        });
        if (existing) {
          if (deliveryEnabled) {
            await enqueueAuthEmailRequestInTransaction(tx, {
              email: emailLower,
              purpose: AuthEmailPurpose.ACCOUNT_EXISTS,
            });
          }
          return "existing";
        }

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
            emailVerified: autoConfirm ? new Date() : null,
          },
        });
        if (!autoConfirm) {
          await enqueueAuthEmailRequestInTransaction(tx, {
            email: emailLower,
            purpose: AuthEmailPurpose.EMAIL_VERIFICATION,
          });
        }
        return autoConfirm ? "created-confirmed" : "created-pending";
      },
    );
  } catch (err) {
    if (isUniqueConstraintError(err)) {
      try {
        if (deliveryEnabled) {
          await prisma.$transaction((tx: Prisma.TransactionClient) =>
            enqueueAuthEmailRequestInTransaction(tx, {
              email: emailLower,
              purpose: AuthEmailPurpose.ACCOUNT_EXISTS,
            }),
          );
        }
        disposition = "existing";
      } catch {
        console.error("[signup] durable account notification failed");
        await waitForSignupResponseFloor(responseBudgetStartedAt);
        return {
          ok: false,
          errors: { _form: "Could not create your account. Please try again." },
          values: { email: emailLower, name: parsed.data.name },
        };
      }
    } else {
      console.error("[signup] account transaction failed");
      await waitForSignupResponseFloor(responseBudgetStartedAt);
      return {
        ok: false,
        errors: {
          _form: "Could not create your account. Please try again.",
        },
        values: {
          email: emailLower,
          name: parsed.data.name,
        },
      };
    }
  }

  if (disposition !== "created-confirmed") {
    await waitForSignupResponseFloor(responseBudgetStartedAt);
    return {
      ok: true,
      // Never place an identity in navigation/history, RSC URLs, or ingress
      // logs. The generic page offers an explicit resend form instead.
      redirect: "/check-email",
    };
  }

  // The only auto-login path is the explicit synthetic-domain bypass. A
  // production account can never be stamped verified merely because the
  // delivery provider is unavailable.
  try {
    await nextAuthSignIn("credentials", {
      redirect: false,
      email: emailLower,
      password: parsed.data.password,
    });
  } catch {
    console.error("[signup] synthetic auto-login failed");
    await waitForSignupResponseFloor(responseBudgetStartedAt);
    return {
      ok: true,
      redirect: "/login",
      warning: "Account created — please sign in to continue.",
    };
  }
  await waitForSignupResponseFloor(responseBudgetStartedAt);
  return { ok: true, redirect: "/dashboard" };
}
