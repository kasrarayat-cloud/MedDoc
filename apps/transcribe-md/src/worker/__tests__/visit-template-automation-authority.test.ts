import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  syntheticContext: vi.fn(),
  assertSyntheticLease: vi.fn(),
  providerContext: vi.fn(),
  rollout: vi.fn(),
  stagingAttempt: vi.fn(),
  serializable: vi.fn(),
  tx: undefined as unknown as { $queryRaw: ReturnType<typeof vi.fn> },
}));

vi.mock("@meddoc/ai", () => ({
  getTemplateTwinSyntheticQaProviderContext: mocks.syntheticContext,
  assertTemplateTwinSyntheticQaWorkerLeaseHealthy: mocks.assertSyntheticLease,
}));
vi.mock("@meddoc/db", () => ({ default: {} }));
vi.mock("@/lib/template-twin/provider-ownership", () => ({
  getTemplateTwinProviderOwnershipContext: mocks.providerContext,
}));
vi.mock("@/lib/template-twin/rollout", () => ({
  TEMPLATE_TWIN_GLOBAL_ROLLOUT_ID: "global",
  lockTemplateTwinRolloutForFinalClaim: mocks.rollout,
}));
vi.mock("@/lib/template-twin/staging-qa-visit-guard", () => ({
  lockAndAssertTemplateTwinStagingQaAttempt: mocks.stagingAttempt,
}));
vi.mock("@/lib/db/transaction-retry", () => ({
  runSerializableTransactionWithRetry: mocks.serializable,
}));

import { canonicalSha256 } from "@/lib/template-twin/canonical";
import {
  runVisitAutomationRevokedAuthorityTerminalization,
  runVisitAutomationTransaction,
  VisitAutomationLiveAuthorityRevokedError,
  VisitAutomationLockError,
} from "../automation-locks";

const LIVE_CONTEXT = {
  practiceId: "practice-live-1",
  actorUserId: "doctor-live-1",
  visitId: "visit-live-1",
  visitInputMode: "audio_upload",
  scope: "VISIT_PIPELINE" as const,
  logicalAttempt: 1,
  subjectId: "visit-live-1",
  subjectSha256: "",
  sourceArtifactId: "source-live-1",
  compiledVersionId: "compiled-live-1",
  noteTemplateId: "template-live-1",
  noteTemplateVersion: 4,
  sourceLineageId: "lineage-live-1",
  sourceLineageVersion: 4,
  sourceSha256: "b".repeat(64),
  syntheticAdmissionId: null,
  rolloutToken: {
    practiceId: "practice-live-1",
    globalGeneration: BigInt(11),
    practiceGeneration: BigInt(7),
    releaseId: "11111111-1111-4111-8111-111111111111",
    releaseIdentitySha256: "c".repeat(64),
    runtimeManifestSha256: "d".repeat(64),
    runtimeInstanceId: "worker-live-1",
  },
};

function subjectSha256(context: typeof LIVE_CONTEXT): string {
  return canonicalSha256({
    contractVersion: "template-twin-visit-provider-subject-v1",
    practiceId: context.practiceId,
    actorUserId: context.actorUserId,
    visitId: context.visitId,
    noteTemplateId: context.noteTemplateId,
    noteTemplateVersion: context.noteTemplateVersion,
    compiledVersionId: context.compiledVersionId,
    sourceArtifactId: context.sourceArtifactId,
    sourceLineageId: context.sourceLineageId,
    sourceLineageVersion: context.sourceLineageVersion,
    sourceSha256: context.sourceSha256,
    logicalAttempt: context.logicalAttempt,
    inputMode: context.visitInputMode,
  });
}
LIVE_CONTEXT.subjectSha256 = subjectSha256(LIVE_CONTEXT);

interface TestLiveRows {
  practice: {
    id: string;
    isActive: boolean;
  };
  actor: {
    id: string;
    practiceId: string;
    role: string;
    isActive: boolean;
    deactivatedAt: Date | null;
    suspendedAt: Date | null;
    softDeletedAt: Date | null;
    products: string[];
  };
  template: {
    id: string;
    version: number;
    doctorId: string | null;
    templateKind: string;
    status: string;
  };
  compilation: {
    id: string;
    noteTemplateId: string;
    sourceArtifactId: string;
    certificationStatus: string;
    providerOwnershipSha256: string | null;
  };
  source: {
    id: string;
    practiceId: string;
    createdById: string | null;
    lineageId: string;
    lineageVersion: number;
    sha256: string;
    validationStatus: string;
    providerOwnershipSha256: string | null;
  };
  certification: {
    id: string;
    compiledVersionId: string;
    certifiedById: string;
    providerAuthorizationMode: string;
    providerAuthorizationAdmissionId: string | null;
  };
  patient: {
    id: string;
    practiceId: string;
    name: string;
    externalId: string | null;
    dateOfBirth: Date | null;
    mrn: string | null;
    insurance: string | null;
    problemList: unknown | null;
    weightKg: number | null;
    allergies: string[];
    deletedAt: Date | null;
  };
  visit: {
    id: string;
    patientId: string;
    userId: string;
    status: string;
    soapVersion: number;
    soapFinal: string | null;
    reviewReason: string | null;
    deletedAt: Date | null;
    archivedAt: Date | null;
    inputMode: string;
    noteTemplateId: string | null;
    noteTemplateVersion: number | null;
    manualRetryCount: number;
  };
}

interface TestLiveRowOverrides {
  practice?: Partial<TestLiveRows["practice"]>;
  actor?: Partial<TestLiveRows["actor"]>;
  template?: Partial<TestLiveRows["template"]>;
  compilation?: Partial<TestLiveRows["compilation"]>;
  source?: Partial<TestLiveRows["source"]>;
  certification?: Partial<TestLiveRows["certification"]>;
  receiptValid?: boolean;
  patient?: Partial<TestLiveRows["patient"]>;
  visit?: Partial<TestLiveRows["visit"]>;
  visitIdentityPatientId?: string;
}

function liveRows(): TestLiveRows {
  return {
    practice: {
      id: LIVE_CONTEXT.practiceId,
      isActive: true,
    },
    actor: {
      id: LIVE_CONTEXT.actorUserId,
      practiceId: LIVE_CONTEXT.practiceId,
      role: "DOCTOR",
      isActive: true,
      deactivatedAt: null,
      suspendedAt: null,
      softDeletedAt: null,
      products: ["TRANSCRIBE_MD"],
    },
    template: {
      id: LIVE_CONTEXT.noteTemplateId,
      version: LIVE_CONTEXT.noteTemplateVersion,
      doctorId: LIVE_CONTEXT.actorUserId,
      templateKind: "template_twin_docx",
      status: "active",
    },
    compilation: {
      id: LIVE_CONTEXT.compiledVersionId,
      noteTemplateId: LIVE_CONTEXT.noteTemplateId,
      sourceArtifactId: LIVE_CONTEXT.sourceArtifactId,
      certificationStatus: "CERTIFIED",
      providerOwnershipSha256: "f".repeat(64),
    },
    source: {
      id: LIVE_CONTEXT.sourceArtifactId,
      practiceId: LIVE_CONTEXT.practiceId,
      createdById: LIVE_CONTEXT.actorUserId,
      lineageId: LIVE_CONTEXT.sourceLineageId,
      lineageVersion: LIVE_CONTEXT.sourceLineageVersion,
      sha256: LIVE_CONTEXT.sourceSha256,
      validationStatus: "accepted",
      providerOwnershipSha256: "f".repeat(64),
    },
    certification: {
      id: "certification-live-1",
      compiledVersionId: LIVE_CONTEXT.compiledVersionId,
      certifiedById: LIVE_CONTEXT.actorUserId,
      providerAuthorizationMode: "LIVE",
      providerAuthorizationAdmissionId: null,
    },
    patient: {
      id: "patient-live-1",
      practiceId: LIVE_CONTEXT.practiceId,
      name: "Synthetic unit patient",
      externalId: "patient-external-live-1",
      dateOfBirth: null,
      mrn: null,
      insurance: null,
      problemList: null,
      weightKg: null,
      allergies: [],
      deletedAt: null,
    },
    visit: {
      id: LIVE_CONTEXT.visitId,
      patientId: "patient-live-1",
      userId: LIVE_CONTEXT.actorUserId,
      status: "AUTOMATING",
      soapVersion: 3,
      soapFinal: "Synthetic non-PHI SOAP",
      reviewReason: null,
      deletedAt: null,
      archivedAt: null,
      inputMode: LIVE_CONTEXT.visitInputMode,
      noteTemplateId: LIVE_CONTEXT.noteTemplateId,
      noteTemplateVersion: LIVE_CONTEXT.noteTemplateVersion,
      manualRetryCount: LIVE_CONTEXT.logicalAttempt - 1,
    },
  };
}

function databaseHarness(overrides: TestLiveRowOverrides = {}) {
  const base = liveRows();
  const rows = {
    practice: { ...base.practice, ...overrides.practice },
    actor: { ...base.actor, ...overrides.actor },
    template: { ...base.template, ...overrides.template },
    compilation: { ...base.compilation, ...overrides.compilation },
    source: { ...base.source, ...overrides.source },
    certification: { ...base.certification, ...overrides.certification },
    patient: { ...base.patient, ...overrides.patient },
    visit: { ...base.visit, ...overrides.visit },
  };
  const trace: string[] = [];
  const queries: string[] = [];
  mocks.tx = {
    $queryRaw: vi.fn(async (query: { strings?: readonly string[] }) => {
      const sql = query.strings?.join("?") ?? "";
      queries.push(sql);
      if (sql.includes('FROM "template_twin_rollout_controls"')) {
        trace.push("global");
        return [{ id: "global" }];
      }
      if (sql.includes('FROM "practices"')) {
        trace.push("practice");
        return [{ ...rows.practice }];
      }
      if (sql.includes('FROM "users"')) {
        trace.push("actor");
        return [{ ...rows.actor }];
      }
      if (sql.includes('FROM "note_templates"')) {
        trace.push("template");
        return [{ ...rows.template }];
      }
      if (sql.includes('FROM "template_twin_compiled_versions"')) {
        trace.push("compilation");
        return [{ ...rows.compilation }];
      }
      if (sql.includes('FROM "template_twin_source_artifacts"')) {
        trace.push("source");
        return [{ ...rows.source }];
      }
      if (sql.includes('FROM "template_twin_certifications"')) {
        trace.push("certification");
        return [{ ...rows.certification }];
      }
      if (sql.includes("template_twin_live_provider_compilation_is_valid")) {
        trace.push("provider-receipt");
        return [{ valid: overrides.receiptValid ?? true }];
      }
      if (
        sql.includes('SELECT "patientId"') &&
        sql.includes('FROM "transcribe_visits"') &&
        !sql.includes('"status"')
      ) {
        return [
          {
            patientId: overrides.visitIdentityPatientId ?? rows.visit.patientId,
          },
        ];
      }
      if (sql.includes('FROM "transcribe_md_patients"')) {
        trace.push("patient");
        return [{ ...rows.patient }];
      }
      if (sql.includes('FROM "transcribe_visits"')) {
        trace.push("visit");
        return [{ ...rows.visit }];
      }
      return [];
    }),
  };
  return { trace, queries };
}

function transactionInput() {
  return {
    operation: "synthetic_live_automation_authority_test",
    visitId: LIVE_CONTEXT.visitId,
    userId: LIVE_CONTEXT.actorUserId,
    practiceId: LIVE_CONTEXT.practiceId,
    transaction: vi.fn(async () => "committed"),
  };
}

function configureSyntheticAuthority(
  input: {
    provider?: Record<string, unknown>;
    synthetic?: Record<string, unknown>;
    database?: TestLiveRowOverrides;
  } = {},
) {
  const providerContext = {
    ...LIVE_CONTEXT,
    syntheticAdmissionId: "admission-synthetic-1",
    rolloutToken: {
      practiceId: LIVE_CONTEXT.practiceId,
      globalGeneration: BigInt(11),
      practiceGeneration: BigInt(7),
    },
    ...input.provider,
  };
  const syntheticContext = {
    admissionId: "admission-synthetic-1",
    runId: "run-synthetic-1",
    visitId: LIVE_CONTEXT.visitId,
    practiceId: LIVE_CONTEXT.practiceId,
    fixtureVersion: "synthetic-fixture-v1",
    requestSha256: "e".repeat(64),
    attempt: 1,
    workerClaimId: "f".repeat(64),
    pinnedGlobalGeneration: BigInt(11),
    pinnedPracticeGeneration: BigInt(7),
    ...input.synthetic,
  };
  mocks.providerContext.mockReturnValue(providerContext);
  mocks.syntheticContext.mockReturnValue(syntheticContext);
  mocks.rollout.mockResolvedValue({
    allowed: true,
    token: providerContext.rolloutToken,
  });
  databaseHarness({
    ...input.database,
    patient: {
      name: "Template Twin Synthetic QA",
      externalId: "SYNTHETIC-QA-ONLY",
      dateOfBirth: null,
      mrn: null,
      insurance: null,
      problemList: null,
      weightKg: null,
      allergies: [],
      deletedAt: null,
      ...input.database?.patient,
    },
  });
  return { providerContext, syntheticContext };
}

describe("live Template Twin visit automation authority", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.syntheticContext.mockReturnValue(null);
    mocks.providerContext.mockReturnValue(LIVE_CONTEXT);
    mocks.rollout.mockResolvedValue({
      allowed: true,
      token: LIVE_CONTEXT.rolloutToken,
    });
    mocks.serializable.mockImplementation(async (input) =>
      input.transaction(mocks.tx),
    );
    mocks.stagingAttempt.mockResolvedValue(undefined);
    databaseHarness();
  });

  it("locks the exact release, doctor, template, and visit identity", async () => {
    const db = databaseHarness();
    const input = transactionInput();
    await expect(runVisitAutomationTransaction(input)).resolves.toBe(
      "committed",
    );
    expect(mocks.rollout).toHaveBeenCalledWith(
      expect.objectContaining({
        practiceId: LIVE_CONTEXT.practiceId,
        pinnedToken: LIVE_CONTEXT.rolloutToken,
      }),
    );
    expect(db.trace).toEqual([
      "actor",
      "template",
      "compilation",
      "source",
      "certification",
      "provider-receipt",
      "patient",
      "visit",
    ]);
    expect(input.transaction).toHaveBeenCalledTimes(1);
  });

  it.each([
    ["suspended doctor", { actor: { suspendedAt: new Date() } }],
    ["soft-deleted doctor", { actor: { softDeletedAt: new Date() } }],
    ["role transfer", { actor: { role: "PRACTICE_ADMIN" } }],
    ["product removal", { actor: { products: ["MEDDOC_PRO"] } }],
    ["practice transfer", { actor: { practiceId: "practice-foreign-1" } }],
  ])("rejects a current %s before a ledger claim", async (_label, changes) => {
    databaseHarness(changes);
    const input = transactionInput();
    await expect(runVisitAutomationTransaction(input)).rejects.toBeInstanceOf(
      VisitAutomationLiveAuthorityRevokedError,
    );
    expect(input.transaction).not.toHaveBeenCalled();
  });

  it.each([
    "TEMPLATE_TWIN_KILL_SWITCH_ACTIVE",
    "TEMPLATE_TWIN_GLOBAL_DISABLED",
    "TEMPLATE_TWIN_PRACTICE_DISABLED",
    "TEMPLATE_TWIN_PRACTICE_GENERATION_STALE",
    "TEMPLATE_TWIN_RELEASE_IDENTITY_STALE",
  ])("rejects rollout/release revocation %s", async (code) => {
    mocks.rollout.mockResolvedValue({
      allowed: false,
      code,
      reason: "synthetic authority revocation",
      currentToken: null,
    });
    const input = transactionInput();
    await expect(runVisitAutomationTransaction(input)).rejects.toBeInstanceOf(
      VisitAutomationLiveAuthorityRevokedError,
    );
    expect(input.transaction).not.toHaveBeenCalled();
  });

  it.each([
    ["visit input mode", { visit: { inputMode: "text_notes" } }],
    ["visit template", { visit: { noteTemplateId: "template-foreign-1" } }],
    ["visit version", { visit: { noteTemplateVersion: 5 } }],
    ["template owner", { template: { doctorId: "doctor-foreign-1" } }],
    ["template version", { template: { version: 5 } }],
    ["template kind", { template: { templateKind: "structured" } }],
    ["draft template state", { template: { status: "draft" } }],
    ["compiled version", { compilation: { id: "compiled-live-foreign" } }],
    [
      "compiled template",
      { compilation: { noteTemplateId: "template-live-foreign" } },
    ],
    [
      "compiled source",
      { compilation: { sourceArtifactId: "source-live-foreign" } },
    ],
    [
      "compiled certification status",
      { compilation: { certificationStatus: "NEEDS_CONFIRMATION" } },
    ],
    [
      "compiled provider receipt",
      { compilation: { providerOwnershipSha256: null } },
    ],
    ["source practice", { source: { practiceId: "practice-foreign-1" } }],
    ["source creator", { source: { createdById: "doctor-foreign-1" } }],
    ["source lineage", { source: { lineageId: "lineage-foreign-1" } }],
    ["source lineage version", { source: { lineageVersion: 5 } }],
    ["source SHA", { source: { sha256: "0".repeat(64) } }],
    ["source admission", { source: { validationStatus: "rejected" } }],
    ["source provider receipt", { source: { providerOwnershipSha256: null } }],
    [
      "certification compilation",
      { certification: { compiledVersionId: "compiled-live-foreign" } },
    ],
    [
      "certifying physician",
      { certification: { certifiedById: "doctor-foreign-1" } },
    ],
    [
      "certification provider mode",
      { certification: { providerAuthorizationMode: "SYNTHETIC_QA" } },
    ],
    [
      "certification admission binding",
      {
        certification: {
          providerAuthorizationAdmissionId: "admission-foreign-1",
        },
      },
    ],
    ["canonical LIVE receipt", { receiptValid: false }],
    ["patient tenant", { patient: { practiceId: "practice-foreign-1" } }],
    [
      "reserved synthetic patient identity",
      { patient: { externalId: "SYNTHETIC-QA-ONLY" } },
    ],
    ["deleted patient", { patient: { deletedAt: new Date() } }],
    ["visit patient binding", { visit: { patientId: "patient-foreign-1" } }],
  ])("rejects changed %s identity", async (_label, changes) => {
    databaseHarness(changes);
    await expect(
      runVisitAutomationTransaction(transactionInput()),
    ).rejects.toBeInstanceOf(VisitAutomationLiveAuthorityRevokedError);
  });

  it("allows an inactive historical version only when the visit stays exactly pinned", async () => {
    databaseHarness({ template: { status: "inactive" } });
    await expect(
      runVisitAutomationTransaction(transactionInput()),
    ).resolves.toBe("committed");

    databaseHarness({
      template: { status: "inactive" },
      visit: { noteTemplateVersion: LIVE_CONTEXT.noteTemplateVersion + 1 },
    });
    await expect(
      runVisitAutomationTransaction(transactionInput()),
    ).rejects.toBeInstanceOf(VisitAutomationLiveAuthorityRevokedError);
  });

  it.each([
    ["compiledVersionId", { compiledVersionId: "compiled-context-forged" }],
    ["sourceArtifactId", { sourceArtifactId: "source-context-forged" }],
    ["sourceLineageId", { sourceLineageId: "lineage-context-forged" }],
    ["sourceLineageVersion", { sourceLineageVersion: 99 }],
    ["sourceSha256", { sourceSha256: "9".repeat(64) }],
    ["logicalAttempt", { logicalAttempt: 2 }],
    ["subjectSha256", { subjectSha256: "8".repeat(64) }],
  ])("rejects forged context %s", async (_label, contextChange) => {
    mocks.providerContext.mockReturnValue({
      ...LIVE_CONTEXT,
      ...contextChange,
    });
    await expect(
      runVisitAutomationTransaction(transactionInput()),
    ).rejects.toBeInstanceOf(VisitAutomationLockError);
    expect(mocks.serializable).not.toHaveBeenCalled();
  });

  it("rejects a forged compilation context even with a self-consistent subject hash", async () => {
    const forged = {
      ...LIVE_CONTEXT,
      compiledVersionId: "compiled-context-forged",
    };
    forged.subjectSha256 = subjectSha256(forged);
    mocks.providerContext.mockReturnValue(forged);
    await expect(
      runVisitAutomationTransaction(transactionInput()),
    ).rejects.toBeInstanceOf(VisitAutomationLiveAuthorityRevokedError);
    expect(mocks.serializable).toHaveBeenCalledTimes(1);
  });

  it("rejects a changed runtime instance in an otherwise allowed release", async () => {
    mocks.rollout.mockResolvedValue({
      allowed: true,
      token: {
        ...LIVE_CONTEXT.rolloutToken,
        runtimeInstanceId: "worker-live-foreign",
      },
    });
    await expect(
      runVisitAutomationTransaction(transactionInput()),
    ).rejects.toBeInstanceOf(VisitAutomationLiveAuthorityRevokedError);
  });

  it("rejects context actor mismatch before any database transaction", async () => {
    const input = { ...transactionInput(), userId: "doctor-foreign-1" };
    await expect(runVisitAutomationTransaction(input)).rejects.toBeInstanceOf(
      VisitAutomationLockError,
    );
    expect(mocks.serializable).not.toHaveBeenCalled();
    expect(mocks.rollout).not.toHaveBeenCalled();
  });

  it("uses a proof-bound, fail-only transaction after observed revocation", async () => {
    mocks.rollout.mockResolvedValue({
      allowed: false,
      code: "TEMPLATE_TWIN_GLOBAL_DISABLED",
      reason: "synthetic authority revocation",
      currentToken: null,
    });
    let rejection: VisitAutomationLiveAuthorityRevokedError | null = null;
    try {
      await runVisitAutomationTransaction(transactionInput());
    } catch (error) {
      if (error instanceof VisitAutomationLiveAuthorityRevokedError) {
        rejection = error;
      }
    }
    expect(rejection).not.toBeNull();

    const terminal = vi.fn(async () => "terminal");
    await expect(
      runVisitAutomationRevokedAuthorityTerminalization({
        operation: "synthetic_fail_only_terminalization",
        visitId: LIVE_CONTEXT.visitId,
        userId: LIVE_CONTEXT.actorUserId,
        practiceId: LIVE_CONTEXT.practiceId,
        rejection: rejection!,
        transaction: terminal,
      }),
    ).resolves.toBe("terminal");
    expect(terminal).toHaveBeenCalledTimes(1);
  });

  it("preserves the ordinary active physician path without Twin restrictions", async () => {
    mocks.providerContext.mockReturnValue(null);
    const db = databaseHarness({
      actor: { role: "DOCTOR", products: ["TRANSCRIBE_MD"] },
      visit: { noteTemplateId: null, noteTemplateVersion: null },
    });
    const input = transactionInput();
    await expect(runVisitAutomationTransaction(input)).resolves.toBe(
      "committed",
    );
    expect(mocks.rollout).not.toHaveBeenCalled();
    expect(input.transaction).toHaveBeenCalledTimes(1);
    const practiceLock = db.queries.find((sql) =>
      sql.includes('FROM "practices"'),
    );
    const actorLock = db.queries.find((sql) => sql.includes('FROM "users"'));
    expect(practiceLock).toContain('SELECT "id", "isActive"');
    for (const field of [
      '"id"',
      '"practiceId"',
      '"role"',
      '"isActive"',
      '"deactivatedAt"',
      '"suspendedAt"',
      '"softDeletedAt"',
      '"products"',
    ]) {
      expect(actorLock).toContain(field);
    }
  });

  const ordinaryProviderAuthorityFences = [
    ["pre-reserve", "reserve_visit_automation_provider_execution"],
    ["pre-claim", "claim_visit_automation_provider_execution"],
    ["post-return", "persist_visit_automation_provider_result"],
  ] as const;
  const ordinaryAuthorityRevocations: ReadonlyArray<
    readonly [string, TestLiveRowOverrides]
  > = [
    ["practice deactivation", { practice: { isActive: false } }],
    ["actor inactivity", { actor: { isActive: false } }],
    ["actor suspension", { actor: { suspendedAt: new Date() } }],
    ["actor deactivation", { actor: { deactivatedAt: new Date() } }],
    ["actor soft-delete", { actor: { softDeletedAt: new Date() } }],
    ["product removal", { actor: { products: ["MEDDOC_PRO"] } }],
    ["practice transfer", { actor: { practiceId: "practice-foreign-1" } }],
    ["clinical role removal", { actor: { role: "STAFF" } }],
    ["actor identity substitution", { actor: { id: "doctor-foreign-1" } }],
  ];
  const ordinaryProviderAuthorityCases =
    ordinaryProviderAuthorityFences.flatMap(([fence, operation]) =>
      ordinaryAuthorityRevocations.map(([revocation, changes]) => ({
        revocation,
        fence,
        operation,
        changes,
      })),
    );

  it.each(ordinaryProviderAuthorityCases)(
    "rejects ordinary $revocation at the provider $fence fence",
    async ({ operation, changes }) => {
      mocks.providerContext.mockReturnValue(null);
      const db = databaseHarness(changes);
      const input = { ...transactionInput(), operation };

      await expect(runVisitAutomationTransaction(input)).rejects.toBeInstanceOf(
        VisitAutomationLockError,
      );
      expect(input.transaction).not.toHaveBeenCalled();
      expect(db.trace).not.toContain("visit");
    },
  );

  it("preserves the existing synthetic admission and worker-lease path", async () => {
    configureSyntheticAuthority();
    const input = transactionInput();
    await expect(runVisitAutomationTransaction(input)).resolves.toBe(
      "committed",
    );
    expect(mocks.assertSyntheticLease).toHaveBeenCalledTimes(1);
    expect(mocks.stagingAttempt).toHaveBeenCalledTimes(1);
    expect(mocks.stagingAttempt).toHaveBeenCalledWith(
      expect.objectContaining({
        claim: expect.objectContaining({
          admissionId: "admission-synthetic-1",
          runId: "run-synthetic-1",
          workerClaimId: "f".repeat(64),
          sourceArtifactId: LIVE_CONTEXT.sourceArtifactId,
          noteTemplateId: LIVE_CONTEXT.noteTemplateId,
          noteTemplateVersion: LIVE_CONTEXT.noteTemplateVersion,
        }),
        allowedStatuses: ["PROCESSING"],
        allowedAdmissionPhases: ["PROCESSING"],
        requireLiveWorkerLease: true,
      }),
    );
    expect(input.transaction).toHaveBeenCalledTimes(1);
  });

  it.each([
    ["patient tenant", { patient: { practiceId: "practice-foreign-1" } }],
    ["patient name", { patient: { name: "Ordinary Patient" } }],
    ["reserved identity", { patient: { externalId: "ordinary-patient" } }],
    ["date of birth", { patient: { dateOfBirth: new Date("2099-01-01") } }],
    ["MRN", { patient: { mrn: "synthetic-mrn" } }],
    ["insurance", { patient: { insurance: "synthetic-insurance" } }],
    ["problem list", { patient: { problemList: { synthetic: true } } }],
    ["weight", { patient: { weightKg: 70 } }],
    ["allergies", { patient: { allergies: ["synthetic-allergy"] } }],
    ["patient deletion", { patient: { deletedAt: new Date() } }],
  ])(
    "rejects synthetic L7 authority after %s drift",
    async (_label, patient) => {
      configureSyntheticAuthority({ database: patient });
      const input = transactionInput();
      await expect(runVisitAutomationTransaction(input)).rejects.toBeInstanceOf(
        VisitAutomationLockError,
      );
      expect(input.transaction).not.toHaveBeenCalled();
    },
  );

  it("rejects a patient reassignment race between identity resolution and the locked visit", async () => {
    configureSyntheticAuthority({
      database: {
        visitIdentityPatientId: "patient-live-1",
        visit: { patientId: "patient-reassigned-1" },
      },
    });
    const input = transactionInput();
    await expect(runVisitAutomationTransaction(input)).rejects.toBeInstanceOf(
      VisitAutomationLockError,
    );
    expect(input.transaction).not.toHaveBeenCalled();
  });

  it.each([
    ["missing provider context", null, {}],
    ["wrong provider scope", { scope: "SYNTHETIC_EVIDENCE" }, {}],
    ["admission mismatch", { syntheticAdmissionId: "admission-foreign-1" }, {}],
    ["logical attempt mismatch", { logicalAttempt: 2 }, {}],
    [
      "rollout generation mismatch",
      {
        rolloutToken: {
          practiceId: LIVE_CONTEXT.practiceId,
          globalGeneration: BigInt(12),
          practiceGeneration: BigInt(7),
        },
      },
      {},
    ],
    ["durable visit mismatch", {}, { visitId: "visit-foreign-1" }],
    ["durable practice mismatch", {}, { practiceId: "practice-foreign-1" }],
  ])(
    "rejects synthetic L7 %s before opening a transaction",
    async (_label, provider, synthetic) => {
      configureSyntheticAuthority({
        provider: provider ?? {},
        synthetic,
      });
      if (provider === null) mocks.providerContext.mockReturnValue(null);
      await expect(
        runVisitAutomationTransaction(transactionInput()),
      ).rejects.toBeInstanceOf(VisitAutomationLockError);
      expect(mocks.serializable).not.toHaveBeenCalled();
    },
  );
});
