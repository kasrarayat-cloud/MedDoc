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

export function mockComplete<T>(args: {
  purpose: ModelCallPurpose;
  schema: ZodType<T>;
}): T {
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
