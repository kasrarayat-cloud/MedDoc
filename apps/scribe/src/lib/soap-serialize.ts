// ============================================================================
// apps/scribe — SOAP serialization helper for the internal API call
// ----------------------------------------------------------------------------
// The internal API (§D4) takes the structured SoapNote JSON directly —
// MedDoc Pro's display layer renders markdown at view time. We keep the
// raw JSON on the Scribe side in ScribeOutput.content, and POST the same
// shape to /api/internal/patients/:id/notes.
// ============================================================================

import type { SoapNote } from '@meddoc/types';

export function readSoapFromOutput(content: unknown): SoapNote | null {
  if (content == null) return null;
  if (typeof content === 'string') {
    try {
      return JSON.parse(content) as SoapNote;
    } catch {
      return null;
    }
  }
  return content as SoapNote;
}
