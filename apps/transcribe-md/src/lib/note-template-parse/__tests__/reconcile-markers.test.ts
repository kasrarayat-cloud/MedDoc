import { describe, expect, it } from 'vitest';
import {
  reconcileTemplateMarkers,
  reconcileBodyMarkers,
  reconcileHeaderMarkers,
  dropHeaderMarkerSections,
} from '../reconcile-markers';
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

  it('a dropped marker line whose FIXED text carries PHI is NOT restored (PHI re-scan)', () => {
    // A filled-example upload: a body marker line carries an age + MRN in its
    // carrier text. The LLM dropped it. The reconciler runs AFTER the gate, so
    // it must re-scan and REFUSE to re-attach this line (else PHI bypasses the
    // gate). A clean marker line on the same run is still restored.
    const phiSource = [
      'FINDINGS',
      '72 y/o male, MRN 5583321, with a {{one of: patent | occluded}} great saphenous vein.',
      'The {{one of: deep | superficial}} system is otherwise normal.',
    ].join('\n');
    const parsed = [
      // LLM kept only a body section that dropped BOTH marker lines above.
      sec('findings', 'FINDINGS', 'Study of the lower extremity venous system.'),
    ];
    const out = reconcileTemplateMarkers(phiSource, parsed);
    const allDT = out.map((s) => s.defaultText ?? '').join('\n');
    // clean line restored; PHI-bearing line dropped
    expect(allDT).toContain('{{one of: deep | superficial}}');
    expect(allDT).not.toContain('MRN 5583321');
    expect(allDT).not.toContain('72 y/o');
    expect(allDT).not.toContain('{{one of: patent | occluded}}'); // its whole line was skipped
  });

  it('two lines with the SAME option sequence but different prose → a dropped duplicate is still restored (count-based)', () => {
    const dupSource = [
      'FINDINGS',
      'The {{one of: left | right}} leg is normal.',
      'The {{one of: left | right}} arm is normal.',
    ].join('\n');
    const parsed = [
      // LLM kept the leg line, dropped the arm line (both share sig `left|right`).
      sec('findings', 'FINDINGS', 'The {{one of: left | right}} leg is normal.'),
    ];
    const out = reconcileTemplateMarkers(dupSource, parsed);
    const allDT = out.map((s) => s.defaultText ?? '').join('\n');
    expect(allDT).toContain('leg is normal.');
    expect(allDT).toContain('arm is normal.'); // the dropped duplicate is back
    // two occurrences of the shared dropdown now present
    expect((allDT.match(/\{\{one of: left \| right\}\}/g) ?? []).length).toBe(2);
  });

  it('dropHeaderMarkerSections is a NO-OP for a SOAP note with a fixed preamble (no header dropdowns) → byte-identical', () => {
    // A SOAP note whose Subjective default echoes a pre-heading preamble line.
    // Because there are NO header-region dropdowns, nothing can be reconciled
    // back, so the header-drop MUST NOT remove the section (it would be lost).
    const soapSource = ['Reason for visit: follow-up', 'SUBJECTIVE', 'HPI prose.', 'ASSESSMENT', 'Impression prose.'].join('\n');
    const secs = [sec('subjective', 'SUBJECTIVE', 'Reason for visit: follow-up'), sec('assessment', 'ASSESSMENT', 'Impression prose.')];
    expect(dropHeaderMarkerSections(soapSource, secs)).toBe(secs); // same reference → no-op
    expect(reconcileTemplateMarkers(soapSource, secs)).toBe(secs); // no markers → no-op
  });

  it('same-seq lines, LLM keeps the LATER duplicate → the EARLIER one is restored (not duplicated)', () => {
    // Reverse of the earlier dup test: identical option sequence, different
    // prose, LLM keeps the ARM line and drops the LEG line. Count-plus-prose
    // matching must restore leg (the truly-missing line), never a second arm.
    const dupSource = [
      'FINDINGS',
      'The {{one of: left | right}} leg is normal.',
      'The {{one of: left | right}} arm is normal.',
    ].join('\n');
    const parsed = [sec('findings', 'FINDINGS', 'The {{one of: left | right}} arm is normal.')];
    const out = reconcileTemplateMarkers(dupSource, parsed);
    const allDT = out.map((s) => s.defaultText ?? '').join('\n');
    expect(allDT).toContain('leg is normal.'); // the dropped earlier line is back
    expect((allDT.match(/arm is normal\./g) ?? []).length).toBe(1); // survivor NOT duplicated
    expect((allDT.match(/\{\{one of: left \| right\}\}/g) ?? []).length).toBe(2);
  });

  it('reconcileBodyMarkers restores BODY markers only (pre-scan pass); header untouched', () => {
    // TECHNIQUE + IMPRESSION survive; the FINDINGS (body) marker was dropped, and
    // the whole header block dropped. The body pass restores the body marker but
    // must NOT create the header Exam Metadata block (the post-gate header pass's
    // job) — so re-attached body content is what flows into the PHI scan.
    const parsed = [
      sec('technique', 'TECHNIQUE', 'A duplex study documenting the {{one of: deep and superficial | superficial}} systems.'),
      sec('impression', 'IMPRESSION', 'Right {{one of: great saphenous vein | small saphenous vein}} is {{one of: reflux positive | is absent}}.'),
    ];
    const out = reconcileBodyMarkers(SOURCE, parsed);
    const allDT = out.map((s) => s.defaultText ?? '').join('\n');
    expect(allDT).toContain('is refluxing.'); // body FINDINGS marker restored under nearest anchor
    expect(out.find((s) => s.key === 'exam_metadata')).toBeUndefined(); // header NOT added here
    expect(allDT).not.toContain('REFERRING PHYSICIAN'); // header markers left for the header pass
  });

  it('stable boundary: a dropped BODY line is never restored by the post-gate HEADER pass (no name leak on section collapse)', () => {
    // Auditor NEW-1 scenario: a header dropdown (SIDE OF EXAM) and a BODY marker
    // line share the sig `left|right`; the body line also carries a NAME. If the
    // body section collapses before the post-gate header pass and the boundary
    // were derived from (now empty) surviving anchors, the body line would be
    // reclassified header and restored into Exam Metadata — leaking the name past
    // the LLM scan. With the SOURCE-INTRINSIC boundary (heading at line 1) the
    // body line (idx 2) stays BODY and the header pass skips it.
    const src = [
      'SIDE OF EXAM: {{one of: left | right}}',
      'FINDINGS',
      'Jane Q Patient tolerated the {{one of: left | right}} study.',
    ].join('\n');
    const boundary = 1; // firstClinicalHeadingIndex(src, [{label:'FINDINGS'}]) === 1
    const collapsed: NoteTemplateSection[] = []; // findings dropped/collapsed pre-header-pass
    const out = reconcileHeaderMarkers(src, collapsed, boundary);
    const allDT = out.map((s) => s.defaultText ?? '').join('\n');
    expect(allDT).toContain('SIDE OF EXAM: {{one of: left | right}}'); // header dropdown restored
    expect(allDT).not.toContain('Jane Q Patient'); // BODY name never enters Exam Metadata
    expect(allDT).not.toContain('tolerated the');
  });

  it('cap-aware append: a body marker that would exceed the persisted defaultText cap is skipped, never sliced mid-marker', () => {
    const src = ['FINDINGS', 'The {{one of: great saphenous vein | small saphenous vein}} is refluxing.'].join('\n');
    const near = 'x'.repeat(7990); // 7990 + '\n' + 60-char marker line > 8000 cap
    const parsed = [sec('findings', 'FINDINGS', near)];
    const out = reconcileBodyMarkers(src, parsed, 0);
    const dt = out.find((s) => s.key === 'findings')!.defaultText ?? '';
    expect(dt).toBe(near); // unchanged — append skipped
    expect(dt).not.toContain('{{one of:'); // no dangling / half-sliced marker
    expect(dt.length).toBeLessThanOrEqual(8000);
  });

  it('reconcileHeaderMarkers restores HEADER markers only (post-gate pass); body untouched', () => {
    // Body already reconciled + scanned upstream; only the header block is gone.
    const parsed = [
      sec('technique', 'TECHNIQUE', 'A duplex study documenting the {{one of: deep and superficial | superficial}} systems.'),
      sec('findings', 'FINDINGS', 'The {{one of: great saphenous vein | small saphenous vein}} is refluxing.'),
      sec('impression', 'IMPRESSION', 'Right {{one of: great saphenous vein | small saphenous vein}} is {{one of: reflux positive | is absent}}.'),
    ];
    const out = reconcileHeaderMarkers(SOURCE, parsed);
    const meta = out.find((s) => s.key === 'exam_metadata');
    expect(meta).toBeTruthy();
    expect(meta!.defaultText).toContain('REFERRING PHYSICIAN: {{one of:');
    expect(meta!.defaultText).toContain('MACHINE: {{one of:');
    expect(markersPreserved(out)).toBe(TOTAL_MARKERS); // header restore completes the set
  });
});
