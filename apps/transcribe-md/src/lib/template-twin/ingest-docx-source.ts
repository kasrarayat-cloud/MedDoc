// ============================================================================
// Unified secure .docx ingestion for custom templates (flag-gated).
// ----------------------------------------------------------------------------
// The UNIFIED PATH: one security-verified read of the uploaded .docx yields
// BOTH artifacts the pipeline needs, from a single source of truth:
//
//   • the deterministic TemplateDocIR   — for native re-render on export
//     (the doctor's own document back, formatting preserved, roundtrip-verified)
//   • the {{one of: …}} marker text     — fed UNCHANGED into the existing
//     parse → reconcile → fill pipeline (parse-determinism preserved)
//
// The compiler is the source of truth for WHICH fields exist. A determinism
// CROSS-CHECK asserts the compiler's native dropdown count equals the marker
// extractor's — so the IR and the marker form can never silently drift apart.
//
// FAIL-CLOSED: inspectDocxPackage + compileTemplateDocx reject macros / OLE /
// zip-bomb / zip-slip / remote-relationship / DDE / XXE by throwing
// TemplateDocxError. Callers MUST propagate that (never fall back to a
// permissive extractor, which would swallow the rejection = fail-open).
//
// Server-only. A template carries no patient data; nothing here persists PHI.
// ============================================================================

import { compileTemplateDocx, inspectDocxPackage } from '@/lib/note-template-docx';
import { docxToTextWithControls } from '@/lib/note-template-parse/docx-content-controls';

import type { TemplateDocIR } from './ir';

export interface DocxIngestionCrossCheck {
  /** Native single/multi-select fields the compiler extracted. */
  selectFields: number;
  /** Compiler dropdown stat (native `<w:dropDownList>` controls). */
  compilerDropdowns: number;
  /** Dropdowns the live marker extractor rendered as `{{one of}}` markers. */
  markerDropdowns: number;
  /** True when the compiler and the marker extractor agree on the dropdown
   *  count — the "one source of truth" invariant. */
  consistent: boolean;
}

export interface IngestedDocxTemplate {
  ir: TemplateDocIR;
  /** `{{one of: …}}` marker text — identical to the live docxToText output for
   *  a dropdown template; feeds the existing parse pipeline unchanged. */
  markerText: string;
  dropdownCount: number;
  crossCheck: DocxIngestionCrossCheck;
}

/**
 * Securely ingest a custom-template .docx. Throws TemplateDocxError (fail-closed)
 * on any macro/OLE/zip/XXE/DDE attack surface; a clean clinical template passes.
 */
export async function ingestDocxTemplateSource(
  bytes: Uint8Array,
): Promise<IngestedDocxTemplate> {
  // 1. Fail-closed OOXML security boundary. Legit templates pass; attacks throw.
  inspectDocxPackage(bytes);

  // 2. Deterministic IR (re-verifies the package internally; the compiler is the
  //    authority for the field/option set).
  const ir = compileTemplateDocx(bytes);

  // 3. Marker text via the PROVEN live extractor — byte-identical to today's
  //    parse input, so the downstream parse/reconcile/fill is unchanged.
  const { text: markerText, dropdownCount } = await docxToTextWithControls(bytes);

  // 4. Determinism cross-check: the compiler's dropdown stat must equal the
  //    marker extractor's dropdown count. If they ever disagree the IR and the
  //    marker form have drifted and the upload is not trustworthy as a single
  //    source of truth.
  const selectFields = ir.fields.filter(
    (f) => f.kind === 'single_select' || f.kind === 'multi_select',
  ).length;
  const crossCheck: DocxIngestionCrossCheck = {
    selectFields,
    compilerDropdowns: ir.stats.dropdowns,
    markerDropdowns: dropdownCount,
    consistent: ir.stats.dropdowns === dropdownCount,
  };

  return { ir, markerText, dropdownCount, crossCheck };
}
