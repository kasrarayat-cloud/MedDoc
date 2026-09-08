// ============================================================================
// Template Twin — deterministic FILL engine (Phase 2b). prepare/finalize/
// processTemplateTwinVisit: resolve fields from anchored encounter facts ->
// independently validate -> conditionally native-render (renderTemplateDocx) +
// round-trip verify -> persist the fill manifest. Invariants: only template
// options, blank when unsaid, never invented; every populated value carries
// evidence. prisma singleton + injectable storage + logTwinAudit only.
// ============================================================================
import { visitByIdScope, asPracticeId } from '@/lib/practice-scope';
import { noteIdentity, overridesIdentity } from './note-identity';
import { Prisma } from '@prisma/client';
import prisma from '@meddoc/db';

import { logTwinAudit as logAudit } from './twin-audit';
import {
  renderTemplateDocx,
  type RenderTemplateDocxResult,
} from '@/lib/note-template-docx';

import { docxToTextWithControls } from '@/lib/note-template-parse/docx-content-controls';

import { canonicalSha256 } from './canonical';
import {
  projectEncounterFacts,
  type EncounterEntitySnapshot,
  type EncounterInputMode,
} from './encounter-facts';
import {
  SemanticMappingSchema,
  TEMPLATE_TWIN_RENDERER_VERSION,
  TEMPLATE_TWIN_RESOLVER_VERSION,
  TemplateDocIRSchema,
  TemplateTwinFillManifestSchema,
  templateTwinCounts,
  type FieldResolution,
  type RecordDerivedRefusal,
  type SemanticMapping,
  type TemplateDocIR,
  type TemplateTwinFillManifest,
} from './ir';
import { templateTwinMappingsSha256 } from './mapping-hash';
import { bridgeTemplateFill } from './bridge-fill';
import {
  applyClinicianOverrides,
  declinedOverrideIssues,
  type ClinicianFieldOverride,
  type ClinicianOverrideDeclineReason,
} from './clinician-override';
import { withProcedureDateFact } from './procedure-date';
import {
  withVisitMetadataFacts,
  type VisitPatientRecord,
} from './visit-metadata';
import {
  resolveTemplateFields,
  withApprovedPracticeDefaultFacts,
} from './resolver';
import {
  createTemplateTwinArtifactStore,
  type TemplateTwinArtifactStore,
} from './storage';
import { validateTemplateTwin } from './validation';

/** The worker-owned review marker for an unresolved Template Twin fill.
 * Correction code may clear it only by exact equality after a fully verified
 * replacement, so unrelated pipeline review reasons remain untouched. */
export const TEMPLATE_TWIN_REVIEW_REASON =
  'The Original Template DOCX has unresolved fields that require clinician review before signing.';

export class TemplateTwinFillError extends Error {
  readonly code:
    | 'CERTIFIED_TEMPLATE_NOT_FOUND'
    | 'TEMPLATE_PROVENANCE_MISMATCH'
    | 'SOURCE_ARTIFACT_UNAVAILABLE'
    | 'SIGNED_MANIFEST_IMMUTABLE'
    | 'MANIFEST_CONFLICT';

  constructor(code: TemplateTwinFillError['code'], message: string, cause?: unknown) {
    super(message, { cause });
    this.name = 'TemplateTwinFillError';
    this.code = code;
  }
}

export interface PrepareTemplateTwinFillInput {
  compiledVersionId: string;
  noteTemplateId: string;
  noteTemplateVersion: number;
  ir: TemplateDocIR;
  mappings: readonly SemanticMapping[];
  facts: ReturnType<typeof projectEncounterFacts>;
  certifiedFieldIds?: readonly string[];
  source?: Uint8Array;
  resolverModelVersion: string | null;
  validationNow: Date | string;
  allowUncertifiedForSyntheticTest?: boolean;
  /** The compiled {{one of}} marker text — drives the CHOICE_SLOT picks overlay. */
  markerText?: string;
  /** The visit (encounter) date — deterministically fills a DATE OF PROCEDURE
   *  content control as metadata (never AI). Absent → the control is left blank. */
  visitDate?: Date | string | null;
  /**
   * #247 — THE PATIENT RECORD, NARROWED TO THE TWO COLUMNS THAT MAY BE PRINTED.
   *
   * ⚠️ OPTIONAL HERE AND LOADED BY THE SHARED READER, NOT BY FIVE CALLERS. The
   * certification self-test constructs this input directly and must NEVER pass
   * one (`assertNoRecordDerivedFacts` refuses if it does), so the parameter
   * cannot be required. Every REAL fill goes through
   * `readAndPrepareTemplateTwinFill`, which loads it from the visit — the same
   * shape, and for the same reason, as F24-S5's clinician overrides: behaviour
   * on the shared function beats four caller-side checklists kept complete by
   * hand.
   */
  patient?: VisitPatientRecord | null;
  /** The LIVE brain's generated note — its picks + table measurements are bridged
   *  onto the resolver baseline. When absent, only the evidence resolver runs
   *  (behaviour-identical to the pre-bridge fill path). */
  generatedNote?: string;
  /**
   * F24-S5 — the clinician's own corrections to enumerated form controls.
   *
   * ⚠️ AN INPUT, READ ON EVERY RUN. This is what makes a correction survive a
   * recompute instead of being reverted by it. Absent or empty → byte-identical
   * to the pre-override behaviour.
   */
  clinicianOverrides?: readonly ClinicianFieldOverride[];
}

export interface PreparedTemplateTwinFill {
  manifest: TemplateTwinFillManifest;
  manifestSha256: string;
  factSetSha256: string;
  render: RenderTemplateDocxResult | null;
}

export interface FinalizeTemplateTwinFillInput
  extends Omit<PrepareTemplateTwinFillInput, 'facts'> {
  facts: ReturnType<typeof projectEncounterFacts>;
  resolutions: readonly FieldResolution[];
  /** F24-S5 — corrections that could not be applied, surfaced as manifest
   *  warnings. See `declinedOverrideIssues`. */
  declinedOverrides?: readonly {
    fieldId: string;
    reason: ClinicianOverrideDeclineReason;
  }[];
}

export async function finalizeTemplateTwinFill(
  input: FinalizeTemplateTwinFillInput,
): Promise<PreparedTemplateTwinFill> {
  const ir = TemplateDocIRSchema.parse(input.ir);
  const mappings = input.mappings.map((mapping) => SemanticMappingSchema.parse(mapping));
  const fields = [...input.resolutions];
  const validated = validateTemplateTwin({
    fields: ir.fields,
    mappings,
    facts: input.facts,
    resolutions: fields,
    tables: ir.tables,
    unsupported: ir.unsupported,
    certifiedFieldIds: input.certifiedFieldIds,
    allowUncertifiedForSyntheticTest: input.allowUncertifiedForSyntheticTest,
    now: input.validationNow,
  });
  // ⚠️ F24-S5 — A DECLINED CORRECTION IS REPORTED, NOT SWALLOWED, AND THIS IS
  // THE CONSUMER THAT MAKES `declined` MORE THAN A `console.info`.
  //
  // The refuted slice's module header promised "the doctor is told through
  // `declined` either way" while the caller destructured the result and dropped
  // it — zero consumers, so a recompiled template silently lost a correction the
  // chat had already reported as `ok: true`.
  //
  // ⚠️ APPENDED AS `warning`, AND `valid` IS DELIBERATELY NOT RECOMPUTED. These
  // issues must never flip a valid fill to invalid: blocking the whole document
  // because one control's correction could not be applied is strictly worse than
  // serving the document with the loss named on it.
  const declinedIssues = declinedOverrideIssues(input.declinedOverrides ?? []);
  const validation =
    declinedIssues.length === 0
      ? validated
      : { ...validated, issues: [...validated.issues, ...declinedIssues] };
  const counts = templateTwinCounts(fields, ir.fields);
  const manifest = TemplateTwinFillManifestSchema.parse({
    manifestVersion: 1,
    compiledVersionId: input.compiledVersionId,
    noteTemplateId: input.noteTemplateId,
    noteTemplateVersion: input.noteTemplateVersion,
    compilerVersion: ir.compilerVersion,
    resolverVersion: TEMPLATE_TWIN_RESOLVER_VERSION,
    resolverModelVersion: input.resolverModelVersion,
    rendererVersion: TEMPLATE_TWIN_RENDERER_VERSION,
    facts: input.facts,
    fields,
    validation,
    counts,
  });
  const manifestSha256 = canonicalSha256(manifest);
  const factSetSha256 = canonicalSha256(input.facts);
  if (!validation.valid) {
    return { manifest, manifestSha256, factSetSha256, render: null };
  }
  if (!input.source) {
    throw new TemplateTwinFillError(
      'SOURCE_ARTIFACT_UNAVAILABLE',
      'The immutable source document is unavailable for verified rendering.',
    );
  }
  const render = await renderTemplateDocx({
    source: input.source,
    ir,
    resolutions: fields,
    validation,
  });
  return { manifest, manifestSha256, factSetSha256, render };
}

/** Pure clinical boundary apart from the exact renderer. Invalid or unresolved
 * fields are retained for review and never rendered. */
export async function prepareTemplateTwinFill(
  input: PrepareTemplateTwinFillInput,
): Promise<PreparedTemplateTwinFill> {
  const ir = TemplateDocIRSchema.parse(input.ir);
  const mappings = input.mappings.map((mapping) => SemanticMappingSchema.parse(mapping));
  // Inject the visit date as a traceable fact for a DATE OF PROCEDURE control
  // (deterministic metadata, never AI), then let the evidence resolver fill it —
  // so the resolution is independently validated like any other, never a bare
  // overlay. No-op when there is no such control / no visit date.
  // #247 — THE PATIENT RECORD'S OWN VALUES, INJECTED AS `visit_record` FACTS
  // BEFORE THE DATE, so the two metadata injectors compose in one direction and
  // each still sees any real dictated fact that would outrank it. A no-op when
  // no record was threaded through, which is exactly the certification path.
  // ⚠️ #264 — the collector the metadata injector names its refusals into, so a
  // blank it produced arrives at the resolver labelled with WHY rather than as
  // "nobody said it". Declared here because this is the only layer that both
  // calls the injector and calls the resolver.
  const injectorRefusals: RecordDerivedRefusal[] = [];

  const facts = withProcedureDateFact({
    fields: ir.fields,
    mappings,
    visitDate: input.visitDate,
    facts: withVisitMetadataFacts({
      fields: ir.fields,
      mappings,
      patient: input.patient,
      visitDate: input.visitDate,
      refusals: injectorRefusals,
      facts: withApprovedPracticeDefaultFacts({
        fields: ir.fields,
        mappings,
        facts: input.facts,
      }),
    }),
  });
  const baseline = resolveTemplateFields({
    fields: ir.fields,
    mappings,
    facts,
    certifiedFieldIds: input.certifiedFieldIds,
    allowUncertifiedForSyntheticTest: input.allowUncertifiedForSyntheticTest,
    refusals: injectorRefusals,
  });
  // Overlay the LIVE brain's CHOICE_SLOT picks + dictated table measurements onto
  // the evidence baseline. Real evidence always wins (bridge fills only where the
  // resolver left a field unfilled). Absent a generated note, the baseline stands
  // — byte-identical to the pre-bridge behaviour.
  const bridged =
    input.markerText != null && input.generatedNote != null
      ? bridgeTemplateFill({
          ir,
          markerText: input.markerText,
          filledNote: input.generatedNote,
          baseline,
          // The SAME facts the resolver used. A bridged MEASUREMENT must cite one
          // of these. A bridged PICK cites the selection itself — its own
          // provenance class — and those facts come back out to be merged in.
          facts,
          mappings,
        })
      : { resolutions: baseline, facts: [] };
  // ⚠️ THE CLINICIAN GOES LAST, AND WINS. Applied OUTSIDE the generated-note
  // ternary above on purpose: a correction must land whether or not this run has
  // a generated note to bridge from, and putting it inside would have made the
  // feature quietly conditional on something unrelated to it — which is exactly
  // the partial edit the WIRING arm now mutation-proves against.
  //
  // Precedence is ORDER, not a flag — `mergeFieldResolutions` keeps its
  // unfilled-only rule untouched, so the evidence resolver still beats every AI
  // bridge, and only the doctor beats the resolver.
  const overridden = applyClinicianOverrides({
    ir,
    resolutions: bridged.resolutions,
    overrides: input.clinicianOverrides ?? [],
    mappings,
    // Parity with the picks bridge: the note the correction was made against is
    // part of the fact's identity. Empty when this run has no generated note —
    // the fact is still uniquely keyed by field + option within its own set.
    noteSha256: noteIdentity(input.generatedNote) ?? '',
  });
  return finalizeTemplateTwinFill({
    ...input,
    ir,
    mappings,
    facts: [...facts, ...bridged.facts, ...overridden.facts],
    resolutions: overridden.resolutions,
    declinedOverrides: overridden.declined,
  });
}

interface PersistedMappingRow {
  sourceType: string;
  clinicalConcept: string | null;
  expectedDataType: string;
  polarityBehavior: string;
  temporality: string | null;
  laterality: string | null;
  unitPolicy: string | null;
  approvedSynonyms: unknown;
  required: boolean;
  blankPolicy: string;
  unmentionedPolicy: string | null;
  /** #217 — JSONB, so `unknown` until shape-checked on read. */
  conceptScope: unknown;
  unknownPolicy: string;
  practiceDefault: string | null;
  mappingStatus: string;
}

function mappingFromRow(fieldId: string, row: PersistedMappingRow): SemanticMapping {
  return SemanticMappingSchema.parse({
    fieldId,
    sourceType: row.sourceType,
    clinicalConcept: row.clinicalConcept,
    expectedDataType: row.expectedDataType,
    polarityBehavior: row.polarityBehavior,
    temporality: row.temporality,
    laterality: row.laterality,
    unitPolicy: row.unitPolicy,
    approvedSynonyms: Array.isArray(row.approvedSynonyms) ? row.approvedSynonyms : [],
    required: row.required,
    blankPolicy: row.blankPolicy,
    // ⚠️ THE KEY IS OMITTED, NOT SET TO `undefined`. An explicit undefined
    // survives the Zod parse and `canonicalSha256` refuses it outright
    // ("Canonical JSON does not support undefined object values"), which broke
    // six certification arms.
    // ⚠️ #194 — AN EXPLICIT `'omit'` SURVIVES THE ROUND TRIP; NULL IS ELIDED.
    // Eliding a ruled `omit` would read the doctor's decision back as "nobody
    // ruled", which is a different behaviour and a different count.
    ...(row.unmentionedPolicy ? { unmentionedPolicy: row.unmentionedPolicy } : {}),
    // ⚠️ #217 — OMITTED WHEN ABSENT, exactly as the policy above. Reading a
    // NULL column back as `[]` would move every pre-existing mapping's
    // attestation sha and de-certify all 185 production rows at once.
    ...(Array.isArray(row.conceptScope) && row.conceptScope.length > 0
      ? { conceptScope: row.conceptScope }
      : {}),
    unknownPolicy: row.unknownPolicy,
    practiceDefault: row.practiceDefault,
    status: row.mappingStatus.toLowerCase(),
  });
}

function asJson(value: unknown): Prisma.InputJsonValue {
  return value as Prisma.InputJsonValue;
}

/**
 * The STORED shape of a clinician override row, as read from
 * `templateTwinFieldOverride`. Distinct from `ClinicianFieldOverride`, which is
 * the DOMAIN shape the fill consumes — the read path converts one to the other,
 * so a simulated row must be in THIS shape to merge before that conversion.
 */
export type TemplateTwinOverrideRow = {
  fieldId: string;
  selectedOptionOrdinal: number | null;
  overrideKind: string;
  insertedText: string | null;
};

export interface ProcessTemplateTwinVisitInput {
  visitId: string;
  /**
   * ⚠️ RULING #287 — THE CHART'S PRACTICE, AND IT DOES BOTH JOBS ON PURPOSE.
   *
   * This was `practiceId`, and one slot was answering two questions: it scoped
   * the VISIT (`transcribe_visits.practiceId`, the tenant) and it validated the
   * TEMPLATE's provenance against `sourceArtifact.practiceId` (the template
   * owner). Those are different columns and nothing constrains them equal — the
   * schema says so at `TranscribeVisit.practiceId`: *"derived from the PATIENT,
   * never from the author … NOTHING kept them agreeing."*
   *
   * ⚠️ SO NEITHER VALUE WAS RIGHT, AND BOTH LANES HAD BEEN WRONG IN OPPOSITE
   * DIRECTIONS. Passing the author's practice (what `main` did) made the visit
   * lookups find nothing on a locum visit; passing the tenant's (what #267 did)
   * made provenance throw `TEMPLATE_PROVENANCE_MISMATCH` and withheld the
   * document entirely.
   *
   * #287 decides the product question the split exposed: **a visit is documented
   * in the TENANT practice's format.** A locum from B seeing A's patient fills
   * A's active template; B's template never fills a visit in A. So one value is
   * correct for both jobs — provenance compares the template's owner against the
   * TENANT — and the parameter is named for the fact rather than for the caller.
   */
  tenantPracticeId: string;
  /**
   * WHO ACTED — audit and attribution, and #287 says NEVER A SCOPE. It reaches
   * `userId` on the audit rows and nothing else; no query filters on it.
   */
  authorUserId: string;
  noteTemplateId: string;
  noteTemplateVersion: number;
  inputMode: EncounterInputMode;
  contextText: string;
  /** Runtime-validated Layer-3 entity object. The legacy generic Zod helper
   * widens some inferred leaf types to unknown, so this boundary narrows only
   * after Layer 3 has parsed the object. */
  entities: unknown;
  /** The LIVE brain's generated note (soapFinal). Its CHOICE_SLOT picks + table
   *  measurements are bridged onto the resolver baseline. Optional: absent it,
   *  only the evidence resolver runs. */
  generatedNote?: string;
  asrQuality?: 'high' | 'review' | 'unknown';
  validationNow: Date | string;
  /** The visit (encounter) date — deterministically fills a DATE OF PROCEDURE
   *  content control as metadata (never AI). Absent → the control is left blank. */
  visitDate?: Date | string | null;
  resolverModelVersion: string | null;
  storage?: TemplateTwinArtifactStore;
  /**
   * SIMULATION ONLY — override rows that are NOT yet in the database, merged
   * over the ones that are, so a caller can ask *"what would this fill look
   * like if I wrote this?"* BEFORE it writes.
   *
   * ⚠️ THIS EXISTS BECAUSE A GUARD THAT READS THE PRE-WRITE STATE CANNOT SEE A
   * WRITE THAT BREAKS THE DOCUMENT. Round four of #1018's pass found it twice,
   * from two independent lenses: an insert onto a `rowPrototype` narrative_text
   * field, and one onto a `laterality: 'required'` mapping. Either makes
   * `finalizeTemplateTwinFill` return `render: null` for the WHOLE fill; the
   * offer then returns `miss('no_render')` and the surface draws no panel — and
   * with no panel there is no Undo button, so the row is permanent and the
   * doctor's document never renders again.
   *
   * Nothing is persisted by passing this: it changes what the fill is computed
   * FROM, never what is stored. `processTemplateTwinVisit` REFUSES it outright.
   */
  simulateOverrides?: readonly TemplateTwinOverrideRow[];
}

/** What the read+prepare phase produces. The persistence phase needs the rows
 *  it read, so they come back rather than being read twice. */
/**
 * READ + PREPARE, with no writes of any kind.
 * ---------------------------------------------------------------------------
 * Extracted VERBATIM from processTemplateTwinVisit so the pre-sign preview and
 * the real export cannot drift: the doctor must be looking at the same fill
 * they are about to sign. Everything here is a read plus pure computation. The
 * template-provenance claim ABOVE it and the manifest persistence BELOW it stay
 * where they were, in the writing path only.
 *
 * A preview must never leave a fill manifest behind. The sign gate validates a
 * STORED manifest against the certified IR, so a manifest written mid-review
 * would let a doctor sign a fill that predates their own adoptions.
 */
export async function readAndPrepareTemplateTwinFill(
  // ⚠️ `visitId` IS REQUIRED, AND THAT IS THE POINT. It used to be `Omit`ed,
  // because nothing here needed it. F24-S5's clinician overrides are keyed by
  // visit and must be read on EVERY fill — preview, worker, export and the sign
  // freeze alike — so requiring it makes a path that forgets them a COMPILE
  // ERROR rather than a document that silently drops the doctor's own
  // correction. The behaviour lives on the shared function, not on four
  // caller-side checklists that are kept complete by hand.
  input: ProcessTemplateTwinVisitInput,
) {
    const row = await prisma.noteTemplate.findFirst({
      where: {
        id: input.noteTemplateId,
        // #287 — THE CHART'S PRACTICE SELECTS THE TEMPLATE. This filtered on
        // `doctorId` (the actor), so a locum documenting A's patient selected
        // the LOCUM's template and provenance below then compared B against A:
        // TEMPLATE_PROVENANCE_MISMATCH on a visit whose form exists and is
        // certified. `practiceId` is the tenant, and `sourceArtifact.practiceId`
        // below confirms it on a SECOND column — two independent reads of one
        // decision, which is why both stay.
        //
        // ⚠️ THE SYSTEM DEFAULT IS UNAFFECTED, and that is measured rather than
        // hoped: it has `doctorId = NULL` AND `practiceId = NULL` (the
        // `note_templates_practice_iff_doctor` constraint ties the two), so a
        // non-null filter excluded it before this change and excludes it after.
        // It carries no compiled twin either, so it exits at the certification
        // guard below as it always did.
        practiceId: input.tenantPracticeId,
        version: input.noteTemplateVersion,
      },
      select: {
        id: true,
        version: true,
        templateTwinCompiledVersion: {
          select: {
            id: true,
            compilerVersion: true,
            compiledDocumentIr: true,
            certificationStatus: true,
            certification: { select: { id: true, approvedMappingsSha256: true } },
            sourceArtifact: {
              select: {
                practiceId: true,
                objectKey: true,
                sha256: true,
                sizeBytes: true,
                validationStatus: true,
              },
            },
            fields: {
              orderBy: { displayOrder: 'asc' },
              select: {
                fieldId: true,
                detectionStatus: true,
                mapping: {
                  select: {
                    sourceType: true,
                    clinicalConcept: true,
                    expectedDataType: true,
                    polarityBehavior: true,
                    temporality: true,
                    laterality: true,
                    unitPolicy: true,
                    approvedSynonyms: true,
                    required: true,
                    blankPolicy: true,
                    unmentionedPolicy: true,
                    conceptScope: true,
                    unknownPolicy: true,
                    practiceDefault: true,
                    mappingStatus: true,
                  },
                },
              },
            },
          },
        },
      },
    });
    const compiled = row?.templateTwinCompiledVersion;
    if (!row || !compiled || compiled.certificationStatus !== 'CERTIFIED' || !compiled.certification) {
      throw new TemplateTwinFillError(
        'CERTIFIED_TEMPLATE_NOT_FOUND',
        'The selected Template Twin version is not certified and active.',
      );
    }
    if (
      row.version !== input.noteTemplateVersion ||
      compiled.sourceArtifact.practiceId !== input.tenantPracticeId ||
      compiled.sourceArtifact.validationStatus !== 'accepted' ||
      !compiled.sourceArtifact.objectKey
    ) {
      throw new TemplateTwinFillError(
        'TEMPLATE_PROVENANCE_MISMATCH',
        'The selected Template Twin provenance does not match this visit.',
      );
    }
    const certifiedFieldIds: string[] = [];
    const mappings = compiled.fields.map((field: {
      fieldId: string;
      detectionStatus: string;
      mapping: PersistedMappingRow | null;
    }) => {
      if (!field.mapping) {
        throw new TemplateTwinFillError(
          'TEMPLATE_PROVENANCE_MISMATCH',
          'The certified Template Twin mapping set is incomplete.',
        );
      }
      if (field.detectionStatus !== 'CERTIFIED') {
        throw new TemplateTwinFillError(
          'TEMPLATE_PROVENANCE_MISMATCH',
          'The certified Template Twin field set is incomplete.',
        );
      }
      certifiedFieldIds.push(field.fieldId);
      return mappingFromRow(field.fieldId, field.mapping);
    });
    const ir = TemplateDocIRSchema.parse(compiled.compiledDocumentIr);
    if (
      mappings.length !== ir.fields.length ||
      templateTwinMappingsSha256(mappings) !==
        compiled.certification.approvedMappingsSha256
    ) {
      throw new TemplateTwinFillError(
        'TEMPLATE_PROVENANCE_MISMATCH',
        'The certified Template Twin mappings no longer match their certification.',
      );
    }
    const facts = projectEncounterFacts({
      mode: input.inputMode,
      contextText: input.contextText,
      entities: input.entities as EncounterEntitySnapshot,
      asrQuality: input.asrQuality,
    });
    const storage = input.storage ?? createTemplateTwinArtifactStore();
    const source = await storage.readSourceArtifact({
      practiceId: input.tenantPracticeId,
      objectKey: compiled.sourceArtifact.objectKey,
      expectedSha256: compiled.sourceArtifact.sha256,
      expectedSizeBytes: compiled.sourceArtifact.sizeBytes,
    });
    // Recover the compiled {{one of}} marker form from the SAME verified source
    // the IR was compiled from — the picks bridge aligns the generated note's picks
    // to it. Cheap, deterministic, no re-parse of the IR.
    const markerText =
      input.generatedNote != null
        ? (await docxToTextWithControls(source)).text
        : undefined;
    // F24-S5 — the clinician's corrections, read as an INPUT to this fill.
    // ⚠️ READ ONCE, AND RETURNED, so the manifest's `overridesSha256` is stamped
    // from THE SAME LIST THIS FILL RAN AGAINST. Re-reading at write time would
    // let a correction landing mid-fill stamp an identity the rendered document
    // does not correspond to — a manifest asserting freshness for a document it
    // never produced, which is the exact drift `note-identity.ts` exists to
    // prevent.
    //
    // Ordered for determinism; the unique index on (visitId, fieldId) means
    // there is at most one row per field, and `overridesIdentity` sorts anyway.
    // #247 — THE PATIENT RECORD, READ HERE FOR THE SAME REASON THE OVERRIDES
    // ARE. Five call sites reach this function (the worker's fill step, the
    // native export, the sign freeze, the pre-sign preview and the worker's own
    // inline step) and FOUR of them never loaded a patient. Threading a
    // parameter through all five would have made "did you remember the patient
    // record?" a per-caller checklist item — and a control that prints a
    // patient's NAME is the last place to rely on remembering. Loading it in
    // the one shared reader makes every path carry it by construction.
    //
    // ⚠️ TWO COLUMNS, PRACTICE-SCOPED. `name` and `dateOfBirth` are the only
    // fields anything downstream may print, and the `where` names the practice
    // as well as the visit so a cross-tenant id cannot return a record at all.
    // Widening this select is a PHI decision, not a convenience.
    const visitPatient = await prisma.transcribeVisit.findFirst({
      where: { id: input.visitId, practiceId: input.tenantPracticeId },
      select: { patient: { select: { name: true, dateOfBirth: true } } },
    });
    const clinicianOverrides = await prisma.templateTwinFieldOverride.findMany({
      where: { visitId: input.visitId, practiceId: input.tenantPracticeId },
      orderBy: { fieldId: 'asc' },
      select: {
        fieldId: true,
        selectedOptionOrdinal: true,
        overrideKind: true,
        insertedText: true,
      },
    });
    // ⚠️ SIMULATED ROWS ARE MERGED BY `fieldId`, NOT APPENDED. The unique index
    // is on (visitId, fieldId), so appending would hand the fill two rows for
    // one field — a state the database cannot hold, which would make the
    // simulation answer about a universe that cannot exist.
    const effectiveOverrides = input.simulateOverrides?.length
      ? [
          ...clinicianOverrides.filter(
            (o) => !input.simulateOverrides!.some((p) => p.fieldId === o.fieldId),
          ),
          ...input.simulateOverrides,
        ].sort((a, b) => a.fieldId.localeCompare(b.fieldId))
      : clinicianOverrides;

    const prepared = await prepareTemplateTwinFill({
      compiledVersionId: compiled.id,
      noteTemplateId: row.id,
      noteTemplateVersion: row.version,
      ir,
      mappings,
      facts,
      certifiedFieldIds,
      source,
      resolverModelVersion: input.resolverModelVersion,
      validationNow: input.validationNow,
      visitDate: input.visitDate,
      patient: visitPatient?.patient ?? null,
      markerText,
      generatedNote: input.generatedNote,
      // ⚠️ THE DATABASE ROW IS NOT THE DOMAIN TYPE, AND THE NARROWING HAPPENS
      // HERE RATHER THAN INSIDE THE OVERLAY. A row whose columns do not satisfy
      // either arm — a `scaffold_default` with no text, an `option` with no
      // ordinal — is DROPPED here rather than passed on as a half-shaped
      // object. The database CHECK makes both cases unreachable; this is the
      // second layer, because a constraint added in a migration protects rows
      // written after it and this code also runs against whatever is already
      // stored.
      clinicianOverrides: effectiveOverrides.flatMap((o): ClinicianFieldOverride[] => {
        if (o.overrideKind === 'scaffold_default') {
          return o.insertedText
            ? [{ kind: 'scaffold_default' as const, fieldId: o.fieldId, insertedText: o.insertedText }]
            : [];
        }
        return typeof o.selectedOptionOrdinal === 'number'
          ? [{ kind: 'option' as const, fieldId: o.fieldId, selectedOptionOrdinal: o.selectedOptionOrdinal }]
          : [];
      }),
    });

  return { prepared, row, compiled, ir, storage, clinicianOverrides };
}

/** Resolves, independently validates, conditionally renders, stores, and
 * records one visit against its already-selected immutable template version. */
export async function processTemplateTwinVisit(
  input: ProcessTemplateTwinVisitInput,
): Promise<PreparedTemplateTwinFill> {
  // ⚠️ A SIMULATED FILL MUST NEVER BE PERSISTED, AND THIS IS THE MECHANISM
  // RATHER THAN THE CONVENTION. This function passes its input straight down to
  // `readAndPrepareTemplateTwinFill`, so `simulateOverrides` would reach the
  // fill — and the manifest is then stamped `overridesIdentity(clinicianOverrides)`
  // from the rows that ARE stored, producing a manifest asserting an identity
  // the rendered document does not correspond to. That is verbatim the drift
  // this file's own comment says `note-identity.ts` exists to prevent.
  //
  // Simulation is a READ-side capability. The writer refuses it.
  if (input.simulateOverrides?.length) {
    throw new Error(
      'processTemplateTwinVisit: refusing a simulated fill. `simulateOverrides` is read-side only — persisting it would stamp a manifest identity the document does not correspond to.',
    );
  }

  // Persist the first selected version before source I/O, resolution, model-
  // derived evidence processing, or rendering. A retry must never switch to a
  // newly activated template after partial work against this version.
  const claimedTemplate = await prisma.transcribeVisit.updateMany({
    where: {
      id: input.visitId,
      practiceId: input.tenantPracticeId,
      deletedAt: null,
      archivedAt: null,
      status: { not: 'SIGNED' },
      OR: [
        { noteTemplateId: null, noteTemplateVersion: null },
        {
          noteTemplateId: input.noteTemplateId,
          noteTemplateVersion: input.noteTemplateVersion,
        },
      ],
    },
    data: {
      noteTemplateId: input.noteTemplateId,
      noteTemplateVersion: input.noteTemplateVersion,
    },
  });
  if (claimedTemplate.count !== 1) {
    throw new TemplateTwinFillError(
      'TEMPLATE_PROVENANCE_MISMATCH',
      'This visit is already pinned to another note template version.',
    );
  }

  const {
    prepared,
    row,
    compiled,
    ir,
    storage,
    clinicianOverrides,
  } = await readAndPrepareTemplateTwinFill(input);
  const existing = await prisma.templateTwinFillManifest.findUnique({
    where: { visitId: input.visitId },
    select: {
      id: true,
      status: true,
      signedDecisionAt: true,
      reviewedAt: true,
      manifestVersion: true,
      manifestSha256: true,
      // F24-S5 — read so the no-op short-circuit below can compare it.
      overridesSha256: true,
      roundTripVerified: true,
    },
  });
  if (
    existing &&
    (existing.status === 'SIGNED' || existing.signedDecisionAt !== null)
  ) {
    throw new TemplateTwinFillError(
      'SIGNED_MANIFEST_IMMUTABLE',
      'A signed Template Twin fill manifest cannot be replaced.',
    );
  }
  // ⚠️ F24-S5 — THE NO-OP SHORT-CIRCUIT MUST ALSO AGREE ON THE OVERRIDE HALF.
  //
  // This returns without writing when the prepared manifest is byte-identical
  // to the stored one. `overridesSha256` is stamped in `writeData` BELOW it, so
  // any state where the manifest sha matches while the override identity does
  // NOT would leave the stamp stale forever — and the freshness gates would then
  // read `overrides_changed` on every single export, recompute, short-circuit
  // again, and never converge. At sign time that is not merely churn: the freeze
  // re-fills, re-reads, still fails to match, and returns `refill_did_not_match`
  // — so the visit signs STYLED and that record loses native export permanently.
  //
  // ⚠️ TODAY NO SUCH STATE IS REACHABLE, AND THAT IS EXACTLY WHY THIS GUARD IS
  // HERE. Every override outcome currently perturbs the manifest by accident of
  // design: an APPLIED one changes the resolution and mints a fact, and a
  // DECLINED one appends a `CLINICIAN_OVERRIDE_DECLINED` warning to
  // `validation`. So "override set changed ⇒ manifest sha changed" holds — as an
  // EMERGENT COUPLING between three unrelated code paths, not as a guarantee.
  // A later tidy-up that stops emitting the declined warning would break it
  // silently, and the failure would surface as a styled signature on a real
  // doctor's record. Comparing the identity directly costs one term and removes
  // the dependency on that coincidence.
  //
  // ⚠️ AND IT CONVERGES FOR A LEGACY MANIFEST RATHER THAN CHURNING. A NULL
  // stamp never equals `overridesIdentity([])`, so the first fill after this
  // ships REWRITES the row to acquire its stamp — and every fill after that
  // short-circuits normally. One extra write, once, and then stable. Production
  // is unaffected either way: both existing NULL-stamped manifests are on SIGNED
  // visits, which throw `SIGNED_MANIFEST_IMMUTABLE` several lines above this.
  if (
    existing?.manifestSha256 === prepared.manifestSha256 &&
    existing.overridesSha256 === overridesIdentity(clinicianOverrides) &&
    (prepared.render === null || existing.roundTripVerified)
  ) {
    return prepared;
  }
  if (existing?.reviewedAt != null) {
    throw new TemplateTwinFillError(
      'MANIFEST_CONFLICT',
      'A clinician-reviewed Template Twin fill cannot be replaced by a worker retry.',
    );
  }

  const storedOutput = prepared.render
    ? await storage.storeOutputArtifact({
        practiceId: input.tenantPracticeId,
        visitId: input.visitId,
        manifestSha256: prepared.manifestSha256,
        bytes: prepared.render.document,
      })
    : null;
  // A DOCUMENT WITH NOTHING IN IT IS NOT A DOCUMENT.
  // A fill that resolves no field at all validates trivially — there is no
  // populated value to object to — so it produced a VERIFIED manifest and the
  // export returned the doctor's blank form as if it were their note. That is
  // the silent-empty-document failure this whole chain exists to prevent, and it
  // reached the export seam wearing a success flag. Certification has carried a
  // fill-coverage floor since it hit the same thing; visit time needs one too.
  const status = prepared.render && prepared.manifest.counts.filled > 0 ? 'VERIFIED' : 'NEEDS_REVIEW';
  if (prepared.render && prepared.manifest.counts.filled === 0) {
    console.warn(
      `[template-twin:fill] NOTHING FILLED visit=${input.visitId} compiled=${compiled.id}; ` +
        'native export withheld, styled export stands',
    );
  }
  const writeData = {
    compiledVersionId: compiled.id,
    noteTemplateId: row.id,
    noteTemplateVersion: row.version,
    compilerVersion: ir.compilerVersion,
    resolverVersion: TEMPLATE_TWIN_RESOLVER_VERSION,
    resolverModelVersion: input.resolverModelVersion,
    rendererVersion: TEMPLATE_TWIN_RENDERER_VERSION,
    status,
    fillManifest: asJson(prepared.manifest),
    manifestSha256: prepared.manifestSha256,
    factSetSha256: prepared.factSetSha256,
    validationResult: asJson(prepared.manifest.validation),
    filledCount: prepared.manifest.counts.filled,
    needsReviewCount: prepared.manifest.counts.needsReview,
    notMentionedCount: prepared.manifest.counts.notMentioned,
    conflictCount: prepared.manifest.counts.conflicts,
    criticalUnresolvedCount: prepared.manifest.counts.criticalUnresolved,
    outputObjectKey: storedOutput?.objectKey ?? null,
    outputSha256: storedOutput?.sha256 ?? null,
    outputMimeType: storedOutput?.mimeType ?? null,
    outputSizeBytes: storedOutput?.sizeBytes ?? null,
    staticContentSha256: prepared.render ? ir.staticContentSha256 : null,
    // ⚠️ THE NOTE THIS FILL RAN AGAINST — stamped ONCE here, so both the
    // `updateMany` and the `create` below inherit it. The serve path recomputes
    // it from the visit's CURRENT note and declines a mismatch; without it a
    // VERIFIED manifest was served forever and a doctor's edit could silently
    // fail to reach their own download.
    noteSha256: noteIdentity(input.generatedNote),
    // ⚠️ F24-S5 — THE OTHER HALF OF THE BOUND IDENTITY, STAMPED FROM THE LIST
    // THIS FILL ACTUALLY USED, never from a fresh read.
    //
    // Without it, `noteSha256` alone could not see a form-control correction —
    // an override never touches `soapFinal` — so every gate keyed on the note
    // read `match`, the stored pre-override bytes were served, and signing
    // pinned the pre-override manifest forever.
    //
    // ⚠️ ALWAYS NON-NULL ON A MANIFEST WRITTEN FROM HERE, INCLUDING WHEN THERE
    // ARE NO OVERRIDES — `overridesIdentity([])` is a real hash, not null. NULL
    // is reserved for manifests that predate the migration, and the gate asserts
    // this write never produces one: a forgotten stamp would silently restore
    // the "unknown" meaning that the null-is-empty rule depends on being
    // impossible.
    overridesSha256: overridesIdentity(clinicianOverrides),
    roundTripVerified: prepared.render?.verification.verified === true,
    roundTripVerification: prepared.render
      ? asJson(prepared.render.verification)
      : Prisma.JsonNull,
  } as const;

  // ⚠️ A SIGNED VISIT NEVER RECEIVES A MANIFEST — RE-CHECKED HERE, AT THE WRITE.
  //
  // The sign-time freeze bounds its WAIT with `Promise.race`, which cannot
  // CANCEL the fill. An orphaned fill therefore keeps running and could land a
  // manifest AFTER the signature — making the signature's own audit row assert
  // a downgrade that did not happen, and handing out a document the signed
  // record never froze.
  //
  // The manifest-level guards below key on the MANIFEST's status, not the
  // VISIT's, so they do not catch it. This does. The read is deliberately as
  // late as possible: it narrows the window to the write itself rather than
  // pretending to close it at the top of a long fill.
  //
  // ⚠️ AND THE DISCARD IS LOUD. A silently dropped fill is indistinguishable
  // from one that never ran; the audit row makes the orphan's landing a
  // RECORDED NON-EVENT, so the sign-time record stays true.
  // ⚠️ PRACTICE-SCOPED, not a system-context read. The engine already holds the
  // practice; reading a clinical row without it would have widened T5's
  // system-context allowlist for no reason — and the allowlist gate caught it
  // going 1 -> 2 on this file, which is exactly its job.
  const visitNow = await prisma.transcribeVisit.findFirst({
    where: visitByIdScope(input.visitId, asPracticeId(input.tenantPracticeId)),
    select: { status: true, signedAt: true },
  });
  if (visitNow?.status === 'SIGNED' || visitNow?.signedAt != null) {
    console.info(
      `[template-twin:fill] DISCARDED post-signature visit=${input.visitId} ` +
        `compiled=${compiled.id} — a signed record is one frozen object`,
    );
    await logAudit({
      // ⚠️ AN EXISTING ACTION, DELIBERATELY. A new AuditAction value is THREE
      // edits — the TS union, the Prisma enum, and its own Postgres migration —
      // and this repo has shipped that half-done twice, each time with the
      // write failing silently at runtime while tsc and prisma validate stayed
      // green. `TEMPLATE_TWIN_SIGN_BLOCKED` already means "the signature state
      // refused a twin operation", which is exactly this. The distinguishing
      // detail lives in the metadata.
      action: 'TEMPLATE_TWIN_SIGN_BLOCKED',
      targetType: 'TranscribeVisit',
      targetId: input.visitId,
      userId: input.authorUserId,
      practiceId: input.tenantPracticeId,
      metadata: {
        fill_discarded_post_signature: true,
        compiledVersionId: compiled.id,
      },
    }).catch(() => {});
    throw new TemplateTwinFillError(
      // Reusing the code this engine already raises for the same refusal.
      'SIGNED_MANIFEST_IMMUTABLE',
      'The visit was signed while this fill was running; the result is discarded.',
    );
  }

  if (existing) {
    // Signing and clinician correction both use optimistic claims. The worker
    // must claim the exact unsigned row it observed; a signed or concurrently
    // replaced row produces no update and remains untouched.
    const updated = await prisma.templateTwinFillManifest.updateMany({
      where: {
        id: existing.id,
        // The VISIT's state, enforced by the database rather than by the read
        // above alone — that read and this write are not atomic together.
        visit: { status: { not: 'SIGNED' } },
        status: { not: 'SIGNED' },
        signedDecisionAt: null,
        reviewedAt: null,
        manifestVersion: existing.manifestVersion,
        manifestSha256: existing.manifestSha256,
      },
      data: {
        ...writeData,
        manifestVersion: { increment: 1 },
      },
    });
    if (updated.count !== 1) {
      const current = await prisma.templateTwinFillManifest.findUnique({
        where: { visitId: input.visitId },
        select: { status: true, signedDecisionAt: true },
      });
      if (
        current &&
        (current.status === 'SIGNED' || current.signedDecisionAt !== null)
      ) {
        throw new TemplateTwinFillError(
          'SIGNED_MANIFEST_IMMUTABLE',
          'A signed Template Twin fill manifest cannot be replaced.',
        );
      }
      throw new TemplateTwinFillError(
        'MANIFEST_CONFLICT',
        'The Template Twin fill changed concurrently and was not replaced.',
      );
    }
  } else {
    try {
      // ⚠️ THE CREATE PATH NEEDS ITS OWN GUARD — a relation filter is only
      // available to `updateMany`.
      //
      // The pre-write visit read above is NOT atomic with this insert, and the
      // aimed TOCTOU pass demonstrated the window: an orphaned fill whose wait
      // the sign-freeze abandoned can pass the read, the signature can land,
      // and the insert can then create a manifest on an already-SIGNED visit.
      // The update branch is protected by `visit: { status: { not: 'SIGNED' } }`;
      // this branch had nothing.
      //
      // SERIALIZABLE, and only around these two statements. The check and the
      // insert must be one indivisible act, and this is the smallest scope that
      // makes them one.
      await prisma.$transaction(
        async (tx) => {
          const still = await tx.transcribeVisit.findFirst({
            where: { id: input.visitId, practiceId: input.tenantPracticeId },
            select: { status: true, signedAt: true },
          });
          if (still?.status === 'SIGNED' || still?.signedAt != null) {
            throw new TemplateTwinFillError(
              'SIGNED_MANIFEST_IMMUTABLE',
              'The visit was signed while this fill was running; the result is discarded.',
            );
          }
          await tx.templateTwinFillManifest.create({
            data: {
              practiceId: input.tenantPracticeId,
              visitId: input.visitId,
              ...writeData,
            },
          });
        },
        { isolationLevel: Prisma.TransactionIsolationLevel.Serializable },
      );
    } catch (error) {
      if (
        error instanceof Prisma.PrismaClientKnownRequestError &&
        (error.code === 'P2002' || error.code === 'P2034')
      ) {
        throw new TemplateTwinFillError(
          'MANIFEST_CONFLICT',
          'Another worker created the Template Twin fill first.',
          error,
        );
      }
      throw error;
    }
  }

  if (prepared.render) {
    await logAudit({
      action: 'TEMPLATE_TWIN_RENDER_VERIFIED',
      targetType: 'TranscribeVisit',
      targetId: input.visitId,
      userId: input.authorUserId,
      practiceId: input.tenantPracticeId,
      metadata: {
        compiledVersionId: compiled.id,
        templateVersion: row.version,
        rendererVersion: prepared.render.rendererVersion,
        outputSha256: prepared.render.outputSha256,
        fieldCount: prepared.manifest.counts.filled,
      },
    });
  }
  return prepared;
}
