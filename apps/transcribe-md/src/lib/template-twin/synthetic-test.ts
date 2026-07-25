// ============================================================================
// Template Twin — certify-time SYNTHETIC TEST (Phase 2b). Runs an INJECTED
// TwinEntityExtractor (this module never imports the worker pipeline) over
// physician-supplied synthetic evidence -> fill -> native render -> persist the
// proof that certification binds. PHI-gated (synthetic-evidence-gate); prisma
// singleton + injectable storage + logTwinAudit only.
// ============================================================================
import { Prisma } from '@prisma/client';
import prisma from '@meddoc/db';

import { logTwinAudit as logAudit } from './twin-audit';

import { prepareTemplateTwinFill } from './fill-engine';
import {
  projectEncounterFacts,
  type EncounterEntitySnapshot,
} from './encounter-facts';
import { SemanticMappingSchema, TemplateDocIRSchema, type SemanticMapping } from './ir';
import { templateTwinMappingsSha256 } from './mapping-hash';
import {
  createTemplateTwinArtifactStore,
  type TemplateTwinArtifactStore,
} from './storage';
import type { TemplateTwinActor } from './certification-lifecycle';
import { readTemplateTwinWorkspace } from './workspace-read';
import { assertTemplateTwinSyntheticEvidencePhiFree } from './synthetic-evidence-gate';
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

export class TemplateTwinSyntheticTestError extends Error {
  readonly code:
    | 'NOT_FOUND'
    | 'IMMUTABLE'
    | 'CONFLICT'
    | 'MAPPINGS_NOT_READY'
    | 'VALIDATION_FAILED'
    | 'SYNTHETIC_EVIDENCE_REJECTED';

  /** For VALIDATION_FAILED: "<fieldId>:<issueCode>" per blocking check.
   *  Ids and codes only — never encounter text or filled values. */
  readonly blocking: readonly string[];

  constructor(
    code: TemplateTwinSyntheticTestError['code'],
    message: string,
    detail?: { blocking?: readonly string[] },
  ) {
    super(message);
    this.name = 'TemplateTwinSyntheticTestError';
    this.code = code;
    this.blocking = detail?.blocking ?? [];
  }
}

interface MappingRow {
  clinicalConcept: string | null;
  expectedDataType: string;
  polarityBehavior: string;
  temporality: string | null;
  laterality: string | null;
  unitPolicy: string | null;
  approvedSynonyms: unknown;
  required: boolean;
  blankPolicy: string;
  unknownPolicy: string;
  practiceDefault: string | null;
  mappingStatus: string;
}

function mapping(fieldId: string, row: MappingRow): SemanticMapping {
  return SemanticMappingSchema.parse({
    fieldId,
    clinicalConcept: row.clinicalConcept,
    expectedDataType: row.expectedDataType,
    polarityBehavior: row.polarityBehavior,
    temporality: row.temporality,
    laterality: row.laterality,
    unitPolicy: row.unitPolicy,
    approvedSynonyms: Array.isArray(row.approvedSynonyms) ? row.approvedSynonyms : [],
    required: row.required,
    blankPolicy: row.blankPolicy,
    unknownPolicy: row.unknownPolicy,
    practiceDefault: row.practiceDefault,
    status: row.mappingStatus.toLowerCase(),
  });
}

function asJson(value: unknown): Prisma.InputJsonValue {
  return value as Prisma.InputJsonValue;
}

export async function runTemplateTwinSyntheticTest(input: {
  noteTemplateId: string;
  actor: TemplateTwinActor;
  expectedMappingsSha256: string;
  encounterText: string;
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
                  clinicalConcept: true,
                  expectedDataType: true,
                  polarityBehavior: true,
                  temporality: true,
                  laterality: true,
                  unitPolicy: true,
                  approvedSynonyms: true,
                  required: true,
                  blankPolicy: true,
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
  const mappings = compiled.fields.map((field: { fieldId: string; mapping: MappingRow | null }) => {
    if (!field.mapping) {
      throw new TemplateTwinSyntheticTestError(
        'MAPPINGS_NOT_READY',
        'Every field needs a physician-confirmed mapping before testing.',
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
  if (mappings.some((item: SemanticMapping) => item.status !== 'certified' || !item.clinicalConcept)) {
    throw new TemplateTwinSyntheticTestError(
      'MAPPINGS_NOT_READY',
      'Every field needs a physician-confirmed mapping before testing.',
    );
  }

  // Certification artifacts retain evidence anchors and filled values. Gate
  // the encounter before Layer 3 or storage so a mislabeled real encounter is
  // not persisted as a synthetic proof.
  try {
    await assertTemplateTwinSyntheticEvidencePhiFree({
      encounterText: input.encounterText,
      practiceId: input.actor.practiceId,
      userId: input.actor.userId,
    });
  } catch {
    throw new TemplateTwinSyntheticTestError(
      'SYNTHETIC_EVIDENCE_REJECTED',
      'Use clearly labeled synthetic test evidence without patient identifiers.',
    );
  }

  const ir = TemplateDocIRSchema.parse(compiled.compiledDocumentIr);
  const encounterMode = input.encounterMode ?? 'text';
  const extracted = await input.extractEntities({
    mode: encounterMode,
    text: input.encounterText,
    practiceId: input.actor.practiceId,
    userId: input.actor.userId,
    noteTemplateId: row.id,
  });
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
  // Run the LIVE brain over the synthetic encounter, then recover the compiled
  // {{one of}} marker form from the SAME verified source the IR came from —
  // byte-for-byte what processTemplateTwinVisit does.
  let generatedNote: string | undefined;
  let markerText: string | undefined;
  if (input.generateNote) {
    generatedNote = await input.generateNote({
      encounterText: input.encounterText,
      noteTemplateId: row.id,
      practiceId: input.actor.practiceId,
      userId: input.actor.userId,
      entities: extracted.entities,
      roleLabeledTranscript: extracted.contextText,
    });
    markerText = (await docxToTextWithControls(source)).text;
  }
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
                  clinicalConcept: true,
                  expectedDataType: true,
                  polarityBehavior: true,
                  temporality: true,
                  laterality: true,
                  unitPolicy: true,
                  approvedSynonyms: true,
                  required: true,
                  blankPolicy: true,
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
