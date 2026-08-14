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

import { readFileSync } from 'node:fs';

import { describe, expect, it } from 'vitest';

import { SPECIALTY_GUIDANCE, specialtyGuidance } from '../specialty-guidance';
import {
  buildSoapSystemPrompt,
  type ResolvedNoteTemplate,
} from '@/worker/note-templates/build-soap-prompt';
import { buildUltrasoundSystemPrompt } from '@/worker/note-templates/build-ultrasound-prompt';
import { SYSTEM_DEFAULT_NOTE_TEMPLATE } from '@/worker/note-templates/system-default-template';
import { ULTRASOUND_REPORT_TEMPLATE } from '@/worker/note-templates/ultrasound-report-template';

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

// ============================================================================
// THE NEVER-EDITORIALIZE CLAUSE — asserted as a CLAUSE, in BOTH prompt routes.
// ----------------------------------------------------------------------------
// ⚠️ THE LIVE EVIDENCE. Production visit `cmssgh1w7000r01no7g394xpj`
// (gastroenterology, READY, unsigned) failed L4 structure validation with SIX
// operative-note headings absent — PROCEDURE, PREOPERATIVE DIAGNOSIS,
// POSTOPERATIVE FINDINGS, CONSENT, DESCRIPTION OF PROCEDURE, RECOMMENDATIONS.
// An office-visit dictation against an operative-note template.
//
// ⚠️ AND THE MODEL DID NOT EDITORIALIZE — measured, seven probe shapes, all
// false, positive-controlled. It went QUIET rather than explaining itself. So
// this clause guards a defect that has NOT occurred in production, and that is
// said out loud rather than implied: it is cheap, its failure mode is silent,
// and a paragraph of meta-commentary inside a signed medical record cannot be
// un-signed. It is not tonight's evidence and must not be cited as such.
//
// ⚠️ ASSERTED AS A CLAUSE, NEVER A BYTE SNAPSHOT. A snapshot of the preamble
// would redden on every unrelated wording change and teach the next reader to
// re-bless it without reading — which is how a safety assertion becomes a
// formality. These match the COMMITMENT.
// ============================================================================
/**
 * Collapse newlines + indentation so an assertion can match a phrase the way a
 * READER sees it.
 *
 * ⚠️ THIS EXISTS BECAUSE THE SAME BUG BIT THREE ASSERTIONS IN A ROW. These
 * rules are authored as arrays of pre-wrapped strings joined with '\n', so a
 * phrase that reads continuously in the source — "an editorial aside in a
 * medical record", "Never delete a heading" — is split by a newline and two
 * spaces in the built prompt. Every one of those was a FALSE RED against a
 * prompt that carried the clause correctly.
 *
 * Hand-picking a fragment that happens to fit inside one line "fixes" each
 * instance and leaves the trap armed for the next person. Normalising once is
 * the durable form.
 */
const flat = (s: string): string => s.replace(/\s+/g, ' ');

describe('the never-editorialize clause reaches BOTH prompt routes', () => {
  // ⚠️ THE MATRIX IS THE POINT. `04-generate-soap.ts` selects between two
  // DIFFERENT builders on `emAppliesToSpecialty`, and the two draw their rules
  // from different templates. Proving one proves ONE — the wrong-universe
  // failure this repo has already paid for on a signed imaging report.
  const ROUTES = [
    {
      name: 'SOAP / gastroenterology',
      prompt: buildSoapSystemPrompt(GI_OP_NOTE, {
        specialty: GI,
        audioQualityAlert: null,
        interpreterAlert: null,
        specialtyGuidanceText: specialtyGuidance(GI),
      }),
    },
    {
      name: 'ULTRASOUND / imaging',
      prompt: buildUltrasoundSystemPrompt(
        ULTRASOUND_REPORT_TEMPLATE as unknown as ResolvedNoteTemplate,
        {
          specialty: 'ultrasound',
          audioQualityAlert: null,
          interpreterAlert: null,
          specialtyGuidanceText: null,
        },
      ),
    },
  ];

  it.each(ROUTES)('$name — the prompt forbids addressing the reader', ({ prompt }) => {
    expect(flat(prompt)).toMatch(/Never address the reader/i);
    expect(flat(prompt)).toMatch(/Write the note and nothing else/i);
  });

  it.each(ROUTES)('$name — it says KEEP THE HEADING, never delete it', ({ prompt }) => {
    // ⚠️ THE FIRST DRAFT SAID "left EMPTY" WITHOUT SAYING "keep the heading",
    // and an adversarial pass showed both readings are harmful: dropping the
    // heading fires the mismatch banner at the doctor, and leaving a bare
    // heading reproduces the recorded empty-Assessment blocker — which
    // `backfillEmptySections` DELIBERATELY cannot repair, because it only
    // restores sections that LOST content to demotion, never ones the model
    // never filled. L6's own wording already said it correctly.
    expect(flat(prompt)).toMatch(/KEEP THE HEADING and leave its body empty/);
    expect(flat(prompt)).toMatch(/Never delete a heading/i);
  });

  it.each(ROUTES)('$name — "not documented" stays CLINICAL CONTENT, not commentary', ({ prompt }) => {
    // ⚠️ THE CONTRADICTION THE FIRST DRAFT CREATED. It forbade saying
    // information was missing and capped the vocabulary at two forms. The same
    // built prompt already MANDATES four other sentences by name — globalRules
    // "If no exam occurred, the Objective section says so", `write exactly:
    // "Formal exam not documented in this encounter."`, the ROS single line,
    // and on imaging `write exactly: "No prior study available for
    // comparison."` plus "[laterality not specified]". No precedence rule
    // exists anywhere to break the tie, so the model was given conflicting
    // instructions and would obey neither reliably.
    expect(flat(prompt)).toMatch(/Recording that a finding was not documented is clinical content/i);
    expect(flat(prompt)).not.toMatch(/only two ways to say nothing was found/i);
  });

  it.each(ROUTES)('$name — it forbids explaining a template mismatch specifically', ({ prompt }) => {
    // ⚠️ MATCHED WITHIN A LINE, NOT ACROSS ONE. These rules are authored as
    // arrays of pre-wrapped strings joined with '\n', so a phrase that reads
    // continuously in the source ("an editorial aside in a medical record")
    // is split by a newline and two spaces in the built prompt. My first
    // version of this assertion spanned the wrap and reddened against a prompt
    // that carried the clause correctly — a FALSE RED, and the mirror of the
    // substring traps this repo already documents.
    expect(flat(prompt)).toMatch(/mismatch between this template and the dictation is NOT yours to explain/i);
    expect(flat(prompt)).toMatch(/an editorial remark in a medical record/i);
  });

  it('⚠️ POSITION — the clause is NOT last, or imaging silently loses it', () => {
    // `ultrasound-report-template.ts` builds its rules as
    // `SOAP_SAFETY.globalRules.slice(0, -1)`, dropping exactly the SOAP output
    // line. A rule appended AFTER that line reaches primary care and NOT
    // imaging — the per-specialty gap, arriving through an array index.
    const rules = SYSTEM_DEFAULT_NOTE_TEMPLATE.styleProfile.globalRules;
    expect(rules[rules.length - 1]).toMatch(/^- Output ONLY the SOAP note markdown/);
    const idx = rules.findIndex((r) => /Never address the reader/i.test(r));
    expect(idx, 'the clause is missing entirely').toBeGreaterThanOrEqual(0);
    expect(idx, 'the clause is LAST — imaging will not receive it').toBeLessThan(rules.length - 1);
  });

  it('NON-VACUITY — the two routes really are different prompts', () => {
    // Without this, both entries could be the same builder and the matrix
    // would prove one thing twice.
    expect(ROUTES[0].prompt).not.toBe(ROUTES[1].prompt);
    expect(ROUTES[0].prompt).toMatch(/SOAP/i);
    expect(ROUTES[1].prompt).toMatch(/ultrasound|imaging|sonograph/i);
  });
});

// ============================================================================
// ⚠️ THE THIRD MODEL CALL — L6, which writes the SIGNED note.
// ----------------------------------------------------------------------------
// THE GATE ABOVE WATCHED TWO BUILDERS AND THERE ARE THREE PROMPTS THAT PRODUCE
// NOTE TEXT. `tm_polish` rewrites the note wholesale whenever L5 finds a
// fixable issue, and `runLayer6Polish` returns `soapFinal`, which `sign/route`
// writes to `signedSoap`. A clause that governs only L4's `soapDraft` does not
// govern what the doctor signs.
//
// Found by an adversarial pass, not by this file — which is the point worth
// keeping: the watched set was "the builders I had just edited", and the
// universe was "every prompt that writes note text". That is this repo's own
// watched-set failure, committed by the person who wrote the entry about it.
//
// ⚠️ AND L6'S OWN ANTI-COMMENTARY SENTENCE WAS FLAG-GATED OFF FOR EXACTLY THE
// ROUTES THAT MATTER. It lived inside `emitStructureLock`, which is
// `!template.isSystemDefault` — so it was absent for the system default AND for
// imaging, because an imaging visit reaches L6 carrying the SOAP system default
// (L4 swaps the ultrasound template in internally and never reflects it back).
// The rule is now emitted unconditionally, which is what these arms pin.
// ============================================================================
describe('the clause reaches L6 — the prompt that writes the SIGNED note', () => {
  const L6_SRC = readFileSync('src/worker/layers/06-polish.ts', 'utf8');
  const code = L6_SRC.replace(/\/\*[\s\S]*?\*\//g, ' ').replace(/^\s*\/\/.*$/gm, ' ');

  it('NON-VACUITY — the stripper left the prompt builder behind', () => {
    expect(code).toContain("'Rules:'");
  });

  it('L6 forbids addressing the reader and describing its own process', () => {
    expect(code).toMatch(/Never address the reader and never describe your own process/);
  });

  it('⚠️ UNGATED — it is NOT inside the emitStructureLock branch', () => {
    // The whole defect: the only anti-commentary sentence L6 had was gated to
    // non-default templates, so the system default and every imaging report
    // were polished by a model told nothing about commentary.
    const lockAt = code.indexOf('emitStructureLock');
    const clauseAt = code.indexOf('Never address the reader');
    expect(lockAt, 'emitStructureLock not found — this arm is measuring nothing').toBeGreaterThan(0);
    expect(clauseAt, 'the clause is not in L6 at all').toBeGreaterThan(0);
    // The gated array closes before `'Rules:'`; the clause must sit after it.
    const rulesAt = code.indexOf("'Rules:'");
    expect(clauseAt).toBeLessThan(rulesAt);
    expect(code.slice(clauseAt, rulesAt)).not.toContain('emitStructureLock');
  });

  it('it PRESERVES "not documented" as clinical content, not commentary', () => {
    // ⚠️ THE DISTINCTION THE FIRST DRAFT COLLAPSED. Saying a finding was not
    // documented is required by `globalRules[7]` and by two "write exactly"
    // section directives. Forbidding it would have put the prompt in
    // contradiction with itself.
    expect(code).toMatch(/not documented is clinical content/);
  });
});
