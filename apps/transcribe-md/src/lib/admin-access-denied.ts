// ============================================================================
// AdminAccessDeniedError — the typed refusal a /admin data helper throws
// ----------------------------------------------------------------------------
// Lives outside `app/admin/_lib/admin-gate.ts` on purpose: that module is
// `server-only` and pulls in next/navigation + React `cache`, while
// `lib/admin-api-gate.ts` only needs to RECOGNISE this error so an adminApi
// route answers a refused data read with its usual silent 404 instead of a 500.
// No framework imports here, so either side can import it cheaply.
// ============================================================================

/** Why the caller was refused. Mirrors the non-`ok` arms of `AdminVerdict`. */
export type AdminDeniedKind = 'denied' | 'mfa-required' | 'stale';

export class AdminAccessDeniedError extends Error {
  readonly kind: AdminDeniedKind;

  constructor(kind: AdminDeniedKind) {
    super(`admin data access refused (${kind})`);
    this.name = 'AdminAccessDeniedError';
    this.kind = kind;
  }
}
