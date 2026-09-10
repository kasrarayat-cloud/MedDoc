/**
 * ADMIN-2 — WHICH PRACTICE DOES THIS HOSTNAME BELONG TO? (ruling #196)
 *
 * `<practice>.quillmd.com` per practice, keyed on `Practice.slug` — the column
 * whose own doc-comment already names subdomain routing as its purpose. This
 * file is the APP SIDE ONLY. Every ingress leg (wildcard DNS, the host-nginx
 * acme/443 blocks, per-subdomain certificates, the Caddy wildcard block) is the
 * deploy owner's and is listed on the ADMIN-2 row, not built here.
 *
 * ⚠️ BEHIND A FLAG THAT DEFAULTS OFF — `PRACTICE_HOST_ROUTING`, server-only,
 * read at request time, ON only for the exact string `true`. With it off, no
 * caller reaches the resolver, reads a header for it, or queries a practice,
 * so production is byte-identical in behaviour until the ingress exists. It is
 * deliberately NOT a `NEXT_PUBLIC_*` name: nothing in a client bundle may
 * decide tenancy, and a build-time inline would freeze the answer into the
 * image.
 *
 * ⚠️ ONE READER OF THE HOST, AND IT READS `Host` ONLY — NEVER `X-Forwarded-Host`.
 * Measured against the tracked ingress config (2026-09-10):
 *
 *   host nginx  `proxy_set_header Host $host;` — and routes on it: the
 *               server_name list is closed, so `$host` is one of the names it
 *               serves. It NEVER sets `X-Forwarded-Host`, and nginx passes any
 *               header it does not set through from the client untouched.
 *   Caddy       every `transcribe-md` upstream carries `header_up Host {host}`
 *               in both the `app.` and `admin.` blocks, and site blocks are
 *               literal host names, so `{host}` is the block's own name.
 *               `trusted_proxies` covers the nginx hop, and a trusted hop's
 *               incoming `X-Forwarded-Host` is KEPT rather than replaced
 *               (Caddy's documented reverse_proxy default — INFERRED from the
 *               docs, not measured with a forged header).
 *
 * So `Host` is the one value both proxies write and route on, and
 * `X-Forwarded-Host` is, on this topology, a value the CLIENT chooses. Letting
 * it pick a practice would be the client-IP spoof (`Caddyfile:36-50`) again,
 * one header over. `gate-admin2-practice-host.test.ts` derives every host read
 * in `src` from the filesystem and reds on any outside this file.
 */
import { headers } from 'next/headers';

import prisma from '@meddoc/db';
import { SessionUnverifiableError } from '@meddoc/auth';

import { slugRefusal } from './practice-write';

/** The one switch. Read literally so a flag inventory that searches the
 *  VARIABLE (not an accessor) finds it. */
export function practiceHostRoutingEnabled(): boolean {
  return process.env.PRACTICE_HOST_ROUTING === 'true';
}

/** The platform's registrable domain. Practice hosts are exactly one label
 *  under it. */
export const PRACTICE_HOST_APEX = 'quillmd.com';

/**
 * Labels under the apex that serve EVERY account, exactly as today. `app.` is
 * the reason nobody is stranded: whatever a practice host refuses, the neutral
 * host still admits.
 */
export const NEUTRAL_LABELS: readonly string[] = ['www', 'app', 'admin'];

/** Loopback names local dev and the QA stack (SSH tunnel) arrive on. */
const LOOPBACK_HOSTS = new Set(['localhost', '127.0.0.1', '[::1]']);
const LOOPBACK_V4 = /^127\.\d{1,3}\.\d{1,3}\.\d{1,3}$/;

/**
 * ⚠️ WHAT A PRACTICE HOST ADMITS — ONE LOCAL CONSTANT, AND IT IS A RECONCILIATION
 * DEBT. ADMIN-6 is introducing a shared `PRACTICE_ADMITS` predicate for "a
 * practice that may still be used". When it lands this constant is replaced by
 * that import, so an archived practice's host and an archived practice's
 * sign-in cannot disagree about what archived means.
 */
export const PRACTICE_HOST_ADMITS = { isActive: true } as const;

export type HostRefusalReason =
  /** No Host header at all — nothing to reconcile against, so nothing is admitted. */
  | 'no_host'
  /** Neither the platform's apex nor a loopback name. */
  | 'foreign_host'
  /** `a.b.quillmd.com` — no practice lives two labels down. */
  | 'nested_label'
  /** `solo-*` — machine-minted at signup (195 of 199 today), unroutable by decision. */
  | 'machine_slug'
  /** Not a DNS label the slug rule accepts. */
  | 'invalid_label'
  /** A platform name (`api`, `staging`, …) — practice-write.ts's reserved set. */
  | 'reserved_label'
  /** Well-formed, but no ACTIVE practice carries this slug. */
  | 'unknown_practice'
  /** The session's practice is not the host's practice. */
  | 'practice_mismatch'
  /** The host or the practice could not be read (sign-in path only). */
  | 'host_unverifiable';

export type HostClass =
  | { kind: 'neutral'; host: string }
  | { kind: 'practice'; host: string; label: string }
  | { kind: 'refused'; host: string | null; reason: HostRefusalReason; label?: string };

export type HostResolution =
  | { kind: 'neutral'; host: string }
  | { kind: 'practice'; host: string; label: string; practiceId: string }
  | { kind: 'refused'; host: string | null; reason: HostRefusalReason; label?: string };

export type HostRefusal = { reason: HostRefusalReason; host: string | null; label?: string };

/**
 * The session is not admitted on this host. REFUSED BY NAME — never a silent
 * `null`, which every caller reads as "signed out" and answers with a bounce to
 * /login that the same host would refuse again.
 *
 * The session is NOT ended and the cookie is NOT cleared: the same account is
 * still admitted on the neutral host.
 */
export class PracticeHostRefusedError extends Error {
  readonly status = 403;
  /** Rides on `digest` for the same reason `SessionUnverifiableError`'s does:
   *  Next.js strips server error messages before a client boundary. */
  static readonly DIGEST = 'PRACTICE_HOST_REFUSED';
  readonly digest = PracticeHostRefusedError.DIGEST;
  constructor(
    readonly reason: HostRefusalReason,
    readonly host: string | null,
  ) {
    super(
      `PRACTICE_HOST_REFUSED: ${reason} — this session is not admitted on ` +
        `${host ?? '(no host)'}. The session is NOT ended.`,
    );
    this.name = 'PracticeHostRefusedError';
  }
}

/** Lowercase, port stripped, one trailing dot stripped. `null` when empty. */
export function normalizeHost(raw: string | null | undefined): string | null {
  if (typeof raw !== 'string') return null;
  let h = raw.trim().toLowerCase();
  if (h === '') return null;
  if (h.startsWith('[')) {
    // IPv6 literal: `[::1]:3011` — the port follows the bracket, not a colon.
    const end = h.indexOf(']');
    return end > 1 ? h.slice(0, end + 1) : null;
  }
  const colon = h.indexOf(':');
  if (colon >= 0) h = h.slice(0, colon);
  if (h.endsWith('.')) h = h.slice(0, -1);
  return h === '' ? null : h;
}

/**
 * THE ONE READER OF THE REQUEST'S HOST. `Host` only — see the file header for
 * why `X-Forwarded-Host` is never consulted.
 *
 * Deliberately does not catch: `headers()` outside a request scope throws, and
 * Next.js also signals dynamic rendering by throwing from it — a catch here
 * would swallow both. Callers that can run outside a request decide for
 * themselves.
 */
export async function requestHost(): Promise<string | null> {
  const h = await headers();
  return normalizeHost(h.get('host'));
}

/** Pure classification of an already-normalized host. No I/O. */
export function classifyHost(host: string | null): HostClass {
  if (host === null) return { kind: 'refused', host, reason: 'no_host' };
  if (LOOPBACK_HOSTS.has(host) || LOOPBACK_V4.test(host)) return { kind: 'neutral', host };
  if (host === PRACTICE_HOST_APEX) return { kind: 'neutral', host };

  const suffix = `.${PRACTICE_HOST_APEX}`;
  if (!host.endsWith(suffix)) return { kind: 'refused', host, reason: 'foreign_host' };

  const label = host.slice(0, -suffix.length);
  if (label.includes('.')) return { kind: 'refused', host, reason: 'nested_label', label };
  // Neutral labels are ALSO reserved slugs, so this must come before the
  // reserved check or `app.` would refuse every account.
  if (NEUTRAL_LABELS.includes(label)) return { kind: 'neutral', host };
  if (label.startsWith('solo-')) return { kind: 'refused', host, reason: 'machine_slug', label };

  // ⚠️ THE RESERVED SET IS practice-write.ts's, IMPORTED — NOT COPIED. A slug
  // the write path refuses must be a host this path refuses, and two lists
  // drift the day either is edited. RECONCILIATION DEBT: ADMIN-2a is to export
  // `practiceLabelRefusal()` (adding `send`, `xn--`, `--` and the `solo-`
  // prefix to the write side); when it lands, this call becomes that one and
  // the local `solo-` line above becomes redundant.
  const refusal = slugRefusal(label);
  if (refusal === 'reserved_slug') return { kind: 'refused', host, reason: 'reserved_label', label };
  if (refusal !== null) return { kind: 'refused', host, reason: 'invalid_label', label };
  return { kind: 'practice', host, label };
}

/**
 * Host → practice. A practice host resolves only to an ACTIVE practice whose
 * slug is exactly the label.
 *
 * ⚠️ A LOOKUP THAT CANNOT ANSWER IS NOT "NO SUCH PRACTICE". It throws
 * `SessionUnverifiableError` — ruling #182(1)'s "cannot tell" — so the request
 * is refused (503) with the session kept, rather than being read as a mismatch
 * or, worse, as a neutral host.
 */
export async function resolvePracticeByHost(host: string | null): Promise<HostResolution> {
  const c = classifyHost(host);
  if (c.kind !== 'practice') return c;

  let row: { id: string } | null;
  try {
    row = await prisma.practice.findFirst({
      where: { slug: c.label, ...PRACTICE_HOST_ADMITS },
      select: { id: true },
    });
  } catch (err) {
    console.error(
      '[practice-host] PRACTICE_HOST_UNVERIFIABLE: the practice lookup for a ' +
        'practice host failed. The request is REFUSED (503); the session is NOT ended.',
      { label: c.label, error: err instanceof Error ? err.message : String(err) },
    );
    throw new SessionUnverifiableError('the practice-host lookup could not reach the database');
  }
  if (!row) return { kind: 'refused', host: c.host, reason: 'unknown_practice', label: c.label };
  return { kind: 'practice', host: c.host, label: c.label, practiceId: row.id };
}

/**
 * THE ONE RECONCILE PREDICATE — both `getSession()` and sign-in ask this.
 * `null` = admitted. May throw `SessionUnverifiableError`.
 */
export async function hostRefusalFor(
  userPracticeId: string | null | undefined,
  host: string | null,
): Promise<HostRefusal | null> {
  const r = await resolvePracticeByHost(host);
  if (r.kind === 'neutral') return null;
  if (r.kind === 'refused') {
    return { reason: r.reason, host: r.host, ...(r.label ? { label: r.label } : {}) };
  }
  if (!userPracticeId || r.practiceId !== userPracticeId) {
    return { reason: 'practice_mismatch', host: r.host, label: r.label };
  }
  return null;
}

/**
 * For `getSession()`: throws `PracticeHostRefusedError` when this request's
 * host does not admit the user's practice. Callers gate on
 * `practiceHostRoutingEnabled()` FIRST, so with the flag off this is never
 * reached and no header is read for it.
 */
export async function assertHostAdmitsPractice(userPracticeId: string, userId: string): Promise<void> {
  const host = await requestHost();
  const refusal = await hostRefusalFor(userPracticeId, host);
  if (!refusal) return;
  console.warn('[practice-host] PRACTICE_HOST_REFUSED: session not admitted on this host', {
    userId,
    reason: refusal.reason,
    host: refusal.host,
  });
  throw new PracticeHostRefusedError(refusal.reason, refusal.host);
}

/**
 * For `authorize()`: the same predicate, FAIL CLOSED on anything it cannot
 * read — a sign-in that cannot be reconciled is refused, by the named reason
 * `host_unverifiable`, rather than admitted.
 */
export async function loginHostRefusal(
  userPracticeId: string | null | undefined,
): Promise<HostRefusal | null> {
  try {
    return await hostRefusalFor(userPracticeId, await requestHost());
  } catch {
    return { reason: 'host_unverifiable', host: null };
  }
}
