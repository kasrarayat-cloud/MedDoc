// ============================================================================
// GATE — the CONTENT-AWARE `tm_soap_draft` and `tm_polish` fixtures
// (ruling #106(a); the content-sensitivity contract, ruled 2026-08-08).
// ----------------------------------------------------------------------------
// ⚠️ A CONSTANT FIXTURE HERE WOULD MAKE THE PROOF AND THE FAILURE IDENTICAL.
// The contract under test is "the model reads a slot inventory and answers it
// from the transcript". A canned answer names slot ids no template produced and
// options no menu offers, so the assembler refuses every one of them — and the
// resulting note, full of empty markers, is indistinguishable from a run where
// the mechanism worked and the transcript simply said nothing.
//
// ⚠️ IT EXERCISES `mockCompleteText`, WHICH READS THE SAME SELECTION FUNCTION
// PRODUCTION READS through `buildMockMessage`. A second copy of the selection
// logic is the B0 failure: a tested helper beside an untested live one keeps
// the suite green while the real path drifts.
//
// (The mock master switch is named only in this comment, deliberately — see
//  mock-chat-edit.test.ts and the exemption note in the suite gate.)
// ============================================================================
import { afterEach, beforeEach, describe, expect, it } from 'vitest';

import {
  MOCK_SLOT_VALUES_CLOSE,
  MOCK_SLOT_VALUES_OPEN,
  mockCompleteText,
  mockPolishEcho,
  parseGeneratedHeadings,
  parseSlotInventory,
} from '../mock';

/** A structural twin of a built system prompt. Sanitized per SPEC §4.3a(e). */
const SYSTEM = [
  'You are a clinical scribe.',
  '',
  'Structure the note with these markdown headings exactly:',
  '',
  '## EXAM',
  'Write this section as prose.',
  '',
  '## TECHNIQUE',
  'SYSTEM-COMPOSED SECTION. Do NOT write this section. Its text is inserted',
  "verbatim from the clinician's own form by the system, and anything you",
  'write under this heading is discarded.',
  'Supply ONLY the values for its 2 slots, under the key "technique":',
  '  s0 — one of: deep and superficial | superficial',
  '  s1 — one of: right | left',
  '',
  '## IMPRESSION',
  'Write this section as prose.',
  '',
  'Critical rules:',
  '- never invent',
  '',
  `${MOCK_SLOT_VALUES_OPEN}`,
  '{"<section key>": {"<slot id>": "<one listed option, copied verbatim>"}}',
  `${MOCK_SLOT_VALUES_CLOSE}`,
].join('\n');

const TRANSCRIPT =
  'Doctor #0: We studied the superficial venous system of the left leg today.\n' +
  'Patient #1: Understood.';

const draft = (system: string, user: string) =>
  mockCompleteText({ purpose: 'tm_soap_draft', system, user }).text;

const parseBlock = (text: string): Record<string, Record<string, string>> => {
  const open = text.lastIndexOf(MOCK_SLOT_VALUES_OPEN);
  const close = text.indexOf(MOCK_SLOT_VALUES_CLOSE, open);
  return JSON.parse(text.slice(open + MOCK_SLOT_VALUES_OPEN.length, close).trim());
};

beforeEach(() => {
  delete process.env.MOCK_SLOT_OUT_OF_MENU;
  delete process.env.MOCK_POLISH_PARAPHRASE;
});
afterEach(() => {
  delete process.env.MOCK_SLOT_OUT_OF_MENU;
  delete process.env.MOCK_POLISH_PARAPHRASE;
});

describe('parseSlotInventory — anchored, never a bare includes', () => {
  it('reads each system-composed section with its slots and menus', () => {
    expect(parseSlotInventory(SYSTEM)).toEqual([
      {
        sectionKey: 'technique',
        slots: [
          { id: 's0', options: ['deep and superficial', 'superficial'] },
          { id: 's1', options: ['right', 'left'] },
        ],
      },
    ]);
  });

  it('does NOT read a slot out of prose that merely says "one of"', () => {
    const prose = 'The study is one of: several performed that day.';
    expect(parseSlotInventory(prose)).toEqual([]);
  });

  it('is empty for a prompt with no system-composed section', () => {
    expect(parseSlotInventory('## EXAM\nWrite this section as prose.')).toEqual([]);
  });
});

describe('parseGeneratedHeadings — the model writes everything it was not told to skip', () => {
  it('excludes the system-composed heading and keeps the rest, in order', () => {
    expect(parseGeneratedHeadings(SYSTEM)).toEqual(['EXAM', 'IMPRESSION']);
  });
});

describe('the fixture ANSWERS the inventory from the TRANSCRIPT', () => {
  it('picks the option the transcript supports, and omits the one it does not', () => {
    expect(parseBlock(draft(SYSTEM, TRANSCRIPT))).toEqual({
      technique: { s0: 'superficial', s1: 'left' },
    });
  });

  it('⚠️ VARIES WITH THE TRANSCRIPT — the whole reason it is not a constant', () => {
    const other = 'Doctor #0: Deep and superficial systems, right leg.';
    expect(parseBlock(draft(SYSTEM, other))).toEqual({
      technique: { s0: 'deep and superficial', s1: 'right' },
    });
  });

  it('omits every slot when the transcript supports none — the fail-closed shape', () => {
    expect(parseBlock(draft(SYSTEM, 'Doctor #0: Nothing relevant was said.'))).toEqual({
      technique: {},
    });
  });

  it('writes the generated headings and NOT the system-composed one', () => {
    const text = draft(SYSTEM, TRANSCRIPT);
    expect(text).toContain('## EXAM');
    expect(text).toContain('## IMPRESSION');
    expect(text).not.toContain('## TECHNIQUE');
  });

  it('MOCK_SLOT_OUT_OF_MENU makes the first slot answer off-menu — the refusal arm', () => {
    process.env.MOCK_SLOT_OUT_OF_MENU = 'true';
    const fills = parseBlock(draft(SYSTEM, TRANSCRIPT));
    expect(fills.technique!.s0).toBe('[MOCK] not on this menu');
    // …and the OTHER slots still answer honestly, so the run discriminates
    // between "refused" and "nothing worked".
    expect(fills.technique!.s1).toBe('left');
  });

  it('⚠️ A PROMPT WITHOUT THE PROTOCOL KEEPS THE CONSTANT FIXTURE', () => {
    const plain = mockCompleteText({
      purpose: 'tm_soap_draft',
      system: '## Subjective\nWrite this section as prose.',
      user: TRANSCRIPT,
    }).text;
    expect(plain).toContain('## Subjective');
    expect(plain).not.toContain(MOCK_SLOT_VALUES_OPEN);
  });

  it('and so does a call that passes no system prompt at all', () => {
    const bare = mockCompleteText({ purpose: 'tm_soap_draft' }).text;
    expect(bare).not.toContain(MOCK_SLOT_VALUES_OPEN);
  });
});

describe('mockPolishEcho — a copy editor returns the note it was given', () => {
  const user = (d: string) =>
    `Draft:\n${d}\n\nIssues to apply (apply in order):\n1. [minor] x: y\n    Fix: z`;

  it('echoes the draft, so a static section survives the polisher', () => {
    const d = '## TECHNIQUE\nreflux over 500 milliseconds.';
    expect(mockPolishEcho(user(d), 'FALLBACK')).toBe(d);
  });

  it('MOCK_POLISH_PARAPHRASE reproduces the production defect on demand', () => {
    process.env.MOCK_POLISH_PARAPHRASE = 'true';
    const d = '## TECHNIQUE\nreflux over 500 milliseconds.';
    expect(mockPolishEcho(user(d), 'FALLBACK')).toBe('## TECHNIQUE\nreflux over 0.5 seconds.');
  });

  it('⚠️ falls back to the constant when there is no draft to echo', () => {
    expect(mockPolishEcho('an arbitrary prompt', 'FALLBACK')).toBe('FALLBACK');
    expect(mockPolishEcho('Draft:\n\n\nIssues to apply (apply in order):', 'FALLBACK')).toBe(
      'FALLBACK'
    );
  });

  it('is reached through the same selection function production uses', () => {
    const d = '## TECHNIQUE\nreflux over 500 milliseconds.';
    expect(mockCompleteText({ purpose: 'tm_polish', user: user(d) }).text).toBe(d);
  });

  it('does NOT change another purpose\'s fixture', () => {
    expect(mockCompleteText({ purpose: 'tm_polish_gate', user: 'anything' }).text).toBe(
      '{"violations":[]}'
    );
  });
});
