// ============================================================================
// GATE — the GI guidance's CLINICAL CONTENT, and that it reaches L4's prompt
// ----------------------------------------------------------------------------
// ⚠ WHY THIS FILE EXISTS. Every gate guarding SPECIALTY_GUIDANCE checked that
// a KEY EXISTS and that its value is non-empty:
//
//   specialty-guidance.test.ts:29        — `missing` set is empty
//   specialty-catalog.test.ts:86-87      — toContain(templateId) + toMatch(/\S/)
//
// An adversarial pass on 2026-08-14 deleted the ENTIRE anti-fabrication safety
// clause from the gastroenterology entry and the full suite still reported
// 3817 passed / 0 failed. A 22-character string would satisfy both gates.
// The most safety-critical prose in the change was protected by nothing.
//
// AND the QA walk could not cover it either: MOCK_AI returns a canned note and
// ignores the prompt entirely, so a mocked walk proves the plumbing and says
// NOTHING about whether the guidance reached the model. That is not a flaw in
// the walk — it is the reason this gate has to exist in the suite instead.
//
// So this file asserts the two things that actually matter: the clinical
// commitments are PRESENT, and they SURVIVE the trip into the built system
// prompt. Assertions are on the load-bearing CLAIMS, not on a byte snapshot —
// a snapshot would go red on every wording change and get re-baselined.
// ============================================================================

import { describe, expect, it } from 'vitest';

import { SPECIALTY_GUIDANCE, specialtyGuidance } from '../specialty-guidance';
import {
  buildSoapSystemPrompt,
  type ResolvedNoteTemplate,
} from '@/worker/note-templates/build-soap-prompt';

const GI = 'gastroenterology';

/** A GI OPERATIVE-NOTE template, shaped like the real ones: six sections,
 *  none of them SOAP. Sanitized — no customer bytes. */
const GI_OP_NOTE: ResolvedNoteTemplate = {
  id: 'tmpl_gi_opnote',
  version: 1,
  isSystemDefault: false,
  styleProfile: {
    tense: 'past',
    tone: 'concise',
    abbreviations: null,
    preamble: null,
    globalRules: [],
  },
  sections: [
    { key: 'procedure', label: 'Procedure', order: 1, formatHint: 'prose', styleInstructions: 'Procedure performed.', defaultText: null, defaultTextMode: 'omit_unless_supported' },
    { key: 'preoperative_diagnosis', label: 'Preoperative Diagnosis', order: 2, formatHint: 'prose', styleInstructions: 'Indication.', defaultText: null, defaultTextMode: 'omit_unless_supported' },
    { key: 'description_of_procedure', label: 'Description of Procedure', order: 3, formatHint: 'prose', styleInstructions: 'What was done.', defaultText: null, defaultTextMode: 'omit_unless_supported' },
    { key: 'postoperative_findings', label: 'Postoperative Findings', order: 4, formatHint: 'prose', styleInstructions: 'Findings.', defaultText: null, defaultTextMode: 'omit_unless_supported' },
    { key: 'recommendations', label: 'Recommendations', order: 5, formatHint: 'numbered', styleInstructions: 'Follow-up.', defaultText: null, defaultTextMode: 'omit_unless_supported' },
  ],
} as unknown as ResolvedNoteTemplate;

describe('GI guidance — the clinical commitments are PRESENT', () => {
  const text = SPECIALTY_GUIDANCE[GI];

  it('exists and is substantial, not a placeholder that satisfies /\\S/', () => {
    expect(text).toBeDefined();
    // The deleted-clause mutation left 22 characters and passed every gate.
    expect(text.length).toBeGreaterThan(1200);
  });

  it('branches on BOTH encounter shapes — office visit AND procedure note', () => {
    expect(text).toMatch(/SHAPE = OFFICE VISIT/);
    expect(text).toMatch(/SHAPE = PROCEDURE \/ OPERATIVE NOTE/);
  });

  it('carries the anti-fabrication clause — THE safety-critical sentence', () => {
    // Deleting exactly this block is what the adversarial pass proved was
    // invisible. Each assertion is a distinct clinical commitment.
    expect(text).toMatch(/NEVER INVENT/i);
    expect(text).toMatch(/surveillance interval/i);
    expect(text).toMatch(/pending pathology/i);
    expect(text).toMatch(/was not dictated/i);
  });

  it('does NOT instruct an unsaid absence to be asserted as a finding', () => {
    // The original wording — "State complications explicitly INCLUDING their
    // absence" — told the model to write "no complications" on a dictation
    // that never mentioned them. That is a fabricated clinical claim in an
    // operative note. The replacement is conditional; this pins it.
    expect(text).toMatch(/WHEN THE DICTATION ADDRESSES/);
    expect(text).toMatch(/IF THE[\s\S]{0,40}DICTATION IS SILENT/);
  });

  it('is CONTENT-ONLY — it never tells the model to invent a heading', () => {
    // The fidelity contract: the doctor's template owns the structure.
    // Two older entries in this file predate that and DO prescribe layout;
    // GI must not, because a GI operative-note template brings its own
    // sections and guidance that invented headings would fight it.
    expect(text).not.toMatch(/Include an? '[^']+' (sub)?section/i);
    expect(text).not.toMatch(/First line of \w+ MUST be/i);
  });
});

describe('GI guidance — it SURVIVES into the L4 system prompt', () => {
  // This is the half a mocked QA walk cannot reach.
  const prompt = buildSoapSystemPrompt(GI_OP_NOTE, {
    specialty: GI,
    audioQualityAlert: null,
    interpreterAlert: null,
    specialtyGuidanceText: specialtyGuidance(GI),
  });

  it('the built prompt carries the GI safety clause verbatim', () => {
    expect(prompt).toMatch(/NEVER INVENT/i);
    expect(prompt).toMatch(/surveillance interval/i);
  });

  it("still carries the doctor's template sections — guidance did not replace structure", () => {
    expect(prompt).toContain('## Procedure');
    expect(prompt).toContain('## Description of Procedure');
    expect(prompt).toContain('## Recommendations');
  });

  it('still carries the IMMUTABLE safety preamble', () => {
    expect(prompt).toContain('Do NOT invent clinical findings');
  });

  it('carries NO slot-values contract — which is WHY the mocked QA walk could not read it', () => {
    // ⚠ PRECISION, CORRECTED 2026-08-14 after a peer challenged an over-broad
    // claim of mine. It is NOT true that "MOCK_AI ignores the prompt". The mock
    // is CONTENT-SENSITIVE, gated at packages/ai/src/mock.ts:673-682 on
    //     purpose === 'tm_soap_draft' && system.includes(MOCK_SLOT_VALUES_OPEN)
    // When a prompt carries the slot contract the mock PARSES it and answers
    // from the transcript — so a mocked walk CAN prove the prompt→answer
    // contract for slot inventory.
    //
    // It could not here, and this assertion says why: a GI operative-note
    // template has no `{{one of:` menus, so nothing is assembled, so the built
    // prompt carries no slot contract, so the mock takes the CONSTANT branch
    // and returns a canned note that reflects no part of this prompt.
    //
    // Pinning it makes the walk's limit a checked fact instead of a sentence
    // in a report. If GI ever gains a slot-carrying template this goes RED,
    // and that is the correct moment to re-read what the walk proves.
    expect(prompt).not.toContain('<<<SLOT_VALUES');
  });

  it('resolves through specialtyGuidance() by ID — the runtime lookup path', () => {
    // 04-generate-soap.ts:100 calls specialtyGuidance(input.specialty) with the
    // catalog ID. The coverage gates assert by templateId. Those agree only
    // because specialties.test.ts pins templateId === id; if that ever relaxes,
    // this is the assertion that notices.
    expect(specialtyGuidance(GI)).toBe(SPECIALTY_GUIDANCE[GI]);
    expect(specialtyGuidance(GI).length).toBeGreaterThan(1200);
  });
});
