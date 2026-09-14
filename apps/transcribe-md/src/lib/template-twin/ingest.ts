// ============================================================================
// RULING #274 — THE INGEST ENTRY POINT: the I/O half, DELEGATED.
// ----------------------------------------------------------------------------
// The PURE half — `identityKeys`, `planTransfer`, and the measurement that
// decided them — lives in `./ingest-plan`, so its arms need no database.
//
// ══ WHY THIS IS FOUR STEPS AND NOT ONE TRANSACTION ═════════════════════════
//
// The first version of this file did the whole thing itself in a single
// `$transaction`. A refutation pass found EIGHT defects in that half, and the
// shape of them is the argument: every one was a job `createTemplateTwinDraft`
// already does correctly and this file re-did badly.
//
//   · the bytes were NEVER STORED — the artifact row pointed at an object that
//     did not exist, under a key the ownership parser cannot even read
//   · no PHI gate, where the upload path enforces one
//   · zero audit rows, for an act that mints a template and copies certified
//     clinical dispositions across
//   · `sections: []`, re-opening a documented 2026-07-25 generation defect
//   · a demotion that was REPORTED and never performed
//
// Owner ruling: DELEGATE, and re-scope atomicity to the act that matters.
//
//   (1) PURE GUARDS      — artifact sha, and the identity plan. No writes.
//   (2) MINT             — through `createTemplateTwinDraft`: storage, PHI
//                          gate, audit rows, sections bridge, and the ONE
//                          column writer. Produces a DRAFT, inactive, exactly
//                          what any upload produces today.
//   (3) APPLY TRANSFER   — idempotent and resumable, its own guards.
//   ... the owner confirms, then certification runs ...
//   (4) ACTIVATE         — THE one atomic transaction: demote the old template
//                          and activate the new, together or not at all.
//
// ⚠️ EVERY STATE BETWEEN THE STEPS IS INERT. A failure anywhere before (4)
// leaves a draft nobody can fill from — no visit resolves against it, nothing
// was demoted, nothing activated. That is strictly safer than one transaction
// that got storage, audit and demotion wrong, which is what the single-
// transaction version actually was.
// ============================================================================
import { createHash } from 'node:crypto';

import { prisma } from '@meddoc/db';

import { compileTemplateDocx } from '../note-template-docx';

import { fromPersistedMapping } from './certification-lifecycle';
import { createTemplateTwinDraft } from './create-draft';
import { planTransfer, TemplateTwinIngestRefused, type TransferPlan } from './ingest-plan';
import { type SemanticMapping, type TemplateDocIR } from './ir';

export * from './ingest-plan';

export interface IngestTemplateTwinInput {
  /** The stored artifact's bytes. Read back, never re-derived. */
  source: Uint8Array;
  actor: { userId: string; userEmail: string; practiceId: string };

  /**
   * The compiled version whose CERTIFIED dispositions are carried across. Its
   * IR supplies the identities; its mappings supply the dispositions.
   */
  transferFrom?: string;

  /**
   * Which `sourceType`s carry across. `undefined`/`null` = all of them.
   *
   * ⚠️ A RULED ACT PASSES IT EXPLICITLY. The re-issue transfers `extraction`
   * only — 43 of the 53 certified rows — and re-proposes the 10 `manual` ones,
   * because a `manual` field is one the doctor fills by hand and has no
   * extraction rule to carry.
   */
  transferSourceTypes?: ReadonlySet<string> | null;

  /**
   * ⚠️ PRE-GUARDS, ALL CHECKED BEFORE STEP (2) WRITES ANYTHING. The compile is
   * pure — `compiler.ts` holds no `prisma` and no `await` — which is what makes
   * that possible.
   *
   * OPTIONAL because the primitive serves two callers with different
   * strictness, and conflating them breaks one of them:
   *
   *   · THE RE-ISSUE ACT passes both. Its bytes are the pinned artifact, so the
   *     field ids must come back identical; anything else means the compiler
   *     moved under us and the act must not proceed.
   *   · THE UPLOAD PATH passes neither. Its bytes are new by definition, so a
   *     set-equality guard would refuse every legitimate re-upload.
   */
  guards?: {
    expectSourceSha256?: string;
    expectFieldIds?: readonly string[];
    expectTransferCount?: number;
  };
}

export interface IngestTemplateTwinResult {
  noteTemplateId: string;
  sourceSha256: string;
  fieldCount: number;
  transferred: number;
  reproposed: number;
}

function sha256(bytes: Uint8Array): string {
  return createHash('sha256').update(bytes).digest('hex');
}

/** Read a compiled version's certified dispositions, keyed by field id.
 *  Exported so the re-upload transfer path reuses the SAME tenant-checked read
 *  (one reader, #274) rather than a second copy that could drift. */
export async function readCertified(
  compiledVersionId: string,
  practiceId: string,
  /**
   * ⚠️ WHICH `sourceType`s CARRY ACROSS — `null` means ALL, and it is never
   * defaulted for a ruled act.
   *
   * Measured on the owner's certified version `18a7ae19`: **43 `extraction` +
   * 10 `manual`, and ALL FIFTY-THREE are `CERTIFIED`.** So filtering on
   * `mappingStatus` alone transfers 53, while the ruling says *transfer the 43,
   * re-propose the ten*. The split the ruling names is by SOURCE TYPE, not by
   * status, and the two are easy to conflate because one implies the other here.
   *
   * ⚠️ THE DECLARED GUARD IS WHAT CAUGHT IT: `expectTransferCount: 43` would
   * have aborted the act against a plan of 53. A declaration whose numbers come
   * from the ruling rather than from the code is the only thing that can
   * disagree with the code.
   *
   * `transfer-args.ts` already makes `--transfer-source-types` REQUIRED for the
   * standalone transfer tool, and its own comment records why: an empty
   * selection once selected ZERO of 53 and failed closed. Same vocabulary here.
   */
  sourceTypes: ReadonlySet<string> | null,
): Promise<{ ir: TemplateDocIR; certified: Map<string, SemanticMapping> }> {
  const from = await prisma.templateTwinCompiledVersion.findUnique({
    where: { id: compiledVersionId },
    include: { fields: { include: { mapping: true } } },
  });
  if (!from) {
    throw new TemplateTwinIngestRefused({ code: 'TRANSFER_SOURCE_NOT_FOUND', compiledVersionId });
  }
  // ⚠️ TENANCY ON THE READ, NOT ON THE WRITE. Reading another practice's
  // dispositions and copying them into this one is a disclosure even if every
  // subsequent write is scoped correctly — the data has already crossed.
  if (from.practiceId !== practiceId) {
    throw new TemplateTwinIngestRefused({
      code: 'TRANSFER_SOURCE_WRONG_PRACTICE',
      compiledVersionId,
    });
  }
  return {
    ir: from.compiledDocumentIr as unknown as TemplateDocIR,
    certified: new Map(
      from.fields
        .filter(
          (f) =>
            f.mapping !== null &&
            f.mapping.mappingStatus === 'CERTIFIED' &&
            (sourceTypes === null || sourceTypes.has(f.mapping.sourceType)),
        )
        .map((f) => [
          f.fieldId,
          fromPersistedMapping(f.fieldId, f.mapping as Parameters<typeof fromPersistedMapping>[1]),
        ]),
    ),
  };
}

/**
 * STEPS (1)–(3). Guards, mint through the proven path, then apply the transfer.
 *
 * ⚠️ IT DOES NOT ACTIVATE, AND IT DOES NOT CERTIFY. The result is a draft the
 * owner confirms; activation is step (4) and is a separate ruled act.
 */
export async function ingestTemplateTwin(
  input: IngestTemplateTwinInput,
): Promise<IngestTemplateTwinResult> {
  // ── (1) PURE GUARDS ───────────────────────────────────────────────────────
  const actualSha = sha256(input.source);
  const expectedSha = input.guards?.expectSourceSha256;
  if (expectedSha !== undefined && expectedSha !== actualSha) {
    throw new TemplateTwinIngestRefused({
      code: 'SOURCE_SHA_MISMATCH',
      expected: expectedSha,
      actual: actualSha,
    });
  }

  const ir = compileTemplateDocx(input.source);
  if (ir.fields.length === 0) {
    throw new TemplateTwinIngestRefused({ code: 'NO_FILLABLE_FIELDS' });
  }

  const expectIds = input.guards?.expectFieldIds;
  if (expectIds !== undefined) {
    const got = new Set(ir.fields.map((f) => f.fieldId));
    const want = new Set(expectIds);
    const missing = [...want].filter((id) => !got.has(id)).sort();
    const unexpected = [...got].filter((id) => !want.has(id)).sort();
    if (missing.length > 0 || unexpected.length > 0) {
      throw new TemplateTwinIngestRefused({ code: 'FIELD_IDS_NOT_SET_EQUAL', missing, unexpected });
    }
  }

  let plan: TransferPlan = { transferred: [], reproposed: ir.fields.map((f) => f.fieldId) };
  if (input.transferFrom) {
    const source = await readCertified(
      input.transferFrom,
      input.actor.practiceId,
      input.transferSourceTypes ?? null,
    );
    plan = planTransfer({ target: ir, sourceIr: source.ir, certifiedByFieldId: source.certified });
  }

  const expectTransfer = input.guards?.expectTransferCount;
  if (expectTransfer !== undefined && expectTransfer !== plan.transferred.length) {
    throw new TemplateTwinIngestRefused({
      code: 'TRANSFER_COUNT_MISMATCH',
      expected: expectTransfer,
      actual: plan.transferred.length,
    });
  }

  // ── (2) MINT, through the proven path ─────────────────────────────────────
  // ⚠️ NOT RE-IMPLEMENTED HERE, AND THAT IS THE RULING. This call carries the
  // artifact store's put-once content-addressed write, the PHI gate, both audit
  // rows, the sections bridge and `fieldCreateInput`. Re-ingesting identical
  // bytes REUSES the stored object rather than colliding with it — the store is
  // content-addressed and put-once, which is the design and not an accident.
  const minted = await createTemplateTwinDraft({
    source: input.source,
    actor: input.actor,
  });

  // ── (3) APPLY THE TRANSFER — idempotent and resumable ─────────────────────
  const applied = await applyCertifiedTransfer({
    noteTemplateId: minted.noteTemplateId,
    practiceId: input.actor.practiceId,
    plan,
  });

  return {
    noteTemplateId: minted.noteTemplateId,
    sourceSha256: minted.sourceSha256,
    fieldCount: minted.fieldCount,
    transferred: applied,
    reproposed: plan.reproposed.length,
  };
}

/**
 * STEP (3), separately callable so a half-finished ingest can be RESUMED rather
 * than restarted — restarting would mint a second template beside the first.
 *
 * ⚠️ IDEMPOTENT: re-running it over the same target writes the same values and
 * returns the same count. The guards below are what make that safe rather than
 * merely tolerable.
 */
export async function applyCertifiedTransfer(input: {
  noteTemplateId: string;
  practiceId: string;
  plan: TransferPlan;
}): Promise<number> {
  const target = await prisma.templateTwinCompiledVersion.findUnique({
    where: { noteTemplateId: input.noteTemplateId },
    include: { fields: { select: { id: true, fieldId: true, mapping: { select: { id: true } } } } },
  });
  if (!target) {
    throw new TemplateTwinIngestRefused({
      code: 'TRANSFER_SOURCE_NOT_FOUND',
      compiledVersionId: input.noteTemplateId,
    });
  }
  if (target.practiceId !== input.practiceId) {
    throw new TemplateTwinIngestRefused({
      code: 'TRANSFER_SOURCE_WRONG_PRACTICE',
      compiledVersionId: target.id,
    });
  }
  // ⚠️ THE TARGET MUST STILL BE AN UNCERTIFIED DRAFT. Applying a transfer over
  // a version already CERTIFIED would overwrite a physician's ruled
  // dispositions with an older document's — the exact loss this primitive
  // exists to prevent, arriving from the other direction.
  if (target.certificationStatus === 'CERTIFIED') {
    throw new TemplateTwinIngestRefused({
      code: 'TRANSFER_TARGET_ALREADY_CERTIFIED',
      compiledVersionId: target.id,
    });
  }

  const definitionByFieldId = new Map(target.fields.map((f) => [f.fieldId, f]));
  let written = 0;

  await prisma.$transaction(async (tx) => {
    for (const t of input.plan.transferred) {
      const definition = definitionByFieldId.get(t.fieldId);
      // ⚠️ A PLAN ROW WITH NO FIELD IN THE TARGET IS A REFUSAL, NOT A SKIP. It
      // means the plan was derived against a different compile than the one
      // that landed, and transferring the rest would produce a partially
      // certified template nobody declared.
      if (!definition || !definition.mapping) {
        throw new TemplateTwinIngestRefused({ code: 'TRANSFER_PLAN_STALE', fieldId: t.fieldId });
      }
      await tx.templateTwinSemanticMapping.update({
        where: { id: definition.mapping.id },
        data: {
          sourceType: t.mapping.sourceType,
          clinicalConcept: t.mapping.clinicalConcept,
          expectedDataType: t.mapping.expectedDataType,
          polarityBehavior: t.mapping.polarityBehavior,
          temporality: t.mapping.temporality,
          laterality: t.mapping.laterality,
          unitPolicy: t.mapping.unitPolicy,
          approvedSynonyms: t.mapping.approvedSynonyms ?? [],
          required: t.mapping.required,
          blankPolicy: t.mapping.blankPolicy,
          unknownPolicy: t.mapping.unknownPolicy,
          // ⚠️ #192 / #217 — CARRIED, NEVER COERCED. `unmentionedPolicy` absent
          // stays absent (a ruled `omit` read back as "nobody ruled" is a
          // different behaviour), and `conceptScope` is left NULL when absent
          // rather than `[]`, because `[]` is a VALUE and would move the
          // attestation sha of every mapping.
          unmentionedPolicy: t.mapping.unmentionedPolicy ?? null,
          ...(t.mapping.conceptScope && t.mapping.conceptScope.length > 0
            ? { conceptScope: t.mapping.conceptScope }
            : {}),
          // ⚠️ practiceDefault TRANSFERS — owner-ruled. The shared create-time
          // writer hard-codes it to null, which is right at PROPOSAL time (a
          // proposal has no practice default) and silently drops physician-
          // approved clinical content on a TRANSFER.
          ...(t.mapping.practiceDefault !== undefined && t.mapping.practiceDefault !== null
            ? { practiceDefault: t.mapping.practiceDefault }
            : {}),
          mappingStatus: 'CERTIFIED',
        },
      });
      written += 1;
    }
  });

  return written;
}

/**
 * STEP (4) — THE ONE ATOMIC TRANSACTION. Demote the old template and activate
 * the new, together or not at all.
 *
 * ⚠️ THIS IS THE ACT ATOMICITY WAS RE-SCOPED TO. Every earlier step leaves an
 * inert state; this is the only moment where a partial apply is visible to a
 * doctor — two active templates, or none. Both are met as "my form is gone".
 *
 * ⚠️ DEMOTED, NEVER DELETED. The frozen per-visit fill manifests keep pointing
 * at whatever they were filled against, and deletion would break every one of
 * them. The active-template id ROTATING is the established shape — it rotated
 * on the 2026-09-03 transfer and again when `939aa9ea` replaced the 35-control
 * form. Anything holding a template id by literal is a defect, not a constraint
 * on this function.
 */
export async function activateIngestedTemplate(input: {
  noteTemplateId: string;
  demoteNoteTemplateId: string | null;
  practiceId: string;
}): Promise<{ activated: string; demoted: string | null }> {
  return prisma.$transaction(async (tx) => {
    const target = await tx.noteTemplate.findUnique({
      where: { id: input.noteTemplateId },
      select: { id: true, practiceId: true },
    });
    if (!target || target.practiceId !== input.practiceId) {
      throw new TemplateTwinIngestRefused({
        code: 'TRANSFER_SOURCE_WRONG_PRACTICE',
        compiledVersionId: input.noteTemplateId,
      });
    }

    if (input.demoteNoteTemplateId) {
      await tx.noteTemplate.update({
        where: { id: input.demoteNoteTemplateId },
        data: { status: 'archived' },
      });
    }
    await tx.noteTemplate.update({
      where: { id: input.noteTemplateId },
      data: { status: 'active' },
    });

    return { activated: input.noteTemplateId, demoted: input.demoteNoteTemplateId };
  });
}
