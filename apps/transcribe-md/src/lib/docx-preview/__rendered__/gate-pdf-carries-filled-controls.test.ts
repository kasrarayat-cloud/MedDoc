// ============================================================================
// THE CERTIFICATION PDF ARM — THROUGH THE REAL LIBREOFFICE.
// ----------------------------------------------------------------------------
// ⚠️ THE PROXY THIS FILE REMOVES. `__tests__/gate-pdf-flatten.test.ts` asserts
// that the bytes handed to the converter carry zero `w:sdt` and the same run
// set as the source. That is a claim about the INPUT, and it is the claim the
// code can make. It says nothing about what LibreOffice paints — and what
// LibreOffice paints is the entire defect:
//
//     the owner's signed export, DOCX -> 22 filled controls, 7,603 chars
//                                PDF  ->  0 of the 22,        2,199 chars
//
// A proxy is a claim about a renderer nobody ran. This file runs it.
//
// ⚠️ WHAT IT IS ALLOWED TO CLAIM, AND WHAT IT IS NOT. The values are injected
// at the BYTE level, in the shape the fill engine emits (one `w:r`/`w:t` inside
// `w:sdtContent`), because this tier has no database and cannot drive the
// certification chain end to end. So the arm proves *a filled control's text
// reaches the PDF*; it does not prove the fill engine produced that control.
// The engine's own coverage lives in the twin suite. Stated here rather than
// discovered later.
// ============================================================================
import { readFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { describe, expect, it } from 'vitest';
import JSZip from 'jszip';
import { extractText, getDocumentProxy } from 'unpdf';

const APP = resolve(__dirname, '..', '..', '..', '..');

// ⚠️ `GOTENBERG_URL` CARRIES TWO DIFFERENT CONTRACTS, AND THAT COST THIS ARM A
// CI RUN. `convert.ts` treats it as the FULL convert endpoint (its own default
// ends in `/forms/libreoffice/convert`, and production sets it that way).
// `docker-compose.qa.rendered.yml` sets it to the BASE — `http://gotenberg:3000`
// — because the sibling rendered tests append the path themselves. Calling the
// SHIPPED function from this tier therefore POSTs to `/` and gets **405**,
// which surfaces as a generic `converter_error`.
//
// So the endpoint is normalised here, accepting either spelling, and the
// normalised value is put back on the environment BEFORE `convert.ts` is
// imported — its URL is a module-level const read at import time.
const BASE = (process.env.GOTENBERG_URL ?? 'http://gotenberg:3000').replace(/\/$/, '');
const CONVERT_URL = BASE.endsWith('/forms/libreoffice/convert')
  ? BASE
  : `${BASE}/forms/libreoffice/convert`;
process.env.GOTENBERG_URL = CONVERT_URL;
const FIXTURE = join(APP, 'tests', 'e2e', 'fixtures', 'sample-form.docx');

/**
 * Put a unique sentinel inside every `w:sdtContent`, replacing whatever is
 * there — the shape the fill engine writes. Returns the bytes and the exact
 * list of sentinels, so the assertion's denominator is MEASURED rather than
 * remembered.
 */
async function fillEveryControl(src: Buffer): Promise<{ docx: Uint8Array; values: string[] }> {
  const zip = await JSZip.loadAsync(src);
  const part = zip.file('word/document.xml');
  if (!part) throw new Error('fixture has no word/document.xml');
  const xml = await part.async('string');

  const values: string[] = [];
  const filled = xml.replace(
    /(<w:sdtContent(?:\s[^>]*)?>)([\s\S]*?)(<\/w:sdtContent>)/g,
    (_all, open: string, inner: string, close: string) => {
      const value = `ZQSENTINEL${values.length}VALUE`;
      values.push(value);
      // ⚠️ AND THE SHAPE IS READ OFF THE CONTROL, NOT ASSUMED — THE SECOND
      // DEFECT IN THIS ARM. A control whose content is BLOCK level holds
      // paragraphs; putting a bare run there is illegal once the wrapper comes
      // off, and LibreOffice drops it. That run reported `1 of 28` — again a
      // fact about the injection. Block controls get a paragraph, inline
      // controls get a run, which is the distinction the fill engine makes.
      const block = /<w:p[ >]/.test(inner);
      if (block) {
        return `${open}<w:p><w:r><w:t xml:space="preserve">${value}</w:t></w:r></w:p>${close}`;
      }
      // ⚠️ A RUN, NOT A PARAGRAPH — AND THE FIRST DRAFT OF THIS ARM GOT IT
      // WRONG, WHICH IS WHY IT IS SPELT OUT. Wrapping the value in `<w:p>`
      // nests a paragraph inside a paragraph for every INLINE control; the
      // document is malformed once the wrapper comes off, and LibreOffice drops
      // it. That run reported `27 of 28 filled values vanished` — a fact about
      // the injection, not about the fix. A run is legal in both positions and
      // is the shape the fill engine emits.
      return `${open}<w:r><w:t xml:space="preserve">${value}</w:t></w:r>${close}`;
    },
  );

  // ⚠️ THE EDIT PROVES ITS OWN APPLICATION. A regex that matched nothing would
  // hand the converter a blank form, every sentinel would be absent, and the
  // arm would fail for a reason that has nothing to do with the converter.
  if (values.length < 20) {
    throw new Error(`expected the real form's controls; filled only ${values.length}`);
  }
  for (const v of values) {
    if (!filled.includes(v)) throw new Error(`sentinel ${v} did not land in the XML`);
  }

  zip.file('word/document.xml', filled);
  return { docx: await zip.generateAsync({ type: 'uint8array' }), values };
}

/** The unflattened control: the fixture's own bytes, straight at LibreOffice. */
async function rawConvert(docx: Uint8Array): Promise<Uint8Array> {
  const form = new FormData();
  form.set(
    'files',
    new Blob([docx as unknown as BlobPart], {
      type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    }),
    'document.docx',
  );
  const res = await fetch(CONVERT_URL, { method: 'POST', body: form });
  // ⚠️ IT THROWS. IT MUST NEVER RETURN NULL. The first version returned null on
  // a non-OK response, the caller turned that into `text = ''`, and the arm
  // printed `unflattened: 0/28 survived` — a FABRICATED measurement of a
  // conversion that never happened. It shipped to CI and read as a clean
  // reproduction of the defect **because 0/28 was exactly what I predicted**;
  // the real figure, measured locally, is 1/28. A failed conversion is a failed
  // MEASUREMENT, and it has to be louder than the number it would otherwise
  // invent.
  if (!res.ok) {
    throw new Error(`converter returned ${res.status} for the unflattened control`);
  }
  return new Uint8Array(await res.arrayBuffer());
}

async function pdfText(pdf: Uint8Array): Promise<string> {
  const proxy = await getDocumentProxy(pdf);
  const { text } = await extractText(proxy, { mergePages: true });
  return Array.isArray(text) ? text.join('\n') : text;
}

describe('the PDF a doctor sends carries what his DOCX carries', () => {
  it(
    '⚠️ EVERY filled content control reaches the rendered PDF',
    async () => {
      const { docx, values } = await fillEveryControl(readFileSync(FIXTURE));

      const { convertDocxToPdf } = await import('../convert');
      const { pdf, reason } = await convertDocxToPdf(docx);
      expect(reason ?? null, 'the converter refused').toBeNull();
      expect(pdf, 'the converter returned no PDF').not.toBeNull();

      const text = await pdfText(pdf!);
      const missing = values.filter((v) => !text.includes(v));

      // The whole product claim, in one line: none of the doctor's filled
      // values may be missing from the document he hands to a referrer.
      expect(missing, `${missing.length} of ${values.length} filled values vanished`).toEqual([]);
    },
    120_000,
  );

  // ⚠️ NOT AN ASSERTION ABOUT LIBREOFFICE, DELIBERATELY. The converter's
  // treatment of `w:sdt` is FILED, not diagnosed — `DEPLOYMENT_RUNBOOK.md`,
  // "the SDT rendering quirk". Asserting that the UNFLATTENED bytes still lose
  // their values would pin somebody else's defect as a requirement and go red
  // the day it is fixed. So this arm MEASURES and REPORTS instead, and the
  // number is the one that made the fix necessary.
  it(
    'records what the same bytes render as WITHOUT the flatten (measurement, not a requirement)',
    async () => {
      const { docx, values } = await fillEveryControl(readFileSync(FIXTURE));
      // ⚠️ IT SPEAKS TO THE CONVERTER DIRECTLY, RATHER THAN THROUGH A
      // `flatten: false` OPTION. Adding a production switch that turns the fix
      // off would put the defect one argument away from any future caller, for
      // the sole benefit of a diagnostic. This arm measures LibreOffice, not our
      // code, so it is the right place to own the transport.
      const pdf = await rawConvert(docx);
      // ⚠️ THE ANTI-FABRICATION ASSERTION. Without it, ANY route to an empty
      // `text` yields `survived = 0` and prints a confident reproduction of the
      // very defect being measured. The number may only be reported if a REAL
      // PDF was really produced.
      expect(Buffer.from(pdf.subarray(0, 4)).toString('ascii')).toBe('%PDF');
      expect(pdf.byteLength, 'the control PDF is implausibly small').toBeGreaterThan(1000);

      const text = await pdfText(pdf);
      const survived = values.filter((v) => text.includes(v)).length;

      // eslint-disable-next-line no-console
      console.log(
        `[sdt-quirk] unflattened: ${survived}/${values.length} filled values survived conversion`,
      );
      // The measurement is now guarded at both ends: a real PDF above, and a
      // real denominator here. What is deliberately NOT asserted is the value
      // of `survived` — pinning LibreOffice's behaviour would red the day it is
      // fixed, and the quirk is FILED, not required.
      expect(values.length).toBeGreaterThan(20);
      expect(survived).toBeLessThanOrEqual(values.length);
    },
    120_000,
  );
});
