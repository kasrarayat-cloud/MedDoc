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
// Both must be set for the gate to flip on. Missing either means we
// can't responsibly deliver mail yet, and features that would otherwise
// require email (forgot-password, email-verification gate, email-change)
// degrade gracefully — forgot-password logs the link, signup skips the
// verify step, change-email 4xx's.
//
// Previously duplicated inline in apps/transcribe-md/src/app/visits/[id]/page.tsx.
// Extracted here so every caller (Settings UI, login flow, signup flow)
// reads the same rule.
// ============================================================================

export function isEmailDeliveryEnabled(): boolean {
  return (
    !!process.env.RESEND_API_KEY &&
    process.env.RESEND_FROM_VERIFIED === 'true'
  );
}
