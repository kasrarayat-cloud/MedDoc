import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

const APP_ROOT = resolve(process.cwd(), "src");

function source(relative: string): string {
  return readFileSync(resolve(APP_ROOT, relative), "utf8");
}

describe("synthetic QA server-boundary architecture", () => {
  it.each([
    "app/api/visits/[id]/export/pdf/route.ts",
    "app/api/visits/[id]/export/docx/route.ts",
    "app/api/visits/[id]/export/email/route.ts",
    "app/api/visits/[id]/export/clipboard/route.ts",
  ])("blocks the generic delivery route %s", (route) => {
    const routeSource = source(route);
    expect(routeSource).toContain("isOwnedTemplateTwinStagingQaVisit");
    expect(routeSource).toContain('return apiError("not found", 404)');
  });

  it.each([
    "app/api/visits/[id]/archive/route.ts",
    "app/api/visits/[id]/delete/route.ts",
    "app/api/visits/[id]/restore/route.ts",
    "app/api/visits/[id]/unarchive/route.ts",
    "app/api/visits/[id]/dictation/upload/route.ts",
    "app/api/visits/[id]/dictation/audio/route.ts",
    "app/api/visits/[id]/text/route.ts",
    "app/api/visits/[id]/upload/route.ts",
    "app/api/visits/[id]/em-score/route.ts",
  ])("blocks unsupported generic staging surface %s", (route) => {
    const routeSource = source(route);
    expect(routeSource).toContain("isOwnedTemplateTwinStagingQaVisit");
    expect(routeSource).toMatch(/apiError\(["']not found["'], 404\)/u);
  });

  it("blocks draft metadata and speaker reassignment for immutable staging evidence", () => {
    expect(source("app/api/visits/[id]/route.ts")).toContain(
      "isOwnedTemplateTwinStagingQaVisit",
    );
    expect(source("actions/soap.ts")).toContain(
      "isOwnedTemplateTwinStagingQaVisit",
    );
    expect(source("lib/rx-warning-audit.ts")).toContain(
      "templateTwinSyntheticQaRun",
    );
  });

  it("routes generic visit retries through the durable staging run ledger", () => {
    const routeSource = source("app/api/visits/[id]/retry/route.ts");
    expect(routeSource).toContain("templateTwinSyntheticQaRun");
    expect(routeSource).toContain("isSameOriginTemplateTwinMutation");
    expect(routeSource).toContain("retryTemplateTwinStagingQaRun");
    expect(routeSource).toContain("TemplateTwinStagingQaRetryRequestSchema");
    expect(routeSource).toContain("expectedAttempt");
    expect(routeSource).toContain("status: 202");
  });

  it("binds direct run retries to the caller's exact current attempt", () => {
    const routeSource = source(
      "app/api/note-templates/template-twin/staging-qa/runs/[id]/retry/route.ts",
    );
    const serviceSource = source("lib/template-twin/staging-qa-service.ts");
    expect(routeSource).toContain("TemplateTwinStagingQaRetryRequestSchema");
    expect(routeSource).toContain("expectedAttempt");
    expect(serviceSource).toContain("run.attempt === reservedAttempt");
    expect(serviceSource).toContain("run.attempt !== expectedAttempt");
    expect(serviceSource).toContain("RETRY_ATTEMPT_STALE");
  });

  it("keeps both admission and final-transaction staging checks on signing and original download", () => {
    for (const route of [
      "app/api/visits/[id]/sign/route.ts",
      "app/api/visits/[id]/export/original-template-docx/route.ts",
    ]) {
      const routeSource = source(route);
      expect(routeSource).toContain("assertTemplateTwinStagingQaVisitGuard");
      expect(routeSource).toContain(
        "lockAndAssertTemplateTwinStagingQaOperation",
      );
    }

    const guardSource = source("lib/template-twin/staging-qa-visit-guard.ts");
    expect(guardSource).toContain("TEMPLATE_TWIN_STAGING_QA_RUN_GUARD_SELECT");
    expect(guardSource).toContain("expectedAttempt");
    expect(guardSource).toContain(
      "input.run.practiceId !== input.actor.practiceId",
    );
    expect(guardSource).toContain(
      "input.currentRolloutToken.practiceId !== input.actor.practiceId",
    );
  });

  it("fails closed on marked visit page, full-read, and polling surfaces", () => {
    for (const route of [
      "app/visits/[id]/page.tsx",
      "app/api/visits/[id]/route.ts",
      "app/api/visits/[id]/status/route.ts",
    ]) {
      const routeSource = source(route);
      expect(routeSource).toContain("assertTemplateTwinStagingQaVisitGuard");
      expect(routeSource).toContain("TemplateTwinStagingQaDisabledError");
    }
  });

  it("guards field correction and manifest acknowledgement inside their final-claim services", () => {
    for (const service of [
      "lib/template-twin/review-service.ts",
      "lib/template-twin/review-acknowledgement.ts",
    ]) {
      const serviceSource = source(service);
      expect(serviceSource).toContain("assertTemplateTwinStagingQaVisitGuard");
      expect(serviceSource).toContain("lockTemplateTwinRolloutForFinalClaim");
    }
  });

  it("locks exact staging run attempts before either fill-manifest claim path", () => {
    const fillEngine = source("lib/template-twin/fill-engine.ts");
    expect(
      fillEngine.match(/lockSyntheticQaAttempt\(/g)?.length,
    ).toBeGreaterThanOrEqual(2);
    expect(fillEngine).toContain("outputWrittenUnclaimed");
    expect(fillEngine).toContain("TEMPLATE_TWIN_STAGING_QA_ATTEMPT_STALE");
  });

  it("keeps staging attempts out of uncancellable retries and live side channels", () => {
    const worker = source("worker.ts");
    expect(worker).toContain("if (job.data.syntheticQaRunId)");
    expect(worker).toContain("failTemplateTwinSyntheticQaProcessing");
    expect(worker).toContain("getTemplateTwinSyntheticQaProviderContext()");

    const sign = source("app/api/visits/[id]/sign/route.ts");
    expect(sign).toContain("if (emBlob && !stagingQaRunId)");
    expect(sign).toContain("if (!stagingQaRunId)");
    expect(sign).toContain("captureEditPattern");

    const queue = source("lib/queue.ts");
    expect(queue).toMatch(/enqueueTemplateTwinSyntheticQaVisit[\s\S]*attempts: 1/u);
    expect(source("worker/cleanup/stuck-visit-watchdog.ts")).toContain(
      "templateTwinSyntheticQaRun: { is: null }",
    );
  });

  it("allows the reserved synthetic date only for the exact immutable staging source", () => {
    const syntheticTest = source("lib/template-twin/synthetic-test.ts");
    expect(syntheticTest).toContain("isTemplateTwinStagingQaFixtureSource");
    expect(syntheticTest).toContain("compiled.sourceArtifact.sha256");
    expect(syntheticTest).toContain("compiled.sourceArtifact.sizeBytes");
    expect(syntheticTest).toContain(
      "assertTemplateTwinStagingQaEvidencePhiFree",
    );
    expect(syntheticTest).toContain(
      "assertTemplateTwinSyntheticEvidencePhiFree",
    );
  });

  it("proves run source and mappings before the model-backed privacy callback", () => {
    const service = source("lib/template-twin/staging-qa-service.ts");
    const boundaryCall = service.indexOf(
      "runWithTemplateTwinStagingQaCertificationProvider",
      service.indexOf("createTemplateTwinStagingQaRun"),
    );
    const privacyCall = service.indexOf(
      "assertTemplateTwinStagingQaEvidencePhiFree",
      boundaryCall,
    );
    expect(boundaryCall).toBeGreaterThan(0);
    expect(privacyCall).toBeGreaterThan(boundaryCall);
    expect(service.slice(boundaryCall, privacyCall)).toContain(
      "TEMPLATE_TWIN_STAGING_QA_FIXTURE_SHA256",
    );
    expect(service.slice(boundaryCall, privacyCall)).toContain(
      "TEMPLATE_TWIN_STAGING_QA_FIXTURE_SIZE_BYTES",
    );
    expect(service.slice(privacyCall, privacyCall + 500)).toContain(
      "providerVisitId",
    );

    const boundary = source(
      "lib/template-twin/staging-qa-lifecycle-guard.ts",
    );
    expect(boundary.indexOf("confirmMappings({")).toBeLessThan(
      boundary.indexOf("assertTemplateTwinStagingQaGate(env)"),
    );
    expect(boundary.indexOf("confirmMappings({")).toBeLessThan(
      boundary.indexOf("pinRollout({"),
    );
  });

  it("forces exact-fixture typed extraction and voice transcription through the staging provider boundary", () => {
    const syntheticTest = source("lib/template-twin/synthetic-test.ts");
    expect(syntheticTest).toContain(
      "runWithTemplateTwinStagingQaCertificationProvider",
    );
    expect(syntheticTest).toContain("providerVisitId");
    expect(syntheticTest).toContain("compiled.sourceArtifact.sha256");
    expect(syntheticTest).toContain("compiled.sourceArtifact.sizeBytes");

    const voiceRoute = source(
      "app/api/note-templates/template-twin/[id]/synthetic-test-voice/route.ts",
    );
    expect(voiceRoute).toContain(
      "runWithTemplateTwinStagingQaCertificationProvider",
    );
    expect(voiceRoute).toContain("sourceArtifact.sha256");
    expect(voiceRoute).toMatch(/sourceArtifact\s*\.sizeBytes/u);
    expect(voiceRoute).toContain("visitId: providerVisitId");

    const boundary = source(
      "lib/template-twin/staging-qa-lifecycle-guard.ts",
    );
    expect(boundary).toContain("assertTemplateTwinStagingQaGate");
    expect(boundary).toContain(
      "assertTemplateTwinSyntheticQaProviderEnvironment",
    );
    expect(boundary).toContain("pinTemplateTwinRollout");
    expect(boundary).toContain(
      "runWithTemplateTwinSyntheticQaProviderContext",
    );
  });
});
