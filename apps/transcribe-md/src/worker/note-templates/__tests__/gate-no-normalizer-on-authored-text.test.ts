// ============================================================================
// GATE — NO NORMALIZER TOUCHES DOCTOR-AUTHORED TEXT (ruling #107, SPEC §4.3a(a)).
// ----------------------------------------------------------------------------
// > "Statics are assembled because NO layer — stochastic or deterministic,
// >  model or normalizer — may rewrite a doctor's authored bytes."
//
// ⚠️ THIS IS THE LAYER THAT COVERS THE TEMPLATES ASSEMBLY DOES NOT. The
// reclassification is narrow by design, so most sections are still
// `scaffold_confirm` and their `defaultText` still goes INTO the prompt. On
// those, assembly protects nothing — and #107's mechanism was a deterministic
// rewrite on the way in, which would have kept firing on every one of them.
//
// So the two layers are tested separately, on purpose:
//   · assembly makes the class structurally impossible on RECLASSIFIED sections
//     (`l4-assembly-imaging.test.ts`)
//   · this file proves no normalizer rewrites authored text on ANY section,
//     reclassified or not, on EITHER prompt route
//
// ⚠️ WHAT IS DELIBERATELY NOT ASSERTED HERE, so the scope is legible rather
// than assumed: `normalizeRefluxTimeUnit` still exists and its application to
// DICTATED or MODEL values is untouched. That is a separate question, recorded
// as one. This gate is about text the DOCTOR wrote.
//
// ⚠️ THE FIXTURE IS SANITIZED, PER SPEC §4.3a(e).
// ============================================================================
import { describe, expect, it } from 'vitest';

import {
  buildSoapSystemPrompt,
  renderStructureDirective,
  type ResolvedNoteTemplate,
} from '../build-soap-prompt';
import { buildUltrasoundSystemPrompt } from '../build-ultrasound-prompt';
import type { NoteTemplateSection } from '../system-default-template';

/** The doctor's own sentence, and the doctor's own column header. Both carry a
 *  millisecond unit that our normalizer used to "reconcile" to seconds. */
const AUTHORED_PROSE =
  'This study documents reflux as lasting more than 500 milliseconds in either ' +
  'the saphenous veins or the perforator veins.';
const AUTHORED_HEADER = 'REFLUX TIME (ms)';

function section(
  over: Partial<NoteTemplateSection> & { key: string; label: string; order: number }
): NoteTemplateSection {
  return {
    formatHint: 'prose',
    styleInstructions: null,
    defaultText: null,
    defaultTextMode: 'omit_unless_supported',
    ...over,
  } as NoteTemplateSection;
}

/** ⚠️ `scaffold_confirm`, NOT `always_include` — a template the migration has
 *  NOT reclassified. Its text DOES reach the prompt, which is exactly why the
 *  normalizer had to stop rather than being made unreachable. */
const NOT_RECLASSIFIED: ResolvedNoteTemplate = {
  id: 'tmpl_not_reclassified',
  version: 1,
  isSystemDefault: false,
  sections: [
    section({
      key: 'technique',
      label: 'TECHNIQUE',
      order: 1,
      defaultText: AUTHORED_PROSE,
      defaultTextMode: 'scaffold_confirm',
    }),
    section({
      key: 'grid',
      label: 'GRID',
      order: 2,
      structure: { kind: 'table', columns: ['Vein', 'DIAMETER (mm)', AUTHORED_HEADER] },
    }),
  ],
  styleProfile: { tense: 'past', tone: 'clinical', abbreviations: 'expand' } as never,
};

const OPTS = {
  specialty: 'ultrasound',
  audioQualityAlert: null,
  interpreterAlert: null,
  specialtyGuidanceText: null,
};

describe.each([
  ['the SOAP route', () => buildSoapSystemPrompt(NOT_RECLASSIFIED, OPTS)],
  ['⚠️ the IMAGING route — where #107 actually fired', () =>
    buildUltrasoundSystemPrompt(NOT_RECLASSIFIED, OPTS)],
])('%s', (_label, build) => {
  it('⚠️ carries the doctor\'s threshold VERBATIM — never "0.5 seconds"', () => {
    const prompt = build();
    expect(prompt).toContain('more than 500 milliseconds');
    expect(prompt).not.toContain('more than 0.5 seconds');
  });

  it('⚠️ carries the doctor\'s column header VERBATIM', () => {
    const prompt = build();
    const header = prompt.split('\n').find((l) => l.startsWith('| Vein')) ?? '';
    expect(header).toContain(AUTHORED_HEADER);
    expect(header).not.toContain('seconds');
  });

  it('emits the authored prose unchanged, character for character', () => {
    // Not a substring spot-check: the whole sentence, as written.
    expect(build()).toContain(AUTHORED_PROSE);
  });
});

describe('the unit convention is STATED, which is what replaced the edit', () => {
  it('the table directive tells the model what a cell holds', () => {
    const out = renderStructureDirective({
      kind: 'table',
      columns: ['Vein', AUTHORED_HEADER],
    });
    expect(out).toMatch(/WRITTEN IN SECONDS AS DICTATED/);
    expect(out).toMatch(/never restate a header or/);
  });

  it('⚠️ and the instruction\'s own EXAMPLE does not model the rewrite', () => {
    // An instruction that illustrates itself with a rewritten header teaches
    // the rewrite — and, incidentally, breaks any negative assertion about it.
    const out = renderStructureDirective({ kind: 'table', columns: [AUTHORED_HEADER] });
    expect(out).not.toContain('REFLUX TIME (seconds)');
  });
});
