// ============================================================================
// The chat editor's safety rules, pinned.
// ----------------------------------------------------------------------------
// These are not tests of the model. They are tests of what the SERVER will
// accept from it — the shape of the hole the model is allowed to speak through.
// A model that decides to sign a note must find that there is simply no way to
// say so.
// ============================================================================

import { readFileSync } from 'node:fs';

import { describe, expect, it } from 'vitest';

import { ChatIntentSchema, ChatReplySchema } from '../intent';
import { CHAT_EDIT_SYSTEM } from '../prompt';

describe('the intent union', () => {
  it('accepts everything the chat may do', () => {
    for (const intent of [
      { kind: 'edit_section', sectionLabel: 'FINDINGS', body: 'Rewritten.' },
      {
        kind: 'edit_table_cell',
        sectionLabel: 'FINDINGS',
        rowLabel: 'GSV at the SFJ',
        columnLabel: 'DIAMETER (mm)',
        value: '6.8',
      },
      { kind: 'edit_header', field: 'patient_name', value: 'Jane Doe' },
      { kind: 'scroll_to', target: 'rx_gate' },
      { kind: 'answer' },
      { kind: 'cannot', what: 'change the letterhead', where: 'Settings › My Note Format' },
      { kind: 'refuse', because: 'That is not part of this visit.' },
    ]) {
      expect(ChatIntentSchema.safeParse(intent).success, JSON.stringify(intent)).toBe(true);
    }
  });

  it('REFUSES the adopt intents — the lane they addressed is gone', () => {
    // The union is CLOSED, and that is the point: the verifier is audit-only,
    // nothing is staged, and an intent that survived here would be a capability
    // the model could still emit and the dispatcher could no longer honour —
    // a silent no-op wearing the name of an action.
    for (const intent of [
      { kind: 'adopt_suggestion', index: 0 },
      { kind: 'adopt_suggestions', indexes: [0, 1] },
      { kind: 'listed_suggestions', indexes: [0] },
      { kind: 'scroll_to', target: 'suggestions' },
    ]) {
      expect(ChatIntentSchema.safeParse(intent).success, JSON.stringify(intent)).toBe(false);
    }
  });

  it('HAS NO WAY to express satisfying a hard gate', () => {
    // Not "rejects" — there is no such member. If one is ever added, this
    // fails, and whoever added it has to justify it here.
    for (const forbidden of [
      { kind: 'override_rx_warning', warningId: 'w1' },
      { kind: 'confirm_em_change' },
      { kind: 'sign_visit' },
      { kind: 'sign', visitId: 'v1' },
      { kind: 'export_visit' },
      { kind: 'delete_visit' },
    ]) {
      expect(
        ChatIntentSchema.safeParse(forbidden).success,
        `${forbidden.kind} must not be expressible`,
      ).toBe(false);
    }
  });

  it('refuses malformed adopts rather than coercing them', () => {
    expect(ChatIntentSchema.safeParse({ kind: 'adopt_suggestion', index: -1 }).success).toBe(false);
    expect(ChatIntentSchema.safeParse({ kind: 'adopt_suggestion', index: 1.5 }).success).toBe(false);
    expect(ChatIntentSchema.safeParse({ kind: 'adopt_suggestions', indexes: [] }).success).toBe(false);
  });

  it('bounds a reply so one turn cannot fan out unboundedly', () => {
    const many = Array.from({ length: 51 }, () => ({ kind: 'scroll_to', target: 'codes' }));
    expect(ChatReplySchema.safeParse({ reply: 'x', intents: many }).success).toBe(false);
  });

  it('requires a reply — an action with no explanation is not allowed', () => {
    expect(
      ChatReplySchema.safeParse({ reply: '', intents: [{ kind: 'scroll_to', target: 'codes' }] })
        .success,
    ).toBe(false);
  });
});

describe('the dispatcher', () => {
  const src = readFileSync('src/actions/chat-edit-visit.ts', 'utf8');

  it('has no adopt path at all, bulk or otherwise', () => {
    // Was: "calls the per-claim adopt, never a bulk endpoint". The per-claim
    // discipline mattered because each adopt produced its own audit row; with
    // the lane gone the honest assertion is that neither shape exists.
    expect(src).not.toMatch(/adoptSuggestionAction|adoptAll|bulkAdopt|acceptRemainingAction/);
  });

  it('never imports a signing, override or export path', () => {
    for (const forbidden of [
      'recordOverride',
      'signVisit',
      '/sign',
      'export/docx',
      'confirmEm',
    ]) {
      expect(src, `chat must not reach ${forbidden}`).not.toContain(forbidden);
    }
  });

  it('refuses a signed visit before doing anything else', () => {
    const beforeModel = src.slice(0, src.indexOf('modelClient.complete'));
    expect(beforeModel).toContain("visit.status === 'SIGNED'");
  });

  it('no longer carries a listing gate — there is nothing to list', () => {
    // The gate existed to put the doctor's eyes between a suggestion being
    // shown and being adopted in bulk. Both halves are gone; the attestation
    // store that backed it is deleted.
    expect(src).not.toContain('bulkNeedsListing');
    expect(src).not.toContain('chat-edit/attestation');
  });

  it('wraps every dispatch so a throw cannot discard completed work', () => {
    const loop = src.slice(src.indexOf('for (const intent of parsed.intents)'));
    expect(loop).toContain('try {');
    expect(loop).toContain('catch (err)');
  });

  it('passes the version it read to the section save', () => {
    expect(src).toContain('visit.soapVersion,');
  });

  it('keeps the doctor’s instruction OUTSIDE the untrusted data region', () => {
    const wrapCall = src.slice(src.indexOf('wrapAsData('), src.indexOf("'transcript',"));
    expect(wrapCall, 'the message must not be wrapped as data').not.toContain('doctorSays');
    expect(src).toContain('THE DOCTOR SAYS');
  });

  it('the model is never handed a suggestions array to address', () => {
    // It cannot adopt what it cannot see, and shipping an empty array would
    // still invite the model to reason about a lane that no longer exists.
    expect(src).not.toContain('suggestions: claims.map');
  });
});

describe('the system prompt', () => {
  it('states the scope guard and the gate rule', () => {
    expect(CHAT_EDIT_SYSTEM).toMatch(/SCOPE/);
    expect(CHAT_EDIT_SYSTEM).toMatch(/never override|cannot override/i);
    expect(CHAT_EDIT_SYSTEM).toMatch(/sign/i);
  });

  it('requires the reply to name what was done', () => {
    expect(CHAT_EDIT_SYSTEM).toMatch(/NAME WHAT YOU DID/);
  });

  it('carries the prompt-injection delimiter suffix', () => {
    expect(CHAT_EDIT_SYSTEM).toMatch(/transcript/);
  });
});

// ============================================================================
// THE SILENT NO-OP, CLOSED AT THE SCHEMA.
// ----------------------------------------------------------------------------
// Production, 2026-07-27 02:36:17Z. One CHAT_EDIT_TURN row, kasra's:
//
//   {"intents": [], "edited": 0, "adopted": 0, "refused": 0, "failed": 0}
//
// The model was called, answered in 183 tokens of prose, declared no intents,
// and the server wrote nothing and logged SUCCESS. The visit was untouched four
// hours later. He asked for something and got sentences, and no counter, row or
// error recorded that anything had been asked.
//
// The cause was one permitted value: an empty intents array, documented as
// "empty when the turn is purely conversational". That made a request the model
// could not map to a tool indistinguishable from a question.
// ============================================================================
describe('a turn always declares what kind of turn it was', () => {
  it('REJECTS an empty intents array — the exact shape of kasra failed turn', () => {
    expect(
      ChatReplySchema.safeParse({ reply: 'I have updated the note for you.', intents: [] }).success,
      'an empty intents array must not be representable',
    ).toBe(false);
  });

  it('accepts a question answered, so a conversational turn stays possible', () => {
    expect(
      ChatReplySchema.safeParse({ reply: 'The level is 99213.', intents: [{ kind: 'answer' }] }).success,
    ).toBe(true);
  });

  it('accepts a capability gap, which is what the failed turn should have been', () => {
    expect(
      ChatReplySchema.safeParse({
        reply: "I can't change the letterhead here; that's in Settings › My Note Format.",
        intents: [{ kind: 'cannot', what: 'change the letterhead', where: 'Settings › My Note Format' }],
      }).success,
    ).toBe(true);
  });

  it('keeps `cannot` and `refuse` as DIFFERENT things', () => {
    // capability vs policy. Collapsing them would let a hard gate be reported
    // as "no tool for that", which reads like an oversight rather than a rule.
    expect(ChatIntentSchema.safeParse({ kind: 'cannot', what: 'sign', where: 'x' }).success).toBe(true);
    expect(ChatIntentSchema.safeParse({ kind: 'refuse', because: 'yours to do' }).success).toBe(true);
    expect(ChatIntentSchema.safeParse({ kind: 'cannot', what: 'x' }).success).toBe(false);
  });

  it('a table-cell edit must carry all four coordinates', () => {
    // A missing column would otherwise be a write to whichever cell matched.
    const full = {
      kind: 'edit_table_cell',
      sectionLabel: 'FINDINGS',
      rowLabel: 'GSV at the SFJ',
      columnLabel: 'DIAMETER (mm)',
      value: '6.8',
    };
    for (const drop of ['sectionLabel', 'rowLabel', 'columnLabel']) {
      const partial = { ...full } as Record<string, unknown>;
      delete partial[drop];
      expect(ChatIntentSchema.safeParse(partial).success, `missing ${drop} must be rejected`).toBe(false);
    }
  });

  it('the header tool reaches ONLY the two fields it names', () => {
    expect(ChatIntentSchema.safeParse({ kind: 'edit_header', field: 'patient_name', value: 'A' }).success).toBe(true);
    expect(ChatIntentSchema.safeParse({ kind: 'edit_header', field: 'chief_complaint', value: 'A' }).success).toBe(true);
    // Not the signature, not the status, not the dates the record turns on.
    for (const field of ['signedAt', 'status', 'userId', 'emScoredCode', 'soapFinal']) {
      expect(
        ChatIntentSchema.safeParse({ kind: 'edit_header', field, value: 'A' }).success,
        `${field} must not be reachable from the chat`,
      ).toBe(false);
    }
  });
});
