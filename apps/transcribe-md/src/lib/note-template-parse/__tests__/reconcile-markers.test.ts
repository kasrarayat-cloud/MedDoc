import { describe, expect, it } from 'vitest';
import { reconcileTemplateMarkers, dropHeaderMarkerSections } from '../reconcile-markers';
import type { NoteTemplateSection } from '../../../worker/note-templates/system-default-template';

const SOURCE = [
  '{{one of: 250 E. Yale Loop, Suite E, Irvine, CA 92604 | 2572 Atlantic Avenue, Long Beach, CA 90806}}',
  'VENOUS DUPLEX of LOWER EXTREMITIES',
  'DATE OF SERVICE:',
  'PATIENT NAME:',
  'SIDE OF EXAM: {{one of: Bilateral Detailed | Bilateral Screening}}',
  'TYPE OF EXAM: Full Study',
  'REFERRING PHYSICIAN: {{one of: Maged S. Mikhail, MD | Khashayar Sarabi, MD}}',
  'MACHINE: {{one of: GE Logiq V2 | Mindray M7}}',
  'LOCATION: {{one of: Irvine, CA | Long Beach, CA}}',
  'DIAGNOSIS: {{one of: Varicose veins right | Chronic venous hypertension left}}',
  'TECHNIQUE',
  'A duplex study documenting the {{one of: deep and superficial | superficial}} systems.',
  'FINDINGS',
  'The {{one of: great saphenous vein | small saphenous vein}} is refluxing.',
  'IMPRESSION',
  'Right {{one of: great saphenous vein | small saphenous vein}} is {{one of: reflux positive | is absent}}.',
].join('\n');

const sec = (key: string, label: string, dt: string | null): NoteTemplateSection => ({
  key, label, order: 1, formatHint: 'prose', styleInstructions: null,
  defaultText: dt, defaultTextMode: dt ? 'scaffold_confirm' : 'omit_unless_supported', structure: null,
});

const lineSeq = (line: string) =>
  [...line.matchAll(/\{\{one of:\s*([^}]*)\}\}/g)].map((m) => m[1].split('|').map((o) => o.trim().toLowerCase()).filter(Boolean).join('|')).join(' >> ');
const seqSet = (text: string) => { const s = new Set<string>(); for (const l of text.split('\n')) { const q = lineSeq(l); if (q) s.add(q); } return s; };

// Every distinct source marker-LINE sequence (9: address, side-of-exam,
// referring, machine, location, diagnosis, technique, findings[vein],
// impression[vein,status]).
const SOURCE_SEQS = seqSet(SOURCE);
const TOTAL_MARKERS = SOURCE_SEQS.size;

/** How many of the source marker-line sequences are present across sections. */
function markersPreserved(sections: NoteTemplateSection[]): number {
  const present = new Set<string>();
  for (const x of sections) for (const q of seqSet(x.defaultText ?? '')) present.add(q);
  return [...SOURCE_SEQS].filter((q) => present.has(q)).length;
}

describe('reconcileTemplateMarkers', () => {
  it('LLM dropped the WHOLE header block → all 9 markers restored (new Exam Metadata section)', () => {
    // LLM kept only the body sections, dropped the metadata region entirely.
    const dropped = [
      sec('technique', 'TECHNIQUE', 'A duplex study documenting the {{one of: deep and superficial | superficial}} systems.'),
      sec('findings', 'FINDINGS', 'The {{one of: great saphenous vein | small saphenous vein}} is refluxing.'),
      sec('impression', 'IMPRESSION', 'Right {{one of: great saphenous vein | small saphenous vein}} is {{one of: reflux positive | is absent}}.'),
    ];
    expect(markersPreserved(dropped)).toBe(3);
    const out = reconcileTemplateMarkers(SOURCE, dropped);
    expect(markersPreserved(out)).toBe(TOTAL_MARKERS); // all 9
    const meta = out.find((s) => s.key === 'exam_metadata');
    expect(meta).toBeTruthy();
    expect(meta!.defaultText).toContain('SIDE OF EXAM: {{one of: Bilateral Detailed');
    expect(meta!.defaultText).toContain('REFERRING PHYSICIAN: {{one of:');
    expect(meta!.defaultText).toContain('MACHINE: {{one of:');
    expect(meta!.defaultText).toContain('LOCATION: {{one of:');
    expect(meta!.defaultText).toContain('DIAGNOSIS: {{one of:');
    expect(meta!.defaultText).toContain('250 E. Yale Loop'); // clinic address dropdown
    // ONLY marker (dropdown) lines are reconciled — never interstitial fixed
    // lines (which can hold a raw provider name that trips the PHI gate).
    expect(meta!.defaultText).not.toContain('TYPE OF EXAM: Full Study');
    expect(meta!.defaultText).not.toContain('PATIENT NAME');
    expect(meta!.defaultText).not.toContain('DATE OF SERVICE');
    expect(out[0].key).toBe('exam_metadata'); // prepended at the top
  });

  it('LLM dropped only SOME header markers → backfilled into the existing metadata section (no dup)', () => {
    const partial = [
      sec('exam_metadata', 'Exam Metadata', '{{one of: 250 E. Yale Loop, Suite E, Irvine, CA 92604 | 2572 Atlantic Avenue, Long Beach, CA 90806}}\nSIDE OF EXAM: {{one of: Bilateral Detailed | Bilateral Screening}}\nDIAGNOSIS: {{one of: Varicose veins right | Chronic venous hypertension left}}'),
      sec('findings', 'FINDINGS', 'The {{one of: great saphenous vein | small saphenous vein}} is refluxing.'),
      sec('impression', 'IMPRESSION', 'Right {{one of: great saphenous vein | small saphenous vein}} is {{one of: reflux positive | is absent}}.'),
    ];
    const out = reconcileTemplateMarkers(SOURCE, partial);
    expect(markersPreserved(out)).toBe(TOTAL_MARKERS);
    const meta = out.find((s) => s.key === 'exam_metadata')!;
    expect(meta.defaultText).toContain('REFERRING PHYSICIAN: {{one of:'); // backfilled
    expect(meta.defaultText).toContain('MACHINE: {{one of:');
    // no duplicate SIDE OF EXAM
    expect((meta.defaultText!.match(/SIDE OF EXAM:/g) ?? []).length).toBe(1);
  });

  it('LLM preserved EVERYTHING → no-op (same array reference, byte-identical)', () => {
    const full = [
      sec('exam_metadata', 'Exam Metadata', SOURCE.split('\nTECHNIQUE')[0]),
      sec('technique', 'TECHNIQUE', 'A duplex study documenting the {{one of: deep and superficial | superficial}} systems.'),
      sec('findings', 'FINDINGS', 'The {{one of: great saphenous vein | small saphenous vein}} is refluxing.'),
      sec('impression', 'IMPRESSION', 'Right {{one of: great saphenous vein | small saphenous vein}} is {{one of: reflux positive | is absent}}.'),
    ];
    expect(markersPreserved(full)).toBe(TOTAL_MARKERS);
    const out = reconcileTemplateMarkers(SOURCE, full);
    expect(out).toBe(full); // SAME reference → no-op
  });

  it('a source with NO markers (SOAP / scaffold-free) → no-op (same reference)', () => {
    const soap = [sec('s', 'Subjective', 'HPI prose.'), sec('a', 'Assessment', 'Impression prose.')];
    const out = reconcileTemplateMarkers('## Subjective\nHPI\n## Assessment\nplan', soap);
    expect(out).toBe(soap);
  });

  it('dropHeaderMarkerSections removes header-only sections from the PHI-scan input, keeps body', () => {
    const llm = [
      sec('meta', 'Exam Metadata', 'REFERRING PHYSICIAN: {{one of: Maged S. Mikhail, MD | Khashayar Sarabi, MD}}\nMACHINE: {{one of: GE Logiq V2 | Mindray M7}}'),
      sec('technique', 'TECHNIQUE', 'A duplex study documenting the {{one of: deep and superficial | superficial}} systems.'),
      sec('findings', 'FINDINGS', 'The {{one of: great saphenous vein | small saphenous vein}} is refluxing.'),
    ];
    const forScan = dropHeaderMarkerSections(SOURCE, llm);
    // provider-label section removed; body sections kept
    expect(forScan.map((s) => s.key)).toEqual(['technique', 'findings']);
    // and the dropped header markers are restored by the reconciler afterwards
    const reconciled = reconcileTemplateMarkers(SOURCE, forScan);
    expect(markersPreserved(reconciled)).toBe(TOTAL_MARKERS);
  });

  it('dropHeaderMarkerSections is a no-op for a scaffold-free (no-marker) note', () => {
    const soap = [sec('s', 'Subjective', 'HPI prose.'), sec('a', 'Assessment', 'Impression prose.')];
    expect(dropHeaderMarkerSections('## Subjective\nHPI', soap)).toBe(soap);
  });

  it('a dropped BODY marker → appended to the nearest section by source position', () => {
    const droppedBody = [
      sec('exam_metadata', 'Exam Metadata', SOURCE.split('\nTECHNIQUE')[0]),
      sec('technique', 'TECHNIQUE', 'A duplex study documenting the {{one of: deep and superficial | superficial}} systems.'),
      sec('impression', 'IMPRESSION', 'Right {{one of: great saphenous vein | small saphenous vein}} is {{one of: reflux positive | is absent}}.'),
      // FINDINGS section (with its vein marker) dropped entirely
    ];
    const out = reconcileTemplateMarkers(SOURCE, droppedBody);
    expect(markersPreserved(out)).toBe(TOTAL_MARKERS);
    // the findings vein marker re-attached under TECHNIQUE (nearest preceding heading)
    const tech = out.find((s) => s.key === 'technique')!;
    expect(tech.defaultText).toContain('is refluxing.');
  });
});
