// ============================================================================
// PDF-native content signatures (feat/pdf-native-durable-cert). Two hashes make
// certification survive template-id rotation (re-upload/re-activation mints a new
// row id — see note-template-lifecycle.ts — which would otherwise orphan the cert
// keyed to the old id and silently drop the doctor back to the styled export):
//   - canvasHash    : sha256 of the doctor's blank PDF bytes (the exact form).
//   - structureHash : sha256 of the template's normalized labels (section +
//                     header). A re-upload of the SAME form parses to the SAME
//                     labels → same structureHash → the cert carries forward.
// Deterministic; PHI-safe (labels + bytes, never patient data).
// ============================================================================
import { createHash } from 'node:crypto';

const normLabel = (s: string): string =>
  s.toLowerCase().replace(/\s+/g, ' ').replace(/:\s*$/, '').trim();

/** sha256 of raw PDF bytes — the exact-form signature. */
export function canvasHash(bytes: Buffer | Uint8Array): string {
  return createHash('sha256').update(bytes).digest('hex');
}

/**
 * Structure signature: the template's labels in form order (header fields by
 * `order`, then sections in sequence), normalized + kind-tagged, sha256'd. Two
 * templates parsed from byte-identical forms produce the same value; a materially
 * different form (a renamed/added/removed labeled field) produces a different one.
 */
export function templateStructureHash(
  sections: ReadonlyArray<{ label: string }>,
  headerFields: ReadonlyArray<{ label: string; order?: number }>
): string {
  const parts = [
    ...[...headerFields]
      .sort((a, b) => (a.order ?? 0) - (b.order ?? 0))
      .map((f) => `h:${normLabel(f.label)}`),
    ...sections.map((s) => `s:${normLabel(s.label)}`),
  ];
  return createHash('sha256').update(parts.join('\n')).digest('hex');
}
