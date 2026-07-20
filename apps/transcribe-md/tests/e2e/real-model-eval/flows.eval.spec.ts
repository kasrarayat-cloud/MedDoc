// ============================================================================
// Real-model eval — non-text flows (feat/fable5-eval).
//   1. Audio file upload → REAL Deepgram transcription → SOAP.
//   2. Custom note-format: blank outline → PHI-safe parse → live Fable
//      sample preview → activate (catch-all) → generate a real note IN that
//      format → verify the custom sections are followed.
// FLOW/STRUCTURE assertions only; captures outputs as artifacts for the judge.
// Manual/operator-only: self-skips unless REAL_MODEL_EVAL=1; real tokens.
// ============================================================================

import path from "node:path";

import { test, expect } from "@playwright/test";

import { signupFreshUser } from "../helpers/signup";
import { createPatientViaApi } from "../helpers/visit-setup";
import { waitForVisitStatus } from "../helpers/waitForReady";
import { captureVisit, visitModels, writeArtifact } from "./capture";

const GATE = process.env.REAL_MODEL_EVAL !== "1";
const LABEL = process.env.EVAL_MODEL_LABEL || "fable";
const READY_TIMEOUT = 300_000;
const FIXTURES = path.resolve(
  process.cwd(),
  "tests/e2e/real-model-eval/fixtures",
);

// Ground truth for the audio dictation (espeak-ng TTS of a synthetic HTN f/u).
const AUDIO_GROUND = {
  mustInclude: [
    "hypertension",
    "blood pressure 148/90",
    "lisinopril",
    "increase lisinopril to 40",
    "recheck blood pressure",
  ],
  negations: [
    "denies chest pain",
    "denies shortness of breath",
    "denies headaches",
  ],
  medsWithDose: ["lisinopril 20 mg daily increased to 40 mg daily"],
  allergies: "No known drug allergies",
  notStated: [
    "diabetes",
    "EKG",
    "stroke",
    "chest x-ray",
    "second medication added",
    "kidney disease",
  ],
};

const HF_TRANSCRIPT = `Cardiology follow-up. 68-year-old with heart failure with reduced ejection fraction, ejection fraction 35 percent. Reports stable exercise tolerance, walks two blocks without stopping. Denies orthopnea, denies paroxysmal nocturnal dyspnea, denies increased leg swelling. Weight stable. On carvedilol 12.5 milligrams twice daily, sacubitril-valsartan 49-51 twice daily, and furosemide 20 milligrams daily. No known drug allergies. Exam: jugular venous pressure normal, lungs clear, no peripheral edema. Assessment: heart failure with reduced ejection fraction, compensated. Plan: continue guideline-directed therapy, up-titrate carvedilol to 25 milligrams twice daily as tolerated, daily weights, follow up in three months.`;
const SAFE_CUSTOM_OUTLINE = [
  "REASON FOR VISIT",
  "[blank]",
  "INTERVAL HISTORY",
  "[blank]",
  "OBJECTIVE / EXAM",
  "[blank]",
  "ASSESSMENT AND PLAN",
  "[blank]",
  "PATIENT INSTRUCTIONS",
  "[blank]",
].join("\n");

test.describe("real-model eval — flows", () => {
  test.skip(
    GATE,
    "Real-model eval — REAL_MODEL_EVAL=1 + --project=real-model-eval on a real-key qa stack.",
  );

  test(`audio upload → Deepgram → SOAP [${LABEL}]`, async ({ page }) => {
    test.setTimeout(15 * 60 * 1000);
    await signupFreshUser(page, `evalaud-${LABEL}`);

    const patient = await createPatientViaApi(page, "Eval Audio");
    await page.goto(`/visits/new?patientId=${patient.id}`);
    await page.getByRole("button", { name: /upload audio/i }).click();
    await page.waitForURL(/\/visits\/c[a-z0-9]{10,}/, { timeout: 30_000 });
    const visitId = new URL(page.url()).pathname.split("/").pop()!;
    await page
      .locator('input[type="file"]')
      .first()
      .setInputFiles(path.join(FIXTURES, "audio/htn-followup-dictation.mp3"));
    await page.getByRole("button", { name: /upload & transcribe/i }).click();

    const status = await waitForVisitStatus(page, visitId, "READY", {
      timeoutMs: READY_TIMEOUT,
    });
    const cap = captureVisit(visitId);
    writeArtifact(LABEL, "audio1-htn-dictation", {
      encounterId: "audio1-htn-dictation",
      kind: "audio",
      modelLabel: LABEL,
      modelsUsed: visitModels(visitId),
      visitId,
      status: cap.status,
      deepgramTranscript: cap.transcriptText,
      soapFinal: cap.soapFinal,
      rxDrafts: cap.rxDrafts,
      ground: AUDIO_GROUND,
    });

    expect(status, "audio visit should reach READY").toBe("READY");
    expect(
      (cap.transcriptText || "").length,
      "Deepgram should produce a transcript",
    ).toBeGreaterThan(0);
    expect(
      (cap.soapFinal || "").length,
      "SOAP should be non-empty",
    ).toBeGreaterThan(0);
  });

  test(`custom note-format: parse → live preview → activate → generate in format [${LABEL}]`, async ({
    page,
  }) => {
    test.setTimeout(20 * 60 * 1000);
    await signupFreshUser(page, `evalfmt-${LABEL}`);

    // Submit a strictly blank, allowlisted outline. No completed example or
    // patient-like prose is eligible for this provider-backed legacy parse.
    await page.goto("/settings");
    await page.getByLabel("Paste a blank outline").fill(SAFE_CUSTOM_OUTLINE);
    await page.getByRole("button", { name: /read blank outline/i }).click();

    // Review editor reached (real parse). Then the live sample preview renders a
    // real Fable sample IN the parsed format, labelled synthetic.
    await expect(
      page.getByRole("button", { name: /save & activate/i }),
    ).toBeVisible({ timeout: READY_TIMEOUT });
    await expect(page.getByText("Sample note in your format")).toBeVisible();
    await expect(page.getByText(/demo visit · synthetic/i)).toBeVisible();
    // The preview generates async (real Fable) — wait for a rendered heading from
    // the custom format to appear in the sample, then capture the panel text.
    const previewPanel = page
      .getByText("Sample note in your format")
      .locator("xpath=ancestor::*[3]");
    await expect(
      previewPanel
        .getByText(/reason for visit|interval history|patient instructions/i)
        .first(),
    ).toBeVisible({ timeout: READY_TIMEOUT });
    const previewText = await previewPanel.innerText().catch(() => "");

    // Activate as catch-all (encounterType left empty → applies to all visits).
    await page.getByRole("button", { name: /save & activate/i }).click();
    await expect(page.getByRole("button", { name: /add format/i })).toBeVisible(
      { timeout: 30_000 },
    );

    // Generate a real note — it must use the activated custom template.
    const patient = await createPatientViaApi(page, "Eval Format");
    await page.goto(`/visits/new?patientId=${patient.id}`);
    await page.getByRole("button", { name: /text to soap/i }).click();
    await page.waitForURL(/\/visits\/c[a-z0-9]{10,}/, { timeout: 30_000 });
    const visitId = new URL(page.url()).pathname.split("/").pop()!;
    await page.getByLabel("Clinical shorthand").fill(HF_TRANSCRIPT);
    await page.getByRole("button", { name: /expand to soap/i }).click();

    const status = await waitForVisitStatus(page, visitId, "READY", {
      timeoutMs: READY_TIMEOUT,
    });
    const cap = captureVisit(visitId);
    const customHeadings = [
      "REASON FOR VISIT",
      "INTERVAL HISTORY",
      "PATIENT INSTRUCTIONS",
    ];
    const headingsHit = customHeadings.filter((h) =>
      (cap.soapFinal || "").toUpperCase().includes(h),
    );
    writeArtifact(LABEL, "format1-cardiology", {
      encounterId: "format1-cardiology",
      kind: "custom-format",
      modelLabel: LABEL,
      modelsUsed: visitModels(visitId),
      visitId,
      status: cap.status,
      usedTemplateId: cap.noteTemplateId,
      customHeadingsHit: headingsHit,
      livePreviewSample: previewText,
      transcript: HF_TRANSCRIPT,
      soapFinal: cap.soapFinal,
      rxDrafts: cap.rxDrafts,
    });

    expect(status, "custom-format visit should reach READY").toBe("READY");
    expect(
      cap.noteTemplateId,
      "visit should have used a custom template",
    ).toBeTruthy();
    expect(
      headingsHit.length,
      `note should follow the custom format (hit ${headingsHit.join(",")})`,
    ).toBeGreaterThanOrEqual(2);
  });
});
