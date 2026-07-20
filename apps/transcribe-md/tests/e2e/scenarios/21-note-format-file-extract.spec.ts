// ============================================================================
// Scenario 21 — legacy blank-outline text upload boundary
// ----------------------------------------------------------------------------
// Scenario 5 covers paste; this locks the only legacy file path that remains:
// UTF-8 .txt/.md. Office/PDF files are refused at the client affordance and at
// the server action before bytes are read; DOCX belongs in quarantined Template
// Twin intake. Provider non-invocation is locked by focused action tests.
// ============================================================================

import { resolve } from "node:path";

import { expect, test, type Page } from "@playwright/test";

import { cleanupTestUsers } from "../helpers/cleanup";
import { signupFreshUser } from "../helpers/signup";
import { gotoNoteFormat } from "../helpers/noteFormat";

const GATE = process.env.NOTE_FORMAT_E2E !== "1";
const GATE_MSG =
  "Needs an app image built with the note-format mock fixtures. Run with NOTE_FORMAT_E2E=1 against a fresh build.";

const FIX = (f: string) => resolve(__dirname, "../fixtures/notes", f);
const TXT = FIX("clinical-notes.txt");
const PDF = FIX("sample-note.pdf"); // 2-page PDF with a real text layer
const DOCX = FIX("sample-note.docx"); // minimal OOXML, mammoth-readable

test.afterEach(() => {
  cleanupTestUsers();
});

/** Drive the upload exactly as a user does: click the visible text-upload
 *  button (which programmatically opens the hidden <input type=file>) and feed
 *  the file via the intercepted chooser. The real-dialog path reliably fires the
 *  input's onChange; a direct setInputFiles on this aria-hidden display:none
 *  input does not. */
async function uploadFile(page: Page, file: string): Promise<void> {
  const [chooser] = await Promise.all([
    page.waitForEvent("filechooser"),
    page.getByRole("button", { name: /upload \.txt or \.md/i }).click(),
  ]);
  await chooser.setFiles(file);
}

/** Upload a populated file and assert extraction lands in the local fail-closed
 *  boundary instead of the review editor. */
async function uploadAndExpectLocalRejection(
  page: Page,
  file: string,
): Promise<void> {
  await uploadFile(page, file);
  await expect(page.getByRole("alert")).toBeVisible({ timeout: 20_000 });
  await expect(
    page.getByText(/accepts only a blank text outline/i),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: /save & activate/i }),
  ).toBeHidden();
}

test("scenario 21: populated .txt upload → extract → local rejection", async ({
  page,
}) => {
  test.skip(GATE, GATE_MSG);
  await signupFreshUser(page, "s21txt");
  await gotoNoteFormat(page);
  await uploadAndExpectLocalRejection(page, TXT);
});

for (const [label, user, file] of [
  ["PDF", "s21pdf", PDF],
  ["DOCX", "s21docx", DOCX],
] as const) {
  test(`scenario 21: ${label} is refused by the legacy shortcut`, async ({
    page,
  }) => {
    test.skip(GATE, GATE_MSG);
    await signupFreshUser(page, user);
    await gotoNoteFormat(page);

    const input = page.locator('input[type="file"][accept*=".txt"]');
    expect(await input.getAttribute("accept")).not.toMatch(/pdf|docx/i);
    await uploadFile(page, file);
    await expect(page.getByText("Use a blank text outline")).toBeVisible();
    await expect(page.getByLabel("Paste a blank outline")).toBeVisible();
    await expect(
      page.getByRole("button", { name: /save & activate/i }),
    ).toBeHidden();
  });
}
