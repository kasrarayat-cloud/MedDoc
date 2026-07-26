import { readFileSync } from 'node:fs';
import path from 'node:path';

import { describe, expect, it } from 'vitest';

import { compileTemplateDocx } from '@/lib/note-template-docx';
import { docxToTextWithControls } from '@/lib/note-template-parse/docx-content-controls';

import { bridgeChoiceSlotPicks } from '../picks-bridge';
import type { TemplateDocIR, TemplateField } from '../ir';

const WM_IOV = path.resolve(process.cwd(), '../../WM IOV Template.docx');
const MARKER_RE = /\{\{one of:\s*([^}]*)\}\}/g;

async function loadWmIov(): Promise<{ ir: TemplateDocIR; markerText: string }> {
  const bytes = new Uint8Array(readFileSync(WM_IOV));
  const ir = compileTemplateDocx(bytes);
  const { text } = await docxToTextWithControls(bytes);
  return { ir, markerText: text };
}

function selects(ir: TemplateDocIR): TemplateField[] {
  return ir.fields
    .filter((f) => f.kind === 'single_select' && f.detectionStatus !== 'unsupported' && !f.rowPrototype)
    .sort((a, b) => a.displayOrder - b.displayOrder || a.fieldId.localeCompare(b.fieldId));
}

/** Fill the marker text by replacing marker N with option (N % optCount). */
function fillNote(markerText: string): { note: string; chosenText: string[] } {
  let i = 0;
  const chosenText: string[] = [];
  const note = markerText.replace(MARKER_RE, (_full, optsStr) => {
    const opts = String(optsStr).split('|').map((o) => o.trim()).filter(Boolean);
    const choice = opts[i % opts.length];
    chosenText.push(choice);
    i += 1;
    return choice;
  });
  return { note, chosenText };
}

/** The bridge is a MATCHER: a pick is only cited when a real fact entails the
 *  option. These facts entail every option these tests expect to be filled;
 *  options expected to stay blank deliberately have none. Real ttfact_ ids —
 *  that is exactly what the validator checks. */
function pickFact(id: string, value: string, concept = 'finding') {
  return {
    factId: `ttfact_${id.padEnd(24, '0').slice(0, 24)}`,
    sourceType: 'encounter_evidence' as const,
    concept,
    value,
    polarity: 'affirmed' as const,
    temporality: 'current' as const,
    experiencer: 'patient' as const,
    laterality: 'not_applicable' as const,
    number: null,
    unit: null,
    speaker: 'Doctor',
    sourceTranscriptOffsets: null,
    audioTimestampSeconds: null,
    evidenceAnchorIds: [`anchor-${id}`],
    evidenceQuote: 'synthetic fixture evidence',
    quality: { asr: 'unknown' as const, evidence: 'direct' as const },
  };
}
const PICK_FACTS = [
  pickFact('aaaaaaaaaaaa', 'x'),
  pickFact('bbbbbbbbbbbb', 'reflux positive'),
  pickFact('cccccccccccc', 'pos'),
];

/** These two tests assert pick RECOVERY over every dropdown, so each injected
 *  pick stands in for something the doctor dictated — which means each has a
 *  supporting fact. Derive one per allowed option rather than hand-listing 28. */
function factsForIr(irLike: { fields: ReadonlyArray<{ allowedOptions?: ReadonlyArray<{ value: string; displayText: string }> }> }) {
  const out: ReturnType<typeof pickFact>[] = [];
  let i = 0;
  for (const f of irLike.fields) {
    for (const o of f.allowedOptions ?? []) {
      out.push(pickFact(`f${(i++).toString(16)}`.padEnd(12, '0'), o.value));
      out.push(pickFact(`d${(i++).toString(16)}`.padEnd(12, '0'), o.displayText));
    }
  }
  return out;
}

/** A pick cites the SELECTION now, not an entailing fact — but it still needs an
 *  approved mapping with a concept for that citation to satisfy, exactly as any
 *  other citation must. One certified mapping per select field. */
function mappingsForIr(irLike: { fields: ReadonlyArray<{ fieldId: string; kind: string }> }) {
  return irLike.fields
    .filter((f) => f.kind === 'single_select')
    .map((f) => ({
      fieldId: f.fieldId,
      sourceType: 'verified_note_selection' as const,
      clinicalConcept: 'exam.vascular',
      expectedDataType: 'single_select' as const,
      polarityBehavior: 'value_only' as const,
      temporality: 'current' as const,
      laterality: 'optional' as const,
      unitPolicy: 'not_applicable' as const,
      approvedSynonyms: [],
      required: false,
      blankPolicy: 'blank' as const,
      unknownPolicy: 'blank' as const,
      practiceDefault: null,
      status: 'certified' as const,
    }));
}

describe('picks-bridge — CHOICE_SLOT picks -> exact-option resolutions (WM_IOV)', () => {
  it('recovers exactly the picks placed into the note, for every dropdown', async () => {
    const { ir, markerText } = await loadWmIov();
    const sfs = selects(ir);
    expect(sfs.length).toBeGreaterThan(0);
    const { note, chosenText } = fillNote(markerText);
    expect(chosenText.length).toBe(sfs.length); // marker count == select-field count

    const out = bridgeChoiceSlotPicks({ facts: factsForIr(ir), ir, markerText, filledNote: note , mappings: mappingsForIr(ir) });

    const res = out.resolutions;
    const byId = new Map(res.map((r) => [r.fieldId, r]));

    sfs.forEach((f, idx) => {
      const r = byId.get(f.fieldId)!;
      const wantOpt = f.allowedOptions.find(
        (o) => o.displayText.trim().toLowerCase() === chosenText[idx].trim().toLowerCase(),
      );
      expect(wantOpt, `field ${f.originalLabel} pick "${chosenText[idx]}" must be an option`).toBeTruthy();
      expect(r.status).toBe('supported');
      expect(r.value).toBe(wantOpt!.value);
      expect(r.selectedOptionOrdinal).toBe(wantOpt!.ordinal);
    });
    // Every non-select field stays not_mentioned (out of this bridge's scope).
    for (const r of res) {
      const f = ir.fields.find((x) => x.fieldId === r.fieldId)!;
      if (f.kind !== 'single_select') expect(r.status).toBe('not_mentioned');
    }
  });

  it('blank stays blank: an omitted (undictated) carrier line -> not_mentioned', () => {
    const ir = {
      fields: [
        { fieldId: `ttf_${'a'.repeat(24)}`, kind: 'single_select', displayOrder: 0, detectionStatus: 'certified', rowPrototype: false,
          originalLabel: 'A', allowedOptions: [{ ordinal: 0, displayText: 'x', value: 'x' }, { ordinal: 1, displayText: 'y', value: 'y' }] },
        { fieldId: `ttf_${'b'.repeat(24)}`, kind: 'single_select', displayOrder: 1, detectionStatus: 'certified', rowPrototype: false,
          originalLabel: 'B', allowedOptions: [{ ordinal: 0, displayText: 'p', value: 'p' }, { ordinal: 1, displayText: 'q', value: 'q' }] },
      ],
    } as unknown as TemplateDocIR;
    const markerText = 'A: {{one of: x | y}}\nB: {{one of: p | q}}';
    const filledNote = 'A: x'; // B undictated -> carrier omitted
    const out = bridgeChoiceSlotPicks({ facts: factsForIr(ir), ir, markerText, filledNote , mappings: mappingsForIr(ir) });
    const res = out.resolutions;
    expect(res[0]).toMatchObject({ status: 'supported', value: 'x', selectedOptionOrdinal: 0 });
    expect(res[1]).toMatchObject({ status: 'not_mentioned', value: null });
  });

  it('never off-list: an unlisted value in the note -> not_mentioned (never coerced)', async () => {
    const { ir, markerText } = await loadWmIov();
    const sfs = selects(ir);
    // Replace only the FIRST marker with a bogus off-list token.
    let replaced = false;
    const note = markerText.replace(MARKER_RE, (_full, optsStr) => {
      if (!replaced) { replaced = true; return 'ZZZ_NOT_AN_OPTION_QX'; }
      const opts = String(optsStr).split('|').map((o) => o.trim()).filter(Boolean);
      return opts[0];
    });
    const out = bridgeChoiceSlotPicks({ facts: factsForIr(ir), ir, markerText, filledNote: note , mappings: mappingsForIr(ir) });
    const res = out.resolutions;
    const firstField = sfs[0];
    const r = res.find((x) => x.fieldId === firstField.fieldId)!;
    expect(r.status).toBe('not_mentioned');
    expect(r.value).toBeNull();
  });

  it('both-legs: two dropdowns with identical options get their own order-mapped pick', () => {
    // Synthetic IR-agnostic proof of the order mapping + duplicate-option case.
    const ir = {
      fields: [
        { fieldId: `ttf_${'a'.repeat(24)}`, kind: 'single_select', displayOrder: 0, detectionStatus: 'certified', rowPrototype: false,
          originalLabel: 'Right side', allowedOptions: [
            { ordinal: 0, displayText: 'reflux positive', value: 'pos' },
            { ordinal: 1, displayText: 'is absent', value: 'neg' }] },
        { fieldId: `ttf_${'b'.repeat(24)}`, kind: 'single_select', displayOrder: 1, detectionStatus: 'certified', rowPrototype: false,
          originalLabel: 'Left side', allowedOptions: [
            { ordinal: 0, displayText: 'reflux positive', value: 'pos' },
            { ordinal: 1, displayText: 'is absent', value: 'neg' }] },
      ],
    } as unknown as TemplateDocIR;
    const markerText = 'Right leg: {{one of: reflux positive | is absent}}\nLeft leg: {{one of: reflux positive | is absent}}';
    const filledNote = 'Right leg: reflux positive\nLeft leg: is absent';
    const out = bridgeChoiceSlotPicks({ facts: factsForIr(ir), ir, markerText, filledNote , mappings: mappingsForIr(ir) });
    const res = out.resolutions;
    expect(res[0]).toMatchObject({ status: 'supported', value: 'pos', selectedOptionOrdinal: 0 });
    expect(res[1]).toMatchObject({ status: 'supported', value: 'neg', selectedOptionOrdinal: 1 });
  });
});
