// ============================================================================
// GATE — statics survive assembly BYTE-VERBATIM (ruling #106(a), SPEC §4.3a).
// ----------------------------------------------------------------------------
// ⚠️ THE FIXTURE IS SANITIZED, PER SPEC §4.3a(e). It carries the same
// STRUCTURAL features as the real customer form that exposed this defect — a
// fixed paragraph, inline dropdown slots, per-leg carrier lines — and NO real
// clinic, physician or technologist names. The distinctive token
// `500 milliseconds` is the permitted verbatim tripwire: it is the exact text
// the live defect normalised to "0.5 seconds", so if assembly ever alters it
// again, this file goes red.
// ============================================================================
import { describe, expect, it } from 'vitest';

import {
  assembleSection,
  EMPTY_SLOT_MARKER,
  rejoinVerbatim,
  sectionSlots,
  segmentSection,
  splitSegments,
} from '../section-assembly';

/** Structural twin of the real form. Sanitized. */
const TECHNIQUE =
  'A duplex Doppler color flow ultrasound study was performed in the upright ' +
  'position with and without manual augmentation of flow, documenting the ' +
  'condition of the {{one of: deep and superficial | superficial}} venous ' +
  'systems of the extremity. This study documents reflux as lasting more than ' +
  '500 milliseconds in either the saphenous veins or the perforator veins.';

const FINDINGS =
  'Right Leg:\n' +
  'The {{one of: great saphenous vein | small saphenous vein}} from the ' +
  '{{one of: mid thigh | knee}} to the {{one of: mid calf | distal calf}} was normal.\n' +
  'Left Leg:\n' +
  'The {{one of: great saphenous vein | small saphenous vein}} from the ' +
  '{{one of: mid thigh | knee}} to the {{one of: mid calf | distal calf}} was normal.';

describe('splitSegments — round-trip identity is the verbatim guarantee', () => {
  it('rejoins byte-for-byte for a slot-bearing paragraph', () => {
    expect(rejoinVerbatim(splitSegments(TECHNIQUE))).toBe(TECHNIQUE);
  });

  it('rejoins byte-for-byte for multi-line, multi-slot text', () => {
    expect(rejoinVerbatim(splitSegments(FINDINGS))).toBe(FINDINGS);
  });

  it('rejoins byte-for-byte for text with NO slots at all', () => {
    const plain = 'Clinical correlation with the above findings is required.';
    expect(rejoinVerbatim(splitSegments(plain))).toBe(plain);
  });

  it('preserves leading/trailing whitespace and blank lines exactly', () => {
    const odd = '  leading\n\n{{one of: a | b}}  \n\ttabbed\n';
    expect(rejoinVerbatim(splitSegments(odd))).toBe(odd);
  });
});

describe('assembleSection — the doctor bytes are emitted, the model only fills', () => {
  it('⚠️ TRIPWIRE: "500 milliseconds" survives assembly UNCHANGED', () => {
    const lines = segmentSection(TECHNIQUE);
    const slots = sectionSlots(lines);
    expect(slots).toHaveLength(1);
    const out = assembleSection(lines, { [slots[0].id]: 'deep and superficial' });

    expect(out.text).toContain('500 milliseconds');
    expect(out.text).not.toContain('0.5 seconds');
    expect(out.text).not.toContain('0.5 s');
    // and the whole paragraph is the doctor's, with only the slot substituted
    expect(out.text).toBe(TECHNIQUE.replace('{{one of: deep and superficial | superficial}}', 'deep and superficial'));
  });

  it('a pure-static line is emitted even when nothing was dictated', () => {
    const lines = segmentSection('Clinical correlation is required.');
    const out = assembleSection(lines, {});
    expect(out.text).toBe('Clinical correlation is required.');
    expect(out.droppedLines).toBe(0);
  });

  it('fail-closed: a value that is NOT one of the slot options is refused', () => {
    const lines = segmentSection(TECHNIQUE);
    const id = sectionSlots(lines)[0].id;
    const out = assembleSection(lines, { [id]: 'deep, superficial and perforator' });
    expect(out.rejected).toBe(1);
    // the invented value never reaches the note
    expect(out.text).not.toContain('perforator veins system');
    expect(out.text).not.toContain('deep, superficial and perforator');
    // ...and the static half is STILL verbatim
    expect(out.text).toContain('500 milliseconds');
    // #106(f): the hole is VISIBLE, not a bare gap
    expect(out.text).toContain(EMPTY_SLOT_MARKER);
    expect(out.text).not.toContain('the  venous');
  });

  it('never invents: an unfilled carrier line is dropped whole', () => {
    const lines = segmentSection(FINDINGS);
    const ids = sectionSlots(lines).map((s) => s.id);
    // fill only the RIGHT leg's three slots; leave the LEFT leg empty
    const out = assembleSection(
      lines,
      {
        [ids[0]]: 'great saphenous vein',
        [ids[1]]: 'mid thigh',
        [ids[2]]: 'mid calf',
      },
      { dropUndictatedCarriers: true }
    );
    expect(out.text).toContain('Right Leg:');
    expect(out.text).toContain('great saphenous vein');
    // the Left Leg HEADING is a pure static line and is kept...
    expect(out.text).toContain('Left Leg:');
    // ...but its undictated carrier sentence is gone, not left with holes
    expect(out.droppedLines).toBe(1);
    expect(out.text).not.toContain('The  from the');
    expect(out.text.split('\n').filter((l) => l.includes('was normal'))).toHaveLength(1);
  });

  it('laterality: a RIGHT value cannot leak into a LEFT slot it is not listed in', () => {
    const lines = segmentSection(
      'Left {{one of: great saphenous vein | small saphenous vein}} is patent.'
    );
    const id = sectionSlots(lines)[0].id;
    // a value from a different menu entirely
    const out = assembleSection(
      lines,
      { [id]: 'anterior accessory great saphenous vein' },
      { dropUndictatedCarriers: true }
    );
    expect(out.rejected).toBe(1);
    expect(out.text).toBe('');
    expect(out.droppedLines).toBe(1);
  });
});

describe('the byte-identical-prompt invariant (ruling #106(e))', () => {
  it('a section with ZERO slots is unchanged by assembly, whatever the fills', () => {
    const plain =
      'Patient seen in clinic. Vitals reviewed. Plan discussed and agreed.';
    const lines = segmentSection(plain);
    expect(sectionSlots(lines)).toHaveLength(0);
    // fills are irrelevant — nothing to fill
    expect(assembleSection(lines, {}).text).toBe(plain);
    expect(assembleSection(lines, { s0: 'anything' }).text).toBe(plain);
  });
});

describe('⚠️ THE COLLISION CASE — RULING #106(f)', () => {
  // Found by this file's own tripwire, not by review. The real TECHNIQUE
  // paragraph is one sentence of protocol text containing one dropdown. Under
  // the first implementation a fail-closed slot dropped the WHOLE line and took
  // "500 milliseconds" with it — deleting the doctor's prose to satisfy the
  // fail-closed rule.
  //
  // #106(f), in the owner's words: "the worst case of keeping is a visible,
  // reviewable hole; the worst case of dropping is the doctor's prose silently
  // vanishing, which is the original defect's own shape." STATICS WIN: the line
  // is kept, fixed bytes verbatim, each unfilled slot rendering the form's
  // visible empty marker.
  it('keeps the static prose and renders a VISIBLE empty marker', () => {
    const lines = segmentSection(TECHNIQUE);
    const id = sectionSlots(lines)[0].id;
    const out = assembleSection(lines, { [id]: 'not a listed option' });
    expect(out.rejected).toBe(1);
    expect(out.text).toContain('500 milliseconds');
    expect(out.text).toContain('A duplex Doppler color flow ultrasound study');
    expect(out.droppedLines).toBe(0);
    // the hole is the form's own mark, not whitespace
    expect(out.text).toContain(EMPTY_SLOT_MARKER);
    expect(out.text).toBe(
      TECHNIQUE.replace('{{one of: deep and superficial | superficial}}', EMPTY_SLOT_MARKER)
    );
  });

  it('and drops it ONLY when the caller declares the line a pure carrier', () => {
    const lines = segmentSection(TECHNIQUE);
    const id = sectionSlots(lines)[0].id;
    const out = assembleSection(lines, { [id]: 'not a listed option' }, { dropUndictatedCarriers: true });
    expect(out.droppedLines).toBe(1);
    expect(out.text).toBe('');
  });
});

describe('#106(f) — a PARTLY dictated carrier keeps its line and marks the gaps', () => {
  it('fills what the transcript supports and marks the rest visibly', () => {
    const lines = segmentSection(
      'The {{one of: great saphenous vein | small saphenous vein}} from the ' +
        '{{one of: mid thigh | knee}} to the {{one of: mid calf | distal calf}} was normal.'
    );
    const ids = sectionSlots(lines).map((s) => s.id);
    const out = assembleSection(
      lines,
      { [ids[0]]: 'great saphenous vein' },
      { dropUndictatedCarriers: true }
    );
    // one slot filled -> the line survives even in carrier mode
    expect(out.droppedLines).toBe(0);
    expect(out.text).toContain('great saphenous vein');
    expect(out.text).toContain('was normal.');
    // the two undictated segments are visibly empty, not silently blank
    expect(out.text.split(EMPTY_SLOT_MARKER)).toHaveLength(3);
    expect(out.unfilled).toBe(2);
  });
});
