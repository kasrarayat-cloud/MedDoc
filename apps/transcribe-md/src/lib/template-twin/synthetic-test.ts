// ============================================================================
// Template Twin — certify-time SYNTHETIC TEST (Phase 2b). Runs an INJECTED
// TwinEntityExtractor (this module never imports the worker pipeline) over
// physician-supplied synthetic evidence -> fill -> native render -> persist the
// proof that certification binds. PHI-gated (synthetic-evidence-gate); prisma
// singleton + injectable storage + logTwinAudit only.
// ============================================================================
import { createHash } from 'node:crypto';

import { Prisma } from '@prisma/client';
import prisma from '@meddoc/db';

import { logTwinAudit as logAudit } from './twin-audit';

import { prepareTemplateTwinFill } from './fill-engine';
import {
  projectEncounterFacts,
  type EncounterEntitySnapshot,
} from './encounter-facts';
import {
  SemanticMappingSchema,
  TemplateDocIRSchema,
  type EncounterFact,
  type SemanticMapping,
} from './ir';
import { templateTwinMappingsSha256 } from './mapping-hash';
import {
  createTemplateTwinArtifactStore,
  type TemplateTwinArtifactStore,
} from './storage';
import type { TemplateTwinActor } from './certification-lifecycle';
import type { DerivedEncounter } from './verification-encounter';
import { readTemplateTwinWorkspace } from './workspace-read';
import { assertTemplateTwinSyntheticEvidencePhiFree } from './synthetic-evidence-gate';
import { residualPlaceholdersInDocx } from './residual-token-scan';
import { residualPlaceholders, unregisteredPlaceholders } from './scaffold-text';
import { docxToTextWithControls } from '@/lib/note-template-parse/docx-content-controls';

/** Injected entity-extraction seam — synthetic-test never imports the worker
 *  clinical pipeline. The caller (certify route / QA harness) supplies an
 *  adapter over the live L3 extractor; the returned shape is Layer3Output. */
export interface TwinEntityExtractor {
  (input: {
    mode: 'text' | 'dictation';
    text: string;
    practiceId: string;
    userId: string;
    noteTemplateId: string;
  }): Promise<{ entities: unknown; contextText: string }>;
}

/** Injected NOTE-GENERATION seam — same reason as TwinEntityExtractor: this
 *  module never imports the worker clinical pipeline. The caller supplies an
 *  adapter over the live constrained-fill generator (CHOICE_SLOT over the
 *  template's enumerated options).
 *
 *  WHY certification needs it: the proof must exercise the SAME fill path a
 *  real visit uses. processTemplateTwinVisit derives markerText from the
 *  verified source and passes generatedNote, so prepareTemplateTwinFill runs
 *  bridgeTemplateFill (the picks -> IR bridge). The synthetic test passed
 *  neither, so it fell through to the resolver-only baseline — attesting a
 *  path production does not take. */
export interface TwinNoteGenerator {
  (input: {
    encounterText: string;
    noteTemplateId: string;
    practiceId: string;
    userId: string;
    /** L3 output for this encounter, already computed here — passed through so
     *  the generator does not pay for extraction a second time. */
    entities: unknown;
    roleLabeledTranscript: string;
  }): Promise<string>;
}

// Re-exported so every existing importer is unchanged. The DEFINITION lives in
// `./synthetic-test-error` — a leaf module, because importing this file drags
// prisma, storage and the docx parser in, and that made the error's own shape
// untestable. See the header there.
export { TemplateTwinSyntheticTestError } from './synthetic-test-error';
import { TemplateTwinSyntheticTestError } from './synthetic-test-error';
import { collectUnready } from './mappings-readiness';

interface MappingRow {
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

function mapping(fieldId: string, row: MappingRow): SemanticMapping {
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
 * ⚠️ #247 — A `visit_record` FACT CAN NEVER REACH A CERTIFICATION MANIFEST.
 *
 * The certification artifact is retained, re-verified and shown; the ruling is
 * that it NEVER contains a real name. A `visit_record` fact is by definition a
 * value read off the patient record, so its presence would mean a real
 * identifier had entered the one artifact that must stay synthetic.
 *
 * ⚠️ DETERMINISTIC, AND DELIBERATELY NOT LEFT TO THE PHI SCAN. That scan is a
 * conservative MODEL judgement over evidence TEXT; this is a structural fact
 * about provenance that needs no judgement and cannot be talked out of. They
 * answer different questions, and the cheap one is the reliable one.
 *
 * ⚠️ AND IT IS A GUARD RATHER THAN A COMMENT BECAUSE TODAY'S SAFETY IS
 * INCIDENTAL: this path simply passes no visit record, so nothing injects. The
 * day somebody threads one through for a good reason, this refuses instead of
 * silently certifying against a real patient's name.
 *
 * EXPORTED so its arm can drive the shipped predicate rather than restate it —
 * a control that re-implements the thing under test measures itself.
 */
export function assertNoRecordDerivedFacts(
  facts: ReadonlyArray<EncounterFact>,
): void {
  const recordDerived = facts.filter((f) => f.sourceType === 'visit_record');
  if (recordDerived.length === 0) return;
  throw new TemplateTwinSyntheticTestError(
    'SYNTHETIC_EVIDENCE_REJECTED',
    'A record-derived fact reached the certification test. The certification artifact must never contain patient-record values.',
    // `blocking` is the existing detail channel. It names WHICH facts arrived
    // and never copies a value, so the refusal itself cannot leak one.
    { blocking: recordDerived.map((f) => `${f.factId}:${f.concept}`) },
  );
}

// #326 — the shared synthetic front-half lives in a LIGHT module so the
// detected-form certify can reuse it without pulling this heavy graph. Imported
// for local use here AND re-exported so existing callers of synthetic-test keep
// resolving it.
import { deriveSyntheticEncounter } from './synthetic-front-half';
export { deriveSyntheticEncounter };

export async function runTemplateTwinSyntheticTest(input: {
  noteTemplateId: string;
  actor: TemplateTwinActor;
  expectedMappingsSha256: string;
  /**
   * THE ENCOUNTER, LAZILY — F5-i.
   *
   * ⚠️ IT IS A THUNK BECAUSE THE ORDER MATTERS, AND THE ORDER BELONGS HERE
   * RATHER THAN IN EACH CALLER. `deriveVerificationEncounter` reads every
   * field's `clinicalConcept`, and `unreadyReason` (mappings-readiness.ts:69)
   * refuses any non-manual field that HAS no concept. So while mappings are
   * unready the derivation is reading an INCOMPLETE field set, and a refusal
   * computed from it is not yet a fact about the form:
   *
   *   a doctor can still supply a measurement concept by hand — F5-a's census
   *   leaves 22 of 80 fields unproposed on the real customer form — which turns
   *   a `no_measurement_rows` form into a derivable one.
   *
   * Evaluating it EAGERLY in the caller therefore told a physician "we cannot
   * self-test this kind of form" when the true and actionable answer was
   * "6 of 80 fields still need confirming". That is a false statement about
   * their form, and it stops them doing the work that would unblock it.
   *
   * ⚠️ SO IT IS EVALUATED BELOW THE READINESS GATES AND NOWHERE ELSE. Passing
   * a string would let a caller re-introduce the ordering bug silently; a thunk
   * cannot be evaluated early by accident, and both callers inherit the order
   * instead of each keeping it by hand.
   */
  deriveEncounter: () => DerivedEncounter;
  encounterMode?: 'text' | 'dictation';
  storage?: TemplateTwinArtifactStore;
  /** Injected live-L3 entity extractor (no worker import in this module). */
  extractEntities: TwinEntityExtractor;
  /** Injected live note generator. When supplied, the proof exercises the
   *  picks -> IR bridge exactly as a real visit does. Optional so existing
   *  callers keep their current (resolver-only) behaviour unchanged. */
  generateNote?: TwinNoteGenerator;
}) {
  const row = await prisma.noteTemplate.findFirst({
    where: {
      id: input.noteTemplateId,
      doctorId: input.actor.userId,
    },
    select: {
      id: true,
      version: true,
      templateTwinCompiledVersion: {
        select: {
          id: true,
          compiledDocumentIr: true,
          certificationStatus: true,
          structureSha256: true,
          pinnedSyntheticNote: true,
          pinnedSyntheticEntities: true,
          pinnedSyntheticContextText: true,
          pinnedNoteEncounterSha256: true,
          pinnedNoteTemplateSha256: true,
          pinnedNoteModelVersion: true,
          pinnedNoteGeneratedAt: true,
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
  if (
    !row ||
    !compiled ||
    compiled.sourceArtifact.practiceId !== input.actor.practiceId ||
    compiled.sourceArtifact.validationStatus !== 'accepted' ||
    !compiled.sourceArtifact.objectKey
  ) {
    throw new TemplateTwinSyntheticTestError('NOT_FOUND', 'Template Twin version not found.');
  }
  if (compiled.certificationStatus === 'CERTIFIED') {
    throw new TemplateTwinSyntheticTestError(
      'IMMUTABLE',
      'Certified Template Twin versions cannot be retested or changed.',
    );
  }
  // ⚠️ COLLECT, DO NOT THROW ON THE FIRST. This used to throw inside the map
  // on the first field with no mapping row, which made the count UNKNOWABLE —
  // the caller could say "some field is not ready" and never "6 of 80". A
  // physician who has just confirmed 74 fields cannot act on the first
  // sentence and can act on the second. (F16.)
  //
  // The PRECEDENCE is deliberately unchanged: a missing mapping row still
  // beats the CONFLICT check below, exactly as it did when this threw early.
  // Only the completeness of the detail is new.
  //
  // ⚠️ AND IT COUNTS THE WHOLE READINESS PREDICATE, NOT JUST THE MISSING ROWS.
  // My own first draft counted only `!field.mapping` here, which made the
  // number NON-MONOTONE: a form with 3 unmapped and 10 unconfirmed fields
  // would say "3 of 80", and then say "10 of 80" after the physician cleared
  // the 3 — the count going UP as a reward for doing the work. Each figure was
  // true of its own blocker class and the sequence was indefensible. Caught by
  // refuting the change before pushing it, not by a test.
  // ⚠️ ONE CLASSIFIER, SHARED WITH THE LATE BRANCH. This used to filter on the
  // three-way readiness predicate and then LABEL with a two-way expression, so
  // a CERTIFIED field missing only its clinical concept was reported to the
  // audit row as `:unconfirmed` — a false reason on the one per-field channel
  // this item exists to make legible. Found by the independent adversarial
  // pass; both call sites now reduce to `unreadyReason` in a leaf module that a
  // unit test can actually execute.
  const unreadyBeforeParse = collectUnready(
    compiled.fields.map((field: { fieldId: string; mapping: MappingRow | null }) => ({
      fieldId: field.fieldId,
      mapping: field.mapping
        ? {
            // the ONLY `.toLowerCase()` on this path — see `ReadinessRow`
            status: field.mapping.mappingStatus.toLowerCase(),
            sourceType: field.mapping.sourceType,
            clinicalConcept: field.mapping.clinicalConcept,
          }
        : null,
    })),
  );
  // Only a MISSING ROW may refuse here — the status checks are re-run below on
  // the parsed mappings, and that is where they belong. This branch exists
  // because `mapping()` cannot be called on a null row; the wider count is
  // carried purely so the DETAIL is complete when it does fire.
  if (compiled.fields.some((field: { mapping: MappingRow | null }) => !field.mapping)) {
    throw new TemplateTwinSyntheticTestError(
      'MAPPINGS_NOT_READY',
      'Every field needs a physician-confirmed mapping before testing.',
      { blocking: unreadyBeforeParse, totalFields: compiled.fields.length },
    );
  }
  const mappings = compiled.fields.map((field: { fieldId: string; mapping: MappingRow | null }) => {
    // Narrowing only — the filter above proved every mapping is present.
    if (!field.mapping) {
      throw new TemplateTwinSyntheticTestError(
        'MAPPINGS_NOT_READY',
        'Every field needs a physician-confirmed mapping before testing.',
        { blocking: [`${field.fieldId}:no_mapping`], totalFields: compiled.fields.length },
      );
    }
    return mapping(field.fieldId, field.mapping);
  });
  const mappingsSha256 = templateTwinMappingsSha256(mappings);
  if (mappingsSha256 !== input.expectedMappingsSha256) {
    throw new TemplateTwinSyntheticTestError(
      'CONFLICT',
      'Mappings changed after the page loaded. Reload before testing.',
    );
  }
  // ⚠️ ONE ENTRY PER FIELD, NOT PER REASON. A field can be both unconfirmed
  // and concept-less; counting reasons would report "7 of 80" for six fields
  // and send a physician looking for a seventh that does not exist. The
  // predicate below is byte-identical to the `.some()` it replaces — this
  // changes WHAT IS REPORTED, never WHAT IS REFUSED. (F16.)
  const notReady = collectUnready(
    mappings.map((item: SemanticMapping) => ({ fieldId: item.fieldId, mapping: item })),
  );
  if (notReady.length > 0) {
    throw new TemplateTwinSyntheticTestError(
      'MAPPINGS_NOT_READY',
      'Every field needs a physician-confirmed mapping before testing.',
      { blocking: notReady, totalFields: mappings.length },
    );
  }

  // ⚠️ THE ENCOUNTER IS DERIVED HERE AND NOT ONE LINE EARLIER — F5-i. Every
  // field now has a physician-confirmed mapping AND (except for `manual`
  // fields, which have none by construction) a clinical concept, because the
  // gate immediately above refuses otherwise. Only now is "this generator
  // cannot speak to this form" a fact about the FORM rather than a fact about
  // how much of it has been confirmed. See the `deriveEncounter` doc above.
  // #326 — the ruled encounter derivation + synthetic-evidence PHI gate + the
  // content hash, shared verbatim with the detected-form proof (one function so
  // the order cannot drift). The DOCX-specific IR/TOKEN gate below is unchanged;
  // moving the pure sha ahead of it is byte-identical (sha has no side effect).
  const { encounterText, encounterSha256 } = await deriveSyntheticEncounter({
    deriveEncounter: input.deriveEncounter,
    actor: input.actor,
    totalFields: mappings.length,
  });

  const ir = TemplateDocIRSchema.parse(compiled.compiledDocumentIr);

  // ⚠️ TOKEN-1 STATIC GATE — NON-VACUOUS, unlike the rendered-bytes scan below.
  // The synthetic path inserts NO scaffold default, so scaffolds render blank
  // and the rendered scan sees no brace. But a scaffold whose TEXT carries an
  // UNREGISTERED placeholder ({mrn}, {provider}, …) can never be inserted
  // safely: substitution touches only the closed {patient}/{age} set, so the
  // brace would print verbatim on a real visit. Refuse to certify such a
  // template here, where the scaffold text is still visible. A registered token
  // in a scaffold is fine — it substitutes on insert.
  const scaffoldTokenOffenders = ir.fields.flatMap((field) => {
    const bad = unregisteredPlaceholders(field.scaffoldText ?? '');
    return bad.length > 0 ? [`${field.fieldId}:${bad.join('|')}`] : [];
  });
  // ⚠️ And the PRACTICE-DEFAULT channel: the resolver applies mapping.practiceDefault
  // VERBATIM (resolver/index.ts), never through substitution — so ANY placeholder
  // there prints its braces, a REGISTERED {patient} included. Scan it with
  // residualPlaceholders (all placeholders), not unregisteredPlaceholders.
  const practiceDefaultOffenders = mappings.flatMap((m) => {
    const bad = residualPlaceholders(m.practiceDefault ?? '');
    return bad.length > 0 ? [`${m.fieldId}(practiceDefault):${bad.join('|')}`] : [];
  });
  const tokenOffenders = [...scaffoldTokenOffenders, ...practiceDefaultOffenders];
  if (tokenOffenders.length > 0) {
    throw new TemplateTwinSyntheticTestError(
      'RESIDUAL_TOKEN',
      `A placeholder that cannot be filled from the visit record would print its braces: ${tokenOffenders.join(', ')}. A scaffold may use {patient}/{age}; a practice default may use no placeholder at all.`,
      { residualTokens: tokenOffenders },
    );
  }

  const encounterMode = input.encounterMode ?? 'text';

  // Run the LIVE brain over the synthetic encounter, then recover the compiled
  // {{one of}} marker form from the SAME verified source the IR came from —
  // byte-for-byte what processTemplateTwinVisit does.
  // ── PINNED SYNTHETIC NOTE ────────────────────────────────────────────────
  // Generate ONCE, then reuse. Which sections L4 emits varies between runs, so
  // an unpinned proof made certification a coin flip: one run filled the
  // DIAGNOSIS control, the next left it NEEDS_CLINICIAN_INPUT and blocked.
  // The pin fixes the stochastic INPUT only — the pinned note still goes
  // through bridge -> matcher -> validator -> renderer -> roundtrip exactly as
  // an unpinned one would. Nothing is bypassed and no requirement is relaxed.
  const templateSha256 = compiled.structureSha256;
  // CONTENT-ADDRESSED. The pin belongs to the (encounter, template structure)
  // pair, not to a compiled-version row: re-uploading the same docx makes a NEW
  // compiled version, so a per-row pin would never be reused and determinism
  // could never be demonstrated. Look the pin up by its content hashes.
  let adoptedFromSibling = false;
  let pinned = compiled.pinnedSyntheticNote;
  let pinnedModel = compiled.pinnedNoteModelVersion;
  let pinnedAt = compiled.pinnedNoteGeneratedAt;
  let pinnedEntities =
    compiled.pinnedNoteEncounterSha256 === encounterSha256
      ? compiled.pinnedSyntheticEntities
      : null;
  let pinnedContextText =
    compiled.pinnedNoteEncounterSha256 === encounterSha256
      ? compiled.pinnedSyntheticContextText
      : null;
  if (
    !pinned ||
    compiled.pinnedNoteEncounterSha256 !== encounterSha256 ||
    compiled.pinnedNoteTemplateSha256 !== templateSha256
  ) {
    const sibling = await prisma.templateTwinCompiledVersion.findFirst({
      where: {
        pinnedNoteEncounterSha256: encounterSha256,
        pinnedNoteTemplateSha256: templateSha256,
        pinnedSyntheticNote: { not: null },
      },
      // Newest first, and prefer one that also carries the pinned EXTRACTION.
      // An unordered findFirst kept selecting an older sibling that had only the
      // note, so the extraction was re-run every time and the second half of the
      // determinism guarantee never took effect.
      orderBy: [{ pinnedSyntheticEntities: 'desc' }, { compiledAt: 'desc' }],
      select: {
        pinnedSyntheticNote: true,
        pinnedSyntheticEntities: true,
        pinnedSyntheticContextText: true,
        pinnedNoteModelVersion: true,
        pinnedNoteGeneratedAt: true,
      },
    });
    if (sibling?.pinnedSyntheticNote) {
      adoptedFromSibling = true;
      pinned = sibling.pinnedSyntheticNote;
      pinnedModel = sibling.pinnedNoteModelVersion;
      pinnedAt = sibling.pinnedNoteGeneratedAt;
      pinnedEntities = sibling.pinnedSyntheticEntities;
      pinnedContextText = sibling.pinnedSyntheticContextText;
      // Copy it onto this compiled version so the proof it certifies is stored
      // with it, not borrowed at read time.
      await prisma.templateTwinCompiledVersion.update({
        where: { id: compiled.id },
        data: {
          pinnedSyntheticNote: pinned,
          pinnedSyntheticEntities: pinnedEntities ?? undefined,
          pinnedSyntheticContextText: pinnedContextText,
          pinnedNoteEncounterSha256: encounterSha256,
          pinnedNoteTemplateSha256: templateSha256,
          pinnedNoteModelVersion: pinnedModel,
          pinnedNoteGeneratedAt: pinnedAt,
        },
      });
    }
  }
  // ⚠️ A NOTE IS VALID ONLY IF ITS KEY MATCHES — PRESENCE IS NOT VALIDITY.
  //
  // This read `!!pinned`. The block above correctly identifies a note whose
  // encounter/template sha no longer match, looks for a sibling that does, and
  // — when there is none — falls through with `pinned` STILL HOLDING THE STALE
  // NOTE. Presence alone then made it valid, so the proof ran against a note
  // generated from a DIFFERENT encounter.
  //
  // Measured in production 2026-08-20: the owner's template certified against a
  // note whose `pinnedNoteGeneratedAt` was 2026-08-18T23:19:50Z — two days
  // before the encounter it was keyed to existed. Fills went 7 -> 5 because the
  // stale note was being matched against a changed expectation, and the refusal
  // read as "your form does not fill" when the truth was "the model never saw
  // this encounter".
  const noteKeyMatches =
    compiled.pinnedNoteEncounterSha256 === encounterSha256 &&
    compiled.pinnedNoteTemplateSha256 === templateSha256;
  const pinValid = !!pinned && (adoptedFromSibling || noteKeyMatches);

  // ── PINNED EXTRACTION ────────────────────────────────────────────────────
  // Layer 3 is a model too. Re-extracting per attempt made the identical
  // encounter yield a different fact set every run, so the same template
  // blocked on a different set of fields each time and no two certifications
  // could match. It is pinned beside the note, resolved through the SAME
  // content-addressed lookup, and invalidated by the same encounter hash.
  // The pinned entities still flow through projection -> resolver -> bridge ->
  // matcher -> validator -> renderer -> roundtrip exactly as fresh ones would;
  // only the stochastic INPUT is fixed.
  const extracted =
    pinnedEntities != null && pinnedContextText != null
      ? { entities: pinnedEntities, contextText: pinnedContextText }
      : await input.extractEntities({
          mode: encounterMode,
          text: encounterText,
          practiceId: input.actor.practiceId,
          userId: input.actor.userId,
          noteTemplateId: row.id,
        });
  const extractionReused = pinnedEntities != null && pinnedContextText != null;
  if (!extractionReused) {
    // Pin it NOW, not only when a note is generated. A run that adopts an older
    // note pin skips generation entirely, and pinning only there left the
    // extraction unpinned forever — the run after it extracted fresh again and
    // certification stayed non-reproducible.
    // ⚠️ THIS WRITE STAMPS THE **NOTE'S** KEY WHILE PINNING ONLY THE EXTRACTION,
    // AND THAT IS HOW A STALE NOTE BECOMES PERMANENTLY "CURRENT".
    //
    // One column, `pinnedNoteEncounterSha256`, keys BOTH pins. Pinning a fresh
    // extraction under a new encounter therefore re-keyed the OLD note to the
    // NEW encounter without regenerating it — a write-on-read. Every later run
    // then found the shas equal at :332, skipped invalidation entirely, and
    // served content that does not correspond to its own key. The cache lied
    // about what it held, and nothing downstream could tell.
    //
    // So: when the note does NOT belong to this encounter, it is DROPPED in the
    // same statement that re-keys the extraction. The key then describes what
    // the row actually holds. A missing note is regenerated on the next line;
    // a mislabelled one is undetectable forever.
    await prisma.templateTwinCompiledVersion.update({
      where: { id: compiled.id },
      data: {
        pinnedSyntheticEntities: asJson(extracted.entities),
        pinnedSyntheticContextText: extracted.contextText,
        pinnedNoteEncounterSha256: encounterSha256,
        ...(pinValid
          ? {}
          : {
              pinnedSyntheticNote: null,
              pinnedNoteGeneratedAt: null,
              pinnedNoteModelVersion: null,
              pinnedNoteTemplateSha256: null,
            }),
      },
    });
  }
  console.info(
    `[template-twin:pin] EXTRACTION ${extractionReused ? 'REUSED' : 'FRESH'} ` +
      `compiled=${compiled.id} encounterSha=${encounterSha256.slice(0, 12)}`,
  );
  const facts = projectEncounterFacts({
    mode: encounterMode,
    contextText: extracted.contextText,
    entities: extracted.entities as unknown as EncounterEntitySnapshot,
    asrQuality: 'unknown',
  });
  const storage = input.storage ?? createTemplateTwinArtifactStore();
  const source = await storage.readSourceArtifact({
    practiceId: input.actor.practiceId,
    objectKey: compiled.sourceArtifact.objectKey,
    expectedSha256: compiled.sourceArtifact.sha256,
    expectedSizeBytes: compiled.sourceArtifact.sizeBytes,
  });

  let generatedNote: string | undefined;
  let markerText: string | undefined;
  if (pinValid) {
    generatedNote = pinned!;
    markerText = (await docxToTextWithControls(source)).text;
    console.info(
      `[template-twin:pin] REUSED compiled=${compiled.id} encounterSha=${encounterSha256.slice(0, 12)} ` +
        `templateSha=${String(templateSha256).slice(0, 12)} model=${pinnedModel} ` +
        `generatedAt=${pinnedAt?.toISOString()}`,
    );
  } else if (input.generateNote) {
    generatedNote = await input.generateNote({
      encounterText: encounterText,
      noteTemplateId: row.id,
      practiceId: input.actor.practiceId,
      userId: input.actor.userId,
      entities: extracted.entities,
      roleLabeledTranscript: extracted.contextText,
    });
    markerText = (await docxToTextWithControls(source)).text;
    // Pin it, with the provenance that decides when it must be regenerated.
    await prisma.templateTwinCompiledVersion.update({
      where: { id: compiled.id },
      data: {
        pinnedSyntheticNote: generatedNote,
        pinnedSyntheticEntities: asJson(extracted.entities),
        pinnedSyntheticContextText: extracted.contextText,
        pinnedNoteEncounterSha256: encounterSha256,
        pinnedNoteTemplateSha256: templateSha256,
        pinnedNoteModelVersion:
          process.env.TRANSCRIBE_MD_CLINICAL_MODEL || 'claude-opus-4-8',
        pinnedNoteGeneratedAt: new Date(),
      },
    });
    console.info(
      `[template-twin:pin] CREATED compiled=${compiled.id} encounterSha=${encounterSha256.slice(0, 12)} ` +
        `templateSha=${String(templateSha256).slice(0, 12)}`,
    );
  }
  // ⚠️ #247 — A `visit_record` FACT CAN NEVER REACH A CERTIFICATION MANIFEST.
  //
  // The certification artifact is retained, shown and re-verified; the ruling is
  // that it NEVER contains a real name. A `visit_record` fact is by definition a
  // value read off the patient record, so its presence here would mean a real
  // identifier had entered the one artifact that must stay synthetic.
  //
  // ⚠️ DETERMINISTIC, AND DELIBERATELY NOT LEFT TO THE PHI SCAN. The scan above
  // is a conservative MODEL judgement over evidence TEXT; this is a structural
  // fact about provenance that needs no judgement and cannot be talked out of.
  // The two answer different questions and the cheap one is the reliable one.
  //
  // It is a guard rather than a comment because the current safety is
  // incidental: this path simply passes no visit record today, so nothing
  // injects. The day someone threads one through for a good reason, this
  // refuses instead of silently certifying against a real patient's name.
  assertNoRecordDerivedFacts(facts);

  const prepared = await prepareTemplateTwinFill({
    compiledVersionId: compiled.id,
    noteTemplateId: row.id,
    noteTemplateVersion: row.version,
    ir,
    mappings,
    facts,
    source,
    markerText,
    generatedNote,
    resolverModelVersion:
      process.env.TRANSCRIBE_MD_CLINICAL_MODEL || 'claude-sonnet-4-6',
    validationNow: new Date(),
    allowUncertifiedForSyntheticTest: true,
  });
  // ⚠️ #247 STAGE B — AND THE CHECK ABOVE WAS ON THE WRONG SIDE OF THE CALL.
  //
  // `assertNoRecordDerivedFacts(facts)` guards this function's INPUT, which is
  // where a record fact could arrive from a caller. It cannot see a fact
  // `prepareTemplateTwinFill` INJECTS — and injection is precisely what family
  // 3 added: `withVisitMetadataFacts` mints `visit_record` facts inside that
  // call, one layer below this one. Stage A's guard was true and was measuring
  // the half that was never going to break.
  //
  // The ruling's words are "a `visit_record` fact can never reach a
  // CERTIFICATION MANIFEST", so the manifest is what gets asserted. Today this
  // passes because no patient record is threaded here; the guard exists for the
  // day somebody threads one, and it is the artifact — not the argument about
  // the artifact — that it reads.
  //
  // Both are kept. The input check fails EARLY and names the caller's fault;
  // this one is the invariant the ruling actually stated.
  assertNoRecordDerivedFacts(prepared.manifest.facts);
  if (!prepared.render) {
    const blocking = prepared.manifest.validation.issues.filter(
      (issue) => issue.severity === 'blocking',
    );
    // Name them. Counting blockers without saying WHICH is the same opacity the
    // certification gate had: it tells the physician a test failed but not what
    // to add to their synthetic encounter, so the only way forward is guessing.
    // Field ids and issue codes only — never the encounter text or a filled
    // value, so this stays safe to log.
    console.warn(
      `[template-twin:synthetic] BLOCKED compiled=${compiled.id}: ` +
        blocking
          .map((issue) => `${issue.fieldId ?? 'field?'}:${issue.code ?? 'issue?'}`)
          .join(', '),
    );
    throw new TemplateTwinSyntheticTestError(
      'VALIDATION_FAILED',
      `The synthetic encounter left ${blocking.length} blocking field check${blocking.length === 1 ? '' : 's'}. Add direct synthetic evidence or correct the mapping, then test again.`,
      { blocking: blocking.map((issue) => `${issue.fieldId ?? 'field?'}:${issue.code ?? 'issue?'}`) },
    );
  }
  const render = prepared.render;

  // ⚠️ TOKEN-1 GATE — no brace placeholder may reach the certified document.
  // The blank-proof machinery only ever tests source/write BYTE-IDENTITY, so a
  // surviving `{patient}`/`{age}` (or any `{word}`) is invisible to every proof
  // kind. This scans the rendered bytes across all parts and refuses to certify
  // a template whose output still carries one. It is content-inspection, which
  // no proof does.
  const residualTokens = await residualPlaceholdersInDocx(render.document);
  if (residualTokens.length > 0) {
    throw new TemplateTwinSyntheticTestError(
      'RESIDUAL_TOKEN',
      `The rendered document still carries unresolved placeholder${
        residualTokens.length === 1 ? '' : 's'
      } ${residualTokens.join(', ')}. A scaffold token must be substituted from the visit record or the field must render blank — braces never print.`,
      { residualTokens },
    );
  }

  const output = await storage.storeOutputArtifact({
    practiceId: input.actor.practiceId,
    visitId: `synthetic_${compiled.id}`,
    manifestSha256: prepared.manifestSha256,
    bytes: render.document,
  });

  await prisma.$transaction(
    async (tx: Prisma.TransactionClient) => {
      const fresh = await tx.templateTwinCompiledVersion.findUnique({
        where: { id: compiled.id },
        select: {
          certificationStatus: true,
          fields: {
            orderBy: { displayOrder: 'asc' },
            select: {
              fieldId: true,
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
      });
      if (!fresh || fresh.certificationStatus === 'CERTIFIED') {
        throw new TemplateTwinSyntheticTestError('IMMUTABLE', 'This template is already certified.');
      }
      const freshMappings = fresh.fields.map((field: { fieldId: string; mapping: MappingRow | null }) => {
        if (!field.mapping) {
          throw new TemplateTwinSyntheticTestError('CONFLICT', 'Mappings changed during the test.');
        }
        return mapping(field.fieldId, field.mapping);
      });
      if (templateTwinMappingsSha256(freshMappings) !== mappingsSha256) {
        throw new TemplateTwinSyntheticTestError('CONFLICT', 'Mappings changed during the test.');
      }
      await tx.templateTwinCompiledVersion.update({
        where: { id: compiled.id },
        data: {
          latestSyntheticTestManifest: asJson(prepared.manifest),
          latestTestMappingsSha256: mappingsSha256,
          latestTestOutputObjectKey: output.objectKey,
          latestTestOutputSha256: output.sha256,
          latestTestStaticContentSha256: ir.staticContentSha256,
          latestTestRoundTrip: asJson(render.verification),
          latestTestVerifiedAt: new Date(),
        },
      });
    },
    { isolationLevel: 'Serializable' },
  );

  await logAudit({
    action: 'TEMPLATE_TWIN_SYNTHETIC_TESTED',
    targetType: 'TemplateTwinCompiledVersion',
    targetId: compiled.id,
    userId: input.actor.userId,
    userEmail: input.actor.userEmail,
    practiceId: input.actor.practiceId,
    metadata: {
      templateVersion: row.version,
      mappingsSha256,
      outputSha256: output.sha256,
      fieldCount: prepared.manifest.fields.length,
      verified: true,
      inputMode: encounterMode,
    },
  });
  const workspace = await readTemplateTwinWorkspace({
    noteTemplateId: row.id,
    doctorId: input.actor.userId,
    practiceId: input.actor.practiceId,
  });
  if (!workspace) {
    throw new TemplateTwinSyntheticTestError('NOT_FOUND', 'Template Twin version not found.');
  }
  return workspace;
}
