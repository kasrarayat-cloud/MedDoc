// ============================================================================
// Custom-template .docx generator (T-M24)
// ----------------------------------------------------------------------------
// Given the doctor's original template binary + the L7f-filled
// token→content dict, produce a new .docx buffer with every
// `{{token}}` replaced in place. Preserves the doctor's formatting
// exactly (fonts, headers, tables, letterhead) because docxtemplater
// operates on the original file's XML stream, not a regenerated one.
//
// Called from the on-demand export endpoint (visits/[id]/export/
// template-docx) so we don't persist the filled binary — a quick
// regen from the stored text + cached template is cheaper than
// managing another MinIO object lifecycle.
// ============================================================================

import Docxtemplater from 'docxtemplater';
import PizZip from 'pizzip';

/** Fill a .docx template with the L7f-produced content dict.
 *
 *  - `templateBuffer` is the raw .docx from MinIO.
 *  - `content` is `JSON.parse(visit.filledTemplate)` — a dict like
 *    `{ hpi: "…", assessment: "…" }`. Tokens absent from the dict
 *    (either because Claude omitted them or because they're
 *    unsupported) render as empty via the nullGetter hook so the
 *    output never shows a literal `{{token}}` in the doctor's
 *    downloaded file.
 *
 *  Throws if the template archive is corrupt (pizzip throws) or if
 *  docxtemplater hits a template-syntax error (e.g. the doctor
 *  typed `{{hpi}` with one brace). Caller decides whether to 500
 *  the request or return 415 "template malformed".
 */
export function fillTemplate(
  templateBuffer: Buffer,
  content: Record<string, string>
): Buffer {
  const zip = new PizZip(templateBuffer);
  const doc = new Docxtemplater(zip, {
    paragraphLoop: true,
    linebreaks: true,
    // T-M24 uses `{{double}}` braces across the parser / extractor /
    // UI guide. docxtemplater's default is single-brace `{tag}`, so
    // we override here to keep the user-facing token syntax consistent
    // and avoid matching prose that happens to have a stray `{…}`
    // (e.g. a legitimate "{5 mg}" in a medication note).
    delimiters: { start: '{{', end: '}}' },
    // nullGetter fires for every token whose key isn't in `content`
    // (or maps to undefined / null). Returning '' keeps the slot
    // blank rather than emitting 'undefined' / the raw `{{tag}}`.
    nullGetter: () => '',
  });
  doc.render(content);
  const out = doc.getZip().generate({
    type: 'nodebuffer',
    compression: 'DEFLATE',
  });
  // docxtemplater's type says `any` for the return of generate();
  // at runtime it's a Node Buffer when type: 'nodebuffer'.
  return out as Buffer;
}
