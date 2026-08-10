// ============================================================================
// B4 — THE ENUMERATED STAGE LIST. One place, and it is the gate's universe.
// ----------------------------------------------------------------------------
// B4's gate reads, verbatim: *"one full QA pipeline run produces one event per
// stage, COUNTED AGAINST THE ENUMERATED STAGE LIST, not eyeballed."* This file
// is that list. Two consumers, deliberately:
//
//   1. `__tests__/gate-b4-stage-enumeration.test.ts` — runs in CI, with no
//      stack and no database. It reconciles this list against the SOURCE:
//      every `purpose:` literal in the pipeline declares a stage that is
//      enumerated here, and every stage enumerated here names a file that
//      actually declares it. That is what stops the list going stale.
//   2. `scripts/qa/b4-stage-coverage.ts` — runs against the QA stack, drives
//      real visits through the real worker under `MOCK_AI_CALLS`, and counts
//      `api_usage_events` against this same table.
//
// ⚠️ WHY THE LIST IS HAND-KEPT AND THE CENSUS IS NOT OPTIONAL.
// AGENTS.md: *"a per-caller list is kept complete by hand, and hand-kept lists
// are wrong eventually."* The cure it prescribes — put the behaviour on the
// component — is not available here, because a stage's INPUT-MODE and its
// EXPECTED COUNT are facts about the pipeline's control flow that no call site
// carries. So the list stays hand-kept and the census makes a stale entry FAIL
// A TEST rather than render quietly.
// ============================================================================

import type { ModelCallPurpose } from '@meddoc/ai';

/** The three ways a visit can enter the pipeline. `worker.ts:7-10`. */
export type PipelineInputMode = 'text_notes' | 'voice_dictation' | 'audio_upload';

export const PIPELINE_INPUT_MODES: readonly PipelineInputMode[] = [
  'text_notes',
  'voice_dictation',
  'audio_upload',
] as const;

/**
 * What a stage is expected to produce, per visit, on a mode it runs on.
 *
 * ⚠️ THESE ARE NOT DECORATION AND THEY ARE NOT GUESSES. Each one is either
 * derived from the code path or measured against production and recorded in
 * `docs/foundation/RELAY.md`. The recon warned in as many words that *"a gate
 * that hardcodes `3 × visits` will be wrong, and wrong in the direction that
 * reads as a metering hole"* — so the shapes below are the ones that survive
 * the real control flow.
 */
export type StageExpectation =
  /** exactly one event per visit on every mode the stage runs on */
  | { kind: 'exactlyOne' }
  /** one or more — a stage with more than one production caller per visit */
  | { kind: 'atLeastOne'; why: string }
  /** a per-visit count drawn from a fixed set (e.g. an all-or-nothing ensemble) */
  | { kind: 'oneOf'; values: readonly number[]; why: string }
  /** fires outside the worker run — counted separately, never per-visit */
  | { kind: 'outOfBand'; why: string };

export interface PipelineStage {
  /** the `operation` column on `api_usage_events`; the `purpose` on `AiLogContext` */
  operation: ModelCallPurpose;
  /** repo-relative files that declare this purpose. MORE THAN ONE IS NORMAL. */
  sources: readonly string[];
  /** the input modes this stage runs on — NOT every stage runs on every mode */
  modes: readonly PipelineInputMode[];
  expected: StageExpectation;
  /** why the modes and the expectation are what they are */
  why: string;
}

/**
 * ⚠️ `transcribe_realtime` IS DELIBERATELY ABSENT FROM THIS TABLE AND PRESENT
 * IN THE JOIN. Ruling 81 obliges the per-stage rollup to accept the legacy
 * label alongside `tm_transcribe` (3 legacy rows in production). It is not a
 * stage anything can still emit, so a coverage gate must not DEMAND it — but a
 * count that silently dropped it would under-report history.
 */
export const LEGACY_OPERATION_ALIASES: Readonly<
  Partial<Record<ModelCallPurpose, ModelCallPurpose>>
> = {
  transcribe_realtime: 'tm_transcribe',
};

export const PIPELINE_STAGES: readonly PipelineStage[] = [
  {
    operation: 'tm_transcribe',
    sources: [
      'src/worker/layers/01-transcribe.ts',
      'src/worker/layers/01b-transcribe-dictation.ts',
    ],
    // TWO FILES, ONE LABEL — and they are mutually exclusive per visit.
    // `worker.ts:335-347` branches on inputMode: L1 for audio_upload, L1b for
    // voice_dictation, and text_notes has nothing to transcribe at all.
    modes: ['voice_dictation', 'audio_upload'],
    expected: { kind: 'exactlyOne' },
    why: 'L1 (audio_upload) and L1b (voice_dictation) are the same label on two branches; text_notes skips TRANSCRIBING entirely (worker.ts:350).',
  },
  {
    operation: 'tm_speaker_roles',
    sources: ['src/worker/layers/02-speaker-roles.ts'],
    modes: ['audio_upload'],
    expected: { kind: 'exactlyOne' },
    why: 'L2 assigns doctor/patient turns to a DIARIZED transcript. Only the audio_upload branch produces one (worker.ts:413).',
  },
  {
    operation: 'tm_entities',
    sources: ['src/worker/layers/03-extract-entities.ts'],
    modes: ['text_notes', 'voice_dictation', 'audio_upload'],
    expected: { kind: 'exactlyOne' },
    why: 'L3 is the earliest layer every mode reaches (worker.ts:607).',
  },
  {
    operation: 'tm_soap_draft',
    sources: ['src/worker/layers/04-generate-soap.ts'],
    modes: ['text_notes', 'voice_dictation', 'audio_upload'],
    expected: { kind: 'exactlyOne' },
    why: 'L4 runs on every mode.',
  },
  {
    operation: 'tm_anchor_entailment',
    sources: ['src/worker/layers/04b-anchor-verify.ts'],
    modes: ['text_notes', 'voice_dictation', 'audio_upload'],
    // ⚠️ MEASURED, NOT ASSUMED — and the naive reading is wrong.
    // `04b-anchor-verify.ts:1023-1028` fans out over 3 ENSEMBLE_LENSES per
    // INVOCATION. Production's per-visit distribution is 3 for every visit
    // that carries the stage at all, and nothing else: `{3: 73}`. Visits with
    // no anchored claims return before the ensemble (`claims.length === 0`)
    // and produce ZERO — which is correct, and is the whole gap between
    // `3 × visits` and the observed total. NO WORK IS NOT A SUPPRESSED CALL.
    expected: {
      kind: 'oneOf',
      values: [0, 3],
      why: 'the L4b ensemble is all-or-nothing: 3 lenses per invocation, one invocation per visit, and 0 when there is no anchored claim to verify.',
    },
    // ⚠️ AND IT IS THE ONE STAGE A MOCKED QA RUN STILL CANNOT COUNT — 2026-08-10.
    // Two conditions have to hold and only one of them is fixable by a flag:
    //
    //   1. `TRANSCRIBE_MD_EVIDENCE_ANCHORS=true`, so L4b runs at all. It was
    //      MISSING from the QA stack while production has it — fixed in
    //      `docker-compose.qa.yml`, and it is why QA held zero rows against
    //      production's 231.
    //   2. L4's draft must actually CARRY anchors (`⟦A:…⟧`, ANCHOR_BLOCK_RE).
    //      Under mock, L4 returns a fixture, and `mock.ts` contains ZERO anchor
    //      markers — so `deterministicStage` partitions every line into the
    //      exempt bucket, `toEntail` is empty, and `entailmentStage` returns at
    //      `04b-anchor-verify.ts:999` before any call.
    //
    // (2) makes the stage correctly silent, not broken — and the coverage run
    // reports it UNPROVEN rather than green, because a permitted zero observed
    // everywhere proves nothing. THE CLOSURE IS AN ANCHORED `tm_soap_draft`
    // VARIANT, selected by its own env flag exactly as MOCK_CRITIQUE_ISSUES
    // selects the populated critique.
    why: 'L4b is nested inside L4 and runs on every mode; a per-visit count of 1, 2, 4 or 6 would be the finding.',
  },
  {
    operation: 'tm_critique',
    sources: ['src/worker/layers/05-self-critique.ts'],
    modes: ['text_notes', 'voice_dictation', 'audio_upload'],
    expected: { kind: 'exactlyOne' },
    why: 'L5 runs on every mode.',
  },
  {
    operation: 'tm_polish',
    sources: ['src/worker/layers/06-polish.ts'],
    modes: ['text_notes', 'voice_dictation', 'audio_upload'],
    // ⚠️ NOT `exactlyOne`, AND THE FIRST VERSION OF THIS TABLE SAID IT WAS.
    // `06-polish.ts:186` — `if (fixable.length === 0)` — takes a PASSTHROUGH
    // branch: the L5 critique found nothing auto-patchable, so the draft *is*
    // the final note and no model call is made. No call, no meter, and that is
    // correct. The same shape as `tm_anchor_entailment`: NO WORK IS NOT A
    // SUPPRESSED CALL.
    //
    // Measured on production's DURABLE table (`api_usage_events`, which has no
    // deleter — a count from `ai_calls` has a shelf life): of 82 visits that
    // carry a `tm_soap_draft`, exactly 28 carry a `tm_polish`, each of them
    // once. Fifty-four took the passthrough.
    expected: {
      kind: 'oneOf',
      values: [0, 1],
      why: 'L6 makes no model call when the critique yielded no fixable issue (06-polish.ts:186). Production: 28 of 82 visits polished, one call each.',
    },
    why: 'L6 runs on every mode, but only CALLS on every mode where there is something to fix.',
  },
  {
    operation: 'tm_polish_gate',
    sources: ['src/worker/layers/06b-polish-fidelity-gate.ts'],
    modes: ['text_notes', 'voice_dictation', 'audio_upload'],
    // ⚠️ AND IT IS COUPLED TO `tm_polish`, NOT MERELY EQUAL-SHAPED. L6b sits
    // INSIDE L6's else-branch, so it can only fire on a visit that polished.
    // Measured: the two visit sets are IDENTICAL — 28 and 28 with a full outer
    // join yielding zero asymmetric rows. That coupling is asserted by the QA
    // coverage run, because it is the kind of invariant a per-stage count
    // cannot see: two stages could each satisfy `{0,1}` on different visits and
    // the totals would still reconcile.
    expected: {
      kind: 'oneOf',
      values: [0, 1],
      why: 'L6b is nested in L6’s model-call branch — it fires iff L6 called, which production confirms as an identical visit set.',
    },
    why: 'L6b is nested inside L6 — invisible to a worker.ts call-site scan (DISCOVERY §C.1), which is exactly why it is enumerated by hand here.',
  },
  {
    operation: 'tm_icd_coding',
    sources: ['src/worker/layers/07a-icd-coding.ts'],
    modes: ['text_notes', 'voice_dictation', 'audio_upload'],
    expected: { kind: 'exactlyOne' },
    why: 'L7 fan-out, one call per visit.',
  },
  {
    operation: 'tm_cpt_coding',
    sources: ['src/worker/layers/07b-cpt-coding.ts'],
    modes: ['text_notes', 'voice_dictation', 'audio_upload'],
    expected: { kind: 'exactlyOne' },
    why: 'L7 fan-out, one call per visit.',
  },
  {
    operation: 'tm_rx_drafting',
    sources: ['src/worker/layers/07c-rx-drafting.ts'],
    modes: ['text_notes', 'voice_dictation', 'audio_upload'],
    expected: { kind: 'exactlyOne' },
    why: 'L7 fan-out, one call per visit.',
  },
  {
    operation: 'tm_referrals',
    sources: ['src/worker/layers/07d-referrals.ts'],
    modes: ['text_notes', 'voice_dictation', 'audio_upload'],
    expected: { kind: 'exactlyOne' },
    why: 'L7 fan-out, one call per visit.',
  },
  {
    operation: 'tm_patient_summary',
    sources: ['src/worker/layers/07e-patient-summary.ts'],
    modes: ['text_notes', 'voice_dictation', 'audio_upload'],
    expected: { kind: 'exactlyOne' },
    why: 'L7 fan-out, one call per visit.',
  },
  {
    operation: 'judge',
    sources: ['src/lib/em-coding/llm-mdm.ts'],
    modes: ['text_notes', 'voice_dictation', 'audio_upload'],
    // ⚠️ A GATE ASSERTING ONE `judge` PER VISIT WILL BE WRONG, and the tail is
    // long enough that a small sample will not reveal it. Production, measured
    // 2026-08-10: 58 visits with 1, 12 with 2, 2 with 3, one with 6, ONE WITH
    // 13. E/M can be re-scored and `callClaudeMdm` retries once on a parse
    // failure. Under mock there are two callers per visit before any re-score:
    // the `worker.ts:944` pre-warm and the `score.ts:142` render — and the
    // pre-warm's cache is never populated under mock (`writeCache` is reached
    // only when the LLM returns a judgement, and the mock returns null), so
    // the render is always a miss and always meters too.
    expected: {
      kind: 'atLeastOne',
      why: 'two production callers per visit (worker pre-warm + score render), plus re-scores and a parse-failure retry.',
    },
    why: 'the judge bypasses `modelClient` entirely and speaks to the Anthropic SDK directly — it has its own meter (B4 step 3, ruling 83).',
  },
  {
    operation: 'tm_embed',
    sources: ['src/lib/edit-tracking.ts'],
    modes: ['text_notes', 'voice_dictation', 'audio_upload'],
    // ⚠️ NOT A WORKER LAYER. `captureEditPattern` fires from the SIGN route
    // (`api/visits/[id]/sign/route.ts:603`), after the pipeline is done, and
    // only for a visit that has both `soapL6Original` and `signedSoap`. A
    // coverage gate that expected it from a pipeline run would be measuring
    // the wrong event.
    //
    // ⚠️ AND ITS PRODUCTION ZERO IS CORRECT, NOT A METERING BUG. The prod
    // OpenAI credential has been dead since 2026-07-02: 38 `ai_calls`, all
    // `success=false`, and no `api_usage_events` row ever. B2 ruled a branch
    // meters iff it holds vendor-reported units, so no row is the right
    // answer — the defect is the credential, and it is PARKED as an owner
    // action. This gate therefore proves the QA/mock path meters and claims
    // NOTHING about production's zero.
    //
    // ⚠️ THE ZERO WAS ALSO GOING TO SURVIVE ITS OWN CURE, AND THE COVERAGE RUN
    // IS WHAT FOUND THAT. `buildOpenAIEmbedUsage` hardcoded
    // `operation: 'embed'` while the caller's purpose was `tm_embed`, so even
    // after the credential is fixed, a query for `operation='tm_embed'` would
    // have kept returning zero forever. Fixed in the same change; production
    // holds zero rows under EITHER label, so nothing historical moves.
    expected: {
      kind: 'outOfBand',
      why: 'sign-time, not pipeline-time — counted per captured visit, never per pipeline run.',
    },
    why: 'the per-doctor edit-pattern embedding, fired fire-and-forget from the sign route.',
  },
] as const;

/**
 * ⚠️ CROSS-STAGE INVARIANTS — the thing a per-stage count CANNOT see.
 *
 * Every stage in the table above is checked in isolation, and two stages can
 * each satisfy `{0,1}` on DIFFERENT visits while every per-stage total
 * reconciles perfectly. That is a real metering defect with a green gate, so
 * the coupling is asserted separately.
 *
 * `follower` fires if and only if `leader` did, ON THE SAME VISIT. Measured on
 * production, not assumed: `tm_polish` and `tm_polish_gate` are the same 28
 * visits, with a full outer join returning zero asymmetric rows.
 */
export const COUPLED_STAGES: ReadonlyArray<{
  leader: ModelCallPurpose;
  follower: ModelCallPurpose;
  why: string;
}> = [
  {
    leader: 'tm_polish',
    follower: 'tm_polish_gate',
    why: 'L6b is nested inside L6’s model-call branch (06-polish.ts:319) — it cannot fire on a visit that took the passthrough.',
  },
];

/** Stages that a worker run on `mode` is expected to produce at least one of. */
export function stagesForMode(mode: PipelineInputMode): readonly PipelineStage[] {
  return PIPELINE_STAGES.filter(
    (s) => s.expected.kind !== 'outOfBand' && s.modes.includes(mode)
  );
}

/** Every operation this list knows about, aliases folded in. */
export function isEnumeratedOperation(op: string): boolean {
  if (PIPELINE_STAGES.some((s) => s.operation === op)) return true;
  return Object.prototype.hasOwnProperty.call(LEGACY_OPERATION_ALIASES, op);
}

/** Fold a legacy label onto the stage it belongs to. Ruling 81. */
export function canonicalOperation(op: string): string {
  const alias = (LEGACY_OPERATION_ALIASES as Record<string, string | undefined>)[op];
  return alias ?? op;
}

/**
 * Does an observed per-visit count satisfy the stage's expectation?
 * Returns `null` when it does, or the reason it does not.
 */
export function violation(stage: PipelineStage, count: number): string | null {
  switch (stage.expected.kind) {
    case 'exactlyOne':
      return count === 1 ? null : `expected exactly 1, saw ${count}`;
    case 'atLeastOne':
      return count >= 1 ? null : `expected at least 1, saw ${count}`;
    case 'oneOf':
      return stage.expected.values.includes(count)
        ? null
        : `expected one of {${stage.expected.values.join(',')}}, saw ${count}`;
    case 'outOfBand':
      return null;
  }
}
