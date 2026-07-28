// ============================================================================
// The tm_chat_edit mock fixture.
// ----------------------------------------------------------------------------
// This purpose had no fixture at all, so the chat editor THREW under
// MOCK_AI_CALLS and its only coverage was an `.eval.spec.ts` — real tokens,
// operator-run, invisible to the required gate. That was survivable while the
// chat was one way to amend a note. It stopped being survivable when the
// per-section edit pills were deleted and the chat became the ONLY way.
//
// The fixture is content-aware because the chat editor's contract is precisely
// "turn what the doctor typed into an intent" — a fixture that cannot read the
// message cannot exercise that, and would pass while the dispatch was broken.
// ============================================================================

import { describe, expect, it } from 'vitest';
import { z } from 'zod';

import { mockComplete } from '../mock';

/** The shape the app validates against — kept local so this package does not
 *  depend on the app, and deliberately permissive about the intent members it
 *  does not exercise. */
const ReplySchema = z.object({
  reply: z.string().min(1).max(4000),
  intents: z
    .array(
      z.discriminatedUnion('kind', [
        z.object({
          kind: z.literal('edit_section'),
          sectionLabel: z.string().min(1).max(120),
          body: z.string().max(20_000),
        }),
        z.object({ kind: z.literal('answer') }),
      ]),
    )
    .min(1)
    .max(50),
});

/** Byte-for-byte the envelope `chat-edit-visit.ts` builds. */
const envelope = (message: string, note = '## FINDINGS\nOld body.\n') =>
  JSON.stringify(
    { note, conversation: [{ role: 'doctor', text: message }] },
    null,
    2,
  );

const run = (message: string) =>
  mockComplete({ purpose: 'tm_chat_edit', schema: ReplySchema, user: envelope(message) });

describe('mockComplete(tm_chat_edit)', () => {
  it('turns the directive into an edit_section intent', () => {
    const out = run('MOCKEDIT FINDINGS :: Reviewed and amended. QM-EDIT-MARK');
    expect(out.intents).toHaveLength(1);
    expect(out.intents[0]).toEqual({
      kind: 'edit_section',
      sectionLabel: 'FINDINGS',
      body: 'Reviewed and amended. QM-EDIT-MARK',
    });
  });

  it('handles a multi-word custom-template section label', () => {
    // The labels that matter here come from a doctor's uploaded form, not from
    // a fixed list — "DIAMETER AND REFLUX TIME" is a real WM_IOV heading.
    const out = run('MOCKEDIT DIAMETER AND REFLUX TIME :: GSV at the SFJ 6.2 mm.');
    expect(out.intents[0]).toMatchObject({
      kind: 'edit_section',
      sectionLabel: 'DIAMETER AND REFLUX TIME',
    });
  });

  it('survives JSON escaping of a multi-line body', () => {
    const out = run('MOCKEDIT IMPRESSION :: Line one.\nLine two.');
    expect(out.intents[0]).toMatchObject({ kind: 'edit_section', sectionLabel: 'IMPRESSION' });
    expect((out.intents[0] as { body: string }).body).toContain('Line one.');
  });

  it('a turn with no directive is an ANSWER, never an empty intent list', () => {
    // `intents: []` was legal once, and it is the exact failure this schema was
    // changed to prevent: a request the model could not map to a tool looked
    // identical to a chat question, and the turn logged SUCCESS having done,
    // written and refused nothing.
    const out = run('what level did this visit get?');
    expect(out.intents).toEqual([{ kind: 'answer' }]);
  });

  it('always satisfies the min(1) intents rule', () => {
    for (const m of ['', 'hello', 'MOCKEDIT', 'MOCKEDIT ::']) {
      expect(run(m).intents.length).toBeGreaterThanOrEqual(1);
    }
  });

  it('an unknown purpose still throws — the fixture wall is intact', () => {
    expect(() =>
      mockComplete({
        purpose: 'tm_not_a_real_purpose' as never,
        schema: ReplySchema,
        user: '',
      }),
    ).toThrow(/no complete\(\) fixture/);
  });
});
