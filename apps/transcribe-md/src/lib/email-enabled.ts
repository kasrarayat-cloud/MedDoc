// ============================================================================
// Email-delivery feature flag — single source of truth (T-M16.2)
// ----------------------------------------------------------------------------
// The email-delivery feature gates on TWO env vars so ops can stage a
// rollout:
//
//   RESEND_API_KEY=<key>            → Resend is reachable
//   RESEND_FROM_VERIFIED=true       → the From address has been domain-
//                                     verified at resend.com/domains
//
// Both must be set for the delivery gate to flip on. Missing either means we
// can't responsibly deliver mail yet, so bearer links are never minted without
// a configured delivery path, production signup is unavailable, and
// change-email returns unavailable.
//
// Account verification is a separate authentication policy. In production it
// remains mandatory even while the provider is absent, unavailable, or being
// rotated. Otherwise an email-provider outage would silently weaken login
// authorization for every existing unverified account.
//
// Previously duplicated inline in apps/transcribe-md/src/app/visits/[id]/page.tsx.
// Extracted here so every caller (Settings UI, login flow, signup flow)
// reads the same rule.
// ============================================================================

export function isEmailDeliveryEnabled(): boolean {
  return (
    !!process.env.RESEND_API_KEY && process.env.RESEND_FROM_VERIFIED === "true"
  );
}

/**
 * Whether credential authentication must require a verified email address.
 *
 * Production is deliberately non-configurable and fail-closed. Development
 * and test retain the historical provider-free workflow, while allowing a
 * focused environment to opt into the production policy explicitly.
 */
export function isEmailVerificationRequired(): boolean {
  if (process.env.NODE_ENV === "production") return true;
  return (
    process.env.EMAIL_VERIFICATION_REQUIRED === "true" ||
    isEmailDeliveryEnabled()
  );
}
