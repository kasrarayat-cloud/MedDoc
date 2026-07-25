// ============================================================================
// Dedicated synthetic account for AUTHENTICATED production smokes.
// ----------------------------------------------------------------------------
// Why this exists: prod sign-up auto-confirm is gated OFF
// (EMAIL_AUTO_CONFIRM_ALLOW_IN_PROD), so for months the only way to smoke an
// authenticated prod flow was to borrow a real clinician's account. That is
// unacceptable — it puts synthetic visits in a real doctor's chart list, writes
// their user id into the audit trail, and makes "is this row real?" unanswerable
// after the fact. Every deploy therefore shipped with the clinical flows
// verified only on QA.
//
// So: ONE clearly-named synthetic doctor, permanently pre-verified, whose
// clinical data is deleted after every smoke. It is a fixture, not a user.
//
// SAFETY PROPERTIES
//   * Email is under a .invalid TLD (RFC 2606). It can never resolve, so no
//     smoke run can email a real person even if a notification path fires.
//   * Its own practice — never shares a practiceId with a real clinician, so
//     practice-scoped queries can never surface a real patient to it.
//   * products = [TRANSCRIBE_MD] only. Explicitly NOT SUPER_ADMIN: a smoke
//     account must not be able to reach /admin.
//   * The cleaner refuses to delete anything not owned by this exact practice.
//
// The password is NOT stored in the repo. provision.ts writes it to
// /opt/meddoc-pro/.smoke-account.env (chmod 600, gitignored).
// ============================================================================

/** Practice slug. The cleaner keys every destructive query on this. */
export const SMOKE_PRACTICE_SLUG = 'quillmd-smoke-practice';

export const SMOKE_PRACTICE_NAME = 'QuillMD Smoke Test Practice (synthetic)';

/** .invalid is reserved by RFC 2606 and can never be delivered to. */
export const SMOKE_EMAIL = 'smoke-doctor@smoke.quillmd.invalid';

export const SMOKE_NAME = 'QuillMD Smoke Bot (synthetic — not a clinician)';

/** Where provision.ts drops the generated credentials for the operator. */
export const SMOKE_ENV_PATH = '/opt/meddoc-pro/.smoke-account.env';

/**
 * Refuse to operate on anything that is not the smoke fixture.
 *
 * Both scripts call this before any write. It exists because these are the only
 * scripts in the tree deliberately pointed at the PRODUCTION database — the
 * usual `assertNonProdDatabase()` guard would block their entire purpose — so
 * the guard has to be about SCOPE instead of target: whatever database we are
 * on, we only ever touch this one synthetic practice.
 */
export function assertIsSmokeFixture(row: {
  email?: string | null;
  practice?: { slug?: string | null } | null;
  slug?: string | null;
}): void {
  const slug = row.slug ?? row.practice?.slug ?? null;
  if (slug !== null && slug !== SMOKE_PRACTICE_SLUG) {
    throw new Error(
      `prod-smoke: refusing to touch practice "${slug}" — only ${SMOKE_PRACTICE_SLUG} is in scope.`
    );
  }
  if (row.email != null && row.email !== SMOKE_EMAIL) {
    throw new Error(
      `prod-smoke: refusing to touch user "${row.email}" — only ${SMOKE_EMAIL} is in scope.`
    );
  }
}
