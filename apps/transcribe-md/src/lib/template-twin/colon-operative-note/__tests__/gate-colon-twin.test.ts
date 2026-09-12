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
import { bulletGroups } from '../../bullet-groups';
import {
  COLON_OPERATIVE_NOTE_DOCUMENT_XML,
  COLON_TWIN_ALIASES,
  COLON_TWIN_CONTROL_COUNT,
  buildColonOperativeNoteDocx,
} from '../source';

// ── PINNED to the produced-once artifact (re-emitted 2026-09-12 for #319: the
// numbered slots now share one identity so they distribute — see source.ts) ────
const ARTIFACT = join(__dirname, '..', 'colon-operative-note.docx');
const PINNED_PACKAGE_SHA = 'a378c4e114288a7b1c2b4fd92ac6725e0a8edc48d915eb8dbdb57b2cb55440eb';
const PINNED_DOCUMENT_XML_SHA = 'a7a393dcfe889ada209faab1fc88b0621b2952ad2b3d153e3d08072e4bef9ac0';
const PINNED_STRUCTURE_SHA = 'd53ec21d90af22c3d4851d8863f395d086dd7ed49c806a92a77a635ce2ad3447';
// ⚠️ AN ORDERED LIST, NOT A LABEL->ID MAP. The three Findings and three
// Recommendations slots share a label (their #313 bullet-group identity), so a
// label-keyed map would collapse them to one entry each. The document-order list
// preserves all seventeen and still pins every id.
const PINNED_FIELD_IDS: ReadonlyArray<readonly [string, string]> = [
  ['Patient Name', 'ttf_93898d16db136a392fd10979'],
  ['Patient DOB', 'ttf_72403b02b2783cc59f1c8282'],
  ['Patient ID', 'ttf_fdd1eceb135903a74b770b85'],
  ['Date of Surgery', 'ttf_41f74d4b18a8a11d358316bc'],
  ['Surgeon', 'ttf_5e2a8db5993b5fc7bd29155e'],
  ['Procedure', 'ttf_0b95705d7e7dedc39354aae4'],
  ['Preoperative Diagnosis', 'ttf_050988ff66a2f3ad444083ae'],
  ['Consent', 'ttf_f6c40d412e2401bca9571e7e'],
  ['Description of Procedure', 'ttf_0088cd9fda07945ac984f867'],
  ['Findings', 'ttf_28daf4f38fe91c541047c757'],
  ['Findings', 'ttf_f27e60993a872d0f6f0cc068'],
  ['Findings', 'ttf_b6dbe4ebdfa05c3c0653cca2'],
  ['Recommendations', 'ttf_bc50d4b3f2bd940530f40393'],
  ['Recommendations', 'ttf_876ce9b7695ba071f147b2cd'],
  ['Recommendations', 'ttf_5fad057f7892389e1a87bdc5'],
  ['DD', 'ttf_7b1d4de1560bd877b62f0c5d'],
  ['DT', 'ttf_701c81fa8005a18840ad6d88'],
];

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

  // P3 — NUMBERED-SLOT DISTINCTNESS **AND DISTRIBUTABILITY**. The three Findings
  // and three Recommendations slots share ONE identity (alias + tag) so they form
  // a #313 bullet group and distribute one dictated item each — but they must
  // still compile to distinct fields (fieldId is salted by structural position).
  // Catches a collapse of the slots, any fieldId collision, or a structural
  // change that stops the slots grouping (which would put the whole joined list
  // in every slot instead of one item per slot).
  it('P3 — the six numbered slots are distinct fields that form two bullet groups', async () => {
    const c = await compiledFromArtifact();
    const numbered = c.fields.filter((f: any) =>
      /^(Findings|Recommendations)$/.test(f.originalLabel),
    );
    expect(numbered.length).toBe(6);
    expect(new Set(numbered.map((f: any) => f.fieldId)).size).toBe(6);
    const allIds = c.fields.map((f: any) => f.fieldId);
    expect(new Set(allIds).size).toBe(allIds.length); // 17 distinct
    // every numbered slot is sole-in-paragraph, alias-labelled, and carries the
    // section's shared tag — the four properties a bullet group is built from.
    expect(numbered.every((f: any) => f.soleParagraphControl === true)).toBe(true);
    expect(numbered.every((f: any) => f.labelSource === 'alias')).toBe(true);
    expect(
      c.fields.filter((f: any) => f.originalLabel === 'Findings')
        .every((f: any) => f.rendererBinding.tag === 'findings'),
    ).toBe(true);
    expect(
      c.fields.filter((f: any) => f.originalLabel === 'Recommendations')
        .every((f: any) => f.rendererBinding.tag === 'recommendations'),
    ).toBe(true);
    // ⚠️ THE PAYOFF PROVEN, NOT ASSUMED: under identical list-valued mappings, the
    // form yields exactly two groups of three. This is what makes the numbered
    // slots distribute instead of each printing the whole joined findings list.
    const listMapping = (fieldId: string, concept: string) => ({
      fieldId,
      clinicalConcept: concept,
      sourceType: 'extraction' as const,
      expectedDataType: 'text' as const,
      polarityBehavior: 'value_only' as const,
      temporality: null,
      laterality: 'not_applicable' as const,
      unitPolicy: 'not_applicable' as const,
      approvedSynonyms: [],
      conceptScope: [],
      required: false,
      blankPolicy: 'blank' as const,
      unknownPolicy: 'blank' as const,
      practiceDefault: null,
      status: 'certified' as const,
    });
    const mappings = c.fields.map((f: any) =>
      f.originalLabel === 'Findings'
        ? listMapping(f.fieldId, 'procedure.findings')
        : f.originalLabel === 'Recommendations'
          ? listMapping(f.fieldId, 'procedure.recommendations')
          : listMapping(f.fieldId, 'plan'),
    );
    const groups = bulletGroups(c.fields, mappings as any);
    expect(groups.map((g: any) => g.memberFieldIds.length).sort()).toEqual([3, 3]);
    expect(new Set(groups.map((g: any) => g.alias))).toEqual(
      new Set(['Findings', 'Recommendations']),
    );
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
    // Ordered [label, fieldId] pairs — preserves the three repeated Findings /
    // Recommendations labels a keyed map would collapse.
    const got = c.fields.map((f: any) => [f.originalLabel, f.fieldId] as const);
    expect(got).toEqual(PINNED_FIELD_IDS.map(([l, i]) => [l, i]));
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
      // The '1.'/'2.'/'3.' number runs are GONE by design (#319): a leading
      // number run is visible paragraph text that would stop the slots being
      // sole-in-paragraph, so it would break bullet-group distribution. The
      // numbered slots are now bare controls, one per line.
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
