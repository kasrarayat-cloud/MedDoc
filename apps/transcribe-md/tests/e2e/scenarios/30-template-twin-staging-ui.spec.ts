import { createHash, randomBytes } from "node:crypto";
import { execFileSync, execSync } from "node:child_process";
import { mkdirSync, readFileSync, statSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";

import { expect, test, type Browser, type Page } from "@playwright/test";
import {
  TEMPLATE_TWIN_SYNTHETIC_QA_EVIDENCE,
  TEMPLATE_TWIN_SYNTHETIC_QA_TRANSCRIPT,
} from "../../../../../packages/ai/src/synthetic-qa-context";

import {
  TEMPLATE_TWIN_READBACK_CONTRACT_VERSION,
  compileTemplateDocx,
  inspectDocxPackage,
  readbackTemplateDocxOutput,
} from "../../../src/lib/note-template-docx";
import { canonicalSha256 } from "../../../src/lib/template-twin/canonical";
import type { TemplateTwinFillManifest } from "../../../src/lib/template-twin/ir";
import { loginUser } from "../helpers/auth";
import { QA_COMPOSE } from "../helpers/qa-compose";
import {
  assertTemplateTwinStagingQaDatabaseTamperGuards,
  readTemplateTwinQaApprovedMappingsSha256,
  readTemplateTwinQaFill,
  readTemplateTwinStagingQaIdempotencyInventory,
  readTemplateTwinStagingQaRunByVisit,
  setTemplateTwinQaPractice,
} from "../helpers/templateTwin";
import { TEST_PASSWORD } from "../helpers/test-utils";
import { waitForVisitStatus } from "../helpers/waitForReady";

const FIXTURE_VERSION = "template-twin-staging-safe-docx/1.0.0";
const ARTIFACT_ROOT = resolve(
  process.cwd(),
  process.env.TEMPLATE_TWIN_STAGING_ARTIFACT_DIR ??
    "template-twin-staging-artifacts",
);
const AXE_SOURCE = readFileSync(
  resolve(process.cwd(), "../../node_modules/axe-core/axe.min.js"),
  "utf8",
);
const SYNTHETIC_ENCOUNTER = TEMPLATE_TWIN_SYNTHETIC_QA_TRANSCRIPT;
const TEMPLATE_NAME = "Template Twin Synthetic QA Fixture";
const ENCOUNTER_SCOPE = "Synthetic follow-up encounter";
const VERSION_DESCRIPTION = "Reviewed synthetic staging fixture v1";

const CONCEPT_BY_LABEL: ReadonlyArray<{
  matches: RegExp;
  value: string;
}> = [
  { matches: /chief concern/i, value: "chief_complaint" },
  { matches: /smoking status/i, value: "social_history.smoking" },
  { matches: /encounter category/i, value: "assessment" },
  { matches: /encounter date/i, value: "hpi.onset" },
  { matches: /respiratory symptom/i, value: "ros.respiratory" },
  { matches: /plan item/i, value: "plan" },
  { matches: /plan detail/i, value: "plan" },
  { matches: /synthetic detail|insert synthetic/i, value: "hpi.context" },
];

test.setTimeout(420_000);

function sha256(bytes: Uint8Array): string {
  return createHash("sha256").update(bytes).digest("hex");
}

function sameOriginHeaders(page: Page): Record<string, string> {
  return {
    Origin: new URL(page.url()).origin,
    "Sec-Fetch-Site": "same-origin",
  };
}

async function revealNoteFormatSettings(page: Page): Promise<void> {
  await expect(
    page.getByRole("heading", { name: "Settings", exact: true }),
  ).toBeVisible();
  const tab = page.getByRole("button", { name: "Note format", exact: true });
  if ((await tab.count()) > 0) await tab.click();
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
  if (!/\/dashboard$/.test(new URL(page.url()).pathname)) {
    await loginUser(page, email, TEST_PASSWORD);
  }
}

async function saveSyntheticScreenshot(
  page: Page,
  filename: string,
): Promise<string> {
  const path = resolve(ARTIFACT_ROOT, filename);
  await page.screenshot({ path, fullPage: true, animations: "disabled" });
  return path;
}

async function expectNoSeriousAccessibilityViolations(
  page: Page,
): Promise<void> {
  await page.addScriptTag({ content: AXE_SOURCE });
  const violations = await page.evaluate(async () => {
    const axe = (
      window as unknown as {
        axe: {
          run: (
            root: Document,
            options: Record<string, unknown>,
          ) => Promise<{
            violations: Array<{ id: string; impact: string | null }>;
          }>;
        };
      }
    ).axe;
    const result = await axe.run(document, {
      runOnly: { type: "tag", values: ["wcag2a", "wcag2aa"] },
    });
    return result.violations.filter(
      (item) => item.impact === "serious" || item.impact === "critical",
    );
  });
  expect(violations).toEqual([]);
}

function canonicalFactProjection(
  facts: TemplateTwinFillManifest["facts"],
): string {
  return canonicalSha256(
    facts
      .map((fact) => ({
        concept: fact.concept,
        value: fact.value,
        polarity: fact.polarity,
        temporality: fact.temporality,
        laterality: fact.laterality,
        unit: fact.unit,
      }))
      .sort((left, right) =>
        `${left.concept}:${JSON.stringify(left.value)}`.localeCompare(
          `${right.concept}:${JSON.stringify(right.value)}`,
        ),
      ),
  );
}

async function waitForVerifiedFill(page: Page, visitId: string) {
  await waitForVisitStatus(page, visitId, "READY", { timeoutMs: 120_000 });
  await expect
    .poll(() => readTemplateTwinQaFill(visitId)?.status, {
      timeout: 120_000,
      message: "the real worker must persist a verified Template Twin fill",
    })
    .toBe("VERIFIED");
  const fill = readTemplateTwinQaFill(visitId);
  expect(fill).not.toBeNull();
  expect(fill).toMatchObject({
    visitStatus: "READY",
    roundTripVerified: true,
  });
  return fill!;
}

async function openTemplateReview(page: Page, visitId: string): Promise<void> {
  await page.goto(`/visits/${encodeURIComponent(visitId)}`);
  await page.getByRole("tab", { name: /^template/i }).click();
  await expect(
    page.getByRole("heading", { name: "Original Template DOCX" }).first(),
  ).toBeVisible({ timeout: 20_000 });
}

async function signupCrossTenantDoctor(
  browser: Browser,
  email: string,
): Promise<{ page: Page; close: () => Promise<void> }> {
  const context = await browser.newContext({
    baseURL: process.env.PW_BASE_URL ?? "http://localhost:9020",
  });
  const page = await context.newPage();
  await signupSyntheticDoctor(page, email);
  setTemplateTwinQaPractice({ email, enabled: true });
  await page.reload();
  return { page, close: () => context.close() };
}

test("Template Twin staging UI drives the real synthetic pipeline fail closed", async ({
  page,
  browser,
}) => {
  mkdirSync(ARTIFACT_ROOT, { recursive: true });
  const suffix = `${Date.now().toString(36)}-${randomBytes(4).toString("hex")}`;
  const email = `qa-template-twin-e2e-staging-${suffix}@synthetic.test`;
  const foreignEmail = `qa-template-twin-e2e-staging-foreign-${suffix}@synthetic.test`;
  const sourcePath = resolve(
    ARTIFACT_ROOT,
    "template-twin-staging-source.docx",
  );
  const outputPath = resolve(
    ARTIFACT_ROOT,
    "template-twin-staging-output.docx",
  );

  await signupSyntheticDoctor(page, email);
  setTemplateTwinQaPractice({ email, enabled: false });
  await page.goto("/settings");
  await revealNoteFormatSettings(page);
  await expect(
    page.getByText(/Template Twin synthetic QA is unavailable/i).first(),
  ).toBeVisible();
  const deniedFixture = await page.request.get(
    "/api/note-templates/template-twin/staging-qa/fixture",
  );
  expect(deniedFixture.status()).toBe(404);

  setTemplateTwinQaPractice({ email, enabled: true });
  await page.reload();
  await revealNoteFormatSettings(page);
  await expect(
    page.getByText("SYNTHETIC TEST ONLY — NOT FOR PATIENT CARE").first(),
  ).toBeVisible();
  await expectNoSeriousAccessibilityViolations(page);
  await saveSyntheticScreenshot(page, "01-settings-entry.png");

  const fixtureDownload = page.waitForEvent("download");
  await page.getByRole("link", { name: "Download synthetic fixture" }).click();
  const fixture = await fixtureDownload;
  expect(fixture.suggestedFilename()).toBe(
    "template-twin-synthetic-qa-v1.docx",
  );
  await fixture.saveAs(sourcePath);
  const source = readFileSync(sourcePath);
  expect(source.byteLength).toBeGreaterThan(1_000);
  expect(inspectDocxPackage(source).sourceSha256).toBe(sha256(source));

  // Even with the exact public filename/MIME/version, changed bytes are not
  // allowed to reach the compiler. This is the staging boundary that keeps
  // arbitrary PHI, media, and OOXML packages out of the synthetic workflow.
  const changedFixture = await page.request.post(
    "/api/note-templates/template-twin/staging-qa/upload",
    {
      headers: sameOriginHeaders(page),
      multipart: {
        file: {
          name: "template-twin-synthetic-qa-v1.docx",
          mimeType:
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
          buffer: Buffer.concat([source, Buffer.from("synthetic-change")]),
        },
        templateName: TEMPLATE_NAME,
        encounterScope: ENCOUNTER_SCOPE,
        versionDescription: VERSION_DESCRIPTION,
        fixtureVersion: FIXTURE_VERSION,
        idempotencyKey: `${suffix}-changed-fixture-upload`,
      },
    },
  );
  expect(changedFixture.status()).toBe(422);
  expect(
    (await changedFixture.json()) as { ok: boolean; code: string },
  ).toMatchObject({ ok: false, code: "SYNTHETIC_FIXTURE_NOT_ALLOWLISTED" });

  // The entry is keyboard operable: focus the explicit staging action and
  // press Enter, rather than reaching a hidden generic upload control.
  const uploadEntry = page.getByRole("button", {
    name: "Upload synthetic DOCX",
  });
  await uploadEntry.focus();
  await page.keyboard.press("Enter");
  const dialog = page.getByRole("dialog", {
    name: /synthetic Word fixture/i,
  });
  await expect(dialog).toBeVisible();
  await expect(dialog.getByLabel("Template name")).toBeFocused();
  await page.keyboard.press("Shift+Tab");
  await expect(dialog.getByRole("button", { name: "Cancel" })).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(dialog.getByLabel("Template name")).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(dialog).toBeHidden();
  await expect(uploadEntry).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(dialog).toBeVisible();
  await expect(dialog.getByLabel("Template name")).toHaveValue(TEMPLATE_NAME);
  await expect(dialog.getByLabel("Template name")).toHaveAttribute("readonly");
  await expect(dialog.getByLabel("Visit or specialty scope")).toHaveValue(
    ENCOUNTER_SCOPE,
  );
  await expect(dialog.getByLabel("Visit or specialty scope")).toHaveAttribute(
    "readonly",
  );
  await expect(dialog.getByLabel("What is this version?")).toHaveValue(
    VERSION_DESCRIPTION,
  );
  await expect(dialog.getByLabel("What is this version?")).toHaveAttribute(
    "readonly",
  );
  const chooserPromise = page.waitForEvent("filechooser");
  await dialog.getByRole("button", { name: "Choose DOCX" }).click();
  const chooser = await chooserPromise;
  await chooser.setFiles(sourcePath);
  const uploadResponsePromise = page.waitForResponse((response) =>
    response
      .url()
      .includes("/api/note-templates/template-twin/staging-qa/upload"),
  );
  await dialog.getByRole("button", { name: "Inspect and compile" }).click();
  const uploadResponse = await uploadResponsePromise;
  const uploadPayload = (await uploadResponse.json()) as {
    ok?: boolean;
    error?: string;
  };
  if (uploadResponse.status() !== 201 || uploadPayload.ok !== true) {
    throw new Error(
      `Synthetic staging upload failed (${uploadResponse.status()}): ${uploadPayload.error ?? "unknown bounded error"}`,
    );
  }
  expect({
    status: uploadResponse.status(),
    payload: uploadPayload,
  }).toMatchObject({ status: 201, payload: { ok: true } });

  await page.waitForURL(/\/settings\/note-format\/[^/]+\/certify$/, {
    timeout: 60_000,
  });
  const certificationUrl = new URL(page.url()).pathname;
  const templateId = certificationUrl.split("/").at(-2)!;
  await expect(page.getByText("One-time physician setup")).toBeVisible();
  const sourceInspection = page.getByLabel("Source inspection results");
  for (const result of [
    ["Malware scan", "Not Attested"],
    ["OOXML package safety", "Passed"],
    ["PHI and privacy inspection", "Passed"],
    ["Embedded media", "Passed"],
  ] as const) {
    const row = sourceInspection
      .locator("dt")
      .filter({ hasText: result[0] })
      .locator("..");
    await expect(row).toContainText(result[1]);
  }
  const structureSummary = page.getByLabel("Detected structure summary");
  await expect(structureSummary).toContainText(/Fields\s*8/u);
  await expect(structureSummary).toContainText(/Dropdowns\s*1/u);
  await expect(structureSummary).toContainText(/Checkboxes\s*1/u);
  await expect(structureSummary).toContainText(/Dates\s*1/u);
  await expect(structureSummary).toContainText(/Tables\s*1/u);
  await expect(structureSummary).toContainText(/Tab-only cells\s*1/u);
  await expect(structureSummary).toContainText(/Placeholders\s*1/u);
  await expect(
    page.getByRole("button", { name: "Certify & activate" }),
  ).toBeDisabled();
  await saveSyntheticScreenshot(page, "02-field-inventory.png");

  const fieldButtons = page
    .getByRole("navigation", { name: "Detected fields" })
    .getByRole("button");
  expect(await fieldButtons.count()).toBe(8);
  for (let index = 0; index < 8; index += 1) {
    const button = fieldButtons.nth(index);
    const label = (await button.textContent()) ?? "";
    const mapping = CONCEPT_BY_LABEL.find((candidate) =>
      candidate.matches.test(label),
    );
    expect(
      mapping,
      `no synthetic mapping fixture for field ${label}`,
    ).toBeDefined();
    await button.click();
    const intent = page.getByLabel("Field intent");
    if (await intent.isVisible().catch(() => false)) {
      await intent.selectOption("supported_concept");
    }
    await page
      .getByLabel("Clinical detail to fill")
      .selectOption(mapping!.value);
    await page.getByLabel("When this detail applies").selectOption("any");
    await page.getByLabel("Left or right").selectOption("not_applicable");
    await page
      .getByLabel("When this detail was not stated")
      .selectOption("requires_input");
    const required = page.getByRole("checkbox", {
      name: "Required before signing",
    });
    if (!(await required.isChecked())) await required.check();
    await page.getByRole("button", { name: "Confirm this field" }).click();
  }
  await page.getByRole("button", { name: "Save draft" }).click();
  await expect(page.getByText("8 of 8 fields confirmed")).toBeVisible({
    timeout: 20_000,
  });

  await page.getByLabel("Synthetic encounter text").fill("");
  await page
    .getByRole("button", { name: "Restore reviewed certification evidence" })
    .click();
  await expect(page.getByLabel("Synthetic encounter text")).toHaveValue(
    SYNTHETIC_ENCOUNTER,
  );
  await page.getByRole("button", { name: "Run synthetic test" }).click();
  await expect(page.getByText("Verified against current mappings")).toBeVisible(
    { timeout: 60_000 },
  );
  await expect(page.getByText("Extracted synthetic facts")).toBeVisible();
  await expect(page.getByText("Field resolution preview")).toBeVisible();
  await saveSyntheticScreenshot(page, "03-evidence-and-resolutions.png");

  await page
    .getByRole("checkbox", {
      name: /I reviewed every detected field and every unsupported item/i,
    })
    .check();
  await page
    .getByRole("checkbox", {
      name: /I inspected the synthetic filled copy/i,
    })
    .check();
  await page.getByRole("button", { name: "Certify & activate" }).click();
  await expect(page.getByText(/^Certified$/).first()).toBeVisible({
    timeout: 30_000,
  });
  await expect(
    page.getByText("Microsoft Word compatibility: Pending"),
  ).toBeVisible();
  const approvedMappingsSha256 =
    readTemplateTwinQaApprovedMappingsSha256(templateId);

  // Mocked voice and typed input enter through distinct authenticated UI
  // actions but converge on the same canonical encounter-fact projection.
  await page.getByRole("button", { name: "Start mocked-voice visit" }).click();
  await page.waitForURL(/\/visits\/[A-Za-z0-9-]+$/, { timeout: 20_000 });
  await expect(
    page.getByText("SYNTHETIC TEST ONLY — NOT FOR PATIENT CARE").first(),
  ).toBeVisible();
  const voiceVisitId = new URL(page.url()).pathname.split("/").at(-1)!;
  const voiceFill = await waitForVerifiedFill(page, voiceVisitId);

  await page.goto(certificationUrl);
  await page.getByLabel("Typed synthetic encounter").fill("");
  await page
    .getByRole("button", { name: "Restore reviewed visit evidence" })
    .click();
  await expect(page.getByLabel("Typed synthetic encounter")).toHaveValue(
    SYNTHETIC_ENCOUNTER,
  );
  const typedAdmissionRequestPromise = page.waitForRequest(
    (request) =>
      request.method() === "POST" &&
      new URL(request.url()).pathname ===
        "/api/note-templates/template-twin/staging-qa/runs",
  );
  await page
    .getByRole("button", { name: "Start typed synthetic visit" })
    .click();
  const typedAdmissionRequest = await typedAdmissionRequestPromise;
  const typedAdmissionBody = typedAdmissionRequest.postData();
  expect(typedAdmissionBody).not.toBeNull();
  const typedAdmissionPayload = JSON.parse(typedAdmissionBody!) as {
    templateId: string;
    mode: "typed";
    idempotencyKey: string;
    expectedTemplateVersion: number;
    encounterText: string;
  };
  await page.waitForURL(/\/visits\/[A-Za-z0-9-]+$/, { timeout: 20_000 });
  await expect(
    page.getByText("SYNTHETIC TEST ONLY — NOT FOR PATIENT CARE").first(),
  ).toBeVisible();
  await saveSyntheticScreenshot(page, "04-processing.png");
  const typedVisitId = new URL(page.url()).pathname.split("/").at(-1)!;
  let typedFill = await waitForVerifiedFill(page, typedVisitId);
  expect(canonicalFactProjection(typedFill.fillManifest.facts)).toBe(
    canonicalFactProjection(voiceFill.fillManifest.facts),
  );
  expect(typedFill.noteTemplateId).toBe(templateId);
  expect(typedFill.fillManifest.fields).toHaveLength(8);
  expect(
    typedFill.fillManifest.fields.every(
      (field) =>
        field.value !== null &&
        field.sourceFactIds.length > 0 &&
        field.evidenceAnchorIds.length > 0,
    ),
  ).toBe(true);
  const factById = new Map(
    typedFill.fillManifest.facts.map((fact) => [fact.factId, fact]),
  );
  for (const fact of typedFill.fillManifest.facts) {
    expect(
      fact.sourceTranscriptOffsets,
      `synthetic fact ${fact.factId} must retain exact transcript offsets`,
    ).not.toBeNull();
    const offsets = fact.sourceTranscriptOffsets!;
    expect(
      typedAdmissionPayload.encounterText.slice(offsets.start, offsets.end),
    ).toBe(fact.evidenceQuote);
    expect(fact.evidenceAnchorIds.length).toBeGreaterThan(0);
  }
  for (const field of typedFill.fillManifest.fields) {
    const citedAnchors = new Set<string>();
    for (const factId of field.sourceFactIds) {
      const fact = factById.get(factId);
      expect(
        fact,
        `field ${field.fieldId} cites missing fact ${factId}`,
      ).toBeDefined();
      for (const anchorId of fact!.evidenceAnchorIds)
        citedAnchors.add(anchorId);
    }
    expect(
      field.evidenceAnchorIds.every((anchorId) => citedAnchors.has(anchorId)),
    ).toBe(true);
  }

  const run = readTemplateTwinStagingQaRunByVisit(typedVisitId);
  expect(run).toMatchObject({
    visitId: typedVisitId,
    status: "COMPLETED",
    attempt: 1,
    fixtureVersion: FIXTURE_VERSION,
    visitStatus: "READY",
  });
  assertTemplateTwinStagingQaDatabaseTamperGuards(run!.runId);

  // Replay the browser's exact serialized request body after the worker has
  // settled. The same token and same bytes recover the existing run without
  // creating a second visit, fill, object, queue attempt, or object claim.
  const replayInventory = readTemplateTwinStagingQaIdempotencyInventory(
    run!.runId,
  );
  expect(replayInventory).toEqual({
    matchingRuns: 1,
    matchingVisits: 1,
    matchingFills: 1,
    matchingOutputObjects: 1,
  });
  const exactReplay = await page.request.post(
    "/api/note-templates/template-twin/staging-qa/runs",
    {
      headers: {
        ...sameOriginHeaders(page),
        "Content-Type": "application/json",
      },
      data: typedAdmissionBody!,
    },
  );
  expect(exactReplay.status()).toBe(200);
  expect(
    (await exactReplay.json()) as {
      ok: boolean;
      reused: boolean;
      runId: string;
      visitId: string;
      run: { attempt: number };
    },
  ).toMatchObject({
    ok: true,
    reused: true,
    runId: run!.runId,
    visitId: typedVisitId,
    run: { attempt: 1 },
  });
  expect(readTemplateTwinStagingQaIdempotencyInventory(run!.runId)).toEqual(
    replayInventory,
  );

  // Synthetic staging rows are reachable only through their guarded direct
  // visit URL. They must not affect ordinary dashboard totals, inbox/search,
  // visit pagination, or patient roster surfaces.
  for (const path of ["/dashboard?tab=all", "/visits", "/patients"]) {
    await page.goto(path);
    await expect(page.locator(`a[href="/visits/${typedVisitId}"]`)).toHaveCount(
      0,
    );
    await expect(
      page.getByText("Template Twin Synthetic QA", { exact: true }),
    ).toHaveCount(0);
  }

  // A replay token cannot be repurposed for different evidence. The
  // admission fails before a visit, queue attempt, or object can be created.
  const conflictingReplay = await page.request.post(
    "/api/note-templates/template-twin/staging-qa/runs",
    {
      headers: {
        ...sameOriginHeaders(page),
        "Content-Type": "application/json",
      },
      data: JSON.stringify({
        ...typedAdmissionPayload,
        encounterText: TEMPLATE_TWIN_SYNTHETIC_QA_EVIDENCE.chief_complaint,
      }),
    },
  );
  expect(conflictingReplay.status()).toBe(409);
  expect(
    (await conflictingReplay.json()) as { ok: boolean; code: string },
  ).toMatchObject({ ok: false, code: "IDEMPOTENCY_CONFLICT" });
  expect(readTemplateTwinStagingQaIdempotencyInventory(run!.runId)).toEqual(
    replayInventory,
  );

  await openTemplateReview(page, typedVisitId);
  await expect(page.getByText("Fields filled").locator("..")).toContainText(
    "8",
  );
  await expect(page.getByText("Need review").locator("..")).toContainText("0");
  await expectNoSeriousAccessibilityViolations(page);

  // An edited SOAP invalidates the old immutable output. The visible staging
  // recovery action requeues the same visit under a fresh guarded attempt.
  await page.getByRole("tab", { name: /^(?:note|soap)/i }).click();
  await page.getByRole("button", { name: "Edit SOAP note" }).first().click();
  const editor = page.getByRole("textbox", { name: "Edit SOAP note" });
  await editor.fill(
    `${await editor.inputValue()}\n\nSynthetic staging SOAP edit marker.`,
  );
  await editor.press("Escape");
  await expect(
    page.getByText("Synthetic staging SOAP edit marker."),
  ).toBeVisible({
    timeout: 20_000,
  });
  await expect
    .poll(() => readTemplateTwinQaFill(typedVisitId)?.status, {
      timeout: 30_000,
    })
    .toBe("NEEDS_REVIEW");
  await openTemplateReview(page, typedVisitId);
  await expect(
    page.getByRole("button", { name: "Regenerate synthetic DOCX" }),
  ).toBeVisible();
  const invalidatedRun = readTemplateTwinStagingQaRunByVisit(typedVisitId);
  expect(invalidatedRun).not.toBeNull();
  const expectedAttempt = invalidatedRun!.attempt;
  const retryUrl = `/api/note-templates/template-twin/staging-qa/runs/${encodeURIComponent(invalidatedRun!.runId)}/retry`;
  const retryRequest = {
    headers: {
      ...sameOriginHeaders(page),
      "Content-Type": "application/json",
    },
    data: { expectedAttempt },
  };
  const [firstRetry, duplicateRetry] = await Promise.all([
    page.request.post(retryUrl, retryRequest),
    page.request.post(retryUrl, retryRequest),
  ]);
  expect(firstRetry.status()).toBe(202);
  expect(duplicateRetry.status()).toBe(202);
  const firstRetryBody = (await firstRetry.json()) as {
    run: { attempt: number };
  };
  const duplicateRetryBody = (await duplicateRetry.json()) as {
    run: { attempt: number };
  };
  expect(firstRetryBody.run.attempt).toBe(expectedAttempt + 1);
  expect(duplicateRetryBody.run.attempt).toBe(expectedAttempt + 1);
  expect(readTemplateTwinStagingQaRunByVisit(typedVisitId)?.attempt).toBe(
    expectedAttempt + 1,
  );
  await page.reload();
  await expect(
    page.getByText("SYNTHETIC TEST ONLY — NOT FOR PATIENT CARE").first(),
  ).toBeVisible();
  await expect
    .poll(() => readTemplateTwinQaFill(typedVisitId)?.status, {
      timeout: 120_000,
    })
    .toBe("VERIFIED");
  typedFill = readTemplateTwinQaFill(typedVisitId)!;
  expect(typedFill.currentSoapVersion).toBe(typedFill.soapVersion);
  expect(readTemplateTwinStagingQaRunByVisit(typedVisitId)?.attempt).toBe(2);

  await openTemplateReview(page, typedVisitId);
  await page
    .getByRole("button", { name: "I reviewed every Template Twin field" })
    .click();
  await expect(
    page.getByText(
      "Physician review confirmed for this exact generated document",
    ),
  ).toBeVisible({ timeout: 20_000 });
  await page.getByText("Technical details and immutable proof").click();
  await expect(page.getByText("Audit status")).toBeVisible();
  await expect(page.getByText("Mapping version (SHA-256)")).toBeVisible();
  await expect(page.getByText(approvedMappingsSha256)).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Delete", exact: true }),
  ).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: "Archive", exact: true }),
  ).toHaveCount(0);
  await expect(
    page.getByRole("tab", { name: "Billing", exact: true }),
  ).toHaveCount(0);

  await page.getByRole("tab", { name: /^(?:note|soap)/i }).click();
  await page.getByRole("button", { name: "Sign & Send" }).click();
  const signDialog = page.getByRole("dialog", {
    name: "Sign synthetic Original Template DOCX",
  });
  await expect(signDialog.getByText("Copy to clipboard")).toHaveCount(0);
  await expect(
    signDialog.getByRole("button", { name: "Download PDF" }),
  ).toHaveCount(0);
  await expect(
    signDialog.getByRole("button", { name: "Download DOCX · Generic" }),
  ).toHaveCount(0);
  await expect(
    signDialog.getByRole("button", { name: "Email to me" }),
  ).toHaveCount(0);
  const primaryOriginal = signDialog.getByRole("button", {
    name: "Original Template DOCX · Primary",
  });
  await expect(primaryOriginal).toBeVisible();
  await expect(primaryOriginal).toBeDisabled();
  await expect(primaryOriginal).toHaveAttribute("aria-pressed", "true");
  const signedDownload = page.waitForEvent("download");
  await signDialog.getByRole("button", { name: "Sign & Deliver" }).click();
  const downloaded = await signedDownload;
  await downloaded.saveAs(outputPath);
  await waitForVisitStatus(page, typedVisitId, "SIGNED", { timeoutMs: 30_000 });

  const authorizedDownloadResponse = await page.request.get(
    `/api/visits/${encodeURIComponent(typedVisitId)}/export/original-template-docx`,
  );
  expect(authorizedDownloadResponse.status()).toBe(200);
  expect(authorizedDownloadResponse.headers()["content-type"]).toBe(
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  );
  expect(authorizedDownloadResponse.headers()["content-disposition"]).toMatch(
    /^attachment; filename="quillmd-original-template-[A-Za-z0-9._-]+\.docx"$/u,
  );
  expect(authorizedDownloadResponse.headers()["cache-control"]).toMatch(
    /private/u,
  );
  expect(authorizedDownloadResponse.headers()["cache-control"]).toMatch(
    /no-store/u,
  );
  expect(authorizedDownloadResponse.headers()["x-content-type-options"]).toBe(
    "nosniff",
  );
  const authorizedDownloadBytes = await authorizedDownloadResponse.body();
  expect(sha256(authorizedDownloadBytes)).toBe(typedFill.outputSha256);

  // The browser cannot turn a staging visit into a generic/live-provider
  // workflow by calling hidden routes directly. Only the verified original
  // DOCX delivery boundary above is available.
  for (const path of [
    `/api/visits/${encodeURIComponent(typedVisitId)}/export/pdf`,
    `/api/visits/${encodeURIComponent(typedVisitId)}/export/docx`,
    `/api/visits/${encodeURIComponent(typedVisitId)}/dictation/audio`,
  ]) {
    expect((await page.request.get(path)).status()).toBe(404);
  }
  for (const [path, data] of [
    [`/api/visits/${encodeURIComponent(typedVisitId)}/archive`, {}],
    [`/api/visits/${encodeURIComponent(typedVisitId)}/delete`, {}],
    [`/api/visits/${encodeURIComponent(typedVisitId)}/restore`, {}],
    [`/api/visits/${encodeURIComponent(typedVisitId)}/unarchive`, {}],
    [
      `/api/visits/${encodeURIComponent(typedVisitId)}/text`,
      { text: "Synthetic direct-route input must remain blocked." },
    ],
    [
      `/api/visits/${encodeURIComponent(typedVisitId)}/em-score`,
      { soapText: "Synthetic scoring bypass must remain blocked." },
    ],
    [
      `/api/visits/${encodeURIComponent(typedVisitId)}/export/clipboard`,
      { format: "generic" },
    ],
    [`/api/visits/${encodeURIComponent(typedVisitId)}/export/email`, {}],
  ] as const) {
    expect(
      (
        await page.request.post(path, {
          headers: sameOriginHeaders(page),
          data,
        })
      ).status(),
    ).toBe(404);
  }
  expect(
    (
      await page.request.patch(
        `/api/visits/${encodeURIComponent(typedVisitId)}`,
        {
          data: {
            chiefComplaint: "Synthetic direct edit must remain blocked.",
          },
        },
      )
    ).status(),
  ).toBe(404);
  for (const path of [
    `/api/visits/${encodeURIComponent(typedVisitId)}/upload`,
    `/api/visits/${encodeURIComponent(typedVisitId)}/dictation/upload`,
  ]) {
    expect(
      (
        await page.request.post(path, {
          headers: sameOriginHeaders(page),
          data: { synthetic: true },
        })
      ).status(),
    ).toBe(404);
  }

  await openTemplateReview(page, typedVisitId);
  await expect(
    page.getByText("Microsoft Word compatibility: PENDING"),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Download generated DOCX" }),
  ).toBeVisible();
  await saveSyntheticScreenshot(page, "05-signed-word-pending.png");

  const output = readFileSync(outputPath);
  expect(sha256(output)).toBe(typedFill.outputSha256);
  expect(output.byteLength).toBe(typedFill.outputSizeBytes);
  inspectDocxPackage(output);
  const ir = compileTemplateDocx(source);
  const proofs = readbackTemplateDocxOutput({
    source,
    output,
    ir,
    resolutions: typedFill.fillManifest.fields,
  });
  expect(proofs).toHaveLength(8);
  expect(
    proofs.every(
      (proof) => proof.occurrences === 1 && proof.bindingEvidence !== undefined,
    ),
  ).toBe(true);
  expect(typedFill.roundTripVerification).toMatchObject({
    verificationContractVersion: TEMPLATE_TWIN_READBACK_CONTRACT_VERSION,
    verified: true,
    packageCheck: "verified",
    fieldCheck: "verified",
    staticRegionCheck: "verified",
  });

  const foreign = await signupCrossTenantDoctor(browser, foreignEmail);
  try {
    expect(
      (
        await foreign.page.request.get(
          `/api/note-templates/template-twin/staging-qa/runs/${encodeURIComponent(run!.runId)}`,
        )
      ).status(),
    ).toBe(404);
    expect(
      (
        await foreign.page.request.get(
          `/api/visits/${encodeURIComponent(typedVisitId)}/export/original-template-docx`,
        )
      ).status(),
    ).toBe(404);
    const foreignHeaders = sameOriginHeaders(foreign.page);
    const foreignReview = await foreign.page.request.post(
      `/api/visits/${encodeURIComponent(typedVisitId)}/template-twin/review`,
      {
        headers: foreignHeaders,
        data: {
          expectedManifestVersion: typedFill.fillManifest.manifestVersion,
          expectedManifestSha256: typedFill.manifestSha256,
        },
      },
    );
    expect(foreignReview.status()).toBe(404);
    const firstField = typedFill.fillManifest.fields[0]!;
    const foreignCorrection = await foreign.page.request.post(
      `/api/visits/${encodeURIComponent(typedVisitId)}/template-twin/corrections`,
      {
        headers: foreignHeaders,
        data: {
          expectedManifestVersion: typedFill.fillManifest.manifestVersion,
          fieldId: firstField.fieldId,
          value: null,
          sourceFactIds: [],
          reasonCode: "physician_review_correction",
          createMappingRule: false,
        },
      },
    );
    expect(foreignCorrection.status()).toBe(404);
    expect(
      (
        await foreign.page.request.post(
          `/api/visits/${encodeURIComponent(typedVisitId)}/sign`,
          {
            headers: foreignHeaders,
            data: { destinations: ["docx_original_template"] },
          },
        )
      ).status(),
    ).toBe(404);
    expect(
      (
        await foreign.page.request.post(
          `/api/visits/${encodeURIComponent(typedVisitId)}/retry`,
          { headers: foreignHeaders },
        )
      ).status(),
    ).toBe(404);
    for (const path of [
      `/api/visits/${encodeURIComponent(typedVisitId)}/archive`,
      `/api/visits/${encodeURIComponent(typedVisitId)}/delete`,
      `/api/visits/${encodeURIComponent(typedVisitId)}/restore`,
      `/api/visits/${encodeURIComponent(typedVisitId)}/unarchive`,
      `/api/visits/${encodeURIComponent(typedVisitId)}/text`,
      `/api/visits/${encodeURIComponent(typedVisitId)}/dictation/upload`,
      `/api/visits/${encodeURIComponent(typedVisitId)}/upload`,
    ]) {
      expect(
        (
          await foreign.page.request.post(path, {
            headers: foreignHeaders,
            data: {
              text: "Synthetic cross-tenant request that must never be admitted.",
            },
          })
        ).status(),
      ).toBe(404);
    }
    const visitAttack = await foreign.page.request.get(
      `/visits/${encodeURIComponent(typedVisitId)}`,
      { maxRedirects: 0 },
    );
    const visitAttackBody = await visitAttack.text();
    // Next.js may stream a segment-level notFound() response with HTTP 200.
    // The security invariant is the same non-enumerating visit-not-found
    // surface with no tenant data, never the owning visit content.
    expect([200, 404]).toContain(visitAttack.status());
    expect(visitAttackBody).toContain("Visit not found");
    expect(visitAttackBody).not.toContain("Template Twin Synthetic QA");
  } finally {
    await foreign.close();
  }

  // A disable commit advances both rollout epochs. Re-enabling admits only a
  // new run under the new epochs; it can never revive the isolated old run.
  const staleAdmission = await page.request.post(
    "/api/note-templates/template-twin/staging-qa/runs",
    {
      headers: {
        ...sameOriginHeaders(page),
        "Content-Type": "application/json",
      },
      data: {
        ...typedAdmissionPayload,
        idempotencyKey: crypto.randomUUID(),
        encounterText: SYNTHETIC_ENCOUNTER,
      },
    },
  );
  expect(staleAdmission.status()).toBe(202);
  const staleAdmissionBody = (await staleAdmission.json()) as {
    ok: true;
    runId: string;
    visitId: string;
    run: {
      attempt: number;
      globalRolloutGeneration: string;
      practiceRolloutGeneration: string;
    };
  };
  setTemplateTwinQaPractice({ email, enabled: false });
  setTemplateTwinQaPractice({ email, enabled: true });

  const staleRunRead = await page.request.get(
    `/api/note-templates/template-twin/staging-qa/runs/${encodeURIComponent(staleAdmissionBody.runId)}`,
  );
  expect(staleRunRead.status()).toBe(409);
  expect((await staleRunRead.json()) as { code: string }).toMatchObject({
    code: "ROLLOUT_CHANGED",
  });
  expect(
    (
      await page.request.get(
        `/api/visits/${encodeURIComponent(staleAdmissionBody.visitId)}/status`,
      )
    ).status(),
  ).toBe(404);
  expect(
    (
      await page.request.post(
        `/api/note-templates/template-twin/staging-qa/runs/${encodeURIComponent(staleAdmissionBody.runId)}/retry`,
        {
          headers: {
            ...sameOriginHeaders(page),
            "Content-Type": "application/json",
          },
          data: { expectedAttempt: staleAdmissionBody.run.attempt },
        },
      )
    ).status(),
  ).toBe(409);
  const staleVisitPage = await page.request.get(
    `/visits/${encodeURIComponent(staleAdmissionBody.visitId)}`,
  );
  const staleVisitBody = await staleVisitPage.text();
  expect([200, 404]).toContain(staleVisitPage.status());
  expect(staleVisitBody).toContain("Visit not found");
  expect(staleVisitBody).not.toContain("Template Twin Synthetic QA");
  expect(
    (
      await page.request.get(
        `/api/visits/${encodeURIComponent(staleAdmissionBody.visitId)}/export/original-template-docx`,
      )
    ).status(),
  ).toBe(404);

  // Re-enabling the rollout does not silently re-admit the previously
  // certified source/template capability. A fresh, explicit source admission
  // is required before another synthetic provider operation may begin.
  const postReenableAdmission = await page.request.post(
    "/api/note-templates/template-twin/staging-qa/runs",
    {
      headers: {
        ...sameOriginHeaders(page),
        "Content-Type": "application/json",
      },
      data: {
        ...typedAdmissionPayload,
        idempotencyKey: crypto.randomUUID(),
        encounterText: SYNTHETIC_ENCOUNTER,
      },
    },
  );
  expect(postReenableAdmission.status()).toBe(422);
  expect(
    (await postReenableAdmission.json()) as {
      ok: boolean;
      code: string;
    },
  ).toMatchObject({ ok: false, code: "TEMPLATE_NOT_READY" });
  expect(
    (
      await page.request.get(
        `/api/note-templates/template-twin/staging-qa/runs/${encodeURIComponent(staleAdmissionBody.runId)}`,
      )
    ).status(),
  ).toBe(409);

  // No trace/video is recorded for this project. The explicit runtime logs
  // must not contain the unique encounter sentinel, auth material, or signed
  // object URLs.
  const logs = execSync(
    `${QA_COMPOSE} logs --no-color transcribe-md transcribe-md-worker`,
    { encoding: "utf8", maxBuffer: 8 * 1024 * 1024 },
  );
  expect(logs).not.toContain(SYNTHETIC_ENCOUNTER);
  expect(logs).not.toMatch(
    /next-auth\.session-token|authorization:\s*bearer|x-amz-signature=/iu,
  );

  const sourceCommit = execFileSync("git", ["rev-parse", "HEAD"], {
    encoding: "utf8",
  }).trim();
  const artifactFiles = [
    "01-settings-entry.png",
    "02-field-inventory.png",
    "03-evidence-and-resolutions.png",
    "04-processing.png",
    "05-signed-word-pending.png",
    "template-twin-staging-source.docx",
    "template-twin-staging-output.docx",
  ];
  const manifest = {
    contractVersion: "template-twin-staging-ui-artifacts/1.0.0",
    sourceCommit,
    syntheticOnly: true,
    microsoftWordStatus: "PENDING",
    fixtureVersion: FIXTURE_VERSION,
    verificationContractVersion: TEMPLATE_TWIN_READBACK_CONTRACT_VERSION,
    files: artifactFiles.map((name) => {
      const bytes = readFileSync(resolve(ARTIFACT_ROOT, name));
      return {
        name,
        sizeBytes: statSync(resolve(ARTIFACT_ROOT, name)).size,
        sha256: sha256(bytes),
      };
    }),
  };
  writeFileSync(
    resolve(ARTIFACT_ROOT, "manifest.json"),
    `${JSON.stringify(manifest, null, 2)}\n`,
    { encoding: "utf8" },
  );
});
