import { z } from 'zod';

import { MediaReviewEvidenceFileSchema } from './media-review';
import { PhysicianIntentDecisionFileSchema } from './physician-intent';

/** Draft 2020-12 schemas embedded in the downloadable human-gate package.
 * Runtime Zod validation remains authoritative and adds cross-document hash,
 * source-commit, field-identity, and readiness checks. */
export const PHYSICIAN_INTENT_DECISION_JSON_SCHEMA = z.toJSONSchema(
  PhysicianIntentDecisionFileSchema,
  {
    target: 'draft-2020-12',
    io: 'input',
  },
);

export const MEDIA_REVIEW_EVIDENCE_JSON_SCHEMA = z.toJSONSchema(
  MediaReviewEvidenceFileSchema,
  {
    target: 'draft-2020-12',
    io: 'input',
  },
);
