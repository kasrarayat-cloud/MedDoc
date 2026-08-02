// ============================================================================
// C2-b — "exports must match preview 1:1", asserted on the BYTES.
// ----------------------------------------------------------------------------
// SPEC.md:200 makes this Phase C's report-template deliverable. Nothing in the
// repo tested it, and the thing that looked like it did could not: the parity
// clause Gate B recorded (`rounds-gates.spec.ts`) compares SECTION-HEADING
// STRINGS extracted from the two artifacts. `helpers/exportText.ts` strips all
// XML tags to do it, which discards `w:pgSz`, `w:rFonts`, `w:sz` and `w:pgMar`,
// and reads the PDF through `unpdf`'s text extractor, which returns bare
// strings. **Text extraction structurally cannot see geometry or type.** So a
// Letter PDF and an A4 Word file containing the same words passed it.
//
// WHAT THE PIPELINE ACTUALLY IS, and why this is the right place to assert:
//   preview  = `preview-visit-document.ts:96` generates the DOCX →
//              `:103` posts it to Gotenberg (LibreOffice) → PDF → pdf.js canvas
//   download = `generateVisitDocx` (Word) or `generateVisitPdf` (pdfkit)
// The on-screen paper IS a render of the DOCX export. So "preview matches
// export" reduces to two checkable claims:
//   (1) the DOCX and the PDF agree on page geometry and type — asserted here;
//   (2) the converter can resolve the fonts they name — asserted here against
//       the image definition, and behaviourally on the host in the item's proof.
//
// ⚠️ THIS FILE IS FLAG-INDEPENDENT ON PURPOSE. Both generators run with
// `NEXT_PUBLIC_SKIN_ROUNDS` off; the divergence it pins ships in production
// today and has nothing to do with the skin.
// ============================================================================

import { readFileSync, readdirSync } from 'node:fs';

import JSZip from 'jszip';
import { getDocumentProxy } from 'unpdf';
import { describe, expect, it } from 'vitest';

import { generateVisitDocx } from '../docx-generator';
import { generateVisitPdf } from '../pdf-generator';
import type { VisitExportData } from '../visit-export';

/** The default QuillMD layout — NOT a custom template. `formOnly:false` and no
 *  header fields is the plain SOAP export every doctor gets without uploading
 *  anything, which is the surface this deliverable is about. */
function fixture(overrides: Partial<VisitExportData> = {}): VisitExportData {
  return {
    visitId: 'v_c2b_parity',
    patientName: 'Parity Fixture',
    specialty: 'Primary Care',
    chiefComplaint: 'Cough',
    status: 'SIGNED',
    createdAt: new Date('2026-08-01T00:00:00Z'),
    signedAt: new Date('2026-08-01T00:00:00Z'),
    clinicianName: 'Dr. Ada Lovelace',
    clinicianEmail: 'ada@example.test',
    soapText: 'Subjective\nCough for three days.\n\nObjective\nChest clear.\n\nAssessment\nViral URI.\n\nPlan\nRest.',
    icdCodes: [],
    em: null,
    procedures: [],
    modifiers: [],
    prescriptions: [],
    rxWarnings: [],
    referrals: [],
    patientSummary: null,
    headerFields: [],
    formOnly: false,
    formTitle: null,
    formSignature: null,
    ...overrides,
  };
}

/** US Letter, the size the PDF generator has always used. Expressed in the two
 *  units the two libraries take, with the conversion written out — the drift
 *  this file exists for is exactly a missing unit conversion. */
const LETTER = { widthPt: 612, heightPt: 792, marginPt: 72 };
const TWIPS_PER_PT = 20;

async function docxPageProps(data = fixture()) {
  const buf = await generateVisitDocx(data);
  const zip = await JSZip.loadAsync(buf);
  const xml = await zip.file('word/document.xml')!.async('string');
  const sz = xml.match(/<w:pgSz\b[^>]*\/>/)?.[0] ?? null;
  const mar = xml.match(/<w:pgMar\b[^>]*\/>/)?.[0] ?? null;
  const num = (tag: string | null, attr: string) =>
    tag ? Number(tag.match(new RegExp(`w:${attr}="(\\d+)"`))?.[1] ?? NaN) : NaN;
  return {
    xml,
    present: sz !== null,
    w: num(sz, 'w'),
    h: num(sz, 'h'),
    top: num(mar, 'top'),
    left: num(mar, 'left'),
  };
}

async function pdfPageProps(data = fixture()) {
  const buf = await generateVisitPdf(data);
  const doc = await getDocumentProxy(new Uint8Array(buf));
  const page = await doc.getPage(1);
  const vp = page.getViewport({ scale: 1 });
  return { width: Math.round(vp.width), height: Math.round(vp.height), pages: doc.numPages };
}

describe('C2-b — the two generators agree on the page', () => {
  it('the harness can read both artifacts — positive control', async () => {
    // Without this, a generator that threw or a zip entry that moved would make
    // every assertion below vacuous.
    const d = await docxPageProps();
    expect(d.xml.length, 'word/document.xml read as empty').toBeGreaterThan(500);
    const p = await pdfPageProps();
    expect(p.pages, 'the PDF has no pages').toBeGreaterThanOrEqual(1);
    expect(p.width, 'the PDF viewport has no width').toBeGreaterThan(0);
  }, 30_000);

  it('⚠️ the DOCX DECLARES a page size at all', async () => {
    // `sections: [{ children }]` with no `page` property is not "the default is
    // fine" — it is the docx library's default, which is A4. Nothing in this
    // repo chose that, and nothing recorded it.
    const d = await docxPageProps();
    expect(
      d.present,
      'the DOCX section declares no <w:pgSz>. Word then uses the library default ' +
        '(A4, 11906x16838 twips) — a size no one in this codebase picked, and ' +
        'not the size the PDF uses',
    ).toBe(true);
  }, 30_000);

  it('the DOCX page size is US Letter, in twips', async () => {
    const d = await docxPageProps();
    expect({ w: d.w, h: d.h }).toEqual({
      w: LETTER.widthPt * TWIPS_PER_PT,
      h: LETTER.heightPt * TWIPS_PER_PT,
    });
  }, 30_000);

  it('the PDF page size is US Letter, in points', async () => {
    const p = await pdfPageProps();
    expect({ width: p.width, height: p.height }).toEqual({
      width: LETTER.widthPt,
      height: LETTER.heightPt,
    });
  }, 30_000);

  it('⚠️ and therefore the PREVIEW matches the download — the same page, both ways', async () => {
    // The claim the deliverable actually makes. The preview is Gotenberg's
    // render of the DOCX, so DOCX geometry IS preview geometry; the download is
    // the PDF. Converted into one unit and compared.
    const [d, p] = await Promise.all([docxPageProps(), pdfPageProps()]);
    expect(
      { widthPt: d.w / TWIPS_PER_PT, heightPt: d.h / TWIPS_PER_PT },
      'the Word file (and therefore the on-screen preview, which is its render) ' +
        'is a different page size from the PDF the doctor downloads',
    ).toEqual({ widthPt: p.width, heightPt: p.height });
  }, 30_000);

  it('the margins agree too', async () => {
    const d = await docxPageProps();
    expect(d.top / TWIPS_PER_PT).toBe(LETTER.marginPt);
    expect(d.left / TWIPS_PER_PT).toBe(LETTER.marginPt);
  }, 30_000);

  it('the unit conversion is right — negative control', () => {
    // If this arithmetic were wrong, every assertion above would be comparing
    // the same wrong number to itself.
    expect(LETTER.widthPt * TWIPS_PER_PT).toBe(12240);
    expect(LETTER.heightPt * TWIPS_PER_PT).toBe(15840);
    // A4 is what the library defaults to; it must NOT equal Letter, or these
    // tests would pass on the defect.
    expect(11906).not.toBe(LETTER.widthPt * TWIPS_PER_PT);
  });
});

describe('C2-b — a custom template is not this item', () => {
  it('the form-only branch still renders, and still shares the default page', async () => {
    // `formOnly` and `headerFields` are BRANCHES INSIDE the default generators,
    // not a separate renderer — the doctor's own FORM BYTES go through
    // `nativePdfExport` / `outcome.native`, which short-circuit before these are
    // reached and are untouched by this item. So a form-only export gets the
    // same page as everything else, which is the consistent answer rather than
    // a second geometry.
    const d = await docxPageProps(fixture({ formOnly: true, formTitle: 'Vascular Study' }));
    expect(d.present, 'the form-only branch lost its page declaration').toBe(true);
    expect(d.w).toBe(LETTER.widthPt * TWIPS_PER_PT);
  }, 30_000);
});

describe('C2-b — the converter can resolve the type the document names', () => {
  // ⚠️ NAMING IS NOT RESOLVING, AND THIS IS THE HALF THE GENERATORS CANNOT FIX.
  // The DOCX names Charter and Inter Tight; the PDF EMBEDS them. The preview is
  // LibreOffice's render of the DOCX inside the Gotenberg container, and the
  // stock image ships neither face — measured on the running container, and
  // then A/B'd by converting one DOCX through both images and reading
  // `/BaseFont` out of each result:
  //
  //     gotenberg/gotenberg:8        → NotoSerif-Bold/Regular/Italic
  //     meddoc-pro-gotenberg:fonts   → CharterRegular/Bold/Italic, InterTight-Regular
  //
  // So the fonts had to go into the image. These assertions pin the wiring,
  // because the failure is silent: a substituted typeface renders perfectly and
  // simply is not the document's.
  const ROOT = '../..';
  const read = (p: string) => readFileSync(`${ROOT}/${p}`, 'utf8');
  const DOCKERFILE = 'docker/gotenberg-fonts.Dockerfile';

  it('the fonts the Dockerfile installs ARE the fonts the PDF embeds', () => {
    // Derived from the directory, not from a list here: drop a face into
    // `fonts/` and both the PDF and the converter get it, or this reds.
    const files = readdirSync('fonts').filter((f) => f.endsWith('.ttf'));
    expect(files.length, 'the export font directory is empty').toBeGreaterThanOrEqual(4);
    const families = new Set(files.map((f) => f.split('-')[0].replace(/\.ttf$/, '')));
    // Both families the two generators name must be present as real files.
    expect([...families].some((f) => /charter/i.test(f)), 'Charter is not in fonts/').toBe(true);
    expect([...families].some((f) => /intertight/i.test(f)), 'Inter Tight is not in fonts/').toBe(true);

    const df = read(DOCKERFILE);
    expect(df, 'the image does not copy the TTFs').toMatch(/COPY \*\.ttf/);
    // fontconfig caches its index; a font copied in without this is on disk and
    // invisible to LibreOffice — "installed but not resolving", one level down.
    expect(df, 'the image does not refresh the fontconfig cache').toContain('fc-cache');
    // …and the build itself must FAIL if they do not register, rather than
    // producing an image that silently substitutes.
    expect(df, 'the build does not assert the fonts resolved').toMatch(/fc-list \| grep -qi charter/);
  });

  it('BOTH composes run the fonts image, not the stock tag', () => {
    for (const f of ['docker-compose.yml', 'docker-compose.qa.yml']) {
      const s = read(f);
      expect(s, `${f}: gotenberg is not built from the fonts Dockerfile`).toContain(
        'gotenberg-fonts.Dockerfile',
      );
      expect(
        s,
        `${f}: still pins the stock gotenberg tag, so the preview substitutes type`,
      ).not.toMatch(/image:\s*gotenberg\/gotenberg:8/);
    }
  });

  it('⚠️ the deploy BUILDS and RECREATES it — a service a deploy never names is left behind', () => {
    // The same shape as the stale `db-migrate` this script already guards
    // against: step 6 ups only the app and the worker, so a gotenberg still
    // running the old image would keep rendering substituted type after a
    // deploy that reported success.
    const d = read('scripts/deploy-prod.sh');
    expect(d, 'the deploy never builds the converter').toMatch(/docker compose build gotenberg/);
    expect(d, 'the deploy builds the converter but never recreates it').toMatch(
      /docker compose up -d gotenberg/,
    );
  });
});

describe('C2-b — the export path is flag-INDEPENDENT, and that is checked', () => {
  // ⚠️ WHY THIS IS ASSERTED RATHER THAN STATED. Everything above runs the real
  // generators directly, so it is a faithful proof of the bytes the export
  // route streams — `pdf = nativePdf ?? await generateVisitPdf(data)` and the
  // DOCX equivalent do no post-processing. But "the unit test is the export
  // path" only holds while nothing in that path branches on the skin. If a
  // generator ever read `isSkinRounds()`, this file would be measuring one
  // configuration and production would ship another, and nothing would say so.
  //
  // So the property is pinned: the export modules read NO skin flag. That is
  // also what makes the Letter/A4 fix a change to the CURRENT product rather
  // than to a flagged one — it ships to every doctor on the next deploy,
  // which is why it needed proving on a production-shaped build.
  const MODULES = [
    'src/lib/export-page.ts',
    'src/lib/pdf-generator.ts',
    'src/lib/docx-generator.ts',
  ];

  it('no export module reads the Rounds skin flag', () => {
    const offenders: string[] = [];
    for (const m of MODULES) {
      const src = readFileSync(m, 'utf8')
        .replace(/\/\*[\s\S]*?\*\//g, ' ')
        .replace(/\/\/[^\n]*/g, ' ');
      for (const needle of ['isSkinRounds', 'NEXT_PUBLIC_SKIN_ROUNDS', 'data-skin', '--rounds-']) {
        if (src.includes(needle)) offenders.push(`${m}: reads ${needle}`);
      }
    }
    expect(
      offenders,
      'an export module branches on the skin. The exported document is the same ' +
        'artifact for every doctor regardless of flag, and a Rounds token cannot ' +
        'reach a filled export — if that changed, these parity assertions stop ' +
        'describing what production ships:\n  ' + offenders.join('\n  '),
    ).toEqual([]);
  });

  it('the flag scan can FIND one — negative control', () => {
    // Without this, a scan that matched nothing would report independence over
    // a module that read the flag on every line.
    const fixture = `const x = isSkinRounds() ? 1 : 2;`;
    expect(fixture.includes('isSkinRounds')).toBe(true);
    // …and the comment stripper must not hide a real read inside code.
    const stripped = `/* mentions isSkinRounds */\nconst y = isSkinRounds();`
      .replace(/\/\*[\s\S]*?\*\//g, ' ')
      .replace(/\/\/[^\n]*/g, ' ');
    expect(stripped.includes('isSkinRounds'), 'a real read was stripped away').toBe(true);
  });

  it('both generators share ONE page definition — the drift cannot come back', () => {
    // The defect was two files each typing their own numbers with no conversion
    // between them. Sharing the module is the structural fix; this asserts the
    // sharing rather than the values, which the assertions above already pin.
    for (const m of ['src/lib/pdf-generator.ts', 'src/lib/docx-generator.ts']) {
      expect(
        readFileSync(m, 'utf8'),
        `${m} no longer reads the shared page definition — it has its own numbers again`,
      ).toMatch(/from '\.\/export-page'/);
    }
  });
});

describe('C2-b — the DOCX names its type, and it lives in TWO parts', () => {
  it('⚠️ Charter is the DEFAULT run style (styles.xml), Inter Tight the override (document.xml)', async () => {
    // Recorded because a check of mine reported a false absence here. The first
    // draft of `tests/e2e/helpers/exportGeometry.ts` scanned `word/document.xml`
    // alone and concluded the export "does not name Charter" — and the E2E
    // reddened on a product that was correct. Charter is set once, as the
    // document-level default (`styles.default.document.run`), so `document.xml`
    // carries only the exceptions. Scanning the part where the exceptions live
    // and calling it the font list is an answer about a set whose boundary was
    // never established.
    const buf = await generateVisitDocx(fixture());
    const zip = await JSZip.loadAsync(buf);
    const read = async (part: string) => {
      const f = zip.file(part);
      return f ? await f.async('string') : '';
    };
    const styles = await read('word/styles.xml');
    const document = await read('word/document.xml');

    expect(styles, 'styles.xml is missing — the default run style has nowhere to live').not.toBe('');
    expect(
      styles.includes('w:ascii="Charter"'),
      'Charter is not the document default run font, so the clinical prose falls ' +
        "back to Word's default and cannot match the PDF, which EMBEDS it",
    ).toBe(true);
    expect(
      document.includes('w:ascii="Inter Tight"'),
      'the label font override is gone from document.xml',
    ).toBe(true);

    // The control: the two parts really do carry DIFFERENT sets, so a
    // one-part reader genuinely misses something.
    expect(
      document.includes('w:ascii="Charter"'),
      'Charter now also appears per-run in document.xml — harmless, but this ' +
        'control no longer demonstrates why both parts must be read',
    ).toBe(false);
  }, 30_000);
});
