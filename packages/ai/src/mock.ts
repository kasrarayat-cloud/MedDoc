// ============================================================================
// @meddoc/ai — MOCK_AI_CALLS test-only shortcut (T-M10)
// ----------------------------------------------------------------------------
// Contract
//   • When process.env.MOCK_AI_CALLS === 'true', modelClient.complete(),
//     modelClient.completeText(), and deepgramBatchTranscribe() all
//     short-circuit: they skip the HTTP call to the provider, skip the
//     logAiCall() write, and return a deterministic fixture instead.
//   • Every other process.env value — including absent, empty, 'false',
//     or '0' — is a no-op. Production behavior is unchanged.
//   • Flipping the switch is a pure env change — no code path exists
//     that writes a fake AiCall row, generates fake telemetry, or
//     otherwise alters persisted state. The only visible difference
//     from the outside is that generated content is canned.
//
// Who uses it
//   Playwright E2E tests (apps/transcribe-md/tests/e2e/*) set
//   MOCK_AI_CALLS=true on the transcribe-md-worker container so the
//   6+7 pipeline layers complete instantly with stable data. Run a
//   production visit with the flag on and you'll get the same canned
//   output — that's the point.
//
// Adding a fixture
//   When a new ModelCallPurpose lands, add a row below. Without a
//   fixture the mock functions throw a clear error on purpose —
//   silent fallback to "something" would let future tests drift.
// ============================================================================

import Anthropic from '@anthropic-ai/sdk';
import type { ZodType } from 'zod';
import type { AnthropicCompleteTextResult } from './anthropic';
import type {
  DeepgramBatchResponse,
  DeepgramBatchResult,
} from './deepgram-batch';
import type { EmbedTextResult } from './embed';
import type { ModelCallPurpose } from './types';

/** Single source of truth for "are we in mock mode". Read each call —
 *  no cache — so a test can flip the env without a module reload. */
export function isMockEnabled(): boolean {
  return process.env.MOCK_AI_CALLS === 'true';
}

// ---------------------------------------------------------------------------
// Fixtures for modelClient.complete() — Zod-validated JSON paths.
// Shapes below intentionally rely on each layer's own `.default()`
// clauses (e.g. IcdResult.codes defaults to []). The schema.parse()
// call inside mockComplete() backfills missing optional fields, so
// these fixtures stay minimal.
// ---------------------------------------------------------------------------
const MOCK_COMPLETE_FIXTURES: Partial<Record<ModelCallPurpose, unknown>> = {
  tm_speaker_roles: {
    '0': { role: 'doctor', confidence: 0.95, reasoning: '[MOCK] e2e fixture' },
    '1': { role: 'patient', confidence: 0.92, reasoning: '[MOCK] e2e fixture' },
  },
  tm_entities: {
    chief_complaint: null,
    hpi: null,
  },
  tm_critique: {
    issues: [],
    overall_quality: 'high',
    safe_to_sign_without_review: true,
  },
  tm_icd_coding: { codes: [] },
  tm_cpt_coding: { em: null },
  // EMPTY by default → no prescriptions/warnings, so the existing specs that
  // sign visits aren't blocked by a critical Rx warning. The populated variant
  // (MOCK_RX_DRAFTING_WITH_WARNINGS) is returned instead when MOCK_RX_WARNINGS=true,
  // so the Rx warnings rail + critical-override sign-gate are testable under MOCK.
  tm_rx_drafting: {},
  tm_referrals: {},
  // Layer 7e calls modelClient.complete<PatientSummaryResult>({ schema }),
  // not completeText — so its fixture lives here, not in the text map.
  // Pre-T-M13 this was misfiled and the layer silently failed on every
  // MOCK run (rescued by Promise.allSettled; surfaced as a latent
  // [MOCK_AI_CALLS] log line).
  tm_patient_summary: {
    summary: '[MOCK] Your visit went well. Drink fluids, rest, and come back if symptoms worsen.',
  },
  // Note-format customization (Phase 2a). parseNoteToTemplate() makes two
  // complete() calls — without fixtures here the mock throws, so the whole
  // upload→parse→review→activate flow can't run under MOCK_AI_CALLS (full-qa
  // F7). `tm_template_parse` extracts a note FORMAT (ParsedTemplateLlmSchema);
  // a small, realistic 4-section template with no patient specifics — the lone
  // defaultText is generic normal-exam boilerplate, so the PHI gate stays clean.
  tm_template_parse: {
    name: '[MOCK] General Follow-up',
    // null = "All my visits". Avoids coupling the fixture to the specialty
    // taxonomy; the parse schema allows encounterType to be null.
    encounterType: null,
    sections: [
      {
        key: 'subjective',
        label: 'Subjective',
        order: 0,
        formatHint: 'prose',
        styleInstructions: '[MOCK] Brief HPI in the patient’s words; one short paragraph.',
        defaultText: null,
      },
      {
        key: 'objective',
        label: 'Objective',
        order: 1,
        formatHint: 'bullets',
        styleInstructions: '[MOCK] Vitals first, then a focused exam by system.',
        defaultText: '[MOCK] General: well-appearing, no acute distress. Normal exam.',
      },
      {
        key: 'assessment',
        label: 'Assessment',
        order: 2,
        formatHint: 'numbered',
        styleInstructions: '[MOCK] One numbered line per active problem.',
        defaultText: null,
      },
      {
        key: 'plan',
        label: 'Plan',
        order: 3,
        formatHint: 'bullets',
        styleInstructions: '[MOCK] Action items per problem; meds and follow-up interval.',
        defaultText: null,
      },
    ],
    styleProfile: {
      tense: 'past',
      tone: 'concise clinical',
      abbreviations: 'standard medical',
    },
    flags: [],
  },
  // PHI scan over the parsed fields (PhiScanSchema). CLEAN by default so the
  // happy-path parse succeeds under MOCK. The FLAGGED variant
  // (MOCK_TEMPLATE_PHI_SCAN_FLAGGED) is returned instead when
  // MOCK_TEMPLATE_PHI_FLAG=true, so the PHI-gate REJECT path is testable too.
  tm_template_phi_scan: { phiFields: [], anyUncertain: false },
  // Synthetic-evidence gate at CERTIFY time — a DIFFERENT schema from the
  // parsed-field scan above (SyntheticEvidencePrivacyScanSchema, and it is
  // .strict()). This fixture was a copy of the `tm_template_phi_scan` shape,
  // which cannot parse: `directIdentifierClasses` and
  // `appearsExplicitlySynthetic` are both required and `phiFields` is not a
  // member. Every call therefore threw inside mockComplete, surfaced as
  // SCAN_UNAVAILABLE, and was rethrown by synthetic-test.ts as
  // SYNTHETIC_EVIDENCE_REJECTED — so the certification path was unreachable
  // under MOCK_AI_CALLS no matter how clean the evidence was.
  //
  // Returning the CLEAN verdict here mocks only the model's second opinion.
  // The deterministic half of that gate is not mocked and still runs in full:
  // the explicit synthetic-marker regex, detectStructuredPhi(), the length
  // bounds and the prompt-injection check all still reject unlabeled or
  // identifier-bearing evidence under MOCK.
  tm_template_synthetic_phi_scan: {
    directIdentifierClasses: [],
    appearsExplicitlySynthetic: true,
    anyUncertain: false,
  },
};

// Note-format PHI gate — the FLAGGED counterpart to the clean
// `tm_template_phi_scan` fixture above. `anyUncertain: true` forces the
// fail-safe gate to reject/scrub even though it also names a field. Exported
// for direct unit-test use, and returned by mockComplete() when
// MOCK_TEMPLATE_PHI_FLAG=true so the reject path is reachable under MOCK.
export const MOCK_TEMPLATE_PHI_SCAN_FLAGGED = {
  phiFields: ['sections[1].defaultText'],
  anyUncertain: true,
} as const;

// Rx & clinical-safety (Layer 7c) — the POPULATED tm_rx_drafting variant.
// Returned by mockComplete() when MOCK_RX_WARNINGS=true so the Rx warnings rail,
// the critical-override flow, and the sign-time override GATE are testable under
// MOCK (the default fixture is {} so signing isn't blocked elsewhere). Shapes
// satisfy the RxResult/Prescription/RxWarning Zod schemas in 07c-rx-drafting.ts.
// One CRITICAL warning (gates sign), one major + one minor (inform only). L7c's
// deterministic validateRxDose floor appends one extra MINOR here (warfarin is
// flagged complex-dosing); it adds NO critical — the test patient has no
// allergies (no contraindication match) and the doses are in range / the drugs
// are all in the verified dose DB — so the critical count stays exactly 1.
// Actions kept to the new|continue subset that the export wire-type
// (visit-export.ts) also accepts.
export const MOCK_RX_DRAFTING_WITH_WARNINGS = {
  prescriptions: [
    {
      drug: 'Warfarin',
      strength: '5 mg',
      form: 'tablet',
      sig: 'Take 1 tablet by mouth once daily',
      quantity: '30',
      refills: '0',
      action: 'new',
      evidence_quote: '[MOCK] start warfarin for new atrial fibrillation',
    },
    {
      drug: 'Amoxicillin',
      strength: '500 mg',
      form: 'capsule',
      sig: 'Take 1 capsule by mouth three times daily',
      quantity: '21',
      refills: '0',
      action: 'new',
      evidence_quote: '[MOCK] treat acute bacterial sinusitis',
    },
    {
      drug: 'Lisinopril',
      strength: '10 mg',
      form: 'tablet',
      sig: 'Take 1 tablet by mouth once daily',
      quantity: '30',
      refills: '3',
      action: 'continue',
      evidence_quote: '[MOCK] continue home lisinopril for hypertension',
    },
  ],
  warnings: [
    {
      severity: 'critical',
      rx_drug: 'Warfarin',
      message:
        '[MOCK] Critical interaction: warfarin + amoxicillin can raise INR and bleeding risk — confirm the indication and plan close INR monitoring.',
      evidence_quote: '[MOCK] both newly started this visit',
    },
    {
      severity: 'major',
      rx_drug: 'Lisinopril',
      message: '[MOCK] Major: monitor renal function and serum potassium on an ACE inhibitor.',
      evidence_quote: null,
    },
    {
      severity: 'minor',
      rx_drug: 'Amoxicillin',
      message: '[MOCK] Minor: advise taking amoxicillin with food to reduce GI upset.',
      evidence_quote: null,
    },
  ],
} as const;

// ---------------------------------------------------------------------------
// Fixtures for modelClient.completeText() — plain-text paths.
// The SOAP draft fixture is the only one that really matters end-to-
// end: it's what the UI renders in the SOAP tab and what the export
// generators (PDF/DOCX/clipboard) serialize. Keep the markdown simple
// enough that section-header regexes in ehr-formatters.ts still find
// Subjective / Objective / Assessment / Plan headings.
// ---------------------------------------------------------------------------
const MOCK_SOAP_TEXT = [
  '## Subjective',
  '[MOCK] Patient reports mild tension headache x 3 days, improving.',
  '',
  '## Objective',
  '[MOCK] Vitals: BP 120/80, HR 72, afebrile. General: well-appearing, NAD.',
  '',
  '## Assessment',
  '[MOCK] Tension-type headache, resolving.',
  '',
  '## Plan',
  '[MOCK] Hydration, OTC analgesics PRN. Return if headache worsens or new neuro symptoms.',
].join('\n');

const MOCK_COMPLETE_TEXT_FIXTURES: Partial<
  Record<ModelCallPurpose, AnthropicCompleteTextResult>
> = {
  tm_soap_draft: {
    text: MOCK_SOAP_TEXT,
    inputTokens: 1,
    outputTokens: 1,
  },
  tm_polish: {
    text: MOCK_SOAP_TEXT,
    inputTokens: 1,
    outputTokens: 1,
  },
  // L6 fabrication gate verifier — MOCK always reports a faithful edit
  // (empty violations) so the qa/CI pipeline keeps its polish output.
  // The gate's reject/fail-closed paths are covered by deterministic
  // unit tests, not the MOCK e2e flow.
  tm_polish_gate: {
    text: '{"violations":[]}',
    inputTokens: 1,
    outputTokens: 1,
  },
  // Anchored-generation entailment verifier — UNREACHABLE in practice: the
  // verifier short-circuits to all-entailed under MOCK_AI_CALLS before any
  // model call (04b-anchor-verify.ts). Defensive fixture only, and it
  // deliberately fails CLOSED (empty verdicts → demote) if ever consumed.
  tm_anchor_entailment: {
    text: '{"verdicts":[]}',
    inputTokens: 1,
    outputTokens: 1,
  },
  // tm_patient_summary lives in MOCK_COMPLETE_FIXTURES (L7e uses
  // modelClient.complete(), not completeText).
};

// ---------------------------------------------------------------------------
// Deepgram fixture — one canned "conversation" with two speakers so
// Layer 2 (speaker roles) has more than one ID to classify.
// ---------------------------------------------------------------------------
const MOCK_DEEPGRAM_BATCH: DeepgramBatchResponse = {
  metadata: { duration: 3.5, request_id: 'mock-deepgram-request' },
  results: {
    channels: [
      {
        alternatives: [
          {
            transcript:
              '[MOCK] Hi, how are you feeling today? [MOCK] My head has been aching for three days.',
            confidence: 0.95,
            words: [],
          },
        ],
      },
    ],
    utterances: [
      {
        start: 0,
        end: 2.0,
        confidence: 0.95,
        channel: 0,
        transcript: '[MOCK] Hi, how are you feeling today?',
        words: [],
        speaker: 0,
      },
      {
        start: 2.1,
        end: 3.5,
        confidence: 0.93,
        channel: 0,
        transcript: '[MOCK] My head has been aching for three days.',
        words: [],
        speaker: 1,
      },
    ],
  },
};

/**
 * tm_chat_edit — the one CONTENT-AWARE fixture.
 *
 * The chat editor's contract is "what the doctor typed becomes an intent", so a
 * purpose-keyed fixture cannot exercise it: every turn would return the same
 * canned edit regardless of the request, and the test would prove nothing about
 * the dispatch it is meant to cover.
 *
 * Without this the purpose had NO fixture at all, so the whole surface threw
 * under MOCK_AI_CALLS and its only spec was `.eval.spec.ts` — real tokens,
 * operator-run, invisible to the gate. Deleting the per-section edit pills made
 * the chat the sole way to amend a note before signing, and the sole way to
 * amend a note before signing must be in CI.
 *
 * THE MODEL IS THE ONLY THING STUBBED. The intent goes through the real
 * dispatcher, the real `saveNoteSectionAction`, the real splice, the real audit
 * row and the real staleness flag — which is where the behaviour under test
 * actually lives.
 *
 * Directive, chosen to survive JSON-encoding into the data envelope:
 *   MOCKEDIT <section label> :: <the section's new body>
 * Anything else is a question, and answers it — `answer` is a legal turn and
 * keeps unrelated chat turns from throwing.
 */
function mockChatEdit(user: string): unknown {
  // THE LAST DIRECTIVE, NOT THE FIRST.
  //
  // The envelope carries `conversation` — the last twelve turns — so from the
  // second edit onward the payload holds every earlier MOCKEDIT too. Matching
  // the first one made turn 2 re-apply turn 1's body: byte-identical to what
  // was already saved, which `saveNoteSectionAction` correctly treats as a
  // successful no-op. The chat reported success, nothing was written, and
  // `emStale` was never set — a mock that faked the exact silent-no-op class
  // this surface was hardened against.
  // MOCKSCROLL <target> — the navigation intent, so the close-then-scroll
  // ordering on Rounds Screen 2 can be proven in CI at all. Without it the only
  // path that emits `scroll_to` is the real model, which lives in an
  // `.eval.spec.ts` and burns real tokens; a mock that cannot express the
  // intent means the drawer's "took you to the E/M gate" is untestable, and an
  // untested handler that fires and does nothing is precisely the class this
  // surface keeps producing.
  //
  // LAST OCCURRENCE, for the same history-replay reason as MOCKEDIT below.
  const scrolls = [...user.matchAll(/MOCKSCROLL\s+([a-z_]+)/g)];
  const scroll = scrolls[scrolls.length - 1];
  if (scroll) {
    return {
      reply: `Took you to the ${scroll[1].replace(/_/g, ' ')}.`,
      intents: [{ kind: 'scroll_to', target: scroll[1] }],
    };
  }

  const all = [...user.matchAll(/MOCKEDIT\s+(.+?)\s*::\s*([\s\S]+?)(?:\\n|\\"|"\s*[,}])/g)];
  const m = all[all.length - 1];
  if (!m) {
    return {
      reply: 'This note is in front of me — ask me to change a section and I will.',
      intents: [{ kind: 'answer' }],
    };
  }
  const sectionLabel = m[1].trim();
  // The envelope is JSON, so the body arrives with escapes intact.
  const body = m[2].replace(/\\n/g, '\n').replace(/\\"/g, '"').trim();
  return {
    reply: `Updated ${sectionLabel}.`,
    intents: [{ kind: 'edit_section', sectionLabel, body }],
  };
}

/**
 * ⚠️ B0 — THE MOCK BOUNDARY MOVED HERE, BELOW THE METER.
 *
 * Before B0 the mock short-circuited the whole STAGE at `model-client.ts`, so a
 * mocked pipeline run never reached `logApiUsage` and emitted ZERO usage events.
 * Zero events is indistinguishable from a broken meter — which is the failure
 * this function exists to kill.
 *
 * Now the mock substitutes only the VENDOR CALL: this returns a real
 * `Anthropic.Messages.Message`, and everything below it — fence-stripping,
 * `JSON.parse`, `extractUsage`, the Zod gate, `logApiUsage` — runs for real,
 * against a real Message shape. **Mock the vendor call, never the stage.**
 *
 * ⚠️ THE FIXTURES ARE RETURNED RAW, NOT PRE-PARSED. `mockComplete` used to hand
 * back `schema.parse(fixture)`, which skipped the parsing path entirely. Feeding
 * the raw fixture through the real parser is the point: a fixture that would
 * fail Zod in production now fails in QA too, instead of being waved through by
 * the mock.
 */
export function buildMockMessage(args: {
  purpose: ModelCallPurpose;
  kind: 'tool' | 'text' | 'completeText';
  toolName?: string;
  user?: string;
  model: string;
}): Anthropic.Messages.Message {
  const base = {
    id: `msg_mock_${args.purpose}`,
    type: 'message' as const,
    role: 'assistant' as const,
    model: args.model,
    stop_reason: 'end_turn' as const,
    stop_sequence: null,
    // ⚠️ These token counts are FIXTURE VALUES, not measurements. They exist so
    // the usage row has a shape; the row is marked `unitsSource: 'mock'` and its
    // money columns are zero, which is what makes it honest. Nothing may read
    // these as a quantity — see UnitsSource.
    usage: { input_tokens: 1, output_tokens: 1 } as Anthropic.Messages.Usage,
  };

  if (args.kind === 'completeText') {
    const fixture = MOCK_COMPLETE_TEXT_FIXTURES[args.purpose];
    if (fixture === undefined) {
      throw new Error(
        `[MOCK_AI_CALLS] no completeText() fixture for purpose=${args.purpose}.`
      );
    }
    return { ...base, content: [{ type: 'text', text: fixture.text, citations: [] }] } as unknown as Anthropic.Messages.Message;
  }

  const raw = rawCompleteFixture(args.purpose, args.user);
  if (args.kind === 'tool') {
    return {
      ...base,
      stop_reason: 'tool_use' as const,
      content: [
        {
          type: 'tool_use',
          id: 'toolu_mock',
          name: args.toolName ?? 'respond',
          input: raw,
        },
      ],
    } as unknown as Anthropic.Messages.Message;
  }
  return {
    ...base,
    content: [{ type: 'text', text: JSON.stringify(raw), citations: [] }],
  } as unknown as Anthropic.Messages.Message;
}

/**
 * The RAW fixture for a `complete()` purpose — the same selection logic
 * `mockComplete` uses, minus the `schema.parse`. Kept as one function so the
 * env-flag branches (PHI scan, Rx warnings, chat-edit content-awareness) cannot
 * drift between the two callers.
 *
 * ⚠️ THE CONTENT-SENSITIVITY OF THESE BRANCHES IS A CONTRACT, NOT AN
 * IMPLEMENTATION DETAIL — RULED 2026-08-08. `tm_chat_edit` reads the user's
 * message, and the E/M movement gates depend on the judge's mock varying with
 * its input. **A constant mock is a regression, not a simplification.**
 */
function rawCompleteFixture(purpose: ModelCallPurpose, user?: string): unknown {
  if (purpose === 'tm_chat_edit') return mockChatEdit(user ?? '');
  if (purpose === 'tm_template_phi_scan' && process.env.MOCK_TEMPLATE_PHI_FLAG === 'true') {
    return MOCK_TEMPLATE_PHI_SCAN_FLAGGED;
  }
  if (purpose === 'tm_rx_drafting' && process.env.MOCK_RX_WARNINGS === 'true') {
    return MOCK_RX_DRAFTING_WITH_WARNINGS;
  }
  const fixture = MOCK_COMPLETE_FIXTURES[purpose];
  if (fixture === undefined) {
    throw new Error(
      `[MOCK_AI_CALLS] no complete() fixture for purpose=${purpose}. ` +
        `Add one to packages/ai/src/mock.ts before enabling this purpose in tests.`
    );
  }
  return fixture;
}

export function mockComplete<T>(args: {
  purpose: ModelCallPurpose;
  schema: ZodType<T>;
  /** The rendered user content. Only tm_chat_edit reads it. */
  user?: string;
}): T {
  if (args.purpose === 'tm_chat_edit') {
    return args.schema.parse(mockChatEdit(args.user ?? ''));
  }
  // Note-format PHI gate: opt into the FLAGGED scan result (the reject path)
  // via env. The mock keys on `purpose` only and can't see the input, so a
  // content-aware "this note has PHI" branch isn't possible; the env flag is
  // the deterministic knob. Unset (the default) returns the clean fixture.
  if (
    args.purpose === 'tm_template_phi_scan' &&
    process.env.MOCK_TEMPLATE_PHI_FLAG === 'true'
  ) {
    return args.schema.parse(MOCK_TEMPLATE_PHI_SCAN_FLAGGED);
  }
  // Rx & clinical-safety (Layer 7c): opt into a populated draft (prescriptions +
  // critical/major/minor warnings) via env, so the Rx warnings rail + sign-time
  // override gate are exercisable under MOCK. Default (unset) returns the empty
  // fixture so visits sign without an Rx block.
  if (
    args.purpose === 'tm_rx_drafting' &&
    process.env.MOCK_RX_WARNINGS === 'true'
  ) {
    return args.schema.parse(MOCK_RX_DRAFTING_WITH_WARNINGS);
  }
  const fixture = MOCK_COMPLETE_FIXTURES[args.purpose];
  if (fixture === undefined) {
    throw new Error(
      `[MOCK_AI_CALLS] no complete() fixture for purpose=${args.purpose}. ` +
        `Add one to packages/ai/src/mock.ts before enabling this purpose in tests.`
    );
  }
  // schema.parse() backfills .default() clauses so fixtures above
  // don't need to spell out every optional array/object.
  return args.schema.parse(fixture);
}

export function mockCompleteText(args: {
  purpose: ModelCallPurpose;
}): AnthropicCompleteTextResult {
  const fixture = MOCK_COMPLETE_TEXT_FIXTURES[args.purpose];
  if (fixture === undefined) {
    throw new Error(
      `[MOCK_AI_CALLS] no completeText() fixture for purpose=${args.purpose}.`
    );
  }
  return fixture;
}

export function mockDeepgramBatch(): DeepgramBatchResult {
  const raw = MOCK_DEEPGRAM_BATCH;
  const firstChannel = raw.results?.channels?.[0]?.alternatives?.[0];
  return {
    raw,
    transcript: (firstChannel?.transcript ?? '').trim(),
    utterances: raw.results?.utterances ?? [],
    durationSec: Math.round(raw.metadata?.duration ?? 0),
  };
}

// ---------------------------------------------------------------------------
// T-M14.1 embed fixture — deterministic 1536-length vector for the
// sign-time capture hook. Values are tiny and non-zero so:
//   • length matches vector(1536) — a real INSERT against pgvector
//     accepts it without dimension mismatch,
//   • any cosine-similarity math in tests returns a defined number
//     rather than NaN (all-zero vectors have length 0).
// ---------------------------------------------------------------------------
const MOCK_EMBED_VECTOR: number[] = Array.from(
  { length: 1536 },
  (_, i) => ((i % 10) + 1) / 10000
);

const MOCK_EMBED_FIXTURES: Partial<Record<ModelCallPurpose, EmbedTextResult>> =
  {
    tm_embed: {
      embedding: MOCK_EMBED_VECTOR,
      inputTokens: 1,
      costCents: 0,
    },
  };

export function mockEmbed(args: {
  purpose: ModelCallPurpose;
}): EmbedTextResult {
  const fixture = MOCK_EMBED_FIXTURES[args.purpose];
  if (fixture === undefined) {
    throw new Error(
      `[MOCK_AI_CALLS] no embedText() fixture for purpose=${args.purpose}.`
    );
  }
  return fixture;
}
