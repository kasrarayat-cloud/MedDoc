// ============================================================================
// Layer 3 — Medical entity extraction with evidence quotes (T-M4 + T-M5)
// ----------------------------------------------------------------------------
// Takes whatever the upstream layer produced (full conversation from L1+L2,
// a single-speaker dictation from L1', or raw typed text from the doctor)
// and turns it into a structured entity set. Every item still carries an
// evidence_quote so Layer 4 can never invent findings.
//
// Three modes:
//   - conversation (audio_upload)   — role-labeled lines, speaker + ts required
//   - dictation    (voice_dictation) — one doctor-only block, speaker = "Doctor"
//   - text         (text_notes)     — raw typed bullets, no timestamps
// ============================================================================

import { z } from 'zod';

import {
  ROS_SYSTEMS,
  ROS_SYSTEMS_RESOLVED,
  resolveRosFinding,
  resolveRosSystem,
  symptomsFor,
} from '@/lib/template-twin/ros-lexicon';
import {
  modelClient,
  type DeepgramUtterance,
  wrapAsData,
  delimiterSystemSuffix,
} from '@meddoc/ai';
import prisma from '@meddoc/db';
import type { SpeakerMap } from './02-speaker-roles';
import { markUnclearTranscript } from './transcript-clarity';
import { logAudit } from '@/lib/audit';

// TRANSCRIBE_MD_CLINICAL_MODEL — eval override (feat/fable5-eval); unset → default unchanged.
const MODEL = process.env.TRANSCRIBE_MD_CLINICAL_MODEL || 'claude-sonnet-4-6';

// ---------------------------------------------------------------------------
// Schema — evidence_quote is always required (no hallucination rule), but
// speaker + timestamp are optional so dictation/text modes don't have to
// fake them. In conversation mode the prompt still demands both.
// ---------------------------------------------------------------------------

export const Evidence = z.object({
  evidence_quote: z.string().min(1),
  speaker: z.string().optional(),
  /** seconds from audio start; only conversation + dictation populate this. */
  timestamp: z.number().nonnegative().optional(),
});
export type Evidence = z.infer<typeof Evidence>;

// A "fact plus evidence" wrapper used everywhere there's a single textual
// finding to capture.
//
// Q2 fix-pack §06.3 — every fact field is `.min(1)` so the model can't
// satisfy the schema with an empty string for a required clinical
// concept. The retry-on-schema-fail loop catches the empty-string case
// and re-prompts.
function factWithEvidence<K extends string>(
  key: K
): z.ZodObject<{ [P in K | 'evidence_quote' | 'speaker' | 'timestamp']: z.ZodTypeAny }> {
  return z.object({
    [key]: z.string().min(1),
    evidence_quote: z.string().min(1),
    speaker: z.string().optional(),
    timestamp: z.number().nonnegative().optional(),
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
  }) as any;
}

/** Q1 #19 follow-up: lift a bare string into a factWithEvidence-shaped
 *  object. Prompt guidance asks the model to emit the full shape, but
 *  the model occasionally shortcuts to `"occupation": "factory worker"`
 *  in social_history fields. This preserves the data instead of
 *  rejecting the whole entity-extraction call (15/68 SCHEMA_FAIL hits
 *  on this in the 2026-05-10 baseline). The string itself becomes
 *  both the value AND evidence_quote — lossy but monotone. */
function liftStringToFact<K extends string>(key: K) {
  const objectShape = factWithEvidence(key);
  return z
    .preprocess((value) => {
      if (typeof value === 'string' && value.length > 0) {
        return { [key]: value, evidence_quote: value };
      }
      return value;
    }, objectShape)
    .nullable()
    .optional();
}

const HpiDimensions = z.object({
  onset: z.string().optional(),
  duration: z.string().optional(),
  quality: z.string().optional(),
  severity: z.string().optional(),
  location: z.string().optional(),
  timing: z.string().optional(),
  context: z.string().optional(),
  modifying_factors: z.string().optional(),
  associated_symptoms: z.string().optional(),
  evidence_quote: z.string().min(1),
  speaker: z.string().optional(),
  timestamp: z.number().nonnegative().optional(),
});

export const ExtractedEntities = z.object({
  chief_complaint: z
    .object({
      // Q2 fix-pack §06.3 — empty statement is invalid; force re-extract.
      statement: z.string().min(1),
      evidence_quote: z.string().min(1),
      speaker: z.string().optional(),
      timestamp: z.number().nonnegative().optional(),
    })
    .nullable(),
  hpi: HpiDimensions.nullable(),
  past_medical_history: z.array(factWithEvidence('condition')).default([]),
  medications: z
    .array(
      z.object({
        // Q2 fix-pack — drug name must be present.
        name: z.string().min(1),
        dose: z.string().nullable().optional(),
        route: z.string().nullable().optional(),
        frequency: z.string().nullable().optional(),
        evidence_quote: z.string().min(1),
        speaker: z.string().optional(),
        timestamp: z.number().nonnegative().optional(),
      })
    )
    .default([]),
  allergies: z
    .array(
      z.object({
        // Q2 fix-pack — substance must be present (clinical safety).
        substance: z.string().min(1),
        reaction: z.string().nullable().optional(),
        evidence_quote: z.string().min(1),
        speaker: z.string().optional(),
        timestamp: z.number().nonnegative().optional(),
        // Q1 #02.8 — allergy conflict resolution. When the visit contains
        // conflicting allergy statements (e.g. "no allergies" then "I'm
        // allergic to penicillin", or a later retraction), the extractor
        // keeps BOTH entries and flags the contradicted/earlier one with
        // `superseded: true` + a short `conflict_note`. NEVER drop either
        // statement. SAFETY INVARIANT: `superseded` is a doctor-review hint
        // ONLY — it must NEVER remove an allergy from a safety check
        // (Rx contraindication still warns on a superseded allergy; only
        // the doctor resolves the conflict). See 07c-rx-drafting.ts.
        superseded: z.boolean().optional(),
        conflict_note: z.string().nullable().optional(),
      })
    )
    .default([]),
  family_history: z
    .array(
      z.object({
        // Q2 fix-pack — both relation and condition meaningful.
        relation: z.string().min(1),
        condition: z.string().min(1),
        evidence_quote: z.string().min(1),
        speaker: z.string().optional(),
        timestamp: z.number().nonnegative().optional(),
      })
    )
    .default([]),
  social_history: z
    .object({
      // Q1 #19 follow-up: each subfield is a factWithEvidence object,
      // but the model occasionally shortcuts to a bare string. Wrap
      // each via liftStringToFact() so the SCHEMA_FAIL cases convert
      // to monotone-lossy objects instead of failing the whole call.
      smoking: liftStringToFact('status'),
      alcohol: liftStringToFact('status'),
      drugs: liftStringToFact('status'),
      occupation: liftStringToFact('value'),
    })
    .default({}),
  ros: z
    .array(
      z.object({
        // Q2 fix-pack — both system and finding meaningful.
        /**
         * ⚠️ #179(1) — A CLOSED PER-SYSTEM LEXICON, NOT FREE TEXT. The system
         * must be one the lexicon names; the SYMPTOM below is meaningless
         * without it.
         */
        system: z.string().min(1),
        /**
         * ⚠️ THE MODEL PICKS FROM A LIST AND THE SCHEMA ENFORCES IT. Free text
         * here was the root of two MEASURED defects, both of them the same
         * root — a concept that could not ADDRESS a clause:
         *
         *   · the projector slugged this into `ros.<system>`, and
         *     `field-value-derivation`'s checkbox arm reads ONLY
         *     `fact.polarity` — the finding is discarded — so one affirmed
         *     symptom ticked EVERY clause in that system;
         *   · `ros` is not in ACCUMULATING_NARRATIVE_CONCEPTS, so a SECOND
         *     affirmed symptom became `multiple_distinct_supported_values`
         *     and the whole export conflicted.
         *
         * No amount of text matching downstream fixes that safely; #157(d)
         * deleted that machinery rather than gate it. `other` is admitted so a
         * symptom outside the list is never silently dropped, and it is
         * excluded from every clause scope by construction.
         */
        finding: z.string().min(1),
        /**
         * WHETHER THE PATIENT HAS THIS OR NOT — as DATA (Q1 audit §02.9).
         *
         * Polarity used to live only inside the prose of `finding`, so every
         * consumer had to guess it back out with a regex. A regex over a
         * clinical sentence is wrong in both directions: it over-fires when one
         * quote carries two findings ("denies chest pain but does get short of
         * breath" marks the dyspnoea denied), and under-fires whenever the
         * patient speaks normally ("None at all" contains no charting token).
         *
         * REQUIRED, WITH NO DEFAULT, deliberately. Neither default is safe —
         * absent → affirmed invents symptoms and drives L5 red-flag false
         * positives; absent → denied hides real ones. A missing polarity is a
         * malformed extraction, and the model client already retries a schema
         * failure with the error fed back.
         */
        polarity: z.enum(['affirmed', 'denied']),
        /** The side, when a side was STATED. Absent means none was — which is
         *  a different claim from 'not_applicable', so the two are not merged. */
        laterality: z.enum(['left', 'right', 'bilateral']).optional(),
        evidence_quote: z.string().min(1),
        speaker: z.string().optional(),
        timestamp: z.number().nonnegative().optional(),
        /**
         * ⚠️ THE DOCTOR'S OWN WORDS, KEPT ONLY WHEN THE LEXICON COULD NOT HOLD
         * THEM. Set by the resolver below, never by the model. Without it a
         * coerced symptom reaches the note and the document as the literal
         * string `other`, and the doctor's "belching" is gone.
         */
        finding_verbatim: z.string().min(1).optional(),
        /** Likewise for a system name the lexicon does not recognise. */
        system_verbatim: z.string().min(1).optional(),
      })
    )
    /**
     * ⚠️ #179(1) RESOLVES TO THE CLOSED SET. IT USED TO REFUSE INTO IT, AND THE
     * REFUSAL DISCARDED THE WHOLE VISIT.
     *
     * The membership check was a `.superRefine` over the ARRAY, so one
     * off-lexicon token failed the parse of the entire `ExtractedEntities`
     * object — 13 other top-level clinical fields with it. MEASURED, against
     * the shipped schema:
     *
     *   lowercase "heartburn"        PARSE OK   cc kept, meds 1, allergies 1
     *   capitalised "Heartburn"      PARSE FAIL chief_complaint, medications
     *                                           AND ALLERGIES all discarded
     *   off-lexicon "burping"        PARSE FAIL  (same)
     *   1 good + 1 capitalised       PARSE FAIL  (same)
     *
     * ⚠️ AND THE CAPITALISED ROW IS NOT A CURIOSITY: this repository's own
     * comment records that L3 capitalises the finding habitually. Nothing on
     * the model's side was ever told the lexicon either (see the prompt below),
     * so attempt 1 of every call was blind to all 72 tokens.
     *
     * ⚠️ THE FILE'S OWN ALLERGIES FIELD CARRIES THE SENTENCE THIS VIOLATED:
     * "SAFETY INVARIANT: `superseded` is a doctor-review hint ONLY — it must
     * NEVER remove an allergy from a safety check." One capitalised ROS token
     * removed every allergy on the visit.
     *
     * SO THE VERB CHANGES FROM REFUSE-THE-OBJECT TO RESOLVE-THE-ITEM, at the
     * same seam and with the same authority. Normalise first (the projector's
     * OWN normaliser, imported — `Heartburn` was already becoming `heartburn`
     * one layer down), then coerce what remains to `other`, keeping the
     * doctor's words. ORDER IS LOAD-BEARING: coerce-first would demote a real
     * lexicon symptom that merely had a capital letter.
     *
     * ⚠️ IDEMPOTENT ON PURPOSE — the `??` preserves an existing verbatim. This
     * schema is parsed a SECOND time at `sample-preview-transcript.ts`, at
     * module load, and a transform that overwrote on re-parse would lose the
     * original words on the second pass.
     */
    .transform((items, ctx) =>
      items.map((item, index) => {
        const system = resolveRosSystem(item.system);
        const finding = resolveRosFinding(system, item.finding);
        // ⚠️ ENFORCEMENT SURVIVES THE CHANGE — it just judges the RESOLVER's
        // output instead of the model's, and it is INSIDE the transform
        // because that is where `ctx` exists. If a future edit to
        // `resolveRosSystem` or `resolveRosFinding` can emit something outside
        // the closed set, this reds rather than letting an unregistered
        // concept reach the projector. It cannot fire on model input: every
        // value here has already been through a resolver whose range IS the
        // closed set, which is exactly the property being asserted.
        if (!ROS_SYSTEMS_RESOLVED.includes(system)) {
          ctx.addIssue({
            code: 'custom',
            path: [index, 'system'],
            message: `resolver emitted unknown system "${system}"`,
          });
        } else if (!symptomsFor(system).includes(finding)) {
          ctx.addIssue({
            code: 'custom',
            path: [index, 'finding'],
            message: `resolver emitted off-lexicon finding "${finding}" for ${system}`,
          });
        }
        return {
          ...item,
          system,
          finding,
          finding_verbatim:
            finding === item.finding ? item.finding_verbatim : (item.finding_verbatim ?? item.finding),
          system_verbatim:
            system === item.system ? item.system_verbatim : (item.system_verbatim ?? item.system),
        };
      }),
    )
    .default([]),
  exam_findings: z
    .array(
      z.object({
        // Q2 fix-pack — both system and finding meaningful.
        system: z.string().min(1),
        finding: z.string().min(1),
        evidence_quote: z.string().min(1),
        speaker: z.string().optional(),
        timestamp: z.number().nonnegative().optional(),
      })
    )
    .default([]),
  tests_mentioned: z
    .array(
      z.object({
        // Q2 fix-pack — test name must be present.
        test: z.string().min(1),
        result_if_given: z.string().nullable().optional(),
        evidence_quote: z.string().min(1),
        speaker: z.string().optional(),
        timestamp: z.number().nonnegative().optional(),
      })
    )
    .default([]),
  assessment_discussed: z
    .array(factWithEvidence('finding'))
    .default([]),
  plan_discussed: z.array(factWithEvidence('item')).default([]),

  /**
   * STRUCTURED MEASUREMENTS (additive).
   *
   * Imaging studies state numbers per anatomical segment and side — "right GSV
   * at the SFJ, diameter 7 millimetres, reflux 2.4 seconds". Until now those
   * landed only as prose inside hpi/tests_mentioned, so nothing downstream
   * could treat them as VALUES: projectEncounterFacts had no numeric fact to
   * emit, and every consumer that needs a number with a side (the Template
   * Twin's measurement cells) was structurally unable to fill.
   *
   * The slot is deliberately narrow: what was measured, where, which side,
   * how much, in what unit, and the span it came from. Anatomy stays a
   * STRUCTURED attribute — never baked into a concept string.
   *
   * `.default([])` keeps every existing consumer byte-identical: a SOAP
   * encounter simply yields an empty array, and the SOAP fields above are
   * untouched.
   */
  measurements: z
    .array(
      z.object({
        /** Anatomical segment as spoken, e.g. "GSV at the SFJ". */
        segment: z.string().min(1).max(120),
        laterality: z.enum(['left', 'right', 'bilateral', 'not_applicable', 'unknown']),
        /** What was measured. Extend deliberately; never free-text. */
        metric: z.enum(['diameter', 'reflux_time', 'velocity', 'length', 'depth']),
        /** The number exactly as stated — normalization happens downstream so
         *  the extractor is never asked to do arithmetic. */
        value: z.number(),
        /** Unit exactly as stated ("mm", "cm", "seconds", "ms"). */
        unit: z.string().min(1).max(24),
        /** Verbatim span the value came from — the evidence anchor. */
        sourceSpan: z.string().min(1),
        speaker: z.string().optional(),
        timestamp: z.number().nonnegative().optional(),
      })
    )
    .default([]),

  /**
   * PROCEDURE CODES THE CLINICIAN SPOKE ALOUD (additive).
   *
   * "Bill this as 93970" is an instruction to a biller, not clinical prose.
   * L4 correctly leaves it out of the SOAP note — which is exactly why it used
   * to vanish: L7b coding only ever reads the finished note and these entities,
   * so by the time coding ran the sentence no longer existed anywhere. A prod
   * smoke caught it on a bilateral venous duplex: the code was dictated, and
   * PROCEDURES came back empty.
   *
   * This layer is the only one that sees the raw dictation, so the capture
   * belongs here. It is a TRANSCRIPTION slot, not a coding one — this layer
   * records what was said, and L7b's fail-closed allowlist still decides
   * whether it is billable.
   */
  spoken_procedure_codes: z
    .array(
      z.object({
        /** Exactly five digits, exactly as spoken. Never inferred from prose. */
        code: z.string().regex(/^[0-9]{5}$/),
        /** Only if the clinician also named it aloud. */
        description: z.string().min(1).max(200).optional(),
        /** Verbatim span. On a billing line this is the doctor's own words. */
        evidence_quote: z.string().min(1),
        speaker: z.string().optional(),
        timestamp: z.number().nonnegative().optional(),
      })
    )
    .default([]),
});
export type ExtractedEntities = z.infer<typeof ExtractedEntities>;

// ---------------------------------------------------------------------------
// Formatting helper for conversation mode — produces the role-labeled
// transcript that Layer 4 + 5 also consume.
// ---------------------------------------------------------------------------

function formatRoleLabeledLine(
  u: DeepgramUtterance,
  speakerMap: SpeakerMap
): string {
  const speakerKey = typeof u.speaker === 'number' ? String(u.speaker) : 'unknown';
  const role = speakerMap[speakerKey]?.role ?? 'unknown';
  const displayRole = role.charAt(0).toUpperCase() + role.slice(1);
  const ts = Math.max(0, Math.floor(u.start ?? 0));
  const mm = Math.floor(ts / 60);
  const ss = (ts % 60).toString().padStart(2, '0');
  // 2026-06-11 inaudible-span hardening: low-confidence content-word runs
  // become explicit "[unclear in recording]" markers so L4/L5 can hedge
  // spans they previously couldn't see (Deepgram garbles unintelligible
  // audio into plausible words — measured: "sphenitol" @0.61 shipped as a
  // drug name). No word-level data → raw text unchanged (dictation/legacy).
  return `[${displayRole} #${speakerKey}, ${mm}:${ss}]: ${markUnclearTranscript(u)}`;
}

export function buildRoleLabeledTranscript(
  utterances: DeepgramUtterance[],
  speakerMap: SpeakerMap
): string {
  return utterances
    .map((u) => formatRoleLabeledLine(u, speakerMap))
    .join('\n');
}

// ---------------------------------------------------------------------------
// Layer 3 input — discriminated union by mode.
// ---------------------------------------------------------------------------

export interface Layer3ConversationInput {
  visitId: string;
  practiceId: string;
  userId: string | null;
  mode: 'conversation';
  utterances: DeepgramUtterance[];
  speakerMap: SpeakerMap;
}
export interface Layer3DictationInput {
  visitId: string;
  practiceId: string;
  userId: string | null;
  mode: 'dictation';
  /** Full text from Layer 1' (single-speaker Deepgram). */
  dictationText: string;
}
export interface Layer3TextInput {
  visitId: string;
  practiceId: string;
  userId: string | null;
  mode: 'text';
  /** Raw bullet-point / prose the doctor typed in the TextComposer UI. */
  rawText: string;
}
export type Layer3Input =
  | Layer3ConversationInput
  | Layer3DictationInput
  | Layer3TextInput;

// Bundled output — Layer 4 wants a "context text" to include alongside the
// entities. Different shape per mode (role-labeled transcript, dictation
// block, raw bullets) but we return it as a single string here so Layer 4
// doesn't have to re-branch.
export interface Layer3Output {
  entities: ExtractedEntities;
  contextText: string;
}

// ---------------------------------------------------------------------------
// Prompt builders — one per mode. Extracted to small functions so the
// surface is testable + easy to eyeball.
// ---------------------------------------------------------------------------

export const COMMON_CATEGORIES = [
  'Categories:',
  '- chief_complaint: {statement, evidence_quote, speaker?, timestamp?} or null',
  '- hpi: {onset?, duration?, quality?, severity?, location?, timing?,',
  '  context?, modifying_factors?, associated_symptoms?, evidence_quote,',
  '  speaker?, timestamp?} or null — each sub-field is a string; all',
  '  sub-fields are optional; one evidence_quote covers the paragraph.',
  '- past_medical_history: list of {condition, evidence_quote, ...}',
  '- medications: list of {name, dose?, route?, frequency?, evidence_quote, ...}',
  '- allergies: list of {substance, reaction?, evidence_quote,',
  '  superseded?, conflict_note?, ...}',
  '',
  '  ALLERGY CONFLICT RESOLUTION (clinical safety — read carefully):',
  '  If the visit contains CONFLICTING allergy statements — e.g. "no known',
  '  allergies" early then "I\'m allergic to penicillin" later, or a stated',
  '  allergy that is later retracted/corrected — you MUST:',
  '    1. Keep a SEPARATE entry for EACH conflicting statement. NEVER drop,',
  '       merge, or silently pick one. Both go in the allergies list.',
  '    2. Set "superseded": true on the entry the conversation contradicts',
  '       or supersedes (the earlier "no allergies", or a retracted claim),',
  '       and leave "superseded" false/absent on the operative one.',
  '    3. Put a one-line "conflict_note" on the superseded entry naming the',
  '       conflict (e.g. "patient first denied allergies, then reported',
  '       penicillin"). No PHI beyond the allergy facts themselves.',
  '  "superseded" is a REVIEW HINT for the doctor — it does NOT mean the',
  '  allergy is safe to ignore. Downstream safety checks still treat a',
  '  superseded allergy as active until the doctor resolves it. When in',
  '  doubt, mark BOTH active (superseded absent) — fail toward caution.',
  '- family_history: list of {relation, condition, evidence_quote, ...}',
  //
  // T-M23.B: expanded social_history shape guidance. Prior wording
  // ("smoking/alcohol/drugs/occupation, each optional") let Claude
  // shortcut to bare strings like `"occupation": "factory operative"`
  // which fails the Zod schema with "expected object, received
  // string" — every ~1 in 50 long audio uploads triggered SCHEMA_FAIL
  // here because the content patterns that invite the shortcut (a
  // single clear occupation phrase) are common. Explicit shape +
  // side-by-side correct/wrong example makes the wrapper non-
  // negotiable.
  //
  '- social_history: an OBJECT with optional sub-fields. Each sub-field',
  '  must itself be an OBJECT (never a bare string):',
  '    smoking:    {status, evidence_quote, speaker?, timestamp?}',
  '    alcohol:    {status, evidence_quote, speaker?, timestamp?}',
  '    drugs:      {status, evidence_quote, speaker?, timestamp?}',
  '    occupation: {value,  evidence_quote, speaker?, timestamp?}',
  '  If you have no evidence quote for a sub-field, OMIT that sub-field',
  '  entirely — do not emit it as a bare string.',
  '  CORRECT:  "social_history": { "occupation": { "value": "factory',
  '            operative", "evidence_quote": "he works as a factory',
  '            operative at Simple Signs Ltd" } }',
  '  WRONG:    "social_history": { "occupation": "factory operative" }',
  '- ros: list of {system, finding, polarity, evidence_quote,',
  '  laterality?, ...} (review of systems).',
  // ⚠️ GENERATED FROM `ROS_LEXICON`, NEVER HAND-COPIED. The schema enforces
  // this vocabulary; before this block nothing ever SHOWED it to the model.
  // Measured on the assembled prompt: 1 of 72 symptom tokens and 0 of 13
  // system names appeared, and the single hit was a false positive (the word
  // "frequency" in the medications bullet). The model's only exposure to the
  // list was the Zod error replayed AFTER a rejection — so on attempt 1 of
  // every call it was guessing, and one wrong guess used to discard the whole
  // extraction. One definition, interpolated: a second hand-written copy is
  // how the prompt and the schema would drift apart again.
  '    * system MUST be one of these, and finding MUST come from that',
  '      system\'s list:',
  ...ROS_SYSTEMS.map(
    (system) => `        ${system}: ${symptomsFor(system).join(', ')}`,
  ),
  '    * These are snake_case identifiers, not prose. Use the identifier',
  '      exactly as written above — lower case, underscores.',
  '    * If the patient reports a symptom that is NOT in its system\'s',
  '      list, use finding "other" and put the words the doctor actually',
  '      used in finding_verbatim. Never invent a token, and never drop',
  '      the symptom.',
  '    * polarity: REQUIRED, "affirmed" (the patient HAS it) or "denied"',
  '      (the patient does NOT). Never omit it and never guess it from the',
  '      shape of the sentence.',
  '    * Record the polarity of THIS finding, not of the sentence it came',
  '      from — one sentence can carry BOTH. "She denies chest pain but',
  '      does get short of breath" is TWO entries:',
  '      {system: cardiovascular, finding: chest_pain, polarity: denied}',
  '      AND {system: respiratory, finding: dyspnea, polarity: affirmed}.',
  '      Do not let the denial swallow the rest of the sentence.',
  '    * Patients do not speak in charting language. "Any chest pain?" —',
  '      "None at all" is polarity "denied". So are "nope", "nothing like',
  '      that", "never had it". Absence of the word "no" is not absence of',
  '      a denial.',
  '    * Equally, do not read a denial into an affirmation: "it is not',
  '      severe, but it is there" is AFFIRMED.',
  '    * laterality: include it whenever a side was stated, and use the',
  '      side of THIS finding — never widen one side to bilateral because',
  '      the other was mentioned. "Numbness in the right hand, left hand is',
  '      fine" is {system: neurologic, finding: numbness, polarity:',
  '      affirmed, laterality: right}. Omit laterality when no side was',
  '      stated; do not guess one.',
  '- exam_findings: list of {system, finding, evidence_quote, ...} — only',
  '  what the doctor stated/observed',
  '- tests_mentioned: list of {test, result_if_given?, evidence_quote, ...}',
  '- measurements: list of {segment, laterality, metric, value, unit,',
  '  sourceSpan}. Populate ONLY for numeric measurements tied to an',
  '  anatomical segment — imaging/duplex studies. One entry PER NUMBER: a',
  '  segment stated with both a diameter and a reflux time yields TWO entries.',
  '    * segment: the anatomical location as spoken ("GSV at the SFJ",',
  '      "small saphenous vein at the saphenopopliteal junction").',
  '    * laterality: left | right | bilateral — carry forward the side from',
  '      the governing sentence or heading ("Right leg." applies to the',
  '      segments that follow). Use "unknown" ONLY when no side is inferable;',
  '      never guess a side.',
  '    * metric: diameter | reflux_time | velocity | length | depth.',
  '    * value: the number EXACTLY as stated. Never convert, round, or',
  '      normalize — 0.62 stays 0.62, 1800 stays 1800.',
  '    * unit: the unit EXACTLY as stated ("mm", "cm", "seconds",',
  '      "milliseconds"). Unit conversion happens downstream.',
  '    * sourceSpan: the verbatim clause the number came from.',
  '  A visit with no measured numbers yields an EMPTY list. Never invent a',
  '  measurement, and never carry a number into a segment it was not stated',
  '  for — an unstated segment is simply absent.',
  '- assessment_discussed: list of {finding, evidence_quote, ...}',
  '- plan_discussed: list of {item, evidence_quote, ...}',
  '- spoken_procedure_codes: list of {code, description?, evidence_quote,',
  '  ...}. ONLY for a CPT/procedure code the clinician SPOKE ALOUD as a',
  '  billing instruction — "bill this as 93970", "code it 76856", "that is',
  '  a 99213". Five digits, transcribed EXACTLY as said.',
  '    * NEVER infer a code from a described procedure. If the clinician',
  '      says "bilateral venous duplex" without saying a number, this list',
  '      gets NOTHING. Suggesting the code is a different job, done later',
  '      by a layer built for it.',
  '    * NEVER correct a code you think is wrong. Transcribe what was said;',
  '      a downstream allowlist decides what is billable.',
  '    * description: only if they also named it aloud. Omit otherwise —',
  '      do not supply one from your own knowledge.',
  '  A visit with no spoken code yields an EMPTY list, which is the normal',
  '  case for almost every visit.',
].join('\n');

function buildConversationPrompt(): { system: string; userPrefix: string } {
  const system = [
    'You are a medical entity extraction system. You extract structured',
    'entities from clinical conversations for downstream SOAP-note',
    'generation.',
    '',
    'CRITICAL RULES (violating these is a pipeline failure):',
    '1. Every entity MUST include an "evidence_quote" that is verbatim',
    '   from the transcript. Do not paraphrase. Do not summarise.',
    '2. Every entity MUST include "speaker" (e.g. "Doctor #0") and the',
    '   "timestamp" in seconds from audio start.',
    '3. If you CANNOT cite evidence for an entity, OMIT IT. Never',
    '   invent. Hallucinating is a critical failure.',
    '4. If the transcript is silent on a category, return [] (or null',
    '   for singleton categories) — do not stretch to populate.',
    '5. "[unclear in recording]" marks unintelligible audio. NEVER extract',
    '   it as an entity value and NEVER guess the underlying word — if the',
    '   only evidence for an entity overlaps such a marker, OMIT it.',
    '',
    COMMON_CATEGORIES,
    '',
    'Respond with VALID JSON ONLY, no markdown fences.',
  ].join('\n');
  return { system, userPrefix: 'Role-labeled transcript:' };
}

function buildDictationPrompt(): { system: string; userPrefix: string } {
  const system = [
    'You are a medical entity extraction system. The input below is a',
    'doctor\'s own dictated summary of a visit, transcribed as a single',
    'block of text (no speakers, no patient-doctor turn-taking). Extract',
    'structured entities for downstream SOAP-note generation.',
    '',
    'CRITICAL RULES (violating these is a pipeline failure):',
    '1. Every entity MUST include an "evidence_quote" — a verbatim',
    '   snippet from the dictation. Speaker is always "Doctor". Timestamp',
    '   is optional (there\'s no meaningful time cue in a single block).',
    '2. If you CANNOT cite evidence for an entity, OMIT IT. Never invent.',
    '   Expanding shorthand is allowed (e.g. "f/u 3mo" → "Follow-up in 3',
    '   months", "bp 148/92" → systolic 148, diastolic 92). Inventing',
    '   findings that weren\'t mentioned is hallucination.',
    '3. Treat the doctor as the only narrator. Everything in the',
    '   dictation is either (a) something the doctor observed, (b)',
    '   something the patient told the doctor, or (c) the doctor\'s',
    '   plan. Use context to decide which category each point belongs',
    '   to — if ambiguous, prefer exam_findings or plan_discussed over',
    '   hpi.',
    '4. If the dictation is silent on a category, return [] (or null).',
    '',
    COMMON_CATEGORIES,
    '',
    'Respond with VALID JSON ONLY, no markdown fences.',
  ].join('\n');
  return { system, userPrefix: 'Doctor\'s dictated visit summary:' };
}

function buildTextPrompt(): { system: string; userPrefix: string } {
  const system = [
    'You are a medical entity extraction system. The input below is a',
    'doctor\'s TYPED shorthand — bullets, abbreviations, or prose — that',
    'they want expanded into a full SOAP note downstream. Extract',
    'structured entities.',
    '',
    'CRITICAL RULES (violating these is a pipeline failure):',
    '1. Every entity MUST include an "evidence_quote" — the relevant',
    '   line/phrase from the typed input, verbatim. Speaker and',
    '   timestamp are both optional and should usually be omitted (this',
    '   isn\'t a recording).',
    '2. Expand common medical shorthand sensibly:',
    '   - "yo" → "year-old", "f/u" → "follow-up", "RTC" → "return to',
    '     clinic", "ROS -" → "review of systems negative",',
    '   - "bp 148/92" → systolic 148, diastolic 92,',
    '   - "A1c 6.8" → HbA1c 6.8,',
    '   - "incr X to Y" → "increase X to Y".',
    '3. If you CANNOT cite an evidence line for an entity, OMIT IT.',
    '   Inventing findings the doctor didn\'t type is hallucination and',
    '   a critical failure.',
    '4. Short or sparse inputs are valid; empty categories stay empty.',
    '',
    COMMON_CATEGORIES,
    '',
    'Respond with VALID JSON ONLY, no markdown fences.',
  ].join('\n');
  return { system, userPrefix: 'Doctor\'s typed shorthand:' };
}

// ---------------------------------------------------------------------------
// The layer itself.
// ---------------------------------------------------------------------------

/**
 * Visit-free extraction core (ADDITIVE, 2026-07-22). The injection-delimiter
 * guard + the single tm_entities model call, parameterised by audit target so it
 * serves BOTH a visit (transcribe_visit) and a Template Twin note template
 * (NoteTemplate). Contains NO visit-specific persistence — the caller owns any
 * transcribeVisit write — so the existing visit path stays behavior-identical
 * (see runLayer3ExtractEntities) while the twin certify-time synthetic test can
 * extract without a visit.
 */
export interface Layer3ExtractionCore {
  mode: Layer3Input['mode'];
  contextText: string;
  prompts: { system: string; userPrefix: string };
  practiceId: string;
  userId: string | null;
  /** Telemetry visit id, or null for a template (no visit). */
  visitId: string | null;
  auditTargetType: string;
  auditTargetId: string;
}

async function completeLayer3Entities(
  input: Layer3ExtractionCore
): Promise<ExtractedEntities> {
  // Round 3 PR-J — A07-P0 prompt-injection delimiter. L3 is the
  // first layer that touches user-supplied content (transcript /
  // dictation / typed text), so wrapping here makes the boundary
  // visible to L4/L5 readers via contextText reuse.
  const wrap = wrapAsData(input.contextText, 'transcript');
  if (wrap.injectionAttemptDetected) {
    void logAudit({
      action: 'PIPELINE_REJECTED_INJECTION_DELIMITER',
      targetType: input.auditTargetType,
      targetId: input.auditTargetId,
      userId: input.userId,
      practiceId: input.practiceId,
      success: false,
      errorCode: 'INJECTION_DELIMITER_DETECTED',
      metadata: { layer: 'L3', mode: input.mode, suffix: wrap.suffix },
    });
  }
  const user = [
    input.prompts.userPrefix,
    '',
    wrap.wrapped,
    '',
    delimiterSystemSuffix('transcript'),
  ].join('\n');

  return modelClient.complete({
    practiceId: input.practiceId,
    visitId: input.visitId,
    userId: input.userId,
    purpose: 'tm_entities',
    provider: 'anthropic',
    model: MODEL,
    system: input.prompts.system,
    user,
    schema: ExtractedEntities,
    maxTokens: 6144,
    // Q2 fix-pack — entity extraction is structured-output; tightened
    // from 0.2 to 0.1 for reproducible parses (audit §08).
    temperature: 0.1,
  });
}

/** Template Twin visit-free entity extraction (text / dictation). Wired into the
 * twin TwinEntityExtractor seam for certify-time synthetic tests. No transcribe-
 * Visit write; audited against the NoteTemplate. */
export interface Layer3TemplateExtractionInput {
  mode: 'text' | 'dictation';
  text: string;
  practiceId: string;
  userId: string | null;
  noteTemplateId: string;
}

export async function extractTemplateTwinEntities(
  input: Layer3TemplateExtractionInput
): Promise<Layer3Output> {
  const contextText = input.text.trim();
  const prompts = input.mode === 'dictation' ? buildDictationPrompt() : buildTextPrompt();
  const entities = await completeLayer3Entities({
    mode: input.mode,
    contextText,
    prompts,
    practiceId: input.practiceId,
    userId: input.userId,
    visitId: null,
    auditTargetType: 'NoteTemplate',
    auditTargetId: input.noteTemplateId,
  });
  return { entities, contextText };
}

export async function runLayer3ExtractEntities(
  input: Layer3Input
): Promise<Layer3Output> {
  let contextText: string;
  let prompts: { system: string; userPrefix: string };
  if (input.mode === 'conversation') {
    contextText = buildRoleLabeledTranscript(
      input.utterances,
      input.speakerMap
    );
    prompts = buildConversationPrompt();
  } else if (input.mode === 'dictation') {
    contextText = input.dictationText.trim();
    prompts = buildDictationPrompt();
  } else {
    contextText = input.rawText.trim();
    prompts = buildTextPrompt();
  }

  // Delegate the injection guard + model call to the shared visit-free core;
  // the visit-specific persistence stays here so this path is behavior-identical.
  const entities = await completeLayer3Entities({
    mode: input.mode,
    contextText,
    prompts,
    practiceId: input.practiceId,
    userId: input.userId,
    visitId: input.visitId,
    auditTargetType: 'transcribe_visit',
    auditTargetId: input.visitId,
  });

  await prisma.transcribeVisit.update({
    where: { id: input.visitId },
    data: { entities: entities as unknown as object },
  });

  return { entities, contextText };
}
