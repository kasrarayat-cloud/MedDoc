// ============================================================================
// GATE — which sections become the doctor's assembled fixed blocks
// (ruling #106(a)/(e), SPEC §4.3a).
// ----------------------------------------------------------------------------
// ⚠️ THIS PREDICATE EXISTS IN TWO PLACES AND THEY MUST AGREE: this function
// (the persist path, so a template uploaded AFTER the fix is classified
// correctly) and the reclassification migration's SQL (rows that already
// exist). If they disagree, the owner's RE-UPLOAD silently undoes the
// migration — and the re-upload is the closing step of this very item. The SQL
// mirror is named in the migration header; the cases below are the shared
// contract.
//
// ⚠️ THE FIXTURE IS SANITIZED, PER SPEC §4.3a(e).
// ============================================================================
import { describe, expect, it } from 'vitest';

import {
  classifyDefaultTextMode,
  FIXED_BLOCK_SECTION_KEYS,
  isSlotBearingFamily,
} from '../classify-default-text-mode';
import type { NoteTemplateSection } from '../system-default-template';

function section(
  over: Partial<NoteTemplateSection> & { key: string }
): NoteTemplateSection {
  return {
    label: over.key.toUpperCase(),
    order: 1,
    formatHint: 'prose',
    styleInstructions: null,
    defaultText: null,
    defaultTextMode: 'omit_unless_supported',
    ...over,
  } as NoteTemplateSection;
}

const TECHNIQUE = section({
  key: 'technique',
  defaultText:
    'A duplex study of the {{one of: deep and superficial | superficial}} venous ' +
    'systems, documenting reflux over 500 milliseconds.',
});
const EXAM_META = section({
  key: 'exam_metadata',
  defaultText: 'SIDE OF EXAM: {{one of: right | left}}\nMACHINE: [not documented]',
});
const FINDINGS = section({
  key: 'findings',
  defaultText: 'Right Leg:\nThe {{one of: great saphenous vein | small saphenous vein}} was normal.',
});
const TABLE = section({
  key: 'diameter_reflux_time',
  defaultText: '| VEIN | DIAMETER (mm) |',
  structure: { kind: 'table', columns: ['DIAMETER (mm)'] },
});
const PLAIN_SOAP = [
  section({ key: 'subjective', defaultText: 'Patient reports…' }),
  section({ key: 'objective', defaultText: 'Vitals within normal limits.' }),
];

const IMAGING = [EXAM_META, TECHNIQUE, FINDINGS, TABLE];

describe('isSlotBearingFamily — the rollout boundary (#106(e))', () => {
  it('true for a template carrying a choice slot', () => {
    expect(isSlotBearingFamily(IMAGING)).toBe(true);
  });

  it('true for one carrying the fixed-protocol token without a slot', () => {
    expect(
      isSlotBearingFamily([section({ key: 'technique', defaultText: 'reflux over 500 milliseconds.' })])
    ).toBe(true);
  });

  it('⚠️ FALSE for plain SOAP — which is what keeps its prompt byte-identical', () => {
    expect(isSlotBearingFamily(PLAIN_SOAP)).toBe(false);
  });
});

describe('classifyDefaultTextMode', () => {
  it('a section with no default text is omit_unless_supported', () => {
    expect(classifyDefaultTextMode(section({ key: 'technique' }), IMAGING)).toBe(
      'omit_unless_supported'
    );
    expect(
      classifyDefaultTextMode(section({ key: 'technique', defaultText: '   ' }), IMAGING)
    ).toBe('omit_unless_supported');
  });

  it('the two fixed blocks become always_include', () => {
    expect(classifyDefaultTextMode(TECHNIQUE, IMAGING)).toBe('always_include');
    expect(classifyDefaultTextMode(EXAM_META, IMAGING)).toBe('always_include');
  });

  // ⚠️ THE ONE THAT PROTECTS THE VISIT'S OWN CONTENT. FINDINGS is a stub the
  // model writes AROUND; assembling it would emit two carrier lines and delete
  // every dictated finding — while preserving the doctor's bytes perfectly.
  it('⚠️ a SCAFFOLD the model extends stays scaffold_confirm', () => {
    expect(classifyDefaultTextMode(FINDINGS, IMAGING)).toBe('scaffold_confirm');
  });

  it('⚠️ a STRUCTURED section is never always_include — a table is a fill surface', () => {
    const t = { ...TABLE, key: 'technique' } as NoteTemplateSection;
    expect(classifyDefaultTextMode(t, IMAGING)).toBe('scaffold_confirm');
  });

  it('⚠️ plain SOAP is untouched — the same key outside the family stays scaffolded', () => {
    const t = section({ key: 'technique', defaultText: 'Standard technique paragraph.' });
    expect(classifyDefaultTextMode(t, [...PLAIN_SOAP, t])).toBe('scaffold_confirm');
  });

  it('every non-allowlisted key stays scaffold_confirm inside the family', () => {
    for (const key of ['impression', 'patient_education', 'procedures_em', 'subjective']) {
      const s = section({ key, defaultText: 'Some fixed-looking prose.' });
      expect(classifyDefaultTextMode(s, [...IMAGING, s])).toBe('scaffold_confirm');
    }
  });

  it('the allowlist is exactly the two kinds that were read and confirmed', () => {
    expect([...FIXED_BLOCK_SECTION_KEYS].sort()).toEqual(['exam_metadata', 'technique']);
  });
});
