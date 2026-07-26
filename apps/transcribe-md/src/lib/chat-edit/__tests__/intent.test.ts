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
  it('accepts the four things the chat may do', () => {
    for (const intent of [
      { kind: 'adopt_suggestion', index: 0 },
      { kind: 'adopt_suggestions', indexes: [0, 1] },
      { kind: 'edit_section', sectionLabel: 'FINDINGS', body: 'Rewritten.' },
      { kind: 'scroll_to', target: 'rx_gate' },
      { kind: 'refuse', because: 'That is not part of this visit.' },
    ]) {
      expect(ChatIntentSchema.safeParse(intent).success, JSON.stringify(intent)).toBe(true);
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

  it('calls the per-claim adopt, never a bulk endpoint', () => {
    expect(src).toContain('adoptSuggestionAction(visitId, index, claim.text)');
    expect(src).not.toMatch(/adoptAll|bulkAdopt|acceptRemainingAction/);
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

  it('decides the listing gate ONCE for the whole turn, not per intent', () => {
    // Checking it inside the switch meant fifty separate `adopt_suggestion`
    // intents adopted fifty suggestions with no listing requirement at all —
    // the singular arm never reached the check.
    const gate = src.slice(0, src.indexOf('for (const intent of parsed.intents)'));
    expect(gate, 'the gate must be computed before the dispatch loop').toContain(
      'bulkNeedsListing',
    );
    expect(src).toContain('parsed.intents.flatMap');
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

  it('adopts highest-index-first so indexes stay valid as the array shrinks', () => {
    expect(src).toContain('sort((a, b) => b - a)');
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
