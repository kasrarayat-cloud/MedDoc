// ============================================================================
// Additive review-state writer (2026-06-11 — audit BLOCK-2 on the L6
// fabrication-gate fix).
// ----------------------------------------------------------------------------
// The worker's final READY write used to assign `needsReview`/`reviewReason`
// from detectIncompleteAutomation UNCONDITIONALLY — clobbering review state
// set earlier in the pipeline (the L6 fabrication-gate rejection banner, L6
// unfixable-criticals, the 02.8 allergy-conflict flag) whenever the L7
// fan-out was clean. The clinician then saw a clean READY visit whose
// critique-flagged fixes were silently unapplied.
//
// This helper is ADDITIVE, matching the 02.8 precedent (worker.ts COALESCE
// comment): needsReview can only be turned ON here, never off; reviewReason
// concatenates rather than replaces (existing reason first — it was set
// earlier in the pipeline and is usually the more safety-relevant one).
// SQL-side so it is atomic — no read-modify-write race with concurrent
// review-flag writers.
// ============================================================================

import prisma from '@meddoc/db';
import { runTemplateTwinSyntheticQaClaimBoundMutation } from '@/worker/staging-qa-mutation-fence';

export async function applyAdditiveReviewState(
  visitId: string,
  incoming: { needsReview: boolean; reviewReason: string | null },
  actor?: { userId: string; practiceId: string },
): Promise<void> {
  // Nothing to add — leave the row's review state exactly as the pipeline
  // set it (writing `needsReview = needsReview OR false` would be a no-op
  // anyway, but skipping avoids a pointless UPDATE on every clean visit).
  if (!incoming.needsReview && incoming.reviewReason === null) return;

  // NULL-safe concat: in Postgres `a || NULL` is NULL, so COALESCE walks
  // (both → concatenated, row-only → row, incoming-only → incoming).
  if (!actor) {
    await prisma.$executeRaw`
      UPDATE "transcribe_visits"
      SET "needsReview" = "needsReview" OR ${incoming.needsReview},
          "reviewReason" = COALESCE(
            "reviewReason" || ' ' || ${incoming.reviewReason},
            "reviewReason",
            ${incoming.reviewReason}
          )
      WHERE id = ${visitId}
    `;
    return;
  }
  await runTemplateTwinSyntheticQaClaimBoundMutation({
    visitId,
    userId: actor.userId,
    practiceId: actor.practiceId,
    mutate: async (client) => {
      await client.$executeRaw`
        UPDATE "transcribe_visits"
        SET "needsReview" = "needsReview" OR ${incoming.needsReview},
            "reviewReason" = COALESCE(
              "reviewReason" || ' ' || ${incoming.reviewReason},
              "reviewReason",
              ${incoming.reviewReason}
            )
        WHERE id = ${visitId}
      `;
    },
  });
}
