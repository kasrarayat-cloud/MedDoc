// ============================================================================
// Unified status vocabulary for the C3 skin (Stage 1).
// ----------------------------------------------------------------------------
// The live app surfaces ~6 user-facing words derived from 7 DB lifecycle
// states (visitStatusLabel in visits/[id]/page.tsx). The calm design collapses
// the whole lifecycle to FOUR plain words used identically everywhere:
//   Recording → Processing → Ready to sign → Signed   (+ Failed for errors)
//
// PURELY a label/key mapping over the EXISTING TranscribeVisitStatus enum — the
// DB enum is unchanged; the worker still transitions QUEUED→…→READY→SIGNED. We
// reuse the existing `qm-lin-pill*` classes so the pills are native to the
// design system.
// ============================================================================
import { TranscribeVisitStatus } from '@prisma/client';

export type C3StatusKey = 'recording' | 'processing' | 'ready' | 'signed' | 'failed';

export interface C3Status {
  key: C3StatusKey;
  label: string;
  /** existing Linear-V1 pill class, so the chip looks native */
  pillClass: string;
}

export function c3Status(
  status: TranscribeVisitStatus,
  needsReview = false,
): C3Status {
  switch (status) {
    case TranscribeVisitStatus.SIGNED:
      return { key: 'signed', label: 'Signed', pillClass: 'qm-lin-pill qm-lin-pill--signed' };
    case TranscribeVisitStatus.FAILED:
      return { key: 'failed', label: 'Failed', pillClass: 'qm-lin-pill bg-linear-danger/15 text-linear-danger' };
    case TranscribeVisitStatus.READY:
      // "Needs review" and "Ready" both collapse to the one calm word.
      return {
        key: 'ready',
        label: 'Ready to sign',
        pillClass: needsReview ? 'qm-lin-pill qm-lin-pill--review' : 'qm-lin-pill qm-lin-pill--ready',
      };
    case TranscribeVisitStatus.QUEUED:
      // QUEUED = awaiting/capturing input → the "Recording" phase.
      return { key: 'recording', label: 'Recording', pillClass: 'qm-lin-pill qm-lin-pill--draft' };
    default:
      // TRANSCRIBING / EXTRACTING / DRAFTING / CRITIQUING / POLISHING / AUTOMATING
      return { key: 'processing', label: 'Processing', pillClass: 'qm-lin-pill qm-lin-pill--processing' };
  }
}
