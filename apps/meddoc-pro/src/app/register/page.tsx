// ============================================================================
// Register page — intentionally invite-only
// ----------------------------------------------------------------------------
// MedDoc Pro is invite-only: new clinicians are provisioned by a practice
// administrator through the System Admin area. Public self-registration is
// disabled because:
//   1. Every User must be bound to a Practice (tenant) at creation time;
//      there is no "default practice" we want a stranger to land in.
//   2. HIPAA-grade identity provisioning is controlled, not self-service.
// This page used to host a form that hit `registerUser()` in `./actions.ts`.
// Both the action and the form were removed on 2026-04-13. If you ever bring
// self-service signup back, it needs an Invite model or a new-practice flow —
// see memory `project_state.md`.
// ============================================================================

import Link from 'next/link';
import { Stethoscope, Mail, ArrowRight, ShieldCheck } from 'lucide-react';

export const metadata = {
  title: 'Register — MedDoc Pro',
  description: 'MedDoc Pro is invite-only. Contact your practice administrator.',
};

export default function RegisterPage() {
  return (
    <div className="flex min-h-screen">
      <div className="relative flex w-full flex-col justify-center px-6 py-12 sm:px-12 lg:w-1/2 lg:px-20">
        <div className="pointer-events-none absolute inset-0 gradient-mesh opacity-40" />

        <div className="relative z-10 mx-auto w-full max-w-md">
          <Link href="/" className="inline-flex items-center gap-2 mb-8 group">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-blue-500 to-teal-500 shadow-lg shadow-blue-500/25 transition-transform duration-300 group-hover:scale-110">
              <Stethoscope className="h-5 w-5 text-white" />
            </div>
            <span className="text-xl font-bold text-slate-900 dark:text-white">
              MedDoc <span className="gradient-text">Pro</span>
            </span>
          </Link>

          <h1 className="text-3xl font-bold tracking-tight text-slate-900 dark:text-white sm:text-4xl">
            Invite only
          </h1>
          <p className="mt-3 text-slate-600 dark:text-slate-400">
            MedDoc Pro accounts are provisioned by your practice administrator.
            We don&apos;t offer public self-registration — every clinician is
            bound to a specific practice at creation time so patient data stays
            isolated.
          </p>

          <div className="mt-8 rounded-2xl border border-blue-500/20 bg-blue-500/5 p-5 backdrop-blur">
            <div className="flex items-start gap-3">
              <div className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-gradient-to-br from-blue-500 to-teal-500">
                <ShieldCheck className="h-4 w-4 text-white" />
              </div>
              <div>
                <p className="text-sm font-semibold text-slate-900 dark:text-white">
                  How to get access
                </p>
                <ol className="mt-2 space-y-1.5 text-sm text-slate-600 dark:text-slate-400 list-decimal list-inside marker:text-slate-400">
                  <li>Ask your practice administrator to create your account.</li>
                  <li>You&apos;ll receive credentials via your practice&apos;s onboarding process.</li>
                  <li>Sign in below and change your password on first login.</li>
                </ol>
              </div>
            </div>
          </div>

          <div className="mt-6 rounded-xl border border-slate-200 bg-white/60 p-4 text-sm text-slate-600 backdrop-blur dark:border-slate-700 dark:bg-slate-800/60 dark:text-slate-400">
            <p className="flex items-start gap-2">
              <Mail className="mt-0.5 h-4 w-4 shrink-0 text-slate-400" />
              <span>
                Already have an account? Or are you an administrator who needs to
                invite new staff? Sign in and use the System Admin area to manage users.
              </span>
            </p>
          </div>

          <Link
            href="/login"
            className="group mt-8 inline-flex w-full items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-blue-600 to-teal-500 py-2.5 text-sm font-semibold text-white shadow-lg shadow-blue-500/25 transition-all duration-300 hover:shadow-blue-500/40 hover:scale-[1.02]"
          >
            Go to sign in
            <ArrowRight className="h-4 w-4 transition-transform duration-300 group-hover:translate-x-0.5" />
          </Link>

          <p className="mt-8 text-center text-sm text-slate-500 dark:text-slate-400">
            Need help?{' '}
            <Link
              href="/"
              className="font-semibold text-blue-600 transition-colors hover:text-blue-700 dark:text-blue-400 dark:hover:text-blue-300"
            >
              Back to home
            </Link>
          </p>
        </div>
      </div>

      <div className="relative hidden overflow-hidden lg:flex lg:w-1/2 lg:items-center lg:justify-center">
        <div className="absolute inset-0 bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900" />
        <div className="absolute inset-0 opacity-30">
          <div className="absolute inset-0" style={{ background: 'radial-gradient(ellipse at 30% 40%, rgba(59, 130, 246, 0.2) 0%, transparent 60%)' }} />
          <div className="absolute inset-0" style={{ background: 'radial-gradient(ellipse at 70% 60%, rgba(20, 184, 166, 0.15) 0%, transparent 50%)' }} />
        </div>

        <div className="relative z-10 max-w-md px-12 text-center">
          <div className="mx-auto mb-8 flex h-20 w-20 items-center justify-center rounded-2xl bg-gradient-to-br from-blue-500 to-teal-500 shadow-2xl shadow-blue-500/30">
            <Stethoscope className="h-10 w-10 text-white" />
          </div>
          <h2 className="text-3xl font-bold text-white">
            MedDoc <span className="bg-gradient-to-r from-blue-400 to-teal-400 bg-clip-text text-transparent">Pro</span>
          </h2>
          <p className="mt-3 text-slate-400">Medical Documentation, Automated</p>

          <div className="mt-10 rounded-2xl border border-white/10 bg-white/5 p-6 text-left backdrop-blur-sm">
            <p className="mb-4 text-sm font-medium text-white">Why invite-only?</p>
            <ul className="space-y-3 text-sm text-slate-300">
              <li className="flex items-start gap-2.5">
                <div className="mt-1 flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-blue-500 to-teal-500">
                  <svg className="h-2.5 w-2.5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                  </svg>
                </div>
                Patient data stays isolated per practice.
              </li>
              <li className="flex items-start gap-2.5">
                <div className="mt-1 flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-blue-500 to-teal-500">
                  <svg className="h-2.5 w-2.5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                  </svg>
                </div>
                Administrators control role assignment (Doctor, Staff, Admin).
              </li>
              <li className="flex items-start gap-2.5">
                <div className="mt-1 flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-blue-500 to-teal-500">
                  <svg className="h-2.5 w-2.5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                  </svg>
                </div>
                HIPAA-grade identity provisioning — no anonymous signups.
              </li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
}
