import { createHash, randomBytes } from "node:crypto";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { expect, test, type APIResponse, type Page } from "@playwright/test";
import JSZip from "jszip";

import {
  buildTemplateTwinSafeAlphaDocx,
  certifiedTemplateTwinMappings,
  TEMPLATE_TWIN_SYNTHETIC_EVIDENCE,
} from "../fixtures/template-twin-safe-alpha";
import { loginUser } from "../helpers/auth";
import { createPatientAndContinue } from "../helpers/patient";
import {
  assertTemplateTwinQaDatabaseGuards,
  markTemplateTwinQaVisitFailed,
  readTemplateTwinQaFields,
  readTemplateTwinQaFill,
  readTemplateTwinQaInventory,
  removeTemplateTwinQaObjectVersion,
  setTemplateTwinQaPractice,
} from "../helpers/templateTwin";
import { TEST_PASSWORD } from "../helpers/test-utils";
import { waitForVisitStatus } from "../helpers/waitForReady";

const DOCX_MIME =
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document";
const DICTATION_AUDIO = resolve(
  __dirname,
  "../fixtures/audio/silence-3sec.mp3",
);

test.setTimeout(300_000);

function sameOriginHeaders(page: Page): Record<string, string> {
  return {
    Origin: new URL(page.url()).origin,
    "Sec-Fetch-Site": "same-origin",
  };
}

async function responseJson<T>(response: APIResponse): Promise<T> {
  const body = await response.text();
  try {
    return JSON.parse(body) as T;
  } catch {
    throw new Error(
      `Expected JSON from ${response.url()}, got HTTP ${response.status()}: ${body}`,
    );
  }
}

async function confirmTemplateTwinReview(
  page: Page,
  visitId: string,
  expectedManifestVersion: number,
  expectedManifestSha256: string,
): Promise<void> {
  const response = await page.request.post(
    `/api/visits/${encodeURIComponent(visitId)}/template-twin/review`,
    {
      headers: {
        ...sameOriginHeaders(page),
        "Content-Type": "application/json",
      },
      data: { expectedManifestVersion, expectedManifestSha256 },
    },
  );
  expect(
    response.status(),
    `Template Twin review acknowledgement failed: ${await response.text()}`,
  ).toBe(200);
}

async function signupSyntheticDoctor(page: Page, email: string): Promise<void> {
  await page.goto("/signup");
  await page.getByLabel("Full name").fill("Synthetic Template Twin Doctor");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password", { exact: true }).fill(TEST_PASSWORD);
  await page.getByLabel("Confirm password").fill(TEST_PASSWORD);
  await page.getByRole("checkbox").check();
  await page.getByRole("button", { name: /create account/i }).click();

  await page.waitForURL(/\/(?:dashboard|check-email)(?:\?|$)/, {
    timeout: 20_000,
  });
  setTemplateTwinQaPractice({ email, enabled: false });
  if (!/\/dashboard$/.test(new URL(page.url()).pathname)) {
    await loginUser(page, email, TEST_PASSWORD);
  }
}

async function uploadTemplate(
  page: Page,
  source: Buffer,
): Promise<APIResponse> {
  return page.request.post("/api/note-templates/template-twin/upload", {
    headers: sameOriginHeaders(page),
    multipart: {
      file: {
        name: "synthetic-template-twin-safe-alpha.docx",
        mimeType: DOCX_MIME,
        buffer: source,
      },
      templateName: "Synthetic primary-care Template Twin",
      encounterScope: "primary-care",
      versionDescription: "Synthetic infrastructure QA alpha",
    },
  });
}

async function createReadySyntheticDictationVisit(page: Page): Promise<string> {
  await page.goto("/visits/new");
  await createPatientAndContinue(page, "Synthetic Dictation Patient");
  await page.getByRole("button", { name: /dictate live/i }).click();
  await page.waitForURL(/\/visits\/c[a-z0-9]{10,}/, { timeout: 15_000 });
  const visitId = new URL(page.url()).pathname.split("/").pop();
  if (!visitId)
    throw new Error("Synthetic dictation visit id was not created.");

  const audio = readFileSync(DICTATION_AUDIO);
  const upload = await page.request.post(
    `/api/visits/${encodeURIComponent(visitId)}/dictation/upload`,
    {
      data: audio,
      headers: {
        "Content-Type": "audio/mpeg",
        "Content-Length": String(audio.byteLength),
        "X-TM-Filename": "synthetic-dictation.mp3",
      },
    },
  );
  expect(
    upload.ok(),
    `Synthetic dictation upload failed: ${upload.status()} ${await upload.text()}`,
  ).toBe(true);
  await waitForVisitStatus(page, visitId, "READY", { timeoutMs: 90_000 });
  return visitId;
}

async function createReadyTemplateTwinTextVisit(
  page: Page,
  patientName: string,
): Promise<string> {
  await page.goto("/visits/new");
  await createPatientAndContinue(page, patientName);
  await page.getByRole("button", { name: /text to soap/i }).click();
  await page.waitForURL(/\/visits\/c[a-z0-9]{10,}/, { timeout: 15_000 });
  const visitId = new URL(page.url()).pathname.split("/").pop();
  if (!visitId) throw new Error("Synthetic text visit id was not created.");
  await page
    .getByLabel("Clinical shorthand")
    .fill(TEMPLATE_TWIN_SYNTHETIC_EVIDENCE);
  await page.getByRole("button", { name: /expand to soap/i }).click();
  await waitForVisitStatus(page, visitId, "READY", { timeoutMs: 90_000 });
  return visitId;
}

async function expectVerifiedEvidenceFill(visitId: string) {
  const fill = await expect
    .poll(() => readTemplateTwinQaFill(visitId), {
      timeout: 20_000,
      message: "worker must persist a Template Twin fill manifest",
    })
    .not.toBeNull();
  void fill;
  const current = readTemplateTwinQaFill(visitId);
  expect(current).not.toBeNull();
  expect(current).toMatchObject({
    status: "VERIFIED",
    visitStatus: "READY",
    roundTripVerified: true,
  });
  expect(current!.soapVersion).toBe(current!.currentSoapVersion);
  expect(current!.soapSha256).toBe(current!.fillManifest.soapSha256);
  expect(current!.currentSoapFinal).toContain("synthetic wrist discomfort");
  expect(current!.currentSoapFinal).toContain("Current");
  expect(current!.currentSoapFinal).toContain("Syntheticmed");
  expect(current!.currentSoapFinal).toContain("synthetic brace");
  expect(current!.currentSoapFinal).not.toContain("headache");
  expect(current!.fillManifest.fields).toHaveLength(4);
  expect(
    current!.fillManifest.fields.every((field) => field.value !== null),
  ).toBe(true);
  expect(
    current!.fillManifest.fields.every(
      (field) =>
        field.sourceFactIds.length > 0 && field.evidenceAnchorIds.length > 0,
    ),
  ).toBe(true);
  expect(
    current!.fillManifest.facts.every(
      (fact) => fact.sourceTranscriptOffsets !== null,
    ),
  ).toBe(true);
  expect(current!.outputObjectKey).toMatch(
    new RegExp(`^practices/.+/template-twin/outputs/${visitId}/`),
  );
  expect(current!.outputSha256).toMatch(/^[a-f0-9]{64}$/);
  expect(current!.outputSizeBytes).toBeGreaterThan(0);
  return current!;
}

test("Template Twin: isolated QA routes, Postgres, worker, and MinIO preserve the original DOCX fail closed", async ({
  page,
}) => {
  const email = `qa-template-twin-e2e-${Date.now().toString(36)}-${randomBytes(4).toString("hex")}@synthetic.test`;
  const source = await buildTemplateTwinSafeAlphaDocx();
  await signupSyntheticDoctor(page, email);

  // Server-side rollout enforcement: a hidden UI is not enough. The exact
  // same authenticated upload is rejected until the QA practice is enabled.
  const disabledUpload = await uploadTemplate(page, source);
  expect(disabledUpload.status()).toBe(403);
  expect(await responseJson<{ error: string }>(disabledUpload)).toMatchObject({
    error: expect.stringMatching(/not enabled|unavailable/i),
  });

  const actor = setTemplateTwinQaPractice({ email, enabled: true });
  const upload = await uploadTemplate(page, source);
  const uploadPayload = await responseJson<{
    ok: boolean;
    certificationUrl?: string;
    error?: string;
  }>(upload);
  expect(
    upload.status(),
    `Template Twin upload failed: ${JSON.stringify(uploadPayload)}`,
  ).toBe(201);
  expect(uploadPayload.ok).toBe(true);
  expect(uploadPayload.certificationUrl).toMatch(
    /^\/settings\/note-format\/.+\/certify$/,
  );
  const templateId = uploadPayload.certificationUrl!.split("/").at(-2)!;

  const persisted = readTemplateTwinQaFields(templateId);
  expect(persisted.fields.map((field) => field.originalLabel)).toEqual([
    "Chief concern",
    "Smoking status",
    "Medication documented",
    "Plan item",
  ]);
  const certifiedMappings = certifiedTemplateTwinMappings(persisted.fields);
  const mappingResponse = await page.request.patch(
    `/api/note-templates/template-twin/${encodeURIComponent(templateId)}/mappings`,
    {
      headers: {
        ...sameOriginHeaders(page),
        "Content-Type": "application/json",
      },
      data: {
        expectedMappingsSha256: persisted.mappingsSha256,
        mappings: certifiedMappings,
      },
    },
  );
  const mappingPayload = await responseJson<{
    ok: boolean;
    workspace?: {
      mappingsSha256: string;
      stats: Record<string, number>;
      fields: unknown[];
    };
    error?: string;
  }>(mappingResponse);
  expect(
    mappingResponse.status(),
    `Mapping save failed: ${JSON.stringify(mappingPayload)}`,
  ).toBe(200);
  expect(mappingPayload.workspace).toMatchObject({
    stats: {
      totalFields: 4,
      dropdowns: 1,
      checkboxes: 1,
      tables: 1,
      blockingUnsupported: 0,
    },
  });
  const mappingsSha256 = mappingPayload.workspace!.mappingsSha256;

  const syntheticText = await page.request.post(
    `/api/note-templates/template-twin/${encodeURIComponent(templateId)}/synthetic-test`,
    {
      headers: {
        ...sameOriginHeaders(page),
        "Content-Type": "application/json",
      },
      data: {
        expectedMappingsSha256: mappingsSha256,
        encounterText: TEMPLATE_TWIN_SYNTHETIC_EVIDENCE,
      },
    },
  );
  const textPayload = await responseJson<{
    ok: boolean;
    workspace?: {
      latestSyntheticTest: {
        roundTripVerified: boolean;
        fieldCoverage: Array<{ exercised: boolean }>;
        downloadUrl: string;
      };
    };
    error?: string;
  }>(syntheticText);
  expect(
    syntheticText.status(),
    `Typed synthetic certification failed: ${JSON.stringify(textPayload)}`,
  ).toBe(200);
  expect(textPayload.workspace!.latestSyntheticTest).toMatchObject({
    roundTripVerified: true,
  });
  expect(
    textPayload.workspace!.latestSyntheticTest.fieldCoverage.every(
      (field) => field.exercised,
    ),
  ).toBe(true);

  const testOutput = await page.request.get(
    textPayload.workspace!.latestSyntheticTest.downloadUrl,
  );
  expect(testOutput.status()).toBe(200);
  const testOutputBytes = Buffer.from(await testOutput.body());
  const testZip = await JSZip.loadAsync(testOutputBytes);
  const testDocumentXml = await testZip
    .file("word/document.xml")!
    .async("string");
  expect(testDocumentXml).toContain("synthetic wrist discomfort");
  expect(testDocumentXml).toContain("<w:t>Current</w:t>");
  expect(testDocumentXml).toContain('w14:checked w14:val="1"');
  expect(testDocumentXml).toContain("Use synthetic brace");
  expect(testDocumentXml).not.toContain("w:showingPlcHdr");
  expect(testDocumentXml).not.toContain('w:rStyle w:val="PlaceholderText"');
  expect(await testZip.file("word/header1.xml")!.async("string")).toContain(
    "Synthetic Clinic Header",
  );
  expect(await testZip.file("word/footer1.xml")!.async("string")).toContain(
    'w:instr=" PAGE "',
  );

  // The provider boundary is real; only its deterministic QA implementation
  // is mocked. Audio bytes are transient and never written to the artifact
  // bucket by the certification route.
  const voiceResponse = await page.request.post(
    `/api/note-templates/template-twin/${encodeURIComponent(templateId)}/synthetic-test-voice`,
    {
      headers: sameOriginHeaders(page),
      multipart: {
        audio: {
          name: "synthetic-template-test.mp3",
          mimeType: "audio/mpeg",
          buffer: readFileSync(DICTATION_AUDIO),
        },
        expectedMappingsSha256: mappingsSha256,
      },
    },
  );
  const voicePayload = await responseJson<{
    ok: boolean;
    workspace?: {
      latestSyntheticTest: {
        roundTripVerified: boolean;
        fieldCoverage: Array<{ exercised: boolean }>;
        provenanceSha256: string;
      };
    };
    error?: string;
  }>(voiceResponse);
  expect(
    voiceResponse.status(),
    `Voice synthetic certification failed: ${JSON.stringify(voicePayload)}`,
  ).toBe(200);
  expect(voicePayload.workspace!.latestSyntheticTest.roundTripVerified).toBe(
    true,
  );
  expect(
    voicePayload.workspace!.latestSyntheticTest.fieldCoverage.every(
      (field) => field.exercised,
    ),
  ).toBe(true);

  const certifyResponse = await page.request.post(
    `/api/note-templates/template-twin/${encodeURIComponent(templateId)}/certify`,
    {
      headers: {
        ...sameOriginHeaders(page),
        "Content-Type": "application/json",
      },
      data: {
        expectedMappingsSha256: mappingsSha256,
        expectedSyntheticTestProvenanceSha256:
          voicePayload.workspace!.latestSyntheticTest.provenanceSha256,
        acknowledgeStructure: true,
        acknowledgeSyntheticOutput: true,
        optionalFieldWaivers: [],
      },
    },
  );
  const certifyPayload = await responseJson<{
    ok: boolean;
    workspace?: {
      template: { status: string; certificationStatus: string };
    };
    error?: string;
  }>(certifyResponse);
  expect(
    certifyResponse.status(),
    `Certification failed: ${JSON.stringify(certifyPayload)}`,
  ).toBe(200);
  expect(certifyPayload.workspace!.template).toMatchObject({
    status: "active",
    certificationStatus: "certified",
  });

  const certifiedInventory = readTemplateTwinQaInventory(actor.practiceId);
  expect(certifiedInventory).toMatchObject({
    sourceArtifacts: 1,
    compiledVersions: 1,
    fieldDefinitions: 4,
    certifications: 1,
  });
  expect(certifiedInventory.objectLedgerRows).toBeGreaterThanOrEqual(3);
  expect(certifiedInventory.auditOutboxRows).toBeGreaterThanOrEqual(1);

  // Typed input traverses real visit routes, BullMQ, the worker, Postgres, the
  // resolver/validator/renderer/readback stack, and MinIO.
  const typedVisitId = await createReadyTemplateTwinTextVisit(
    page,
    "Synthetic Template Twin Patient",
  );
  let typedFill = await expectVerifiedEvidenceFill(typedVisitId);
  expect(typedFill.noteTemplateId).toBe(templateId);

  await page.goto(`/visits/${typedVisitId}`);
  await page.getByRole("tab", { name: /^template/i }).click();
  await expect(page.getByText(/original template docx/i).first()).toBeVisible();

  const chiefField = typedFill.fillManifest.fields.find((field) => {
    const definition = persisted.fields.find(
      (candidate) => candidate.fieldId === field.fieldId,
    );
    return definition?.originalLabel === "Chief concern";
  });
  expect(chiefField).toBeDefined();
  const correction = await page.request.patch(
    `/api/visits/${encodeURIComponent(typedVisitId)}/template-twin/corrections`,
    {
      headers: {
        ...sameOriginHeaders(page),
        "Content-Type": "application/json",
      },
      data: {
        expectedManifestVersion: typedFill.manifestVersion,
        fieldId: chiefField!.fieldId,
        value: "synthetic wrist discomfort reviewed",
        sourceFactIds: chiefField!.sourceFactIds,
        reasonCode: "physician_review_correction",
        createMappingRule: false,
      },
    },
  );
  expect(
    correction.status(),
    `Physician correction failed: ${await correction.text()}`,
  ).toBe(200);
  const correctedFill = readTemplateTwinQaFill(typedVisitId)!;
  expect(correctedFill.manifestVersion).toBe(typedFill.manifestVersion + 1);
  expect(
    correctedFill.fillManifest.fields.find(
      (field) => field.fieldId === chiefField!.fieldId,
    )?.value,
  ).toBe("synthetic wrist discomfort reviewed");
  expect(readTemplateTwinQaInventory(actor.practiceId).reviewDecisions).toBe(1);

  // Compile a second, inactive lineage solely to prove the migrated database
  // rejects a review decision linked to a field from another compiled version.
  const foreignUpload = await uploadTemplate(page, source);
  const foreignUploadPayload = await responseJson<{
    ok: boolean;
    certificationUrl?: string;
    error?: string;
  }>(foreignUpload);
  expect(
    foreignUpload.status(),
    `Adversarial lineage setup failed: ${JSON.stringify(foreignUploadPayload)}`,
  ).toBe(201);
  const foreignNoteTemplateId = foreignUploadPayload
    .certificationUrl!.split("/")
    .at(-2)!;
  assertTemplateTwinQaDatabaseGuards({
    fillManifestId: correctedFill.id,
    foreignNoteTemplateId,
  });

  // Editing the physician-visible SOAP invalidates the Twin immediately and
  // the server refuses a direct sign until the worker regenerates against the
  // new SOAP version/hash.
  await page.reload();
  await page.getByRole("button", { name: "Edit SOAP note" }).first().click();
  const soapEditor = page.getByRole("textbox", { name: "Edit SOAP note" });
  await soapEditor.fill(
    `${await soapEditor.inputValue()}\n\nSynthetic QA SOAP edit marker.`,
  );
  await soapEditor.press("Escape");
  await expect(page.getByText("Synthetic QA SOAP edit marker.")).toBeVisible({
    timeout: 15_000,
  });
  await expect
    .poll(() => readTemplateTwinQaFill(typedVisitId)?.status, {
      timeout: 15_000,
    })
    .toBe("NEEDS_REVIEW");
  const staleFill = readTemplateTwinQaFill(typedVisitId)!;
  expect(staleFill.currentSoapVersion).toBeGreaterThan(staleFill.soapVersion!);

  const staleSign = await page.request.post(
    `/api/visits/${encodeURIComponent(typedVisitId)}/sign`,
    { data: { destinations: [] } },
  );
  const staleSignPayload = await responseJson<{
    code: string;
    blockerCodes?: string[];
  }>(staleSign);
  expect(staleSign.status()).toBe(422);
  expect(staleSignPayload).toMatchObject({
    code: "TEMPLATE_TWIN_SIGN_BLOCKED",
    blockerCodes: expect.arrayContaining(["SOAP_BINDING_MISMATCH"]),
  });

  markTemplateTwinQaVisitFailed(typedVisitId);
  const retry = await page.request.post(
    `/api/visits/${encodeURIComponent(typedVisitId)}/retry`,
  );
  expect(retry.status(), `Worker retry failed: ${await retry.text()}`).toBe(
    200,
  );
  await waitForVisitStatus(page, typedVisitId, "READY", { timeoutMs: 90_000 });
  typedFill = await expectVerifiedEvidenceFill(typedVisitId);
  expect(typedFill.currentSoapVersion).toBe(staleFill.currentSoapVersion);
  expect(typedFill.soapSha256).not.toBe(staleFill.soapSha256);
  const unreviewedSign = await page.request.post(
    `/api/visits/${encodeURIComponent(typedVisitId)}/sign`,
    { data: { destinations: [] } },
  );
  expect(unreviewedSign.status()).toBe(422);
  expect(
    await responseJson<{ blockerCodes?: string[] }>(unreviewedSign),
  ).toMatchObject({
    blockerCodes: expect.arrayContaining(["FILL_REVIEW_REQUIRED"]),
  });
  await confirmTemplateTwinReview(
    page,
    typedVisitId,
    typedFill.manifestVersion,
    typedFill.manifestSha256,
  );

  // Destination-independent byte verification: an empty delivery selection
  // still requires a stream-read/hash/size check of the stored DOCX.
  const sign = await page.request.post(
    `/api/visits/${encodeURIComponent(typedVisitId)}/sign`,
    { data: { destinations: [] } },
  );
  expect(sign.status(), `Template Twin sign failed: ${await sign.text()}`).toBe(
    200,
  );
  await waitForVisitStatus(page, typedVisitId, "SIGNED", { timeoutMs: 15_000 });
  const signedFill = readTemplateTwinQaFill(typedVisitId)!;
  expect(signedFill.status).toBe("SIGNED");

  const originalOutput = await page.request.get(
    `/api/visits/${encodeURIComponent(typedVisitId)}/export/original-template-docx`,
  );
  expect(originalOutput.status()).toBe(200);
  const originalBytes = Buffer.from(await originalOutput.body());
  expect(createHash("sha256").update(originalBytes).digest("hex")).toBe(
    signedFill.outputSha256,
  );
  expect(originalBytes.byteLength).toBe(signedFill.outputSizeBytes);
  const signedZip = await JSZip.loadAsync(originalBytes);
  expect(await signedZip.file("word/document.xml")!.async("string")).toContain(
    "Synthetic Template Twin QA — immutable static title",
  );
  expect(await signedZip.file("word/header1.xml")!.async("string")).toContain(
    "Synthetic Clinic Header",
  );

  // A real mocked-provider dictation visit follows the same active template,
  // evidence resolver, exact renderer, object store, and sign-time byte gate.
  const dictationVisitId = await createReadySyntheticDictationVisit(page);
  const dictationFill = await expectVerifiedEvidenceFill(dictationVisitId);
  expect(dictationFill.noteTemplateId).toBe(templateId);
  await confirmTemplateTwinReview(
    page,
    dictationVisitId,
    dictationFill.manifestVersion,
    dictationFill.manifestSha256,
  );
  const dictationSign = await page.request.post(
    `/api/visits/${encodeURIComponent(dictationVisitId)}/sign`,
    { data: { destinations: [] } },
  );
  expect(
    dictationSign.status(),
    `Synthetic dictation sign failed: ${await dictationSign.text()}`,
  ).toBe(200);

  // Adversarial deletion of the exact pinned QA MinIO version: a replacement
  // or latest-key read must never satisfy the immutable signing claim.
  const corruptVisitId = await createReadyTemplateTwinTextVisit(
    page,
    "Synthetic Corrupt Object Patient",
  );
  const corruptFill = await expectVerifiedEvidenceFill(corruptVisitId);
  await confirmTemplateTwinReview(
    page,
    corruptVisitId,
    corruptFill.manifestVersion,
    corruptFill.manifestSha256,
  );
  expect(corruptFill.outputVersionId).toBeTruthy();
  removeTemplateTwinQaObjectVersion(
    corruptFill.outputObjectKey!,
    corruptFill.outputVersionId!,
  );
  const corruptSign = await page.request.post(
    `/api/visits/${encodeURIComponent(corruptVisitId)}/sign`,
    { data: { destinations: [] } },
  );
  const corruptPayload = await responseJson<{ code: string }>(corruptSign);
  expect(corruptSign.status()).toBe(409);
  expect(corruptPayload.code).toBe("TEMPLATE_TWIN_OUTPUT_INTEGRITY_FAILED");
  expect(readTemplateTwinQaFill(corruptVisitId)).toMatchObject({
    status: "VERIFIED",
    visitStatus: "READY",
  });
});
