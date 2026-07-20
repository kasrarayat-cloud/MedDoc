// ============================================================================
// resolveActiveTemplate — pick the note template L4 should generate against
// ----------------------------------------------------------------------------
// Phase 0: ships DORMANT. Nothing in the pipeline calls this yet, and no
// behavior depends on it. It is written + tested now so Phase 1 can wire it
// into L4 (04-generate-soap.ts) with confidence.
//
// Two pieces, "functional core / imperative shell":
//   - selectTemplate(...)        — PURE. Deterministic fallback-chain logic
//                                  over an already-loaded candidate set.
//                                  Fully unit-tested.
//   - resolveActiveTemplate(...) — thin async wrapper that loads the
//                                  candidate set from the DB then delegates
//                                  to selectTemplate.
//
// Fallback chain (most → least specific):
//   1. the doctor's ACTIVE template whose encounterType matches the request
//   2. the doctor's ACTIVE catch-all template (encounterType === null)
//   3. the SYSTEM DEFAULT (the seeded singleton)
//
// In Phase 0 no doctor has a custom template, so this always resolves to the
// system default — which is exactly today's L4 SOAP format. Hence: zero
// behavior change.
// ============================================================================

import type { NoteTemplate } from '@prisma/client';
import prisma from '@meddoc/db';
import { templateTwinRuntimeEnabled } from '@/lib/runtime-protocol';
import {
  evaluateTemplateTwinRollout,
  pinTemplateTwinRollout,
  type TemplateTwinRolloutToken,
} from '@/lib/template-twin/rollout';
import {
  TEMPLATE_TWIN_STAGING_QA_FIXTURE_SHA256,
  TEMPLATE_TWIN_STAGING_QA_FIXTURE_SIZE_BYTES,
} from '@/lib/template-twin/staging-qa-fixtures';
import { isTemplateTwinStagingQaRequested } from '@/lib/template-twin/staging-qa-gate';
import {
  isTemplateTwinSourceAdmissionCurrent,
  type TemplateTwinSourceAdmissionRecord,
} from '@/lib/template-twin/source-admission';

export interface ResolveTemplateInput {
  /** The signing/owning doctor (User.id). */
  doctorId: string;
  /** Encounter type to match (a specialty / visit-type slug). Null or
   *  omitted = resolve the doctor's catch-all (or the system default). */
  encounterType?: string | null;
}

export interface ResolveVisitTemplateInput extends ResolveTemplateInput {
  /** Exact visit required to prove a pinned staging template has a durable,
   * tenant-bound synthetic QA run. Ordinary templates do not require it. */
  visitId?: string | null;
  /** Existing visit/fill provenance. When present, retries must reuse this
   * exact version even if a newer lineage version has since been activated. */
  pinnedTemplateId?: string | null;
  pinnedTemplateVersion?: number | null;
}

type TemplateWithSourceProvenance = NoteTemplate & {
  templateTwinCompiledVersion?: {
    sourceArtifact: TemplateTwinSourceAdmissionRecord;
  } | null;
};

const TEMPLATE_TWIN_SOURCE_ADMISSION_SELECT = {
  practiceId: true,
  lineageId: true,
  objectVersionId: true,
  objectEtag: true,
  sha256: true,
  sizeBytes: true,
  validationStatus: true,
  quarantineArtifact: {
    select: {
      practiceId: true,
      lineageId: true,
      intakeMode: true,
      sha256: true,
      sizeBytes: true,
      status: true,
      malwareScanEvidence: true,
      metadataMinimizationEvidence: true,
      rejectionCodes: true,
      scannedAt: true,
      admittedAt: true,
    },
  },
} as const;

function isStagingFixtureTemplate(
  template: TemplateWithSourceProvenance,
): boolean {
  const source = template.templateTwinCompiledVersion?.sourceArtifact;
  return (
    source?.sha256 === TEMPLATE_TWIN_STAGING_QA_FIXTURE_SHA256 &&
    source.sizeBytes === TEMPLATE_TWIN_STAGING_QA_FIXTURE_SIZE_BYTES
  );
}

function hasCurrentTemplateTwinSourceAdmission(
  template: TemplateWithSourceProvenance,
): boolean {
  const compiled = template.templateTwinCompiledVersion;
  // Immutable compiled lineage and mutable kind must agree in both
  // directions. A kind-drifted compiled Twin is never an ordinary candidate.
  if (template.templateKind !== 'template_twin_docx') return compiled == null;
  const source = compiled?.sourceArtifact;
  return Boolean(source && isTemplateTwinSourceAdmissionCurrent(source));
}

/** Worker admission result. A Twin selection always carries the exact
 * persisted rollout epoch that authorized that selection; structured
 * templates deliberately carry no Twin token. */
export interface ResolvedVisitTemplateAdmission {
  template: NoteTemplate;
  templateTwinRolloutToken: TemplateTwinRolloutToken | null;
}

export class PinnedTemplateUnavailableError extends Error {
  constructor() {
    super(
      'The note template version already pinned to this visit is unavailable or no longer owned by the visit clinician.'
    );
    this.name = 'PinnedTemplateUnavailableError';
  }
}

export class TemplateTwinWorkerRolloutError extends Error {
  readonly code = 'TEMPLATE_TWIN_ROLLOUT_DISABLED';

  constructor() {
    super('Template Twin is disabled for this practice or by the global kill switch.');
    this.name = 'TemplateTwinWorkerRolloutError';
  }
}

/** Earliest worker boundary: reject a queued/pinned Twin before any provider. */
export function assertTemplateTwinWorkerRuntimeAdmission(
  templateKind: string | null | undefined,
  env: Readonly<Record<string, string | undefined>> = process.env,
): void {
  if (
    templateKind === 'template_twin_docx' &&
    !templateTwinRuntimeEnabled(env)
  ) {
    throw new TemplateTwinWorkerRolloutError();
  }
}

async function admitTemplateTwinForDoctor(
  doctorId: string
): Promise<TemplateTwinRolloutToken | null> {
  try {
    const user = await prisma.user.findUnique({
      where: { id: doctorId },
      select: {
        role: true,
        isActive: true,
        practiceId: true,
        practice: { select: { templateTwinEnabled: true } },
      },
    });
    if (
      !user ||
      !user.isActive ||
      user.role !== 'DOCTOR' ||
      !user.practiceId
    ) {
      return null;
    }
    const processGate = evaluateTemplateTwinRollout({
      practiceEnabled: user.practice.templateTwinEnabled,
    });
    if (!processGate.allowed) return null;
    return await pinTemplateTwinRollout({ practiceId: user.practiceId });
  } catch {
    return null;
  }
}

/**
 * Thrown when the candidate set contains no system-default template. This is
 * an invariant violation — the Phase-0 seed guarantees exactly one row with
 * isSystemDefault = true, and the partial unique index keeps it singular.
 * Surfacing loudly beats silently generating an unstructured note.
 */
export class MissingSystemDefaultTemplateError extends Error {
  constructor() {
    super(
      'No system-default NoteTemplate found in the candidate set. The Phase-0 ' +
        'seed (migration add_note_templates_phase0) must insert exactly one ' +
        'row with isSystemDefault = true.'
    );
    this.name = 'MissingSystemDefaultTemplateError';
  }
}

/**
 * PURE resolver core. Selects the active template from a candidate set per
 * the fallback chain documented above. No I/O — deterministic and directly
 * unit-testable. The caller need not pre-filter: this applies the
 * `status === 'active'` filter itself so the function is self-contained.
 *
 * @throws {MissingSystemDefaultTemplateError} if no system default is present.
 */
export function selectTemplate(
  candidates: readonly NoteTemplate[],
  { doctorId, encounterType = null }: ResolveTemplateInput
): NoteTemplate {
  const active = candidates.filter(
    (t) => t.status === 'active'
  );

  // 1. doctor's template for this exact encounter type (only when a type
  //    was requested — a null request skips straight to the catch-all).
  if (encounterType != null) {
    const exact = active.find(
      (t) => t.doctorId === doctorId && t.encounterType === encounterType
    );
    if (exact) return exact;
  }

  // 2. doctor's catch-all (encounterType === null).
  const doctorDefault = active.find(
    (t) => t.doctorId === doctorId && t.encounterType === null
  );
  if (doctorDefault) return doctorDefault;

  // 3. the seeded system default — terminal fallback. Not required to be
  //    'active'-filtered (it always is), and located across ALL candidates
  //    so a mis-set status can't strand resolution.
  const systemDefault = candidates.find((t) => t.isSystemDefault);
  if (!systemDefault) throw new MissingSystemDefaultTemplateError();
  return systemDefault;
}

/**
 * DB-backed resolver. Loads the doctor's templates + the system default, then
 * delegates to {@link selectTemplate}.
 *
 * DORMANT in Phase 0 — intentionally unreferenced by the pipeline. Phase 1
 * calls this from L4 and records the result into TranscribeVisit
 * .noteTemplateId / .noteTemplateVersion.
 */
export async function resolveActiveTemplate(
  input: ResolveTemplateInput
): Promise<NoteTemplate> {
  return (await resolveActiveTemplateAdmission(input)).template;
}

/** Worker-facing active resolver that preserves Twin rollout admission. */
export async function resolveActiveTemplateAdmission(
  input: ResolveTemplateInput
): Promise<ResolvedVisitTemplateAdmission> {
  const twinRuntimeEnabled = templateTwinRuntimeEnabled(process.env);
  const candidates = (await prisma.noteTemplate.findMany({
    where: {
      OR: [{ doctorId: input.doctorId }, { isSystemDefault: true }],
      ...(twinRuntimeEnabled
        ? {}
        : { templateKind: { not: 'template_twin_docx' } }),
    },
    include: {
      templateTwinCompiledVersion: {
        select: {
          sourceArtifact: { select: TEMPLATE_TWIN_SOURCE_ADMISSION_SELECT },
        },
      },
    },
  })) as TemplateWithSourceProvenance[];
  const stagingQaRequested = isTemplateTwinStagingQaRequested();
  const ordinaryCandidates = candidates.filter(
    (template) =>
      (twinRuntimeEnabled || template.templateKind !== 'template_twin_docx') &&
      hasCurrentTemplateTwinSourceAdmission(template) &&
      !isStagingFixtureTemplate(template) &&
      (!stagingQaRequested || template.templateKind !== 'template_twin_docx'),
  );
  const preferred = selectTemplate(ordinaryCandidates, input);
  if (preferred.templateKind !== 'template_twin_docx') {
    return { template: preferred, templateTwinRolloutToken: null };
  }
  const token = await admitTemplateTwinForDoctor(input.doctorId);
  if (token) {
    return { template: preferred, templateTwinRolloutToken: token };
  }
  const eligible = ordinaryCandidates.filter(
    (template) => template.templateKind !== 'template_twin_docx'
  );
  return {
    template: selectTemplate(eligible, input),
    templateTwinRolloutToken: null,
  };
}

/**
 * Retry-safe visit resolver. A visit with no provenance uses the normal active
 * fallback chain. Once L4 or Template Twin has pinned a template, every retry
 * loads that exact row and version without requiring it to remain active.
 */
export async function resolveVisitTemplate(
  input: ResolveVisitTemplateInput
): Promise<NoteTemplate> {
  return (await resolveVisitTemplateAdmission(input)).template;
}

/** Retry-safe worker resolver that preserves Twin admission provenance. */
export async function resolveVisitTemplateAdmission(
  input: ResolveVisitTemplateInput
): Promise<ResolvedVisitTemplateAdmission> {
  const hasId = Boolean(input.pinnedTemplateId);
  const hasVersion = input.pinnedTemplateVersion != null;
  if (hasId !== hasVersion) throw new PinnedTemplateUnavailableError();
  if (!hasId) return resolveActiveTemplateAdmission(input);
  const twinRuntimeEnabled = templateTwinRuntimeEnabled(process.env);

  const pinned = (await prisma.noteTemplate.findFirst({
    where: {
      id: input.pinnedTemplateId!,
      version: input.pinnedTemplateVersion!,
      OR: [{ doctorId: input.doctorId }, { isSystemDefault: true }],
      ...(twinRuntimeEnabled
        ? {}
        : { templateKind: { not: 'template_twin_docx' } }),
    },
    include: {
      templateTwinCompiledVersion: {
        select: {
          sourceArtifact: { select: TEMPLATE_TWIN_SOURCE_ADMISSION_SELECT },
        },
      },
    },
  })) as TemplateWithSourceProvenance | null;
  if (!pinned) throw new PinnedTemplateUnavailableError();
  if (!twinRuntimeEnabled && pinned.templateKind === 'template_twin_docx') {
    throw new PinnedTemplateUnavailableError();
  }
  if (!hasCurrentTemplateTwinSourceAdmission(pinned)) {
    throw new PinnedTemplateUnavailableError();
  }
  const stagingFixture = isStagingFixtureTemplate(pinned);
  if (
    isTemplateTwinStagingQaRequested() &&
    pinned.templateKind === 'template_twin_docx' &&
    !stagingFixture
  ) {
    throw new PinnedTemplateUnavailableError();
  }
  if (stagingFixture) {
    if (!input.visitId) throw new PinnedTemplateUnavailableError();
    const run = await prisma.templateTwinSyntheticQaRun.findFirst({
      where: {
        visitId: input.visitId,
        doctorId: input.doctorId,
        noteTemplateId: pinned.id,
        noteTemplateVersion: pinned.version,
      },
      select: { id: true },
    });
    if (!run) throw new PinnedTemplateUnavailableError();
  }
  if (pinned.templateKind === 'template_twin_docx') {
    const token = await admitTemplateTwinForDoctor(input.doctorId);
    if (!token) throw new TemplateTwinWorkerRolloutError();
    return { template: pinned, templateTwinRolloutToken: token };
  }
  return { template: pinned, templateTwinRolloutToken: null };
}
