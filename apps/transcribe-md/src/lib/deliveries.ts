// ============================================================================
// VisitDelivery logging helper (T-M7)
// ----------------------------------------------------------------------------
// One-liner for writing a delivery row. Fire-and-forget from callers —
// a failed log must not fail the export (the PDF is already in the
// doctor's hands by the time we get here).
// ============================================================================

import prisma from '@meddoc/db';

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
}

export function logDelivery(input: LogDeliveryInput): void {
  void prisma.visitDelivery
    .create({
      data: {
        visitId: input.visitId,
        channel: input.channel,
        destination: input.destination ?? null,
        sizeBytes: input.sizeBytes ?? null,
      },
    })
    .catch((err: unknown) => {
      console.error('[delivery-log] write failed:', err);
    });
}
