// ============================================================================
// GATE — THE ROUTE PRODUCTION ACTUALLY TAKES, AND THE FLAG IT ACTUALLY RUNS.
// Ruling #106(a), SPEC §4.3a.
// ----------------------------------------------------------------------------
// ⚠️ THIS FILE EXISTS BECAUSE `l4-assembly.test.ts` WAS FLAWLESS OVER THE WRONG
// UNIVERSE — twice over, and either one alone was a shipped clinical defect.
//
//   WRONG SPECIALTY. It used `primary-care`, which routes L4 through
//   `buildSoapSystemPrompt`. **Every production visit bound to a template the
//   reclassification touches is an IMAGING visit** and routes through
//   `buildUltrasoundSystemPrompt` — a second builder that carried its own copy
//   of the section renderer and never learned the slot-values contract. The
//   model was handed the doctor's bytes as scaffold while `composeNote`
//   composed as though it had not been, replacing dictated values (side of
//   exam, indication) with an em dash on a signed imaging report. Silently:
//   both structure gates pass on that output.
//
//   WRONG FLAG. It ran with `TRANSCRIBE_MD_EVIDENCE_ANCHORS` unset.
//   **Production runs it TRUE.** On that path `runAnchorVerify` was handed the
//   un-stripped output and rebuilt the note from it, putting the slot-values
//   JSON — including a value the assembler had REFUSED — back into `soapDraft`.
//
// Neither was visible to the suite, the mutation proofs, or a 15-of-16 QA walk.
// Both were found by an adversarial pass. So this file pins the ROUTE, and the
// suite below runs in BOTH flag states — a matrix, not a default.
//
// ⚠️ THE FIXTURE IS SANITIZED, PER SPEC §4.3a(e).
// ============================================================================
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  modelCompleteText: vi.fn(),
  prismaUpdate: vi.fn(),
  logAudit: vi.fn(),
}));

vi.mock('@meddoc/ai', async () => {
  const actual = await vi.importActual<typeof import('@meddoc/ai')>('@meddoc/ai');
  return { ...actual, modelClient: { complete: vi.fn(), completeText: mocks.modelCompleteText } };
});
vi.mock('@meddoc/db', () => ({
  default: { transcribeVisit: { update: mocks.prismaUpdate } },
}));
vi.mock('@/lib/audit', () => ({ logAudit: mocks.logAudit }));

import { runLayer4GenerateSoap, type Layer4Input } from '../04-generate-soap';
import {
  SLOT_VALUES_CLOSE,
  SLOT_VALUES_OPEN,
} from '@/worker/note-templates/slot-fill-protocol';
import type { ResolvedNoteTemplate } from '@/worker/note-templates/build-soap-prompt';
import type { NoteTemplateSection } from '@/worker/note-templates/system-default-template';

const TECHNIQUE_TEXT =
  'A duplex Doppler color flow ultrasound study was performed in the upright ' +
  'position, documenting the condition of the {{one of: deep and superficial | ' +
  'superficial}} venous systems of the extremity. This study documents reflux ' +
  'as lasting more than 500 milliseconds in either the saphenous veins or the ' +
  'perforator veins.';

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

const EXAM = section({
  key: 'exam_metadata',
  label: 'EXAM',
  order: 1,
  defaultText: 'SIDE OF EXAM: {{one of: right | left}}',
  defaultTextMode: 'always_include',
});
const TECHNIQUE = section({
  key: 'technique',
  label: 'TECHNIQUE',
  order: 2,
  defaultText: TECHNIQUE_TEXT,
  defaultTextMode: 'always_include',
});
const FINDINGS = section({
  key: 'findings',
  label: 'FINDINGS',
  order: 3,
  defaultText: 'Right Leg:\nThe {{one of: great saphenous vein | small saphenous vein}} was assessed.',
  defaultTextMode: 'scaffold_confirm',
});

const IMAGING: ResolvedNoteTemplate = {
  id: 'tmpl_imaging',
  version: 1,
  isSystemDefault: false,
  sections: [EXAM, TECHNIQUE, FINDINGS],
  styleProfile: { tense: 'past', tone: 'clinical', abbreviations: 'expand' } as never,
};

/** ⚠️ `ultrasound`, the specialty every affected production visit carries. */
const input = (): Layer4Input =>
  ({
    visitId: 'v1',
    practiceId: 'p1',
    userId: 'd1',
    specialty: 'ultrasound',
    roleLabeledTranscript:
      'Doctor #0: We studied the superficial venous system of the left leg today.\n' +
      'Patient #1: Understood.',
    entities: {} as unknown as Layer4Input['entities'],
    audioConfidenceStats: null,
    interpreterMode: false,
    noteTemplate: IMAGING,
  }) as Layer4Input;

const answer = (fills: string) =>
  [
    '## FINDINGS',
    'Right GSV 6.2 mm with reflux 1.4 seconds. Left GSV competent.',
    SLOT_VALUES_OPEN,
    fills,
    SLOT_VALUES_CLOSE,
  ].join('\n');

const persisted = () => mocks.prismaUpdate.mock.calls.at(-1)![0].data.soapDraft as string;
const system = () => mocks.modelCompleteText.mock.calls[0][0].system as string;

// Both flag states. Production runs ON; CI ran OFF and saw nothing.
describe.each([
  ['anchors OFF', undefined],
  ['⚠️ anchors ON — THE PRODUCTION CONFIGURATION', 'true'],
])('%s', (_label, flag) => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.stubEnv('NEXT_PUBLIC_ULTRASOUND_SPECIALTY', 'true');
    vi.stubEnv('TRANSCRIBE_MD_EVIDENCE_ANCHORS', flag ?? '');
    mocks.prismaUpdate.mockResolvedValue({ id: 'v1' });
    mocks.logAudit.mockResolvedValue(undefined);
  });
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.restoreAllMocks();
  });

  it('⚠️ THE IMAGING PROMPT CARRIES THE CONTRACT, not the doctor\'s bytes', async () => {
    mocks.modelCompleteText.mockResolvedValue({
      text: answer('{"technique":{"s0":"superficial"},"exam_metadata":{"s0":"left"}}'),
    });
    await runLayer4GenerateSoap(input());
    expect(system()).not.toContain('500 milliseconds');
    expect(system()).not.toContain('This study documents reflux');
    expect(system()).toContain('SYSTEM-COMPOSED SECTION');
    expect(system()).toContain(SLOT_VALUES_OPEN);
  });

  // ⚠️ THE ROOT CAUSE OF #106, AND IT WAS OURS. `normalizeRefluxTimeUnit` was
  // applied to `defaultText` on this route, so the PROMPT said `0.5 seconds`
  // and the model reproduced it faithfully.
  it('⚠️ the imaging prompt never rewrites the doctor\'s threshold to 0.5 seconds', async () => {
    mocks.modelCompleteText.mockResolvedValue({ text: answer('{}') });
    await runLayer4GenerateSoap(input());
    expect(system()).not.toContain('0.5 seconds');
  });

  it('the tripwire reaches the persisted draft, verbatim', async () => {
    mocks.modelCompleteText.mockResolvedValue({
      text: answer('{"technique":{"s0":"superficial"},"exam_metadata":{"s0":"left"}}'),
    });
    await runLayer4GenerateSoap(input());
    expect(persisted()).toContain('500 milliseconds');
    expect(persisted()).toContain('SIDE OF EXAM: left');
  });

  it('⚠️ THE PROTOCOL BLOCK NEVER REACHES THE NOTE — the arm anchors ON broke', async () => {
    mocks.modelCompleteText.mockResolvedValue({
      text: answer('{"technique":{"s0":"superficial"}}'),
    });
    await runLayer4GenerateSoap(input());
    expect(persisted()).not.toContain(SLOT_VALUES_OPEN);
    expect(persisted()).not.toContain('"s0"');
  });

  it('⚠️ a REFUSED out-of-menu value is never printed anywhere in the note', async () => {
    mocks.modelCompleteText.mockResolvedValue({
      text: answer('{"technique":{"s0":"whatever the model preferred"}}'),
    });
    await runLayer4GenerateSoap(input());
    expect(persisted()).not.toContain('whatever the model preferred');
    expect(persisted()).toContain('500 milliseconds');
  });

  it('the model\'s dictated FINDINGS survive byte-for-byte', async () => {
    mocks.modelCompleteText.mockResolvedValue({
      text: answer('{"exam_metadata":{"s0":"left"}}'),
    });
    await runLayer4GenerateSoap(input());
    expect(persisted()).toContain('Right GSV 6.2 mm with reflux 1.4 seconds.');
  });
});
