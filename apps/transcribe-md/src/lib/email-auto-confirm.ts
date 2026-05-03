// ============================================================================
// QA-only email auto-confirm bypass — RESERVED TEST DOMAINS ONLY
// ----------------------------------------------------------------------------
// When EMAIL_AUTO_CONFIRM_DOMAINS is set on the server (production env or
// otherwise), any signup whose email domain matches the comma-separated
// allowlist gets `emailVerified` stamped immediately at create time and
// SKIPS the verification email dispatch entirely.
//
// This exists so the QA harness can sign up with a non-deliverable
// `*@quillmd-test.local` address (RFC 6762 reserved TLD) and proceed
// through the full authenticated flow without holding a real mailbox.
// It MUST NOT bypass verification for any real-user domain.
//
// Safety guards (defense in depth):
//
//  1. Default behavior: empty / missing env var → bypass NEVER fires.
//  2. Hard-coded `DENYLIST` of common real-mail domains. If the operator
//     fat-fingers EMAIL_AUTO_CONFIRM_DOMAINS=gmail.com (or any of the
//     other common providers), the bypass refuses to apply for those
//     domains regardless of what's in the allowlist.
//  3. The bypass is a positive opt-in — domain must EXPLICITLY appear
//     in the allowlist; substring matching is never used.
//  4. The caller (signupAction) emits a warning to stdout every time
//     this bypass actually fires, so it's visible in container logs.
//
// Compose plumbing: see docker-compose.yml `transcribe-md.environment`.
// On production we set `EMAIL_AUTO_CONFIRM_DOMAINS=quillmd-test.local`.
// ============================================================================

/** Common real-mail providers + our own production domain. The bypass
 *  refuses to fire for these even if mistakenly listed in the env var. */
const REAL_MAIL_DENYLIST: ReadonlySet<string> = new Set([
  // Big consumer providers
  'gmail.com',
  'googlemail.com',
  'outlook.com',
  'hotmail.com',
  'hotmail.co.uk',
  'live.com',
  'msn.com',
  'yahoo.com',
  'yahoo.co.uk',
  'ymail.com',
  'rocketmail.com',
  'icloud.com',
  'me.com',
  'mac.com',
  'protonmail.com',
  'proton.me',
  'aol.com',
  'fastmail.com',
  'pm.me',
  'zoho.com',
  'mail.com',
  'gmx.com',
  'gmx.de',
  'web.de',
  // Our own surfaces — production verification must NEVER be bypassed
  // for these even if env is misconfigured
  'quillmd.com',
  'ashtechgroup.com',
]);

/**
 * Returns true iff `email` belongs to a domain on the
 * `EMAIL_AUTO_CONFIRM_DOMAINS` allowlist AND not on the real-mail
 * denylist. Used by the signup action to skip the verification-email
 * dispatch for the QA-test reserved domain.
 *
 * Returns false on:
 *  - empty / missing env var
 *  - malformed email (no `@`)
 *  - domain in the real-mail denylist (defensive)
 *  - domain not explicitly listed in the env allowlist
 */
export function isAutoConfirmDomain(email: string): boolean {
  if (typeof email !== 'string') return false;
  const at = email.lastIndexOf('@');
  if (at < 1 || at === email.length - 1) return false;

  const domain = email.slice(at + 1).trim().toLowerCase();
  if (!domain) return false;

  // Defensive: even if the operator set EMAIL_AUTO_CONFIRM_DOMAINS=gmail.com,
  // refuse to bypass for real-mail domains.
  if (REAL_MAIL_DENYLIST.has(domain)) return false;

  const raw = process.env.EMAIL_AUTO_CONFIRM_DOMAINS ?? '';
  if (!raw.trim()) return false;

  const allowlist = new Set(
    raw
      .split(',')
      .map((d) => d.trim().toLowerCase())
      .filter((d) => d.length > 0)
  );

  return allowlist.has(domain);
}
