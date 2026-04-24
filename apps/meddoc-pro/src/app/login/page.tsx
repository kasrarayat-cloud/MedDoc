'use client';

// ============================================================================
// Login Page — Glassmorphism UI on Hero Design System
// ----------------------------------------------------------------------------
// Uses CLIENT-SIDE `signIn` from next-auth/react (not a server action).
// Why: in NextAuth v5 beta, calling `signIn('credentials', { redirect: false })`
// from a server action does NOT reliably set the session cookie — the action
// returns ok, but the Set-Cookie header never lands on the client. The
// client-side signIn POSTs directly to /api/auth/callback/credentials and
// the cookie is set in the real HTTP response, guaranteed.
// ============================================================================

import { useState, useTransition, FormEvent } from 'react';
import { signIn, getSession } from 'next-auth/react';
import Link from 'next/link';
import { Stethoscope, Mail, Lock, ArrowRight, Loader2, AlertCircle, ExternalLink } from 'lucide-react';

interface CrossAppRedirect {
  message: string;
  url: string;
  /** Plain-text linked label for the button. Kept short. */
  buttonLabel: string;
}

export default function LoginPage() {
  const [isPending, startTransition] = useTransition();
  const [error, setError] = useState<string | null>(null);
  const [crossAppRedirect, setCrossAppRedirect] =
    useState<CrossAppRedirect | null>(null);
  const [success, setSuccess] = useState(false);

  // Button keeps the spinner visible from the moment credentials are accepted
  // until NextAuth's internal navigation actually replaces the page.
  const isNavigating = success;

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    setCrossAppRedirect(null);

    const fd = new FormData(e.currentTarget);
    const email = String(fd.get('email') ?? '').trim().toLowerCase();
    const password = String(fd.get('password') ?? '');

    if (!email || !password) {
      setError('Email and password are required.');
      return;
    }

    startTransition(async () => {
      // Pre-check entitlement BEFORE signIn so we can branch the form
      // UX on a cross-app redirect (TRANSCRIBE_MD-only user landed
      // here by mistake). The endpoint is rate-limited and returns
      // generic for wrong-password / no-account, so this doesn't
      // weaken the anti-enumeration posture of the form. The
      // authorize() callback in nextauth.ts is still the security
      // boundary; this branch is purely UX.
      try {
        const preCheck = await fetch('/api/auth/check-entitlement', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email, password }),
        });
        if (preCheck.ok || preCheck.status === 429) {
          const data: {
            ok: boolean;
            code?: string;
            redirectTo?: string;
            retryAfterSeconds?: number;
          } = await preCheck.json();

          if (!data.ok) {
            if (data.code === 'NO_MEDDOC_PRO_HAS_TRANSCRIBE' && data.redirectTo) {
              setCrossAppRedirect({
                message:
                  'This account is for TranscribeMD, not MedDoc Pro. Continue to the right app:',
                url: data.redirectTo,
                buttonLabel: 'Go to TranscribeMD',
              });
              return;
            }
            if (data.code === 'ACCOUNT_LOCKED') {
              const mins = Math.ceil((data.retryAfterSeconds ?? 900) / 60);
              setError(
                `Account temporarily locked. Try again in ${mins} minute${mins === 1 ? '' : 's'}.`
              );
              return;
            }
            if (data.code === 'RATE_LIMITED') {
              const mins = Math.ceil((data.retryAfterSeconds ?? 900) / 60);
              setError(
                `Too many attempts. Try again in ${mins} minute${mins === 1 ? '' : 's'}.`
              );
              return;
            }
            // INVALID_CREDENTIALS or anything else → generic.
            setError('Invalid email or password.');
            return;
          }
        }
        // pre-check unreachable (5xx) → fall through to signIn so the
        // user isn't blocked by a flaky pre-check; signIn enforces the
        // gate authoritatively anyway.
      } catch {
        // Network error → fall through to signIn for the same reason.
      }

      // Sign in without letting NextAuth navigate. We do the role-based
      // fan-out client-side: ADMINs → /system-admin, everyone else →
      // /dashboard. window.location.assign forces a full page load so
      // the correct server layout (admin vs clinician) renders fresh
      // without any stale RSC tree carryover.
      try {
        const result = await signIn('credentials', {
          email,
          password,
          redirect: false,
        });

        if (result?.error) {
          // next-auth v5 surfaces credential failures as 'CredentialsSignin'.
          // We already log the specific errorCode (USER_NOT_FOUND,
          // CREDENTIALS_MISMATCH, etc.) server-side via logAudit in
          // authorize() — the user-facing message stays generic so we
          // don't leak which emails exist.
          setError('Invalid email or password.');
          return;
        }
        if (!result?.ok) {
          setError('Sign-in failed. Please try again.');
          return;
        }

        setSuccess(true);

        // Pull the freshly-set session to decide where to land.
        // getSession() does a fetch('/api/auth/session') — reads the new
        // JWT cookie that signIn just set on the response.
        const session = await getSession();
        const role = session?.user?.role;
        const destination =
          role === 'ADMIN' || role === 'SUPER_ADMIN'
            ? '/system-admin'
            : '/dashboard';
        window.location.assign(destination);
      } catch {
        // signIn throws only for transport/framework errors (not bad creds).
        setError('Sign-in failed. Please try again.');
      }
    });
  }

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-[#0A192F] px-4 py-12">
      {/* ───────── Ambient Glows ───────── */}
      <div
        aria-hidden
        className="pointer-events-none absolute -top-40 -left-40 h-[500px] w-[500px] rounded-full bg-blue-600/20 blur-[120px]"
      />
      <div
        aria-hidden
        className="pointer-events-none absolute -bottom-40 -right-40 h-[500px] w-[500px] rounded-full bg-teal-500/20 blur-[120px]"
      />
      <div
        aria-hidden
        className="pointer-events-none absolute top-1/2 left-1/2 h-[600px] w-[600px] -translate-x-1/2 -translate-y-1/2 rounded-full bg-cyan-500/5 blur-[140px]"
      />

      {/* ───────── Login Card ───────── */}
      <div className="relative z-10 w-full max-w-md">
        {/* Logo / Brand */}
        <div className="mb-8 flex flex-col items-center">
          <Link href="/" className="group inline-flex items-center gap-3">
            <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-gradient-to-br from-blue-500 to-teal-500 shadow-lg shadow-blue-500/30 transition-transform duration-300 group-hover:scale-110">
              <Stethoscope className="h-6 w-6 text-white" />
            </div>
            <span className="text-2xl font-bold text-white">
              MedDoc{' '}
              <span className="bg-gradient-to-r from-blue-400 to-teal-400 bg-clip-text text-transparent">
                Pro
              </span>
            </span>
          </Link>
        </div>

        {/* Glassmorphism Card */}
        <div className="rounded-2xl border border-white/10 bg-white/5 p-8 shadow-2xl shadow-black/40 backdrop-blur-md">
          <div className="mb-6 text-center">
            <h1 className="text-2xl font-bold text-white">Welcome back</h1>
            <p className="mt-2 text-sm text-slate-400">
              Sign in to your physician portal
            </p>
          </div>

          {/* Error Alert */}
          {error && (
            <div className="mb-5 flex items-start gap-3 rounded-xl border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-300">
              <AlertCircle className="mt-0.5 h-4 w-4 flex-shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {/* Cross-app redirect — TRANSCRIBE_MD user landed on the wrong door. */}
          {crossAppRedirect && (
            <div className="mb-5 rounded-xl border border-blue-400/30 bg-blue-500/10 p-4 text-sm text-blue-100">
              <div className="flex items-start gap-3">
                <AlertCircle className="mt-0.5 h-4 w-4 flex-shrink-0 text-blue-300" />
                <span>{crossAppRedirect.message}</span>
              </div>
              <a
                href={crossAppRedirect.url}
                className="mt-3 inline-flex items-center gap-2 rounded-lg bg-blue-500/20 px-4 py-2 text-sm font-semibold text-blue-100 transition-colors hover:bg-blue-500/30 focus:outline-none focus:ring-2 focus:ring-blue-400/40"
              >
                {crossAppRedirect.buttonLabel}
                <ExternalLink className="h-4 w-4" aria-hidden="true" />
              </a>
            </div>
          )}

          {/* Form — uses client-side next-auth/react signIn */}
          <form onSubmit={handleSubmit} className="space-y-5" noValidate>
            {/* Email */}
            <div>
              <label
                htmlFor="email"
                className="mb-2 block text-xs font-semibold uppercase tracking-wider text-slate-400"
              >
                Email address
              </label>
              <div className="relative">
                <Mail className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" />
                <input
                  id="email"
                  name="email"
                  type="email"
                  autoComplete="email"
                  required
                  placeholder="doctor@clinic.com"
                  className="w-full rounded-xl border border-white/10 bg-white/5 py-3 pl-11 pr-4 text-sm text-white placeholder-slate-500 outline-none transition-all focus:border-blue-400/60 focus:bg-white/10 focus:ring-2 focus:ring-blue-400/20"
                />
              </div>
            </div>

            {/* Password */}
            <div>
              <div className="mb-2 flex items-center justify-between">
                <label
                  htmlFor="password"
                  className="block text-xs font-semibold uppercase tracking-wider text-slate-400"
                >
                  Password
                </label>
                <Link
                  href="#"
                  className="text-xs font-medium text-blue-400 transition-colors hover:text-blue-300"
                >
                  Forgot?
                </Link>
              </div>
              <div className="relative">
                <Lock className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" />
                <input
                  id="password"
                  name="password"
                  type="password"
                  autoComplete="current-password"
                  required
                  placeholder="••••••••"
                  className="w-full rounded-xl border border-white/10 bg-white/5 py-3 pl-11 pr-4 text-sm text-white placeholder-slate-500 outline-none transition-all focus:border-blue-400/60 focus:bg-white/10 focus:ring-2 focus:ring-blue-400/20"
                />
              </div>
            </div>

            {/* Submit */}
            <SubmitButton isPending={isPending} isNavigating={isNavigating} />
          </form>

          {/* Divider */}
          <div className="my-6 flex items-center gap-3">
            <div className="h-px flex-1 bg-white/10" />
            <span className="text-xs font-medium uppercase tracking-wider text-slate-500">
              HIPAA Secured
            </span>
            <div className="h-px flex-1 bg-white/10" />
          </div>

          {/* Footer */}
          <p className="text-center text-sm text-slate-400">
            Don&apos;t have an account?{' '}
            <Link
              href="/register"
              className="font-semibold text-blue-400 transition-colors hover:text-blue-300"
            >
              Request access
            </Link>
          </p>
        </div>

        {/* Compliance footer */}
        <p className="mt-6 text-center text-xs text-slate-500">
          Protected by 256-bit encryption · §164.312(a)(1) compliant
        </p>
      </div>
    </div>
  );
}

// ────────────────────────────────────────────────────────────────────────────
// Submit button — spinner visible both while the signIn request is in flight
// (isPending) AND while the subsequent hard navigation resolves (isNavigating).
// ────────────────────────────────────────────────────────────────────────────
function SubmitButton({ isPending, isNavigating }: { isPending: boolean; isNavigating: boolean }) {
  const isLoading = isPending || isNavigating;

  return (
    <button
      type="submit"
      disabled={isLoading}
      className="group relative flex w-full items-center justify-center gap-2 overflow-hidden rounded-xl bg-gradient-to-r from-blue-500 to-teal-500 py-3 text-sm font-semibold text-white shadow-lg shadow-blue-500/30 transition-all duration-300 hover:shadow-blue-500/50 hover:scale-[1.01] disabled:cursor-not-allowed disabled:opacity-70 disabled:hover:scale-100"
    >
      {isLoading ? (
        <>
          <Loader2 className="h-4 w-4 animate-spin" />
          {isNavigating ? 'Redirecting...' : 'Signing in...'}
        </>
      ) : (
        <>
          Sign In
          <ArrowRight className="h-4 w-4 transition-transform duration-300 group-hover:translate-x-0.5" />
        </>
      )}
    </button>
  );
}
