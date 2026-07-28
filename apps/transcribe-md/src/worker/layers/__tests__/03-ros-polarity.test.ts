// ============================================================================
// "DENIES CHEST PAIN" MUST NOT READ AS CHEST PAIN (Q1 audit §02.9).
// ----------------------------------------------------------------------------
// L3's ROS entries were `{system, finding, evidence_quote}` — polarity lived
// only inside the prose of `finding`, so every downstream consumer had to guess
// it back out of the words. `projectEncounterFacts` does exactly that, with a
// regex over the finding and its evidence quote.
//
// A regex over a clinical sentence gets this wrong in BOTH directions, and both
// are shown here against the real heuristic before the fix:
//
//   OVER-FIRES → an affirmed symptom rendered DENIED. One quote often carries
//   two findings ("denies chest pain but does get short of breath"). The word
//   "denies" is in the shared evidence, so the dyspnoea is marked denied too.
//   In a cardiology note that is a materially different patient.
//
//   UNDER-FIRES → a denied symptom rendered AFFIRMED. Patients do not speak in
//   chart language. "Chest pain? None at all" contains no token the denial
//   pattern matches — "none" is not "no ", so the symptom is recorded as
//   present.
//
//   AND SIDE COLLAPSES → "numbness in the right hand, left hand is fine"
//   mentions both sides, so laterality infers BILATERAL. The complaint is
//   right-sided; bilateral numbness is a different neurological picture.
//
// The fix is to stop inferring what the extractor already knew. L3 states
// polarity and side as DATA, and the projection uses the stated value instead
// of guessing — the same structured-override pattern `measurements` already
// established.
//
// POLARITY IS REQUIRED, WITH NO DEFAULT, DELIBERATELY. Neither default is safe:
// absent → 'affirmed' invents symptoms and drives L5 red-flag false positives;
// absent → 'denied' hides real ones. A missing polarity is a malformed
// extraction, and the model client already retries a schema failure with the
// error fed back — the house pattern for "invalid → force re-extract".
// ============================================================================

import { describe, expect, it, vi } from 'vitest';

// L3 reaches prisma and the audit logger transitively, and the audit logger
// pulls next-auth into a plain node test run. Neither is exercised here.
vi.mock('@meddoc/db', () => ({ default: {} }));
vi.mock('@/lib/audit', () => ({ logAudit: vi.fn() }));

import { ExtractedEntities } from '../03-extract-entities';
import { projectEncounterFacts } from '@/lib/template-twin/encounter-facts';

/** chief_complaint and hpi are nullable-but-required. */
const MINIMAL = { chief_complaint: null, hpi: null };

// ---------------------------------------------------------------------------
// The schema
// ---------------------------------------------------------------------------

describe('L3 states ROS polarity rather than implying it', () => {
  it('a ROS entry WITHOUT polarity is rejected', () => {
    // Not defaulted. A missing polarity is a malformed extraction, not a
    // half-known one, and the retry loop exists for exactly this.
    const r = ExtractedEntities.safeParse({
      ...MINIMAL,
      ros: [
        {
          system: 'cardiovascular',
          finding: 'chest pain',
          evidence_quote: 'some chest pain',
        },
      ],
    });
    expect(r.success, 'polarity must be required, with no default').toBe(false);
  });

  it('carries both directions', () => {
    const parsed = ExtractedEntities.parse({
      ...MINIMAL,
      ros: [
        {
          system: 'cardiovascular',
          finding: 'chest pain',
          evidence_quote: 'no chest pain at all',
          polarity: 'denied',
        },
        {
          system: 'respiratory',
          finding: 'shortness of breath on exertion',
          evidence_quote: 'short of breath climbing stairs',
          polarity: 'affirmed',
        },
      ],
    });
    expect(parsed.ros.map((r) => r.polarity)).toEqual(['denied', 'affirmed']);
  });

  it('carries a side when one was stated, and none when it was not', () => {
    const parsed = ExtractedEntities.parse({
      ...MINIMAL,
      ros: [
        {
          system: 'neurological',
          finding: 'numbness in the hand',
          evidence_quote: 'numbness in the right hand, left hand is fine',
          polarity: 'affirmed',
          laterality: 'right',
        },
        {
          system: 'constitutional',
          finding: 'fever',
          evidence_quote: 'no fevers',
          polarity: 'denied',
        },
      ],
    });
    expect(parsed.ros[0].laterality).toBe('right');
    // Absent means NO SIDE WAS STATED. It is not the same claim as
    // "not_applicable", and collapsing the two would assert something the
    // transcript never said.
    expect(parsed.ros[1].laterality).toBeUndefined();
  });
});

// ---------------------------------------------------------------------------
// The projection — where the guessing actually happened
// ---------------------------------------------------------------------------

const rosFact = (facts: ReturnType<typeof projectEncounterFacts>, needle: string) =>
  facts.find((f) => f.concept.startsWith('ros.') && String(f.value).includes(needle))!;

describe('the projection uses the stated polarity, not a regex over the prose', () => {
  it('OVER-FIRE: an affirmed symptom sharing a quote with a denial stays affirmed', () => {
    // One sentence, two findings. "denies" belongs to the chest pain; the
    // shortness of breath is real and the patient said so.
    const contextText =
      'She denies chest pain but does get short of breath climbing stairs.';
    const facts = projectEncounterFacts({
      mode: 'conversation',
      contextText,
      entities: {
        ...MINIMAL,
        ros: [
          {
            system: 'cardiovascular',
            finding: 'chest pain',
            evidence_quote: contextText,
            polarity: 'denied',
          },
          {
            system: 'respiratory',
            finding: 'shortness of breath on exertion',
            evidence_quote: contextText,
            polarity: 'affirmed',
          },
        ],
      },
    });
    expect(rosFact(facts, 'chest pain').polarity).toBe('denied');
    expect(rosFact(facts, 'shortness of breath').polarity).toBe('affirmed');
  });

  it('UNDER-FIRE: a denial in plain speech is still a denial', () => {
    // "None at all" matches nothing in the denial pattern — "none" is not "no ".
    const contextText = 'Doctor #0: Any chest pain?\nPatient #1: None at all.';
    const facts = projectEncounterFacts({
      mode: 'conversation',
      contextText,
      entities: {
        ...MINIMAL,
        ros: [
          {
            system: 'cardiovascular',
            finding: 'chest pain',
            evidence_quote: 'None at all.',
            polarity: 'denied',
          },
        ],
      },
    });
    expect(rosFact(facts, 'chest pain').polarity).toBe('denied');
  });

  it('SIDE: a one-sided complaint that names both sides does not become bilateral', () => {
    const contextText = 'Numbness in the right hand, left hand is fine.';
    const facts = projectEncounterFacts({
      mode: 'conversation',
      contextText,
      entities: {
        ...MINIMAL,
        ros: [
          {
            system: 'neurological',
            finding: 'numbness in the hand',
            evidence_quote: contextText,
            polarity: 'affirmed',
            laterality: 'right',
          },
        ],
      },
    });
    expect(rosFact(facts, 'numbness').laterality).toBe('right');
  });

  it('A VISIT STORED BEFORE THIS FIELD EXISTED still projects', () => {
    // THE RESUME PATH, and it is live: `transcribe_visits.entities` is read back
    // as `resumeState.entities as ExtractedEntities` — a CAST, not a parse — so
    // the required-polarity schema never runs against it. Production holds 10
    // visits with stored ROS entries and none of them has the field.
    //
    // Those rows must fall back to the inference they have always had, not throw
    // and not silently become 'affirmed'. That is exactly why `polarity` is
    // optional on the projection's snapshot type while being REQUIRED in the L3
    // schema: new extractions must state it, old rows cannot be made to.
    const contextText = 'She denies chest pain.';
    const facts = projectEncounterFacts({
      mode: 'conversation',
      contextText,
      entities: {
        ...MINIMAL,
        ros: [
          {
            system: 'cardiovascular',
            finding: 'chest pain',
            evidence_quote: contextText,
            // no polarity, no laterality — a pre-2026-07-28 row
          },
        ],
      },
    });
    expect(rosFact(facts, 'chest pain').polarity).toBe('denied');
  });

  it('and every OTHER fact path still infers, byte-identically', () => {
    // The structured override is scoped to ROS. Medications, allergies and the
    // rest keep the heuristic they have always had — this change is not a
    // rewrite of the projection, and a silent behaviour change on paths nobody
    // asked about would be its own defect.
    const contextText = 'No known allergies.';
    const facts = projectEncounterFacts({
      mode: 'conversation',
      contextText,
      entities: {
        ...MINIMAL,
        allergies: [
          { substance: 'No known allergies', evidence_quote: contextText },
        ],
      },
    });
    const allergy = facts.find((f) => f.concept === 'allergy.substance')!;
    expect(allergy.polarity).toBe('denied');
  });
});

// ---------------------------------------------------------------------------
// The prompt — where the extractor is actually told
// ---------------------------------------------------------------------------

describe('the L3 prompt states both failure directions', () => {
  const src = (() => {
    const { readFileSync } = require('node:fs') as typeof import('node:fs');
    const { join } = require('node:path') as typeof import('node:path');
    return readFileSync(join(__dirname, '../03-extract-entities.ts'), 'utf8');
  })();

  it('names the denial-in-plain-speech case', () => {
    expect(src).toContain('None at all');
  });

  it('names the shared-quote case, so one denial does not swallow the sentence', () => {
    expect(src).toContain('one sentence can carry BOTH');
  });

  it('requires the side when a side was stated', () => {
    expect(src).toContain('never widen one side to bilateral');
  });

  it('non-vacuity: these live in the ROS field rule the model is shown', () => {
    expect(src).toContain("'- ros: list of {system, finding, polarity, evidence_quote,',");
  });
});
