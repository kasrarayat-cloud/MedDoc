// ============================================================================
// Read an exported artifact as TEXT, and refuse to lie about it.
// ----------------------------------------------------------------------------
// Used by the export-guard specs: the claim "an imaging report exports no office
// E/M code" is only worth anything if asserted against the bytes the doctor
// receives, not the DOM.
//
// ⚠️ THE TRAP THIS EXISTS TO AVOID. A `not.toMatch(/992\d\d/)` assertion passes
// against an EMPTY STRING. So an extractor that silently fails to read a PDF
// turns the strongest assertion in the pack into a no-op that reports success
// forever. A hand-rolled zlib-stream scrape of a Gotenberg PDF returned nothing
// on the first attempt here, and looked exactly like "no E/M code found".
//
// So every extraction is followed by a NON-VACUITY check against a string the
// document must contain. If the extractor cannot find that, it THROWS rather than
// returning an empty string for an assertion to pass on.
// ============================================================================

import { readFile } from 'node:fs/promises';
import { Buffer } from 'node:buffer';

/** Strip XML tags, collapse whitespace. Word splits runs, so tag removal is what
 *  rejoins "992" + "12" into something a regex can catch. */
function xmlToText(xml: string): string {
  return xml.replace(/<[^>]+>/g, '').replace(/\s+/g, ' ').trim();
}

async function docxText(path: string): Promise<string> {
  // Minimal zip reader via the same dependency the app parses uploads with.
  const JSZip = (await import('jszip')).default;
  const zip = await JSZip.loadAsync(await readFile(path));
  const parts: string[] = [];
  for (const name of Object.keys(zip.files)) {
    if (!/^word\/.*\.xml$/.test(name)) continue;
    parts.push(xmlToText(await zip.files[name].async('string')));
  }
  return parts.join(' ');
}

async function pdfText(path: string): Promise<string> {
  // unpdf is already a runtime dependency (PDF template ingestion), so this uses
  // the same extractor the product does rather than a bespoke stream scrape.
  const { extractText, getDocumentProxy } = await import('unpdf');
  const doc = await getDocumentProxy(new Uint8Array(await readFile(path)));
  const { text } = await extractText(doc, { mergePages: true });
  return (Array.isArray(text) ? text.join(' ') : text).replace(/\s+/g, ' ').trim();
}

/**
 * Extract the text of an exported artifact.
 *
 * @param mustContain a string the document is KNOWN to contain. Guards against a
 *   vacuous assertion: if the extractor cannot see this, it never had the text,
 *   and any "absence" conclusion drawn from it would be false.
 */
export async function extractExportText(
  path: string,
  filename: string,
  mustContain: string,
): Promise<string> {
  const isDocx = /\.docx$/i.test(filename);
  const isPdf = /\.pdf$/i.test(filename);
  if (!isDocx && !isPdf) {
    throw new Error(`extractExportText: unsupported artifact ${filename}`);
  }

  let text = '';
  try {
    text = isDocx ? await docxText(path) : await pdfText(path);
  } catch (err) {
    throw new Error(
      `extractExportText: could NOT read ${filename} (${err instanceof Error ? err.message : String(err)}). ` +
        'Treat this as a failure, never as "no match found".',
    );
  }

  if (!text.includes(mustContain)) {
    throw new Error(
      `extractExportText: read ${text.length} chars from ${filename} but could not find ` +
        `the expected marker ${JSON.stringify(mustContain)}. The extractor is not seeing the ` +
        'document text, so an absence assertion against it would be vacuous. ' +
        `First 200 chars: ${JSON.stringify(text.slice(0, 200))}`,
    );
  }

  return text;
}

/** Bytes, for the rare assertion that wants them. */
export async function readExportBytes(path: string): Promise<Buffer> {
  return readFile(path);
}
