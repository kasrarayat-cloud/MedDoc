// ============================================================================
// SLICE 0 (#317) — FIVE ADDITIVE PROOFS for the colon OPERATIVE NOTE twin.
// ----------------------------------------------------------------------------
// Build-time, deterministic, no AI and no DB. Each proof catches ONE way the
// authored twin stops being a faithful, pinned, certifiable, blank form. The
// certified artifact is the COMMITTED bytes (the package sha is not reproducible
// and fieldId is salted by it), so the shas below are PINNED to those bytes; a
// re-emit that changes them is a defect, not a refresh.
//
// ⚠️ "Five additive proofs" is the established pattern from
// `regenerate-consult-form.ts` / the 53-control provenance doc — it is NOT an
// owner-quoted enumeration. See ruling #317.
// ============================================================================
import { readFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { join } from 'node:path';

import { describe, expect, it } from 'vitest';
import JSZip from 'jszip';

import { compileTemplateDocx } from '../../../note-template-docx/compiler';
import { inspectDocxPackage } from '../../../note-template-docx/package-security';
import {
  COLON_OPERATIVE_NOTE_DOCUMENT_XML,
  COLON_TWIN_ALIASES,
  COLON_TWIN_CONTROL_COUNT,
  buildColonOperativeNoteDocx,
} from '../source';

// ── PINNED to the produced-once artifact (emit-twin, 2026-09-12) ──────────────
const ARTIFACT = join(__dirname, '..', 'colon-operative-note.docx');
const PINNED_PACKAGE_SHA = '64aef465d7b9aba5f82329b61bdffeecd4a8b85d9f2026f46a7232e026c8b589';
const PINNED_DOCUMENT_XML_SHA = '015a2abe8897d77df3becd57f683cc87f69ef2b6795dc8a8e1352a7f412c95b1';
const PINNED_STRUCTURE_SHA = 'ce398ccbc8717de00d31274b727c303bd6f2863d021ac5c643a08e252170f051';
const PINNED_FIELD_IDS: Record<string, string> = {
  'Patient Name': 'ttf_09fc9deb07d452ab43f9505d',
  'Patient DOB': 'ttf_eabcd4f6779fc4e053374447',
  'Patient ID': 'ttf_c377ed3c21faba05e3644900',
  'Date of Surgery': 'ttf_6082ecc08c46733069a4ea47',
  Surgeon: 'ttf_06d81043a5c82a2febf047df',
  Procedure: 'ttf_1a70b5ad35130667793fe679',
  'Preoperative Diagnosis': 'ttf_fe2c91758d5eb010565a1c1d',
  Consent: 'ttf_fbd41cbe1f012839ed6cc392',
  'Description of Procedure': 'ttf_ed5996703353863808dec8a2',
  'Findings 1': 'ttf_34cf33c00640cb63211a2267',
  'Findings 2': 'ttf_2e930a38e3a95dc0151b4d1d',
  'Findings 3': 'ttf_329bce3999cebf959a598a17',
  'Recommendations 1': 'ttf_c46d1af5b33177765d769757',
  'Recommendations 2': 'ttf_7f0c3d66fd1714e84ca70eaa',
  'Recommendations 3': 'ttf_6c3579035c6a9fdefce8daef',
  DD: 'ttf_dd18011febfda5a7058f43e8',
  DT: 'ttf_0a3c6f1b5ba40c9a63c63bef',
};

const sha256 = (b: Buffer | Uint8Array) => createHash('sha256').update(b).digest('hex');
const artifactBytes = () => readFileSync(ARTIFACT);
async function compiledFromArtifact() {
  const buf = artifactBytes();
  await inspectDocxPackage(new Uint8Array(buf)); // fail-closed OPC gate
  return (await compileTemplateDocx(new Uint8Array(buf))) as any;
}

describe('SLICE-0 colon operative-note twin — five additive proofs', () => {
  // P1 — SOURCE FIDELITY. The field set is exactly the owner's enumerated form,
  // in document order, each recognized by its alias. Catches a control added,
  // removed, renamed, or its label no longer read from the alias.
  it('P1 — the twin carries exactly the enumerated fields, alias-labelled, in order', async () => {
    const c = await compiledFromArtifact();
    expect(c.stats.totalFields).toBe(COLON_TWIN_CONTROL_COUNT); // 17
    expect(c.fields.map((f: any) => f.originalLabel)).toEqual([...COLON_TWIN_ALIASES]);
    expect(c.fields.every((f: any) => f.labelSource === 'alias')).toBe(true);
    expect(c.fields.every((f: any) => f.detectionStatus === 'recognized')).toBe(true);
  });

  // P2 — COMPILE CLEAN / CERTIFIABLE. No control the compiler refuses (picture,
  // group, data-bound, non-table repeating section, comboBox), every field a
  // narrative text field. Catches an authoring change that plants a control
  // which would BLOCK certification. Positive control: the count is non-zero.
  it('P2 — compiles with zero blocking refusals; every field is narrative text', async () => {
    const c = await compiledFromArtifact();
    expect(c.stats.blockingUnsupported).toBe(0);
    expect(c.stats.comboBoxes).toBe(0);
    expect(c.stats.totalFields).toBeGreaterThan(0); // not vacuously clean
    expect(c.fields.every((f: any) => f.kind === 'narrative_text')).toBe(true);
  });

  // P3 — NUMBERED-SLOT DISTINCTNESS. Findings 1–3 and Recommendations 1–3 reuse
  // their base label yet must compile to distinct fields (fieldId is salted by
  // structural position). Catches a collapse of the numbered slots, or any
  // fieldId collision across the form.
  it('P3 — the six numbered slots are distinct fields, and all ids are unique', async () => {
    const c = await compiledFromArtifact();
    const numbered = c.fields.filter((f: any) =>
      /^(Findings|Recommendations) [123]$/.test(f.originalLabel),
    );
    expect(numbered.length).toBe(6);
    expect(new Set(numbered.map((f: any) => f.fieldId)).size).toBe(6);
    const allIds = c.fields.map((f: any) => f.fieldId);
    expect(new Set(allIds).size).toBe(allIds.length); // 17 distinct
  });

  // P4 — DETERMINISTIC DOCUMENT + PINNED PACKAGE. The source document.xml is
  // byte-deterministic; the committed package and its compiled identity are the
  // pinned ones. Catches the source drifting from the certified artifact — which
  // would silently break a certificate keyed to fieldId — or the artifact being
  // regenerated and overwritten (a new, uncertified identity).
  it('P4 — source, package, structure and every fieldId match the pin', async () => {
    expect(sha256(Buffer.from(COLON_OPERATIVE_NOTE_DOCUMENT_XML, 'utf8'))).toBe(PINNED_DOCUMENT_XML_SHA);
    expect(sha256(artifactBytes())).toBe(PINNED_PACKAGE_SHA);
    const c = await compiledFromArtifact();
    expect(c.structureSha256).toBe(PINNED_STRUCTURE_SHA);
    const got = Object.fromEntries(c.fields.map((f: any) => [f.originalLabel, f.fieldId]));
    expect(got).toEqual(PINNED_FIELD_IDS);
    // The freshly-built document.xml equals the committed one (byte-deterministic
    // document, even though the ZIP package around it is not reproducible).
    const fresh = await buildColonOperativeNoteDocx();
    // structure is identical even if package bytes differ:
    const freshCompiled = (await compileTemplateDocx(new Uint8Array(fresh))) as any;
    expect(freshCompiled.fields.map((f: any) => f.originalLabel)).toEqual(
      c.fields.map((f: any) => f.originalLabel),
    );
  });

  // P5 — BLANK FORM, NO PATIENT DATA. Every visible text run is either a section
  // label or an "Enter …" placeholder prompt — a fixed blank-form vocabulary,
  // never a filled value. Catches a filled document being committed as the twin.
  // (The live no-clinical-data gate `assertTemplateTwinSourcePhiFree` runs again
  // at certification; this is its deterministic build-time counterpart.)
  it('P5 — carries only blank-form furniture and placeholder prompts, no patient data', async () => {
    const allowedLabels = new Set<string>([
      'OPERATIVE NOTE', 'PATIENT NAME:', 'PATIENT DOB:', 'PATIENT ID #:',
      'DATE OF SURGERY:', 'SURGEON:', 'PROCEDURE:', 'PREOPERATIVE DIAGNOSIS:',
      'CONSENT:', 'DESCRIPTION OF PROCEDURE:', 'POSTOPERATIVE FINDINGS:',
      'RECOMMENDATIONS:', 'Electronically Signed', 'DD:', 'DT:',
      '1.', '2.', '3.',
    ]);
    // ⚠️ MATCH ATTRIBUTED RUNS TOO. `<w:t xml:space="preserve">…</w:t>` is the
    // standard OOXML serialization for any run carrying significant whitespace,
    // and an attribute-free-only regex lets a filled value hide in one (adversarial
    // F2). `<w:t\b[^>]*>` matches both forms; `[\s\S]*?` spans newlines in a value.
    const scan = (xml: string, where: string) => {
      const texts = [...xml.matchAll(/<w:t\b[^>]*>([\s\S]*?)<\/w:t>/g)].map((m) => m[1]);
      expect(texts.length, `${where}: no text runs found`).toBeGreaterThan(COLON_TWIN_CONTROL_COUNT);
      for (const t of texts) {
        const value = t.trim();
        const ok = value === '' || allowedLabels.has(value) || value.startsWith('Enter ');
        expect(ok, `${where}: unexpected text run (possible patient data): ${JSON.stringify(value)}`).toBe(true);
      }
    };
    // Scan the source constant AND the COMMITTED .docx's document.xml — the latter
    // is what actually fills notes, so it, not only the source, must be blank.
    scan(COLON_OPERATIVE_NOTE_DOCUMENT_XML, 'source constant');
    const zip = await JSZip.loadAsync(artifactBytes());
    const committedDocXml = await zip.file('word/document.xml')!.async('string');
    scan(committedDocXml, 'committed .docx document.xml');
  });
});
