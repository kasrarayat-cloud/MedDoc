// ============================================================================
// GATE — the ATOMIC PAIR, at pipeline level: the prompt asks for slot VALUES,
// and the seam composes the doctor's own bytes into the persisted draft
// (ruling #106(a)/(e), SPEC §4.3a).
// ----------------------------------------------------------------------------
// ⚠️ IT RUNS `runLayer4GenerateSoap`, NOT THE BUILDER, ON PURPOSE. A prompt
// asserted in isolation proves the prompt; the defect this item exists to fix
// lived in the JOIN between what the prompt asked for and what the seam did
// with the answer. A commit where the model produces scaffolds while the
// assembler expects values — or the reverse — passes any test that looks at one
// half. Both halves are measured here, through the real seam, with only the
// vendor call stubbed.
//
// ⚠️ THE FIXTURE IS SANITIZED, PER SPEC §4.3a(e): the structural twin of the
// real customer form, no real clinic / physician / technologist names, with
// `500 milliseconds` as the permitted verbatim tripwire.
// ============================================================================
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  modelCompleteText: vi.fn(),
  prismaUpdate: vi.fn(),
  logAudit: vi.fn(),
}));

vi.mock('@meddoc/ai', async () => {
  const actual = await vi.importActual<typeof import('@meddoc/ai')>('@meddoc/ai');
  return {
    ...actual,
    modelClient: { complete: vi.fn(), completeText: mocks.modelCompleteText },
  };
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
import { CHOICE_SLOT_DIRECTIVE } from '@/worker/note-templates/build-soap-prompt';
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

const EXAM = section({ key: 'exam', label: 'EXAM', order: 1 });
const IMPRESSION = section({ key: 'impression', label: 'IMPRESSION', order: 3 });

const TECHNIQUE_STATIC = section({
  key: 'technique',
  label: 'TECHNIQUE',
  order: 2,
  defaultText: TECHNIQUE_TEXT,
  defaultTextMode: 'always_include',
});
const TECHNIQUE_SCAFFOLD = section({
  key: 'technique',
  label: 'TECHNIQUE',
  order: 2,
  defaultText: TECHNIQUE_TEXT,
  defaultTextMode: 'scaffold_confirm',
});

const template = (sections: NoteTemplateSection[]): ResolvedNoteTemplate => ({
  id: 'tmpl_test',
  version: 1,
  isSystemDefault: false,
  sections,
  styleProfile: { tense: 'past', tone: 'clinical', abbreviations: 'expand' } as never,
});

const ASSEMBLING = template([EXAM, TECHNIQUE_STATIC, IMPRESSION]);
const ZERO_STATIC = template([EXAM, TECHNIQUE_SCAFFOLD, IMPRESSION]);

const input = (t: ResolvedNoteTemplate): Layer4Input =>
  ({
    visitId: 'v1',
    practiceId: 'p1',
    userId: 'd1',
    specialty: 'primary-care',
    roleLabeledTranscript:
      'Doctor #0: We studied the superficial venous system today.\n' +
      'Patient #1: Understood.',
    entities: {} as unknown as Layer4Input['entities'],
    audioConfidenceStats: null,
    interpreterMode: false,
    noteTemplate: t,
  }) as Layer4Input;

/** What a compliant model returns: markdown for the sections it was asked to
 *  write, and the slot-values block. It does NOT reproduce the static section —
 *  and when it tries to (the second helper), the composer overwrites it. */
const answer = (fills: string, extra = '') =>
  [
    '## EXAM',
    'Bilateral lower extremity venous duplex.',
    '',
    '## IMPRESSION',
    'No acute findings on this study.',
    extra,
    SLOT_VALUES_OPEN,
    fills,
    SLOT_VALUES_CLOSE,
  ].join('\n');

const persisted = () => mocks.prismaUpdate.mock.calls.at(-1)![0].data.soapDraft as string;

beforeEach(() => {
  vi.clearAllMocks();
  mocks.prismaUpdate.mockResolvedValue({ id: 'v1' });
  mocks.logAudit.mockResolvedValue(undefined);
});
afterEach(() => vi.restoreAllMocks());

describe('the PROMPT half — the model is never handed the doctor\'s prose', () => {
  it('⚠️ the fixed paragraph is ABSENT from the system prompt', async () => {
    mocks.modelCompleteText.mockResolvedValueOnce({
      text: answer('{"technique":{"s0":"superficial"}}'),
    });
    await runLayer4GenerateSoap(input(ASSEMBLING));
    const { system } = mocks.modelCompleteText.mock.calls[0][0];
    expect(system).not.toContain('500 milliseconds');
    expect(system).not.toContain('This study documents reflux');
  });

  it('asks for that section\'s slots by id, with its own menu, and for the block', async () => {
    mocks.modelCompleteText.mockResolvedValueOnce({ text: answer('{}') });
    await runLayer4GenerateSoap(input(ASSEMBLING));
    const { system } = mocks.modelCompleteText.mock.calls[0][0];
    expect(system).toContain('SYSTEM-COMPOSED SECTION');
    expect(system).toContain('under the key "technique"');
    expect(system).toContain('s0 — one of: deep and superficial | superficial');
    expect(system).toContain(SLOT_VALUES_OPEN);
  });

  it('RETIRES the reproduce-the-scaffold contract for that template', async () => {
    mocks.modelCompleteText.mockResolvedValueOnce({ text: answer('{}') });
    await runLayer4GenerateSoap(input(ASSEMBLING));
    const { system } = mocks.modelCompleteText.mock.calls[0][0];
    expect(system).not.toContain(CHOICE_SLOT_DIRECTIVE);
  });
});

describe('the SEAM half — the doctor\'s bytes reach the persisted draft', () => {
  it('⚠️ THE TRIPWIRE: 500 milliseconds is in soapDraft, verbatim', async () => {
    mocks.modelCompleteText.mockResolvedValueOnce({
      text: answer('{"technique":{"s0":"superficial"}}'),
    });
    await runLayer4GenerateSoap(input(ASSEMBLING));
    expect(persisted()).toContain('500 milliseconds');
    expect(persisted()).toContain(
      'condition of the superficial venous systems of the extremity'
    );
  });

  it('the protocol block never reaches the note', async () => {
    mocks.modelCompleteText.mockResolvedValueOnce({
      text: answer('{"technique":{"s0":"superficial"}}'),
    });
    await runLayer4GenerateSoap(input(ASSEMBLING));
    expect(persisted()).not.toContain(SLOT_VALUES_OPEN);
    expect(persisted()).not.toContain('"s0"');
  });

  it('an OUT-OF-MENU value is refused on the wire and leaves a visible hole', async () => {
    mocks.modelCompleteText.mockResolvedValueOnce({
      text: answer('{"technique":{"s0":"whatever the model preferred"}}'),
    });
    await runLayer4GenerateSoap(input(ASSEMBLING));
    expect(persisted()).not.toContain('whatever the model preferred');
    expect(persisted()).toContain('condition of the — venous systems');
    expect(persisted()).toContain('500 milliseconds');
  });

  it('NO block at all → fail-closed hole, and the paragraph still ships', async () => {
    mocks.modelCompleteText.mockResolvedValueOnce({
      text: '## EXAM\nBilateral.\n\n## IMPRESSION\nNo acute findings on this study.',
    });
    await runLayer4GenerateSoap(input(ASSEMBLING));
    expect(persisted()).toContain('500 milliseconds');
    expect(persisted()).toContain('—');
  });

  it('⚠️ a model that reproduces the section anyway is OVERWRITTEN, not merged', async () => {
    mocks.modelCompleteText.mockResolvedValueOnce({
      text: answer(
        '{"technique":{"s0":"superficial"}}',
        '\n## TECHNIQUE\nA duplex study documenting reflux over 0.5 seconds.\n'
      ),
    });
    await runLayer4GenerateSoap(input(ASSEMBLING));
    expect(persisted()).not.toContain('0.5 seconds');
    expect(persisted()).toContain('500 milliseconds');
  });

  it('carries the generated sections through byte-for-byte', async () => {
    mocks.modelCompleteText.mockResolvedValueOnce({
      text: answer('{"technique":{"s0":"superficial"}}'),
    });
    await runLayer4GenerateSoap(input(ASSEMBLING));
    expect(persisted()).toContain('## EXAM\nBilateral lower extremity venous duplex.');
    expect(persisted()).toContain('## IMPRESSION\nNo acute findings on this study.');
  });
});

describe('⚠️ #106(e) at PIPELINE level — a ZERO-STATIC template is untouched', () => {
  it('keeps the scaffold contract and never mentions the slot-values protocol', async () => {
    mocks.modelCompleteText.mockResolvedValueOnce({
      text: '## EXAM\nx\n\n## TECHNIQUE\nreflux over 500 milliseconds\n\n## IMPRESSION\nNo acute findings today.',
    });
    await runLayer4GenerateSoap(input(ZERO_STATIC));
    const { system } = mocks.modelCompleteText.mock.calls[0][0];
    expect(system).toContain(CHOICE_SLOT_DIRECTIVE);
    expect(system).not.toContain(SLOT_VALUES_OPEN);
    expect(system).not.toContain('SYSTEM-COMPOSED SECTION');
    // The doctor's text IS in the prompt on this path — that is today's
    // behaviour, preserved deliberately until the reclassification moves it.
    expect(system).toContain('500 milliseconds');
  });

  it('persists the model output byte-for-byte — no splice, no strip', async () => {
    const raw =
      '## EXAM\nx\n\n## TECHNIQUE\nreflux over 500 milliseconds\n\n## IMPRESSION\nNo acute findings today.';
    mocks.modelCompleteText.mockResolvedValueOnce({ text: raw });
    await runLayer4GenerateSoap(input(ZERO_STATIC));
    expect(persisted()).toBe(raw);
  });
});
