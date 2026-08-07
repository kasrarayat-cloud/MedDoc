// ============================================================================
// VisitDelivery logging helper (T-M7)
// ----------------------------------------------------------------------------
// One-liner for writing a delivery row. Fire-and-forget from callers —
// a failed log must not fail the export (the PDF is already in the
// doctor's hands by the time we get here).
// ============================================================================

import prisma from '@meddoc/db';
import { redactPhi } from '@meddoc/ai';

export type DeliveryChannel =
  | 'clipboard_epic'
  | 'clipboard_athena'
  | 'clipboard_cerner'
  | 'clipboard_eclinicalworks'
  | 'clipboard_generic'
  | 'pdf'
  | 'docx'
  | 'email';

export interface LogDeliveryInput {
  visitId: string;
  channel: DeliveryChannel;
  destination?: string | null;
  sizeBytes?: number | null;
  /** ⚠️ T7 — REQUIRED. Callers already hold it (every export route resolves a
   *  practice-scoped visit first). Passed rather than derived because this
   *  writer is fire-and-forget: a derivation query here could fail as silently
   *  as the insert it feeds. */
  practiceId: string;
}

export function logDelivery(input: LogDeliveryInput): void {
  void prisma.visitDelivery
    .create({
      data: {
        visitId: input.visitId,
        // ⚠️ T7 — REQUIRED, AND THIS WRITER IS FIRE-AND-FORGET. Without it every
        // delivery log would fail SILENTLY (`void … .catch()` swallows it) and
        // the export would still look successful. tsc cannot help here: the
        // shared prisma client is typed `any`, so no Prisma argument in this
        // codebase is type-checked. Found by enumerating the table, not by the
        // compiler.
        practiceId: input.practiceId,
        channel: input.channel,
        destination: input.destination ?? null,
        sizeBytes: input.sizeBytes ?? null,
      },
    })
    .catch((err: unknown) => {
      // T-M18.3 A17: redactPhi in case a Prisma error echoes a column
      // value (visit.destination can carry an email address).
      console.error(
        '[delivery-log] write failed:',
        redactPhi(err instanceof Error ? err.message : err)
      );
    });
}
