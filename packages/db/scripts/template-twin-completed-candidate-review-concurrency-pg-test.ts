#!/usr/bin/env tsx

// Actual-PostgreSQL proof for the completed-document candidate protected
// comparison workflow. The harness calls the production create, preview,
// terminal-review, and rollout-mutation helpers against synthetic-only DOCX,
// actor, malware, and private-storage fixtures. It uses PostgreSQL-observed
// lock waits as barriers and refuses any database that is not positively
// identified as disposable QA/test.

import { createHash } from "node:crypto";

import { PrismaPg } from "@prisma/adapter-pg";
import { Prisma, PrismaClient } from "@prisma/client";
import JSZip from "jszip";

import type { CompletedCandidateActor } from "../../../apps/transcribe-md/src/lib/template-twin/completed-candidate-service";
import type {
  TemplateTwinMalwareScanEvidence,
  TemplateTwinMalwareScanner,
} from "../../../apps/transcribe-md/src/lib/template-twin/malware-scan";
import type {
  ReadArtifactInput,
  StoredTemplateTwinArtifact,
  StoreCandidateArtifactInput,
  StoreOutputArtifactInput,
  StoreQuarantineArtifactInput,
  StoreSourceArtifactInput,
  TemplateTwinArtifactStore,
} from "../../../apps/transcribe-md/src/lib/template-twin/storage";
import type { TemplateTwinRolloutToken } from "../../../apps/transcribe-md/src/lib/template-twin/rollout";
import { assertNonProdDatabase } from "../src/db-guard";

const configuredDatabaseUrl =
  process.env.TEMPLATE_TWIN_COMPLETED_CANDIDATE_TEST_DATABASE_URL ??
  process.env.DATABASE_URL;
assertNonProdDatabase(configuredDatabaseUrl);
if (!configuredDatabaseUrl) {
  throw new Error(
    "A disposable completed-candidate test database is required.",
  );
}
const verifiedDatabaseUrl = configuredDatabaseUrl;

// The production helpers instantiate @meddoc/db lazily below. Bind that
// singleton to the already guarded target before importing application code.
process.env.DATABASE_URL = verifiedDatabaseUrl;
process.env.TEMPLATE_TWIN_KILL_SWITCH = "false";
process.env.TEMPLATE_TWIN_RUNTIME_MODE = "standard";
process.env.NODE_ENV = "test";
process.env.PRISMA_POOL_MAX = "8";
process.env.PRISMA_POOL_TIMEOUT_MS = "30000";
process.env.PRISMA_STATEMENT_TIMEOUT_MS = "30000";

const suffix = `${process.pid}-${Date.now()}`;
const practiceId = `synthetic-candidate-pg-${suffix}`;
const physicianId = `synthetic-candidate-physician-${suffix}`;
const physicianEmail = `candidate-${suffix}@synthetic.test`;
const revokerApplicationName = `tt-candidate-revoker-${suffix}`;
const blockerApplicationName = `tt-candidate-blocker-${suffix}`;

const CONTENT_TYPES = `<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>`;
const ROOT_RELS = `<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>`;
const SYNTHETIC_SENTINEL = "QUILLMD SYNTHETIC EXAMPLE — NO REAL PATIENT DATA";
const DOCX_MIME_TYPE =
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document" as const;

type CompletedCandidateServiceModule =
  typeof import("../../../apps/transcribe-md/src/lib/template-twin/completed-candidate-service");
type RolloutModule =
  typeof import("../../../apps/transcribe-md/src/lib/template-twin/rollout");
type StorageModule =
  typeof import("../../../apps/transcribe-md/src/lib/template-twin/storage");
type MalwareModule =
  typeof import("../../../apps/transcribe-md/src/lib/template-twin/malware-scan");
type CompletedCandidateConverterModule =
  typeof import("../../../apps/transcribe-md/src/lib/template-twin/completed-candidate-converter");
type SourceMetadataModule =
  typeof import("../../../apps/transcribe-md/src/lib/template-twin/source-metadata");

let completedCandidateService!: CompletedCandidateServiceModule;
let rollout!: RolloutModule;
let storageHelpers!: StorageModule;
let malware!: MalwareModule;
let completedCandidateConverter!: CompletedCandidateConverterModule;
let sourceMetadata!: SourceMetadataModule;
let applicationPrisma: PrismaClient | null = null;
let activePhase = "module-load";

function client(applicationName: string): PrismaClient {
  const url = new URL(verifiedDatabaseUrl);
  url.searchParams.set("application_name", applicationName);
  return new PrismaClient({
    adapter: new PrismaPg({
      connectionString: url.toString(),
      max: 1,
      connectionTimeoutMillis: 10_000,
    }),
  });
}

const observer = client(`tt-candidate-observer-${suffix}`);
const revoker = client(revokerApplicationName);
const candidateBlocker = client(blockerApplicationName);

function latch<T = void>(): {
  promise: Promise<T>;
  release: (value: T) => void;
} {
  let release!: (value: T) => void;
  const promise = new Promise<T>((resolve) => {
    release = resolve;
  });
  return { promise, release };
}

function immediate(): Promise<void> {
  return new Promise((resolve) => setImmediate(resolve));
}

function sha256(value: Uint8Array | string): string {
  return createHash("sha256").update(value).digest("hex");
}

function documentXml(finding: string, plan: string): string {
  return `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>
  <w:p><w:r><w:t>${SYNTHETIC_SENTINEL}</w:t></w:r></w:p>
  <w:tbl><w:tblGrid><w:gridCol w:w="2400"/><w:gridCol w:w="4800"/></w:tblGrid>
    <w:tr><w:tc><w:p><w:r><w:t>Finding</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>${finding}</w:t></w:r></w:p></w:tc></w:tr>
    <w:tr><w:tc><w:p><w:r><w:t>Plan</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>${plan}</w:t></w:r></w:p></w:tc></w:tr>
  </w:tbl><w:sectPr/>
</w:body></w:document>`;
}

async function syntheticCompletedExample(
  finding: string,
  plan: string,
): Promise<Buffer> {
  const zip = new JSZip();
  zip.file("[Content_Types].xml", CONTENT_TYPES);
  zip.file("_rels/.rels", ROOT_RELS);
  zip.file("word/document.xml", documentXml(finding, plan));
  return zip.generateAsync({
    type: "nodebuffer",
    compression: "DEFLATE",
    compressionOptions: { level: 6 },
  });
}

class SyntheticPrivateStorage implements TemplateTwinArtifactStore {
  readonly bucket = "quillmd-candidate-qa-private";
  private readonly objects = new Map<
    string,
    { bytes: Buffer; versionId: string; etag: string; sha256: string }
  >();
  private version = 0;

  private async record(input: {
    practiceId: string;
    objectKey: string;
    bytes: Uint8Array;
    kind: "quarantine" | "candidate" | "source" | "output";
  }): Promise<StoredTemplateTwinArtifact> {
    const bytes = Buffer.from(input.bytes);
    const digest = sha256(bytes);
    this.version += 1;
    const versionId = `synthetic-version-${this.version}`;
    const etag = `synthetic-etag-${this.version}`;
    await storageHelpers.beginTemplateTwinObjectWrite(observer, {
      practiceId: input.practiceId,
      objectKey: input.objectKey,
      sha256: digest,
      sizeBytes: bytes.byteLength,
      kind: input.kind,
    });
    this.objects.set(input.objectKey, {
      bytes,
      versionId,
      etag,
      sha256: digest,
    });
    await storageHelpers.markTemplateTwinObjectWritten(observer, {
      objectKey: input.objectKey,
      practiceId: input.practiceId,
      objectVersionId: versionId,
      objectEtag: etag,
      retentionUntil: new Date(Date.now() + 24 * 60 * 60 * 1000),
    });
    return {
      bucket: this.bucket,
      objectKey: input.objectKey,
      objectVersionId: versionId,
      objectEtag: etag,
      sha256: digest,
      mimeType: DOCX_MIME_TYPE,
      sizeBytes: bytes.byteLength,
      created: true,
    };
  }

  storeQuarantineArtifact(
    input: StoreQuarantineArtifactInput,
  ): Promise<StoredTemplateTwinArtifact> {
    const bytes = Buffer.from(input.bytes);
    const digest = sha256(bytes);
    return this.record({
      practiceId: input.practiceId,
      objectKey: storageHelpers.createQuarantineArtifactKey({
        practiceId: input.practiceId,
        lineageId: input.lineageId,
        lineageVersion: input.lineageVersion,
        sha256: digest,
      }),
      bytes,
      kind: "quarantine",
    });
  }

  storeCandidateArtifact(
    input: StoreCandidateArtifactInput,
  ): Promise<StoredTemplateTwinArtifact> {
    const bytes = Buffer.from(input.bytes);
    const digest = sha256(bytes);
    return this.record({
      practiceId: input.practiceId,
      objectKey: storageHelpers.createCandidateArtifactKey({
        practiceId: input.practiceId,
        candidateId: input.candidateId,
        candidateVersion: input.candidateVersion,
        sha256: digest,
      }),
      bytes,
      kind: "candidate",
    });
  }

  storeSourceArtifact(
    input: StoreSourceArtifactInput,
  ): Promise<StoredTemplateTwinArtifact> {
    const bytes = Buffer.from(input.bytes);
    const digest = sha256(bytes);
    return this.record({
      practiceId: input.practiceId,
      objectKey: storageHelpers.createSourceArtifactKey({
        practiceId: input.practiceId,
        lineageId: input.lineageId,
        templateVersion: input.templateVersion,
        sha256: digest,
      }),
      bytes,
      kind: "source",
    });
  }

  storeOutputArtifact(
    input: StoreOutputArtifactInput,
  ): Promise<StoredTemplateTwinArtifact> {
    const bytes = Buffer.from(input.bytes);
    const digest = sha256(bytes);
    return this.record({
      practiceId: input.practiceId,
      objectKey: storageHelpers.createOutputArtifactKey({
        practiceId: input.practiceId,
        visitId: input.visitId,
        manifestSha256: input.manifestSha256,
        outputSha256: digest,
      }),
      bytes,
      kind: "output",
    });
  }

  private read(input: ReadArtifactInput): Promise<Buffer> {
    const stored = this.objects.get(input.objectKey);
    if (
      !stored ||
      stored.versionId !== input.expectedObjectVersionId ||
      stored.etag !== input.expectedObjectEtag ||
      stored.sha256 !== input.expectedSha256 ||
      (input.expectedSizeBytes !== undefined &&
        input.expectedSizeBytes !== stored.bytes.byteLength)
    ) {
      throw new Error("Synthetic private artifact identity mismatch.");
    }
    return Promise.resolve(Buffer.from(stored.bytes));
  }

  readQuarantineArtifact(input: ReadArtifactInput): Promise<Buffer> {
    return this.read(input);
  }

  readCandidateArtifact(input: ReadArtifactInput): Promise<Buffer> {
    return this.read(input);
  }

  readSourceArtifact(input: ReadArtifactInput): Promise<Buffer> {
    return this.read(input);
  }

  readOutputArtifact(input: ReadArtifactInput): Promise<Buffer> {
    return this.read(input);
  }
}

function syntheticMalwareScanner(): TemplateTwinMalwareScanner {
  return {
    async scan(source: Uint8Array): Promise<TemplateTwinMalwareScanEvidence> {
      const unsigned = {
        profileVersion: malware.TEMPLATE_TWIN_MALWARE_SCAN_PROFILE,
        scanner: "clamav-clamd" as const,
        transport: "unix-domain-socket" as const,
        engineVersion: "synthetic-local-clamav/1.0",
        signatureVersion: "27888",
        sourceSha256: sha256(source),
        sourceSizeBytes: source.byteLength,
        verdict: "clean" as const,
        threatNameSha256: null,
        scannedAt: new Date().toISOString(),
      };
      return {
        ...unsigned,
        attestationSha256: sha256(JSON.stringify(unsigned)),
      };
    },
  };
}

function actor(token: TemplateTwinRolloutToken): CompletedCandidateActor {
  return {
    userId: physicianId,
    userEmail: physicianEmail,
    practiceId,
    rolloutToken: token,
  };
}

async function currentToken(): Promise<TemplateTwinRolloutToken> {
  const locked = await observer.$transaction(
    (tx) =>
      rollout.lockTemplateTwinRolloutForFinalClaim({
        tx,
        practiceId,
      }),
    { isolationLevel: "ReadCommitted" },
  );
  if (!locked.allowed) {
    throw new Error(`Synthetic rollout admission failed (${locked.code}).`);
  }
  return locked.token;
}

async function enableGlobalAndPractice(): Promise<TemplateTwinRolloutToken> {
  const mutationActor = {
    userId: physicianId,
    userEmail: physicianEmail,
    practiceId,
  };
  await observer.$transaction((tx) =>
    rollout.applyTemplateTwinGlobalRolloutMutation({
      tx,
      enabled: true,
      actor: mutationActor,
    }),
  );
  await observer.$transaction((tx) =>
    rollout.applyTemplateTwinPracticeRolloutMutation({
      tx,
      practiceId,
      enabled: true,
      actor: mutationActor,
    }),
  );
  return currentToken();
}

interface WaitingBackend {
  pid: number;
  waitEvent: string;
  blockers: number[];
}

async function lockWaits(): Promise<WaitingBackend[]> {
  return observer.$queryRawUnsafe<WaitingBackend[]>(
    `SELECT pid, wait_event AS "waitEvent", pg_blocking_pids(pid) AS blockers
     FROM pg_stat_activity
     WHERE datname = current_database()
       AND backend_type = 'client backend'
       AND wait_event_type = 'Lock'`,
  );
}

async function waitForDirectBlock(blockerPid: number): Promise<WaitingBackend> {
  for (let attempt = 0; attempt < 50_000; attempt += 1) {
    const waiting = await lockWaits();
    const blocked = waiting.find((row) => row.blockers.includes(blockerPid));
    if (blocked) return blocked;
    await immediate();
  }
  throw new Error(
    "PostgreSQL never reported preview issuance blocked behind global revocation.",
  );
}

async function waitForReviewRace(blockerPid: number): Promise<{
  candidateWaiter: WaitingBackend;
  rolloutWaiter: WaitingBackend;
}> {
  for (let attempt = 0; attempt < 50_000; attempt += 1) {
    const waiting = await lockWaits();
    const candidateWaiter = waiting.find((row) =>
      row.blockers.includes(blockerPid),
    );
    const rolloutWaiter = candidateWaiter
      ? waiting.find((row) => row.blockers.includes(candidateWaiter.pid))
      : undefined;
    if (candidateWaiter && rolloutWaiter) {
      return { candidateWaiter, rolloutWaiter };
    }
    await immediate();
  }
  throw new Error(
    "PostgreSQL never reported the two-review candidate/rollout lock wait chain.",
  );
}

function stableFailureCode(error: unknown): string {
  if (typeof error === "object" && error !== null) {
    const record = error as {
      code?: unknown;
      name?: unknown;
      message?: unknown;
      cause?: unknown;
    };
    if (
      typeof record.message === "string" &&
      /could not serialize|serialization failure/iu.test(record.message)
    ) {
      return "SERIALIZATION_ABORT";
    }
    if (
      typeof record.code === "string" &&
      /^[A-Z0-9_]{2,80}$/u.test(record.code)
    ) {
      return record.code;
    }
    if (
      typeof record.cause === "object" &&
      record.cause !== null &&
      "code" in record.cause &&
      typeof (record.cause as { code?: unknown }).code === "string"
    ) {
      const causeCode = (record.cause as { code: string }).code;
      if (/^[A-Z0-9_]{2,80}$/u.test(causeCode)) return causeCode;
    }
    if (
      typeof record.name === "string" &&
      /^[A-Za-z][A-Za-z0-9]{1,80}$/u.test(record.name)
    ) {
      return record.name;
    }
  }
  return "UNKNOWN_FAILURE";
}

function assertExpectedClosedFailure(code: string, context: string): void {
  if (
    ![
      "ROLLOUT_CHANGED",
      "REVIEW_CONFLICT",
      "P2034",
      "SERIALIZATION_ABORT",
    ].includes(code)
  ) {
    throw new Error(`${context} failed with an unexpected class (${code}).`);
  }
}

interface PreviewRevocationProof {
  waitEvent: string;
  failureCode: string;
  candidatePending: boolean;
  receiptCount: number;
  previewAuditCount: number;
}

async function proveGlobalRevocationWinsPreview(input: {
  candidateId: string;
  token: TemplateTwinRolloutToken;
}): Promise<PreviewRevocationProof> {
  const mutationEntered = latch<number>();
  const releaseMutation = latch();
  const mutationActor = {
    userId: physicianId,
    userEmail: physicianEmail,
    practiceId,
  };
  const revocation = revoker.$transaction(
    async (tx) => {
      const [session] = await tx.$queryRawUnsafe<Array<{ pid: number }>>(
        "SELECT pg_backend_pid() AS pid",
      );
      if (!session) throw new Error("Revocation backend PID was unavailable.");
      await rollout.applyTemplateTwinGlobalRolloutMutation({
        tx,
        enabled: false,
        actor: mutationActor,
      });
      mutationEntered.release(session.pid);
      await releaseMutation.promise;
    },
    {
      isolationLevel: "Serializable",
      maxWait: 10_000,
      timeout: 60_000,
    },
  );

  const revokerPid = await mutationEntered.promise;
  const preview = completedCandidateService
    .issueCompletedCandidateReviewPreview({
      candidateId: input.candidateId,
      actor: actor(input.token),
    })
    .then(
      () => ({ ok: true as const }),
      (error: unknown) => ({ ok: false as const, error }),
    );

  let wait: WaitingBackend;
  try {
    wait = await waitForDirectBlock(revokerPid);
  } finally {
    releaseMutation.release();
  }
  await revocation;
  const previewResult = await preview;
  if (previewResult.ok) {
    throw new Error(
      "A preview receipt was issued after concurrent global revocation won.",
    );
  }
  const failureCode = stableFailureCode(previewResult.error);
  assertExpectedClosedFailure(failureCode, "Blocked preview");

  const [candidate, receiptCount, previewAuditCount] = await Promise.all([
    observer.templateTwinCompletedCandidate.findUniqueOrThrow({
      where: { id: input.candidateId },
      select: {
        status: true,
        reviewedAt: true,
        reviewReceiptId: true,
        regions: { select: { decision: true } },
      },
    }),
    observer.templateTwinCompletedCandidateReviewReceipt.count({
      where: { candidateId: input.candidateId },
    }),
    observer.templateTwinAuditOutbox.count({
      where: {
        action: "TEMPLATE_TWIN_COMPLETED_CANDIDATE_REVIEW_PREVIEWED",
        targetId: input.candidateId,
      },
    }),
  ]);
  const candidatePending =
    candidate.status === "PENDING_REVIEW" &&
    candidate.reviewedAt === null &&
    candidate.reviewReceiptId === null &&
    candidate.regions.length > 0 &&
    candidate.regions.every((region) => region.decision === "PENDING");
  if (!candidatePending || receiptCount !== 0 || previewAuditCount !== 0) {
    throw new Error(
      "Global revocation did not leave preview receipt, candidate, and audit state fail-closed.",
    );
  }
  return {
    waitEvent: wait.waitEvent,
    failureCode,
    candidatePending,
    receiptCount,
    previewAuditCount,
  };
}

function receiptId(bearer: string): string {
  const match =
    /^([0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12})\.[A-Za-z0-9_-]{43}$/u.exec(
      bearer,
    );
  if (!match?.[1]) throw new Error("A protected review receipt was malformed.");
  return match[1];
}

function jsonRecord(value: Prisma.JsonValue): Record<string, Prisma.JsonValue> {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new Error("The terminal audit metadata was malformed.");
  }
  return value as Record<string, Prisma.JsonValue>;
}

interface ReviewRaceProof {
  candidateWaitEvent: string;
  rolloutWaitEvent: string;
  committedStatus: "APPROVED" | "REJECTED";
  failedReviewCode: string;
  receiptCount: number;
  consumedReceiptCount: number;
  terminalAuditCount: number;
}

async function proveOneTerminalReviewWins(input: {
  candidateId: string;
  token: TemplateTwinRolloutToken;
}): Promise<ReviewRaceProof> {
  const reviewActor = actor(input.token);
  const firstPreview =
    await completedCandidateService.issueCompletedCandidateReviewPreview({
      candidateId: input.candidateId,
      actor: reviewActor,
    });
  const secondPreview =
    await completedCandidateService.issueCompletedCandidateReviewPreview({
      candidateId: input.candidateId,
      actor: reviewActor,
    });
  const firstReceiptId = receiptId(firstPreview.reviewReceipt);
  const secondReceiptId = receiptId(secondPreview.reviewReceipt);
  if (firstReceiptId === secondReceiptId) {
    throw new Error("Two comparison openings returned the same receipt.");
  }

  const regions = await observer.templateTwinCompletedCandidateRegion.findMany({
    where: { candidateId: input.candidateId },
    orderBy: { displayOrder: "asc" },
    select: { regionId: true },
  });
  if (regions.length < 1) {
    throw new Error("The synthetic candidate has no review regions.");
  }

  const blockerHasLock = latch<number>();
  const releaseBlocker = latch();
  const blocker = candidateBlocker.$transaction(
    async (tx) => {
      const [session] = await tx.$queryRawUnsafe<Array<{ pid: number }>>(
        "SELECT pg_backend_pid() AS pid",
      );
      if (!session) throw new Error("Candidate blocker PID was unavailable.");
      await tx.$queryRaw`SELECT "id" FROM "template_twin_completed_candidates" WHERE "id" = ${input.candidateId} FOR UPDATE`;
      blockerHasLock.release(session.pid);
      await releaseBlocker.promise;
    },
    {
      isolationLevel: "Serializable",
      maxWait: 10_000,
      timeout: 60_000,
    },
  );
  const blockerPid = await blockerHasLock.promise;

  const attempts = [
    {
      desiredStatus: "APPROVED" as const,
      receiptId: firstReceiptId,
      promise: completedCandidateService.reviewCompletedCandidate({
        candidateId: input.candidateId,
        actor: reviewActor,
        payload: {
          decisions: regions.map((region) => ({
            regionId: region.regionId,
            decision: "APPROVED" as const,
          })),
          physicianAttestation: true,
          reviewReceipt: firstPreview.reviewReceipt,
        },
      }),
    },
    {
      desiredStatus: "REJECTED" as const,
      receiptId: secondReceiptId,
      promise: completedCandidateService.reviewCompletedCandidate({
        candidateId: input.candidateId,
        actor: reviewActor,
        payload: {
          decisions: regions.map((region) => ({
            regionId: region.regionId,
            decision: "REJECTED" as const,
          })),
          physicianAttestation: true,
          reviewReceipt: secondPreview.reviewReceipt,
        },
      }),
    },
  ];

  let waits: Awaited<ReturnType<typeof waitForReviewRace>>;
  try {
    waits = await waitForReviewRace(blockerPid);
  } finally {
    releaseBlocker.release();
  }
  await blocker;
  const results = await Promise.allSettled(
    attempts.map((attempt) => attempt.promise),
  );
  const winners = results
    .map((result, index) => ({ result, attempt: attempts[index]! }))
    .filter(
      (
        entry,
      ): entry is {
        result: PromiseFulfilledResult<{ status: "APPROVED" | "REJECTED" }>;
        attempt: (typeof attempts)[number];
      } => entry.result.status === "fulfilled",
    );
  const losers = results
    .map((result, index) => ({ result, attempt: attempts[index]! }))
    .filter(
      (
        entry,
      ): entry is {
        result: PromiseRejectedResult;
        attempt: (typeof attempts)[number];
      } => entry.result.status === "rejected",
    );
  if (winners.length !== 1 || losers.length !== 1) {
    throw new Error(
      `Expected one terminal review commit and one rejection; observed ${winners.length}/${losers.length}.`,
    );
  }
  const winner = winners[0]!;
  const loser = losers[0]!;
  if (winner.result.value.status !== winner.attempt.desiredStatus) {
    throw new Error("The committed terminal status differed from its payload.");
  }
  const failedReviewCode = stableFailureCode(loser.result.reason);
  assertExpectedClosedFailure(failedReviewCode, "Losing terminal review");

  const [candidate, receipts, audits, previewAuditCount] = await Promise.all([
    observer.templateTwinCompletedCandidate.findUniqueOrThrow({
      where: { id: input.candidateId },
      select: {
        status: true,
        reviewedAt: true,
        reviewReceiptId: true,
        regions: {
          orderBy: { displayOrder: "asc" },
          select: { decision: true, decidedById: true, decidedAt: true },
        },
      },
    }),
    observer.templateTwinCompletedCandidateReviewReceipt.findMany({
      where: { candidateId: input.candidateId },
      orderBy: { createdAt: "asc" },
      select: { id: true, consumedAt: true },
    }),
    observer.templateTwinAuditOutbox.findMany({
      where: {
        action: "TEMPLATE_TWIN_COMPLETED_CANDIDATE_REVIEWED",
        targetId: input.candidateId,
      },
      select: { metadata: true, status: true },
    }),
    observer.templateTwinAuditOutbox.count({
      where: {
        action: "TEMPLATE_TWIN_COMPLETED_CANDIDATE_REVIEW_PREVIEWED",
        targetId: input.candidateId,
      },
    }),
  ]);
  const consumedReceipts = receipts.filter(
    (receipt) => receipt.consumedAt !== null,
  );
  const terminalAudit = audits[0];
  if (!terminalAudit) throw new Error("The terminal review audit is missing.");
  const auditMetadata = jsonRecord(terminalAudit.metadata);
  const expectedDecision = winner.attempt.desiredStatus;
  if (
    candidate.status !== expectedDecision ||
    candidate.reviewedAt === null ||
    candidate.reviewReceiptId !== winner.attempt.receiptId ||
    candidate.regions.length !== regions.length ||
    candidate.regions.some(
      (region) =>
        region.decision !== expectedDecision ||
        region.decidedById !== physicianId ||
        region.decidedAt === null,
    ) ||
    receipts.length !== 2 ||
    consumedReceipts.length !== 1 ||
    consumedReceipts[0]?.id !== winner.attempt.receiptId ||
    consumedReceipts[0].consumedAt?.getTime() !==
      candidate.reviewedAt.getTime() ||
    receipts.find((receipt) => receipt.id === loser.attempt.receiptId)
      ?.consumedAt !== null ||
    audits.length !== 1 ||
    terminalAudit.status !== "PENDING" ||
    auditMetadata.reviewReceiptId !== winner.attempt.receiptId ||
    auditMetadata.gateOutcome !== expectedDecision.toLowerCase() ||
    previewAuditCount !== 2
  ) {
    throw new Error(
      "The winning review, receipt consumption, terminal state, and durable audit diverged.",
    );
  }

  return {
    candidateWaitEvent: waits.candidateWaiter.waitEvent,
    rolloutWaitEvent: waits.rolloutWaiter.waitEvent,
    committedStatus: expectedDecision,
    failedReviewCode,
    receiptCount: receipts.length,
    consumedReceiptCount: consumedReceipts.length,
    terminalAuditCount: audits.length,
  };
}

async function createFixture(): Promise<{
  candidateId: string;
  token: TemplateTwinRolloutToken;
}> {
  const lineage = await observer.$queryRawUnsafe<Array<{ phase: string }>>(
    `SELECT "phase"
     FROM "template_twin_lineage_migration_progress"
     WHERE "operationKey" = 'note_templates_lineage_v1'`,
  );
  if (lineage[0]?.phase !== "CONTRACTED") {
    throw new Error(
      "Disposable QA lineage must be CONTRACTED before candidate concurrency proof.",
    );
  }
  await observer.practice.create({
    data: {
      id: practiceId,
      name: "Synthetic completed candidate concurrency practice",
      slug: practiceId,
    },
  });
  await observer.user.create({
    data: {
      id: physicianId,
      email: physicianEmail,
      passwordHash: "synthetic-not-a-login-credential",
      role: "DOCTOR",
      practiceId,
    },
  });
  const token = await enableGlobalAndPractice();
  const examples = await Promise.all([
    syntheticCompletedExample(
      "Synthetic mild finding",
      "Synthetic conservative plan",
    ),
    syntheticCompletedExample(
      "Synthetic moderate finding",
      "Synthetic exercise plan",
    ),
  ]);
  activePhase = "fixture-conversion-binding";
  const minimized = await Promise.all(
    examples.map((document) =>
      sourceMetadata.minimizeTemplateTwinSourceMetadata(document),
    ),
  );
  const converted =
    await completedCandidateConverter.convertCompletedDocumentsToCandidate(
      minimized.map((example) => ({
        document: example.document,
        minimizedSha256: example.evidence.minimizedSha256,
      })),
    );
  if (
    converted.reviewProjection.candidateStructureSha256 !==
    converted.candidateStructureSha256
  ) {
    throw Object.assign(
      new Error("Candidate structure digests are not coherently bound."),
      { code: "CANDIDATE_STRUCTURE_BINDING_MISMATCH" },
    );
  }
  activePhase = "fixture-production-create";
  const created = await completedCandidateService.createCompletedCandidate({
    examples,
    identity: {
      name: "Synthetic concurrency candidate",
      encounterScope: "Synthetic follow-up encounter",
      versionDescription:
        "Two structurally matching synthetic examples for PostgreSQL concurrency proof",
    },
    actor: actor(token),
    storage: new SyntheticPrivateStorage(),
    malwareScanner: syntheticMalwareScanner(),
  });
  const candidate =
    await observer.templateTwinCompletedCandidate.findUniqueOrThrow({
      where: { id: created.candidateId },
      select: {
        status: true,
        converterVersion: true,
        reviewProjectionSha256: true,
        regions: { select: { decision: true } },
      },
    });
  if (
    candidate.status !== "PENDING_REVIEW" ||
    candidate.converterVersion !== "completed-document-candidate/1.1.0" ||
    !candidate.reviewProjectionSha256 ||
    candidate.regions.length < 1 ||
    candidate.regions.some((region) => region.decision !== "PENDING")
  ) {
    throw new Error(
      "Production candidate creation did not persist pending v1.1 evidence.",
    );
  }
  return { candidateId: created.candidateId, token };
}

async function main(): Promise<void> {
  // These dynamic imports are load-bearing: @meddoc/db must not instantiate
  // until DATABASE_URL has passed the non-production guard above.
  [
    completedCandidateService,
    rollout,
    storageHelpers,
    malware,
    completedCandidateConverter,
    sourceMetadata,
    applicationPrisma,
  ] = await Promise.all([
    import("../../../apps/transcribe-md/src/lib/template-twin/completed-candidate-service"),
    import("../../../apps/transcribe-md/src/lib/template-twin/rollout"),
    import("../../../apps/transcribe-md/src/lib/template-twin/storage"),
    import("../../../apps/transcribe-md/src/lib/template-twin/malware-scan"),
    import("../../../apps/transcribe-md/src/lib/template-twin/completed-candidate-converter"),
    import("../../../apps/transcribe-md/src/lib/template-twin/source-metadata"),
    import("@meddoc/db").then(
      (module) => module.default as unknown as PrismaClient,
    ),
  ]);

  activePhase = "fixture-create";
  const fixture = await createFixture();
  activePhase = "preview-revocation-race";
  const revocationProof = await proveGlobalRevocationWinsPreview(fixture);

  activePhase = "global-reenable";
  await observer.$transaction((tx) =>
    rollout.applyTemplateTwinGlobalRolloutMutation({
      tx,
      enabled: true,
      actor: {
        userId: physicianId,
        userEmail: physicianEmail,
        practiceId,
      },
    }),
  );
  const refreshedToken = await currentToken();
  activePhase = "terminal-review-race";
  const reviewRaceProof = await proveOneTerminalReviewWins({
    candidateId: fixture.candidateId,
    token: refreshedToken,
  });

  process.stdout.write(
    `${JSON.stringify({
      profile:
        "template-twin-completed-candidate-review-concurrency-postgres-v1",
      synthetic: true,
      databaseGuard: "passed",
      productionHelpersExercised: [
        "createCompletedCandidate",
        "issueCompletedCandidateReviewPreview",
        "reviewCompletedCandidate",
        "applyTemplateTwinGlobalRolloutMutation",
        "applyTemplateTwinPracticeRolloutMutation",
      ],
      bearerReceiptsPrinted: false,
      timingSleepsUsed: false,
      databaseObservedBlocking: true,
      globalRevocationWinsPreview: revocationProof,
      terminalReviewRace: reviewRaceProof,
      fixtureLifecycle:
        "synthetic immutable evidence retained only in the disposable database",
    })}\n`,
  );
}

void main()
  .catch((error: unknown) => {
    // Never serialize operation inputs: review bearer receipts exist only in
    // closures above and cannot enter this stable error channel.
    process.stderr.write(
      `Completed-candidate PostgreSQL concurrency proof failed at ${activePhase} (${stableFailureCode(error)}).\n`,
    );
    process.exitCode = 1;
  })
  .finally(async () => {
    await Promise.all([
      observer.$disconnect(),
      revoker.$disconnect(),
      candidateBlocker.$disconnect(),
      applicationPrisma?.$disconnect(),
    ]);
  });
