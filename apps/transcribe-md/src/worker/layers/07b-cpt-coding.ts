// ============================================================================
// Layer 7b — CPT + E&M level (T-M6)
// ----------------------------------------------------------------------------
// Extracts the E&M code per 2021 AMA guidelines (Medical Decision Making
// OR total time, whichever is higher) plus any procedural CPT codes and
// modifiers. The model's reasoning is persisted so the UI can show
// "how we got 99214" alongside the code itself.
// ============================================================================

import { z } from 'zod';
import { modelClient, isValidCpt } from '@meddoc/ai';
import prisma from '@meddoc/db';
import { logAudit } from '@/lib/audit';

const MODEL = 'claude-sonnet-4-6';

const EmReasoning = z.object({
  problems: z
    .array(
      z.object({
        description: z.string(),
        /** stable / unstable / new with uncertain prognosis */
        status: z.string(),
      })
    )
    .default([]),
  /** Free-text summary of labs/imaging/records reviewed. */
  data: z.string(),
  // Q1 #19 follow-up: model occasionally writes prose into this enum
  // field (e.g. "Low — prescription NSAID initiated; however..."
  // instead of just "low"). 47 of 103 tm_cpt_coding calls SCHEMA_FAILed
  // on this exact pattern in the 2026-05-10 baseline shadow audit.
  // Preprocess extracts the first enum value present in the string;
  // strict enum still applies if extraction returns no match.
  risk: z.preprocess(
    (value) => {
      if (typeof value !== 'string') return value;
      const match = value.toLowerCase().match(/\b(minimal|low|moderate|high)\b/);
      return match ? match[1] : value;
    },
    z.enum(['minimal', 'low', 'moderate', 'high']),
  ),
});

export const EmCode = z.object({
  code: z.string().regex(/^[0-9]{5}$/, '5-digit CPT'),
  /** Optional human description ("Established patient, level 4"). */
  description: z.string(),
  reasoning: EmReasoning,
  evidence_quote: z.string().min(1),
});

export const ProcedureCpt = z.object({
  code: z.string().regex(/^[0-9]{5}$/, '5-digit CPT'),
  description: z.string(),
  evidence_quote: z.string().min(1),
  /** Q2 fix-pack §06.6 — categorical confidence on the procedure
   *  attribution. "low" → SOAP barely supports this procedure; the
   *  doctor should review before billing. The post-processor uses
   *  this to flip needsReview when any procedure lands "low". */
  confidenceLevel: z.enum(['high', 'medium', 'low']).default('high'),
  /** WHERE THIS CODE CAME FROM, and it is not decoration.
   *
   *  'dictated'        — the clinician said it aloud ("bill this as 93970").
   *                      An instruction.
   *  'coach_suggested' — this layer's model proposed it from the note.
   *                      A suggestion to review.
   *
   *  Billing cannot tell those apart if the note flattens them together, and
   *  they are different claims about the world. Defaults to coach_suggested
   *  because that is what the MODEL produces — the dictated path sets it
   *  explicitly at the merge below. */
  provenance: z.enum(['dictated', 'coach_suggested']).default('coach_suggested'),
  // NB the default is a type convenience, NOT the mechanism. Provenance is
  // stamped explicitly at the merge below, because the model must never get a
  // vote on where its own output came from.
});

export const Modifier = z.object({
  code: z.string().regex(/^[0-9]{2}$/, '2-digit modifier'),
  rationale: z.string().min(1),
});

export const CptResult = z.object({
  em: EmCode.nullable(),
  procedures: z.array(ProcedureCpt).default([]),
  modifiers: z.array(Modifier).default([]),
});
export type CptResult = z.infer<typeof CptResult>;

export interface Layer7bInput {
  visitId: string;
  practiceId: string;
  userId: string | null;
  specialty: string;
  soapFinal: string;
  entitiesJson: string;
  /** DOES AN OFFICE-VISIT E/M LEVEL APPLY TO THIS VISIT AT ALL?
   *
   *  `emAppliesToVisit({ specialtyId, templateSections, noteText })` —
   *  `@/lib/note-shape`. Both axes: the SPECIALTY (an imaging report has no
   *  office E/M) and the NOTE SHAPE (neither does an operative or procedure
   *  note — ruling #123).
   *
   *  ⚠️ REQUIRED, NOT OPTIONAL, AND NOT DEFAULTED. This is the COMPUTE layer of
   *  the three-layer invariant `packages/shared/src/specialties.ts:139-143`
   *  names — COMPUTE · STORE · EXPORT — and it was the one still keyed on
   *  specialty alone. A caller that has not thought about applicability must
   *  fail to TYPECHECK rather than inherit a permissive default; that is the
   *  same rule `visit-export.ts:66-70` states for the export seam and the same
   *  one `seedEmBaselineIfUnset` states for the store seam.
   *
   *  ⚠️ IT DOES NOT GATE THE WHOLE LAYER, AND THAT DISTINCTION IS THE ITEM.
   *  Suppressing L7b entirely on an operative note would delete the PROCEDURE
   *  CPT code from a colonoscopy — the one code that encounter genuinely bills.
   *  Only the E/M half is dropped; procedures and modifiers are untouched. */
  emApplies: boolean;
}

/** Placeholder when neither the clinician nor the coding model named the code.
 *  Deliberately not a guess at the nomenclature — an invented description on a
 *  billing line is worse than a bare one. */
const DICTATED_DESCRIPTION_FALLBACK = 'Dictated procedure code';

/** Procedure codes the clinician DICTATED, as captured by L3 from the raw
 *  transcript. Tolerant by construction: entitiesJson is model output, so a
 *  malformed or absent field must yield "no dictated codes" rather than throw
 *  and take the whole coding layer down with it. */
function extractSpokenProcedureCodes(
  entitiesJson: string,
): Array<z.infer<typeof ProcedureCpt>> {
  let parsed: unknown;
  try {
    parsed = JSON.parse(entitiesJson);
  } catch {
    return [];
  }
  if (typeof parsed !== 'object' || parsed === null) return [];
  const raw = (parsed as { spoken_procedure_codes?: unknown }).spoken_procedure_codes;
  if (!Array.isArray(raw)) return [];

  const out: Array<z.infer<typeof ProcedureCpt>> = [];
  const seen = new Set<string>();
  for (const item of raw) {
    if (typeof item !== 'object' || item === null) continue;
    const r = item as Record<string, unknown>;
    const code = typeof r.code === 'string' ? r.code.trim() : '';
    if (!/^[0-9]{5}$/.test(code) || seen.has(code)) continue;
    seen.add(code);
    out.push({
      code,
      description:
        typeof r.description === 'string' && r.description.trim()
          ? r.description.trim()
          : DICTATED_DESCRIPTION_FALLBACK,
      // The doctor's own words are the evidence. Falling back to a synthesised
      // quote would put words in their mouth on a billing line.
      evidence_quote:
        typeof r.evidence_quote === 'string' && r.evidence_quote.trim()
          ? r.evidence_quote.trim()
          : `Dictated code ${code}`,
      confidenceLevel: 'high',
      provenance: 'dictated',
    });
  }
  return out;
}

export async function runLayer7bCptCoding(
  input: Layer7bInput
): Promise<CptResult> {
  const system = [
    'You are a certified CPT coding specialist. From this SOAP note:',
    '',
    '1. Determine the E&M code under 2021 AMA guidelines. Level is the',
    '   HIGHER OF Medical Decision Making complexity OR total time',
    '   (including documentation).',
    '',
    '   Established patient (99212-99215):',
    '     99212 — Straightforward. 1 minor, self-limited problem.',
    '     99213 — Low. 2 minor OR 1 stable chronic; minimal data',
    '             review; minimal risk.',
    '     99214 — Moderate. 1+ chronic not at goal OR 2+ chronic',
    '             stable; moderate data review; moderate risk',
    '             (e.g. prescription-drug management).',
    '     99215 — High. 1+ chronic with severe exacerbation OR new',
    '             problem with uncertain prognosis; extensive data',
    '             review; high risk.',
    '',
    '   New patient (99202-99205) — parallel tiers. Default to',
    '   ESTABLISHED unless the SOAP explicitly says "new patient".',
    '',
    '2. List any procedural CPT codes performed during the visit',
    '   (injections, biopsies, EKG interpretation, etc.) — only those',
    '   the SOAP documents as performed at this encounter.',
    '',
    '3. Suggest CPT modifiers ONLY when clearly warranted:',
    '     -25 separately identifiable E&M on the same day as a',
    '         procedure',
    '     -59 distinct procedural service',
    '     -95 telehealth synchronous',
    '   Skip modifiers if none apply.',
    '',
    'Evidence rule: every code carries a specific SOAP quote. If you',
    'cannot cite evidence, omit the code.',
    '',
    'Procedure confidence: assign confidenceLevel to each procedure:',
    '  "high"   — SOAP explicitly documents the procedure as performed',
    '  "medium" — implied by findings + plan but not unambiguous',
    '  "low"    — speculative based on context (worth doctor review)',
    'When in doubt, prefer "low" + let the doctor confirm rather than',
    '"medium" + risk a speculative bill.',
    '',
    'Respond with VALID JSON ONLY, no markdown fences:',
    '{',
    '  "em": {',
    '    "code": "99214",',
    '    "description": "Established patient, moderate complexity",',
    '    "reasoning": {',
    '      "problems": [{ "description": "HTN not at goal", "status": "unstable" }],',
    '      "data": "reviewed last 3 months of BP log",',
    '      "risk": "moderate"',
    '    },',
    '    "evidence_quote": "…"',
    '  },',
    '  "procedures": [{ "code": "...", "description": "...", "evidence_quote": "..." }],',
    '  "modifiers": [{ "code": "25", "rationale": "..." }]',
    '}',
    '',
    'If the SOAP really describes no E&M encounter (rare — edge case',
    'for telephone-only encounters captured accidentally), return',
    '{ "em": null, "procedures": [], "modifiers": [] }.',
  ].join('\n');

  const user = [
    `Specialty: ${input.specialty}`,
    '',
    'Entities:',
    input.entitiesJson,
    '',
    'SOAP note:',
    input.soapFinal,
  ].join('\n');

  const result = await modelClient.complete({
    practiceId: input.practiceId,
    visitId: input.visitId,
    userId: input.userId,
    purpose: 'tm_cpt_coding',
    provider: 'anthropic',
    model: MODEL,
    system,
    user,
    schema: CptResult,
    maxTokens: 3072,
    // Q2 fix-pack — same rationale as L7a: billing codes deterministic.
    temperature: 0,
  });

  // Round 3 PR-D — A06-P0-002 deterministic CPT allowlist floor.
  // Filter the E&M code + each procedure code through the curated
  // pilot-specialty allowlist. Drop invalid codes; emit one audit
  // row aggregating all rejections per visit. Modifiers are
  // validated as part of the codes (e.g. "99213-25") via isValidCpt.
  const rejectedCodes: string[] = [];

  // F12-c / ruling #123 — THE COMPUTE LAYER. An imaging report and an
  // OPERATIVE / PROCEDURE note have no office-visit E/M level, so the E/M half
  // of this layer's output is dropped before anything is persisted.
  //
  // ⚠️ WHY THE MODEL IS STILL ASKED, AND WHY THAT IS THE RIGHT TRADE. The
  // alternative is a second system prompt with the E/M instructions removed.
  // That would edit the one blob that also carries the PROCEDURE and MODIFIER
  // instructions, on the clinical coding path, with no way to prove the
  // procedure output did not move — and a colonoscopy's procedure code is the
  // one code that encounter genuinely bills. Dropping a field deterministically
  // after the call cannot move procedures at all. The cost is the output tokens
  // for an E/M object that is discarded; the benefit is that this change is
  // provably confined to one field.
  //
  // ⚠️ AND IT IS DROPPED **BEFORE** THE ALLOWLIST CHECK, DELIBERATELY. A
  // suppressed E/M is not an allowlist rejection, and routing it through
  // `rejectedCodes` would file a `CODING_COACH_REJECTED_INVALID_CPT` audit row
  // whose stated reason is false — the code was not invalid, it did not apply.
  // A WRONG field in an audit row is worse than an absent one.
  let filteredEm = input.emApplies ? result.em : null;
  if (input.emApplies && result.em && !isValidCpt(result.em.code)) {
    rejectedCodes.push(result.em.code);
    filteredEm = null;
  }

  // A CODE THE DOCTOR SAID ALOUD IS NOT IN THE SOAP NOTE.
  //
  // "Bill this as 93970" is an instruction to a biller, not clinical prose, so
  // L4 correctly leaves it out of the note — and this layer only ever reads the
  // note and the entities. A production smoke caught the consequence: a
  // bilateral venous duplex was dictated with the CPT spoken and PROCEDURES came
  // back empty. The code was in the transcript the whole time.
  //
  // L3 sees the raw dictation, so it captures these into
  // `spoken_procedure_codes`, and they arrive here through entitiesJson. They
  // are merged BEFORE the allowlist filter below, deliberately: one fail-closed
  // floor, applied to every code regardless of who said it. A code the doctor
  // dictated is still a claim, and a mistyped or misheard one is still a False
  // Claims Act vector.
  // Deduped with the dictated entry winning: if the doctor said it AND the model
  // proposed it, that is one procedure, and the instruction outranks the guess.
  //
  // The DESCRIPTION is the exception, and it is borrowed rather than won. A live
  // check against the real model showed L3 returns the code with no description
  // — correctly, because its prompt forbids supplying one from its own knowledge
  // — which left a dictated code rendering as "93970 — Dictated procedure code"
  // on a billing line. When the coding model independently proposed the same
  // code it already carried the real nomenclature, and taking that is not an
  // invention: it is the same source every other procedure description comes
  // from. Provenance stays 'dictated' — where the CODE came from is the claim
  // being made, and a borrowed label does not change who said the number.
  const spokenProcedures = extractSpokenProcedureCodes(input.entitiesJson).map(
    (sp) => {
      if (sp.description !== DICTATED_DESCRIPTION_FALLBACK) return sp;
      const proposed = result.procedures.find((p) => p.code === sp.code);
      return proposed?.description
        ? { ...sp, description: proposed.description }
        : sp;
    },
  );
  const modelProcedures = result.procedures
    .filter((p) => !spokenProcedures.some((sp) => sp.code === p.code))
    // Stamped here rather than left to the schema default: this function knows
    // the origin, the model does not, and a claim about origin should be made
    // by whoever actually knows.
    .map((p) => ({ ...p, provenance: 'coach_suggested' as const }));
  const mergedProcedures = [...spokenProcedures, ...modelProcedures];

  const filteredProcedures = mergedProcedures.filter((p) => {
    const ok = isValidCpt(p.code);
    if (!ok) rejectedCodes.push(p.code);
    return ok;
  });
  if (rejectedCodes.length > 0) {
    void logAudit({
      action: 'CODING_COACH_REJECTED_INVALID_CPT',
      targetId: input.visitId,
      targetType: 'TranscribeVisit',
      userId: input.userId,
      practiceId: input.practiceId,
      success: false,
      metadata: {
        rejectedCount: rejectedCodes.length,
        rejectedCodes,
      },
    });
  }
  const filtered: typeof result & { emSuppressed?: true } = {
    em: filteredEm,
    procedures: filteredProcedures,
    modifiers: result.modifiers,
    // ⚠️ THE RECORD CARRIES **WHY** THE FIELD IS ABSENT, AND THAT IS NOT
    // DECORATION — IT IS WHAT STOPS A LATER READER RE-DERIVING A DIFFERENT
    // ANSWER ABOUT THE SAME ROW.
    //
    // `em: null` alone is ambiguous: it means "the model produced nothing" AND
    // "nobody asked for one". Every reader that wants to tell those apart was
    // recomputing `emAppliesToVisit` at READ time — against a note the doctor
    // may have edited since. Two independent refuters found the same seam:
    //
    //   worker writes em:null under emApplies=FALSE (operative note)
    //     -> doctor edits the note, the shape flips to office
    //     -> doctor hits Retry; L7b is SKIPPED (`hasContent(cptCodes)` is true
    //        for ANY object) and records status:'ok'
    //     -> the incompleteness check recomputes emApplies as TRUE, reads
    //        em:null, and reports "no E&M code emitted (status:ok)"
    //     -> "Auto-coding incomplete … Click Retry" that RETRY CANNOT CLEAR,
    //        because L7b is skipped on every subsequent attempt, until the
    //        5-retry budget is spent and the route answers 429.
    //
    // That is precisely the failure the `emApplies` parameter was introduced to
    // prevent, reappearing through the resume door — because the guard was keyed
    // on a RECOMPUTED verdict while the emptiness it judged was produced under a
    // DIFFERENT one. Same function, two moments, two answers.
    //
    // So the verdict is STORED WITH THE ROW IT DESCRIBES. A stored fact cannot
    // drift from the record it is attached to; a recomputation always can.
    // Additive JSON — no migration, and every existing consumer reads `em`,
    // `procedures`, `modifiers` or `codes` and is inert to an extra key.
    ...(input.emApplies ? {} : { emSuppressed: true as const }),
  };

  // Q2 fix-pack §06.6 — flag visits where any procedure landed at low
  // confidence. Doctor sees the warning before signing rather than
  // auto-attaching speculative billing codes.
  const lowConfProcedures = filteredProcedures.filter(
    (p) => p.confidenceLevel === 'low'
  );

  // FIND-P1-004 (comprehensive-audit 2026-05-14) — collapse the
  // previous two-step write (needsReview update + cptCodes update)
  // into ONE atomic update. The dual-write pattern could leave the
  // visit with `needsReview=true` + a "verify before billing: ..."
  // reviewReason BUT `cptCodes=null` if the worker crashed between
  // the two `prisma.update` calls. Doctor would then see the
  // warning banner with no codes to verify. BullMQ retry rescued
  // most of these via L7b re-run, and the stuck-visit watchdog
  // backstopped the rest at 15 min — but the inconsistent window
  // is closed entirely by collapsing to a single atomic write.
  const reviewFields = lowConfProcedures.length > 0
    ? {
        needsReview: true,
        reviewReason: `${lowConfProcedures.length} CPT procedure code${lowConfProcedures.length === 1 ? '' : 's'} at low confidence — verify before billing: ${lowConfProcedures.map((p) => p.code).join(', ')}.`,
      }
    : {};

  await prisma.transcribeVisit.update({
    where: { id: input.visitId },
    data: {
      cptCodes: filtered as unknown as object,
      ...reviewFields,
    },
  });

  return filtered;
}
