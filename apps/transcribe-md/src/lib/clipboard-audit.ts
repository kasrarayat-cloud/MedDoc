// ============================================================================
// Client helper — record that clinical text was copied to the clipboard.
// ----------------------------------------------------------------------------
// Copying a SOAP section, the patient summary, or the whole note puts PHI on
// the OS clipboard, outside anything the app controls. Under §164.312(b) that
// is a disclosure worth recording, and until now only ONE of the four copy
// affordances recorded it: the EHR-format copy in the sign-and-send modal goes
// through /export/clipboard, while the per-section pill, the patient-summary
// copy and the full-note copy wrote to the clipboard directly and left no
// trace. copy-section-button.tsx even said so out loud — "No VisitDelivery row
// — too granular for the audit trail" — which was a defensible product call
// about DELIVERY rows, but it also meant a doctor could lift every section of
// a note and the audit trail would show nothing at all.
//
// Fire-and-forget on purpose. The clipboard write has already happened by the
// time this runs; making the user wait on (or fail from) an audit round-trip
// would be strictly worse UX for zero safety gain. A failed beacon is logged
// to the console and dropped — it must never surface as a copy error, because
// the copy genuinely succeeded.
//
// keepalive lets the request survive a tab close in the same tick as the copy.
// Only the SIZE of the text is sent, never the text itself: the server already
// owns the note, so echoing PHI back over the wire would add exposure and no
// information.
// ============================================================================

export type ClipboardScope = 'section' | 'summary' | 'full_note';

export function reportClipboardCopy(
  visitId: string,
  scope: ClipboardScope,
  section: string,
  text: string
): void {
  if (!visitId || !text) return;
  try {
    void fetch(`/api/visits/${encodeURIComponent(visitId)}/export/clipboard-section`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ scope, section, sizeBytes: text.length }),
      keepalive: true,
    }).catch((err) => {
      console.warn('[clipboard-audit] beacon failed (copy itself succeeded):', err);
    });
  } catch (err) {
    console.warn('[clipboard-audit] beacon threw (copy itself succeeded):', err);
  }
}
