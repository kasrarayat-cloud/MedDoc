import type { Metadata } from 'next';
import { NavBar } from '@/components/nav-bar';
import { Footer } from '@/components/footer';
import { Badge } from '@/components/badge';

export const metadata: Metadata = {
  title: 'Security',
  description:
    'How QuillMD is built, deployed, and monitored to keep patient data safe.',
};

const LAST_UPDATED = '2026-04-20';

export default function SecurityPage() {
  return (
    <>
      <NavBar />
      <main>
        <section className="relative overflow-hidden pt-32 pb-16">
          <div className="relative mx-auto max-w-3xl px-6 lg:px-8">
            <Badge dot="violet">Security</Badge>
            <h1 className="mt-6 type-h1 text-text-primary">
              Security practices
            </h1>
            <p className="mt-6 text-[14px] text-text-muted">
              Last updated: {LAST_UPDATED}
            </p>

            <div className="mt-8 rounded-lg border border-amber-500/40 bg-amber-500/5 p-4 text-[13px] leading-relaxed text-amber-200">
              <strong className="font-semibold">
                [DRAFT — PENDING LEGAL REVIEW]
              </strong>
              <p className="mt-1.5">
                This page summarizes how QuillMD is built and operated.
                It&apos;s a transparent operational statement, not a marketing
                claim. If you need a signed SOC 2, ISO 27001, or HITRUST
                report, see &quot;Certifications&quot; below.
              </p>
            </div>
          </div>
        </section>

        <section className="relative border-t border-border-subtle py-12">
          <div className="mx-auto max-w-3xl px-6 lg:px-8 space-y-10 text-[15px] leading-relaxed text-text-secondary">
            <div>
              <h2 className="type-h2 text-text-primary">Application</h2>
              <ul className="mt-4 list-disc space-y-2 pl-5">
                <li>
                  Auth via NextAuth (Auth.js v5) with JWT sessions, bcrypt-12
                  password hashing, 5-attempt lockout with 15-minute cooldown.
                </li>
                <li>
                  Single-session enforcement: a new login revokes prior
                  sessionTokens so stolen JWTs stop resolving.
                </li>
                <li>
                  Every API route validates session + per-record ownership
                  before serving data; cross-user access returns 404 to
                  prevent ID enumeration.
                </li>
                <li>
                  Structured input validation via Zod on every request that
                  accepts user data.
                </li>
                <li>
                  File uploads are size-capped (500 MB audio, 50 MB
                  dictation) and MIME-validated before being streamed to
                  object storage.
                </li>
              </ul>
            </div>

            <div>
              <h2 className="type-h2 text-text-primary">Infrastructure</h2>
              <ul className="mt-4 list-disc space-y-2 pl-5">
                <li>
                  All services run in Docker containers on a dedicated VPS.
                  No shared-tenant compute.
                </li>
                <li>
                  Postgres (with pgvector for embedding workloads), Redis
                  (BullMQ broker), and MinIO (S3-compatible object storage)
                  are bound to localhost on the VPS. Public traffic enters
                  only through Caddy.
                </li>
                <li>
                  Caddy serves as the public edge; TLS is handled by Let&apos;s
                  Encrypt with auto-renewal once a domain is configured.
                </li>
                <li>
                  Secrets live in a root-owned <code>.env</code> file on the
                  VPS only; <code>.env*</code> is gitignored.
                </li>
              </ul>
            </div>

            <div>
              <h2 className="type-h2 text-text-primary">
                Data handling
              </h2>
              <ul className="mt-4 list-disc space-y-2 pl-5">
                <li>
                  TLS 1.2+ for every outbound call to AI providers, email, and
                  the browser.
                </li>
                <li>
                  At-rest encryption inherits from the VPS provider&apos;s
                  disk encryption.
                </li>
                <li>
                  A PHI scrubber (<code>redactPhi</code>) masks emails, phone
                  numbers, and SSNs in error logs and Sentry events. Free-text
                  fields above a length threshold collapse to length markers.
                </li>
                <li>
                  Audio retention defaults to 90 days; transcripts retain for
                  7 years per HIPAA.
                </li>
              </ul>
            </div>

            <div>
              <h2 className="type-h2 text-text-primary">
                Operations
              </h2>
              <ul className="mt-4 list-disc space-y-2 pl-5">
                <li>
                  Secrets rotated quarterly (JWT, AI provider keys) per our
                  internal rotation runbook.
                </li>
                <li>
                  Every deploy is preceded by a pg_dump backup; rollback path
                  is documented.
                </li>
                <li>
                  Production error surfacing via Sentry on the CRM app;
                  transcribe-md Sentry integration is in progress (tracked
                  in the T-M15 audit).
                </li>
                <li>
                  Vulnerability disclosure: email{' '}
                  <code>security@ashtechgroup.com</code>. We aim to
                  acknowledge within 48 hours. Please do not open GitHub
                  issues for security reports.
                </li>
              </ul>
            </div>

            <div>
              <h2 className="type-h2 text-text-primary">
                Certifications
              </h2>
              <p className="mt-4">
                QuillMD does not currently hold a SOC 2, ISO 27001, or
                HITRUST certification. Our launch target is SOC 2 Type 2
                readiness within 12 months of general availability. Our
                HIPAA posture is covered by{' '}
                <a
                  href="/hipaa"
                  className="text-violet-400 hover:text-violet-300"
                >
                  BAAs and operational controls
                </a>{' '}
                rather than third-party audit today.
              </p>
            </div>

            <div>
              <h2 className="type-h2 text-text-primary">
                Known gaps (transparent)
              </h2>
              <p className="mt-4">
                We publish pre-launch audit findings. See our internal{' '}
                <code>docs/T-M15-AUDIT-REPORT.md</code> (available on request
                for prospects under NDA) for the current queue of
                hardening work.
              </p>
            </div>

            <div>
              <h2 className="type-h2 text-text-primary">Contact</h2>
              <p className="mt-4">
                Security: <code>security@ashtechgroup.com</code>.
              </p>
            </div>
          </div>
        </section>
      </main>
      <Footer />
    </>
  );
}
