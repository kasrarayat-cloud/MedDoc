'use strict';
// Local visual-check server for the CPT Studio customer page. NOT used in production.
//
// Serves studio/templates/studio/*.html rendered as plain HTML (only the template tags those files use are supported;
// anything else fails loudly), the files in studio/static/studio/ (the PDF library's as its manifest lists them, with
// exactly the headers the site sends for them, its own policy included), and a
// mock of the customer JSON API (client contract customer-2026-11-26) backed by the hand-made customer fixtures in
// tests/fixtures/customer/. Binds 127.0.0.1 on the port given as --port=N, else on the first free port in 9170-9179.
// A decision names the coding review the page shows and a line of it, as the server takes it ({round, line, code,
// action, acknowledgement, note}, and for an Undo the decision it undoes: {..., decision}): a round that is not the
// document's latest finished one, a line it does not have, a code that is not that line's, or an Undo naming another
// decision than the line's current one is answered 409 with the server's sentence (decisionAnswer). A download names
// the coding review the page shows ({kind, fmt, round}, fmt pdf - the only report made): another round is answered 409 the same
// way (reportAnswer). A PDF download is a one-page synthetic PDF made here, not the server's physician report.
//
// Request headers understood by the mock: "X-Preview-Session: agent" serves the agent session;
// "X-Preview-Encounters: empty" serves an empty document list, and "X-Preview-Encounters: <n>" a synthetic practice of n
// documents made from the fixtures' rows (up to 20,000; its documents open no review: 404).
// A new upload answers 201 with the reading fixture's id and plays it forward on each read of the document: reading,
// then checking, then questions for you; sending answers plays a second coding review forward to ready for approval.
// The same client_key from the same session answers with the same id and creates nothing. A retry the document offers
// (the failed fixture's Retry, the earlier review's Review again) plays that document forward the same way. Every other
// change (decisions, stop, resume, downloads) answers as the real server does on success and never changes a fixture.
// The original document of every fixture is a synthetic one made here (SYNTHETIC_DOCUMENTS): a two-page PDF, plain text
// or a Word file. GET .../original downloads it; GET .../original?view=1 serves what the page's viewer shows, inline
// and framable by this origin only: the PDF or the text, and for a Word document the PDF of its pages (as the server
// serves the PDF the coding review read) - once converted: a Word document of an earlier review, or one uploaded here
// before its second read, has no view (404). The fixtures quote these documents exactly, on the pages given
// (tests/frontend/app.test.cjs).
// POST /__preview__/reset restarts the uploads and the retried documents; POST /__preview__/outdated makes every API
// call answer 409 {"error_code": "client_outdated"} until the next reset; POST /__preview__/offline makes reads of a
// document fail (503) until the next reset, which shows the page's reconnecting line.
// Release 2 (R2-1, R2-17): the shell carries the session as data-session-json - the payload GET /api/session answers
// for the same request - and POST /session/activity answers as the server answers a signed-in session (ACTIVITY),
// outside the client contract as there; the page pings it at load, so a 404 there was an error in every page.
// Release 2 (R2-19, R2-20): the lists a page at a time, as the server pages them - GET /api/encounters?list=documents|
// queue|recent[&before=<cursor>] answers {encounters, next, total}, 50 rows a page (the recent 5), newest first by
// created_at then id, the cursor '<UTC microseconds>~<id>', total on a first page of the documents or the queue, and
// opens_pdf on each row (a first file that is a PDF of at most 1 MiB, R2-16; a fixture row's own value where it has
// one); an unknown list or an unreadable cursor answers 400 with the server's sentences. POST /api/encounters/search
// {text, before} answers the rows whose text - the page's own documentRow's, release 1's rule - holds the words, 50 at a
// time, total null; blank words answer 400, words past 240 characters or holding a NUL or a lone surrogate an empty page.
// Release 2 (R2-15): a PDF view carries an ETag shaped as the server's (a quoted UUID, never a hash of the file: here an
// HMAC of this run's key, the document and its bytes), and a request whose If-None-Match names it (its weak form too,
// never '*') is answered 304 with no body, as studio.api answers the copy a page holds.

const http = require('node:http');
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');

const ROOT = path.resolve(__dirname, '..');
const TEMPLATES = path.join(ROOT, 'studio', 'templates', 'studio');
const STATIC = path.join(ROOT, 'studio', 'static', 'studio');
const FIXTURES = path.join(ROOT, 'tests', 'fixtures', 'customer');
const HOST = '127.0.0.1';
const PORTS = Array.from({ length: 10 }, (_, i) => 9170 + i);
const MAX_BODY = 16 * 1024 * 1024;
const MAX_ANSWER_CHARS = 2000;
const CSRF = crypto.randomBytes(16).toString('hex');
const STATIC_TYPES = { 'styles.css': 'text/css; charset=utf-8', 'app.js': 'text/javascript; charset=utf-8', 'favicon.svg': 'image/svg+xml' };
// The PDF library the review page loads for a PDF view (studio/static/studio/lib/): exactly the files its manifest lists,
// served with exactly the headers the site sends for them (Django and WhiteNoise, through studio.access.
// SecurityHeadersMiddleware, which wraps WhiteNoise: tests/test_frontend.py holds the two equal), so a local check sees
// the production truth - above all the module worker's own policy (STATIC_CSP), which is what binds the worker that
// parses the document, not the page's. Scripts are JavaScript (a module or module worker of another type is refused
// under nosniff), anything else is bytes.
const PDF_LIB = 'lib/pdfjs-6.5.438/';
const PDF_LIB_FILES = new Set(JSON.parse(fs.readFileSync(path.join(STATIC, PDF_LIB, 'MANIFEST.json'), 'utf8')).files.map(file => `${PDF_LIB}${file.path}`));
const PDF_LIB_TYPES = { '.mjs': 'text/javascript; charset="utf-8"', '.js': 'text/javascript; charset="utf-8"' };
// studio.access.SecurityHeadersMiddleware.STATIC_CSP: the site's policy with base-uri 'none'.
const STATIC_CSP = "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'; font-src 'self'; frame-ancestors 'none'; object-src 'none'; base-uri 'none'; form-action 'self'";
// The page's policy, as studio.access.SecurityHeadersMiddleware sends it, with the viewer's frame allowed from this
// origin only, so violations surface here.
const CSP = "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'; font-src 'self'; frame-src 'self'; frame-ancestors 'none'; object-src 'none'; base-uri 'self'; form-action 'self'";
// The in-page view of an original: framable by this origin only.
const VIEW_CSP = "frame-ancestors 'self'";
const UUID = '[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}';
const ACTIONS = new Set(['approve', 'reject', 'revoke']);
// The server's answer to a decision made on a coding review, or a line, that is no longer what it has.
const CHANGED = 'This coding review has changed. Reload to see the latest.';
const DOCX_TYPE = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document';
const UPLOAD_TYPES = { pdf: 'application/pdf', txt: 'text/plain', docx: DOCX_TYPE };
const INSURANCE = new Set(['medicare', 'medicaid', 'commercial', 'unknown']);
// studio.views.activity_ping's answer for a signed-in session: how long it has before it idles out and before its cap
// (the member's limits), the warning's lead, and the session's tag - empty here, as the shell's data-session is.
const ACTIVITY = { idle_seconds: 900, cap_seconds: 28800, warning_seconds: 120, session: '' };

// The synthetic documents the fixtures' quotes come from: invented, no real patient.
const SYNTHETIC_DOCUMENTS = {
  'synthetic-egd-colonoscopy.pdf': {
    type: 'application/pdf',
    pages: [
      ['SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE', 'Endoscopy report (fictional)',
        'Patient: Riley Synthetic. Date of service: 2026-11-02.', 'Procedures: upper endoscopy (EGD) and colonoscopy.',
        'EGD: The endoscope was passed to the second part of the duodenum.', 'Patchy erythema was seen in the gastric antrum.',
        'Cold forceps biopsies were taken from the gastric antrum.'],
      ['Colonoscopy: The colonoscope was advanced to the cecum.', 'The appendiceal orifice and the ileocecal valve were identified.',
        'A 9 mm sessile polyp in the sigmoid colon was removed with a cold snare.', 'A 4 mm polyp in the ascending colon was removed with cold forceps.',
        'Bowel preparation quality was not recorded.', 'Impression: antral erythema; two colon polyps removed.'],
    ],
  },
  'synthetic-colonoscopy-note.txt': {
    type: 'text/plain',
    pages: [['SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE', 'Colonoscopy note (fictional)',
      'Patient: Jordan Synthetic. Date of service: 2026-11-05.', 'The colonoscope was advanced to the cecum.',
      'A 12 mm pedunculated polyp in the descending colon was removed.', 'A 3 mm polyp in the rectum was seen and left in place.',
      'Upper endoscopy was planned but is not recorded as performed.']],
  },
  // one question for two lines (D370): the title names a biopsy the description does not, and the note's date of
  // service is not the one entered at upload
  'synthetic-colonoscopy-biopsy-title.txt': {
    type: 'text/plain',
    pages: [['SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE', 'Procedure: colonoscopy with biopsy (fictional)',
      'Patient: Avery Synthetic. Date of service: 2026-11-12.', 'The colonoscope was advanced to the cecum and the mucosa was examined on withdrawal.',
      'The mucosa appeared normal throughout, and the scope was withdrawn.', 'Moderate sedation was given by the endoscopist; no start or stop time is recorded.']],
  },
  'pasted-cancelled-colonoscopy': {
    type: 'text/plain',
    pages: [['SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE', 'Procedure note (fictional)',
      'Patient: Casey Synthetic. Date of service: 2026-11-06.', 'The patient arrived for colonoscopy.',
      'The procedure was cancelled before sedation because the patient had eaten that morning.', 'No scope was inserted.']],
  },
  // a Word file of two pages; its view is the PDF of the same pages, so the quoted pages are the pages shown
  'synthetic-colonoscopy-report.docx': {
    type: DOCX_TYPE,
    pages: [
      ['SYNTHETIC TEST DOCUMENT - FICTIONAL PATIENT - NOT FOR CLINICAL USE', 'Colonoscopy report (fictional)',
        'Patient: Morgan Synthetic. Date of service: 2026-11-09.', 'Indication: surveillance after an earlier polyp removal.',
        'The colonoscope was advanced to the cecum and the terminal ileum was entered.',
        'Two biopsies were taken from the cecum with cold forceps.'],
      ['A 7 mm sessile polyp in the transverse colon was removed with a cold snare.',
        'The polypectomy site was marked with a submucosal ink injection.', 'The bowel preparation was rated good.',
        'Impression: one transverse colon polyp removed and its site marked; cecal biopsies taken.'],
    ],
  },
};

function pdfText(value) {
  return value.replace(/[\\()]/g, ch => `\\${ch}`);
}

// A minimal, valid PDF of plain text pages (Helvetica 11 pt), so the viewer has real pages to open at #page=N.
function syntheticPdf(pages) {
  const objects = [];
  objects[1] = '<< /Type /Catalog /Pages 2 0 R >>';
  objects[2] = `<< /Type /Pages /Kids [${pages.map((_, i) => `${4 + i * 2} 0 R`).join(' ')}] /Count ${pages.length} >>`;
  objects[3] = '<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>';
  pages.forEach((lines, i) => {
    const stream = ['BT', '/F1 11 Tf', '16 TL', '56 740 Td', ...lines.flatMap(line => [`(${pdfText(line)}) Tj`, 'T*']), 'ET'].join('\n');
    objects[4 + i * 2] = `<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 3 0 R >> >> /Contents ${5 + i * 2} 0 R >>`;
    objects[5 + i * 2] = `<< /Length ${Buffer.byteLength(stream, 'latin1')} >>\nstream\n${stream}\nendstream`;
  });
  let body = '%PDF-1.4\n';
  const offsets = [];
  for (let id = 1; id < objects.length; id += 1) {
    offsets[id] = Buffer.byteLength(body, 'latin1');
    body += `${id} 0 obj\n${objects[id]}\nendobj\n`;
  }
  const xref = Buffer.byteLength(body, 'latin1');
  body += `xref\n0 ${objects.length}\n0000000000 65535 f \n${offsets.slice(1).map(offset => `${String(offset).padStart(10, '0')} 00000 n \n`).join('')}`;
  body += `trailer\n<< /Size ${objects.length} /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF\n`;
  return Buffer.from(body, 'latin1');
}

const CRC_TABLE = Array.from({ length: 256 }, (_, value) => {
  let crc = value;
  for (let bit = 0; bit < 8; bit += 1) crc = crc & 1 ? 0xedb88320 ^ (crc >>> 1) : crc >>> 1;
  return crc >>> 0;
});

function crc32(bytes) {
  let crc = 0xffffffff;
  for (const byte of bytes) crc = CRC_TABLE[(crc ^ byte) & 0xff] ^ (crc >>> 8);
  return (crc ^ 0xffffffff) >>> 0;
}

// A ZIP archive of [name, bytes] entries, stored without compression (all a Word file needs to open).
function storedZip(entries) {
  const parts = [];
  const directory = [];
  let offset = 0;
  for (const [name, data] of entries) {
    const file = Buffer.from(name, 'utf8');
    const crc = crc32(data);
    const local = Buffer.alloc(30);
    local.writeUInt32LE(0x04034b50, 0);
    local.writeUInt16LE(20, 4);
    local.writeUInt16LE(0x21, 12);  // 1 January 1980
    local.writeUInt32LE(crc, 14);
    local.writeUInt32LE(data.length, 18);
    local.writeUInt32LE(data.length, 22);
    local.writeUInt16LE(file.length, 26);
    const central = Buffer.alloc(46);
    central.writeUInt32LE(0x02014b50, 0);
    central.writeUInt16LE(20, 4);
    central.writeUInt16LE(20, 6);
    central.writeUInt16LE(0x21, 14);
    central.writeUInt32LE(crc, 16);
    central.writeUInt32LE(data.length, 20);
    central.writeUInt32LE(data.length, 24);
    central.writeUInt16LE(file.length, 28);
    central.writeUInt32LE(offset, 42);
    parts.push(local, file, data);
    directory.push(central, file);
    offset += local.length + file.length + data.length;
  }
  const listing = Buffer.concat(directory);
  const end = Buffer.alloc(22);
  end.writeUInt32LE(0x06054b50, 0);
  end.writeUInt16LE(entries.length, 8);
  end.writeUInt16LE(entries.length, 10);
  end.writeUInt32LE(listing.length, 12);
  end.writeUInt32LE(offset, 16);
  return Buffer.concat([...parts, listing, end]);
}

function xmlText(value) {
  return value.replace(/[&<>]/g, ch => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' }[ch]));
}

// A minimal, valid Word file: one paragraph per line and a page break between pages.
function syntheticDocx(pages) {
  const head = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n';
  const paragraph = line => `<w:p><w:r><w:t xml:space="preserve">${xmlText(line)}</w:t></w:r></w:p>`;
  const body = pages.map(lines => lines.map(paragraph).join('')).join('<w:p><w:r><w:br w:type="page"/></w:r></w:p>');
  return storedZip([
    ['[Content_Types].xml', Buffer.from(`${head}<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>`, 'utf8')],
    ['_rels/.rels', Buffer.from(`${head}<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>`, 'utf8')],
    ['word/document.xml', Buffer.from(`${head}<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>${body}<w:sectPr><w:pgSz w:w="12240" w:h="15840"/></w:sectPr></w:body></w:document>`, 'utf8')],
  ]);
}

// One synthetic document's bytes and type as uploaded: a PDF of its pages, a Word file of them, or its lines as plain
// text.
function documentBytes(name) {
  const source = SYNTHETIC_DOCUMENTS[name] || SYNTHETIC_DOCUMENTS['synthetic-colonoscopy-note.txt'];
  if (source.type === 'application/pdf') return { bytes: syntheticPdf(source.pages), type: source.type };
  if (source.type === DOCX_TYPE) return { bytes: syntheticDocx(source.pages), type: source.type };
  return { bytes: Buffer.from(`${source.pages.flat().join('\n')}\n`, 'utf8'), type: 'text/plain; charset=utf-8' };
}

// What the viewer is served of one synthetic document: the PDF or text as uploaded, and for a Word file the PDF of its
// pages (the server serves the PDF the coding review read: the converted file).
function viewBytes(name) {
  if (SYNTHETIC_DOCUMENTS[name]?.type === DOCX_TYPE) return { bytes: syntheticPdf(SYNTHETIC_DOCUMENTS[name].pages), type: 'application/pdf' };
  return documentBytes(name);
}

// The synthetic document a fixture's original stands for: by its name, a pasted text by its own key, else by its type.
function documentFor(doc) {
  const name = doc?.document?.name;
  if (typeof name === 'string' && Object.hasOwn(SYNTHETIC_DOCUMENTS, name)) return name;
  if (doc?.document?.kind === 'paste') return 'pasted-cancelled-colonoscopy';
  const type = doc?.document?.media_type;
  if (type === DOCX_TYPE) return 'synthetic-colonoscopy-report.docx';
  return type === 'application/pdf' ? 'synthetic-egd-colonoscopy.pdf' : 'synthetic-colonoscopy-note.txt';
}

// The fixtures, read when the server starts (requiring this file for its documents reads nothing). The played
// stages are named by file, never by which fixture a directory listing happens to give first.
let fixtures = null;

function loadFixtures() {
  const readJson = name => JSON.parse(fs.readFileSync(path.join(FIXTURES, name), 'utf8'));
  return {
    session: readJson('session.json'),
    agent: readJson('session-agent.json'),
    encounters: readJson('encounters.json'),
    empty: readJson('encounters-empty.json'),
    byId: new Map(fs.readdirSync(FIXTURES).filter(name => /^encounter-.+\.json$/.test(name)).sort().map(name => {
      const doc = readJson(name);
      return [doc.id, doc];
    })),
    reading: readJson('encounter-reading.json'),
    checking: readJson('encounter-checking.json'),
    asking: readJson('encounter-awaiting-answer.json'),
    results: readJson('encounter-ready.json'),
  };
}

// R2-19, R2-20: the lists' pages and the search, as the server answers them.
const LIST_PAGE = 50;
const RECENT_PAGE = 5;
const QUEUE_STATES = new Set(['awaiting_answer', 'needs_review', 'ready']);
const LIST_CURSOR = new RegExp(`^(\\d{1,20})~(${UUID})$`);
const SEARCH_CHARS = 240;
const LIST_UNKNOWN = 'That list is not available.';
const CURSOR_UNREADABLE = 'That part of the list could not be read. Open the list again.';
const SEARCH_BLANK = 'Type the words to search for.';
let pageScript = null;

// Whether a fixture's document opens as a PDF of at most 1 MiB (R2-16's opens_pdf): its first file is an uploaded PDF.
function opensPdf(id) {
  const part = fixtures.byId.get(id)?.document;
  return Boolean(part) && part.kind === 'upload' && part.media_type === 'application/pdf' && Number.isInteger(part.size) && part.size <= 1048576;
}

// The practice the request reads: the fixtures' rows (each with opens_pdf), none, or a synthetic practice of n rows.
function practiceRows(req) {
  const asked = String(req.headers['x-preview-encounters'] || '');
  if (asked === 'empty') return [];
  const rows = fixtures.encounters.encounters.map(row => ({ ...row, opens_pdf: Object.hasOwn(row, 'opens_pdf') ? row.opens_pdf : opensPdf(row.id) }));
  if (!/^\d{1,5}$/.test(asked)) return rows;
  const start = Date.parse('2026-11-20T10:00:00Z');
  return Array.from({ length: Math.min(Number(asked), 20000) }, (_, n) => {
    const from = rows[n % rows.length];
    const id = `5e${(n % rows.length).toString(16).padStart(6, '0')}-0000-4000-8000-${n.toString(16).padStart(12, '0')}`;
    return { ...from, id, title: `${from.title} (${n + 1})`, created_at: iso(start - n * 60000) };
  });
}

const placeOf = row => [Date.parse(row.created_at) * 1000, row.id];
const newestFirst = (a, b) => {
  const [timeA, idA] = placeOf(a);
  const [timeB, idB] = placeOf(b);
  return timeB - timeA || (idB > idA ? 1 : idB < idA ? -1 : 0);
};

// [status, payload] of one page of `rows` (already the list's), from the place `before` names (null: the first page).
function listAnswer(rows, which, before) {
  const ordered = rows.slice().sort(newestFirst);
  let start = 0;
  if (before !== null) {
    const match = LIST_CURSOR.exec(before);
    if (!match) return [400, { error: CURSOR_UNREADABLE }];
    const [time, id] = [Number(match[1]), match[2]];
    start = ordered.findIndex(row => { const [rowTime, rowId] = placeOf(row); return rowTime < time || (rowTime === time && rowId < id); });
    if (start < 0) start = ordered.length;
  }
  const size = which === 'recent' ? RECENT_PAGE : LIST_PAGE;
  const shown = ordered.slice(start, start + size);
  const more = which !== 'recent' && start + size < ordered.length;
  const last = shown[shown.length - 1];
  return [200, { encounters: shown, next: more ? `${placeOf(last)[0]}~${last.id}` : null,
    total: which !== 'recent' && before === null ? rows.length : null }];
}

// The text the page's search reads of a row: its own documentRow's (release 1's rule), as the server rebuilds it.
function rowText(row) {
  pageScript = pageScript || require(path.join(STATIC, 'app.js'));
  return pageScript.documentRow(row).replace(/<[^>]*>/g, '')
    .replace(/&(?:amp|lt|gt|quot|#x27|#x60);/g, entity => ({ '&amp;': '&', '&lt;': '<', '&gt;': '>', '&quot;': '"', '&#x27;': "'", '&#x60;': '`' })[entity]);
}

// [status, payload] of POST /api/encounters/search.
function searchAnswer(rows, body) {
  const words = body?.text;
  if (typeof words !== 'string' || !words.trim()) return [400, { error: SEARCH_BLANK }];
  const before = body.before ?? null;
  if (before !== null && typeof before !== 'string') return [400, { error: CURSOR_UNREADABLE }];
  if ([...words].length > SEARCH_CHARS || words.includes('\u0000') || /\p{Cs}/u.test(words)) return [200, { encounters: [], next: null, total: null }];
  const wanted = words.toLowerCase();
  const [status, payload] = listAnswer(rows.filter(row => rowText(row).toLowerCase().includes(wanted)), 'documents', before);
  return [status, status === 200 ? { ...payload, total: null } : payload];
}

const uploads = new Map();  // '<session> <client_key>' -> encounter id
// encounter id -> {reads, at, started, answered, round, trigger, title, name, kind, mediaType, size, context, answers,
// converted}: an uploaded or retried document, played forward
const plays = new Map();
const reports = new Map();
const flags = { outdated: false, offline: false };

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, ch => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#x27;' }[ch]));
}

function renderTemplate(name, context = {}) {
  const html = fs.readFileSync(path.join(TEMPLATES, name), 'utf8')
    .replace(/\{%\s*load\s+static\s*%\}/g, '')
    .replace(/\{%\s*static\s+'([^']+)'\s*%\}/g, (_, file) => `/static/${file}`)
    .replace(/\{%\s*csrf_token\s*%\}/g, `<input type="hidden" name="csrfmiddlewaretoken" value="${CSRF}">`)
    .replace(/\{%\s*if\s+(\w+)\s*%\}([\s\S]*?)\{%\s*endif\s*%\}/g, (_, key, body) => (context[key] ? body : ''))
    .replace(/\{\{\s*(\w+)\s*\}\}/g, (_, key) => escapeHtml(context[key]));
  if (/\{[%{]/.test(html)) throw new Error(`${name}: template syntax the preview renderer does not support`);
  return html;
}

function send(res, status, body, headers = {}) {
  res.writeHead(status, {
    'Content-Security-Policy': CSP, 'X-Content-Type-Options': 'nosniff', 'Referrer-Policy': 'same-origin',
    'X-Frame-Options': 'DENY', 'Cache-Control': 'no-store', ...headers,
  });
  res.end(body);
}

const json = (res, status, data) => send(res, status, JSON.stringify(data), { 'Content-Type': 'application/json' });

// One file of the PDF library with the site's headers for it and nothing else: WhiteNoise's (its type, CORS, caching of
// an unhashed name, Vary, validators), Django's SecurityMiddleware's (nosniff, referrer, opener) and the site's own
// (STATIC_CSP, no-index, permissions); no X-Frame-Options and no no-store, as on the site.
function sendLibraryFile(res, name) {
  const file = path.join(STATIC, name);
  const stat = fs.statSync(file);
  res.writeHead(200, {
    'Access-Control-Allow-Origin': '*', 'Cache-Control': 'max-age=60, public', 'Content-Length': String(stat.size),
    'Content-Security-Policy': STATIC_CSP, 'Content-Type': PDF_LIB_TYPES[path.extname(name)] || 'application/octet-stream',
    'Cross-Origin-Opener-Policy': 'same-origin', ETag: `"${Math.floor(stat.mtimeMs / 1000).toString(16)}-${stat.size.toString(16)}"`,
    'Last-Modified': stat.mtime.toUTCString(), 'Permissions-Policy': 'camera=(), microphone=(), geolocation=()',
    'Referrer-Policy': 'same-origin', Vary: 'Accept-Encoding', 'X-Content-Type-Options': 'nosniff', 'X-Robots-Tag': 'noindex, nofollow',
  });
  res.end(fs.readFileSync(file));
}
const apiError = (res, status, message, details = {}) => json(res, status, { error: message, details });

function readBody(req) {
  return new Promise((resolve, reject) => {
    const chunks = [];
    let size = 0;
    req.on('data', chunk => {
      size += chunk.length;
      if (size > MAX_BODY) {
        reject(new Error('body too large'));
        req.destroy();
      } else {
        chunks.push(chunk);
      }
    });
    req.on('end', () => resolve(Buffer.concat(chunks)));
    req.on('error', reject);
  });
}

// R2-15: a PDF view's tag, shaped as studio.api.view_tag's: a quoted UUID, bound to this run and the document.
function viewTag(id, bytes) {
  const hex = crypto.createHmac('sha256', CSRF).update(`${id}:`).update(crypto.createHash('sha256').update(bytes).digest('hex')).digest('hex');
  return `"${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20, 32)}"`;
}

// Whether an If-None-Match header names `tag`, as studio.api._held reads it (django.utils.http.parse_etags): the weak form
// counts, '*' never does.
function namesTag(header, tag) {
  return String(header || '').split(',').map(item => item.trim().replace(/^W\//, '')).some(item => item !== '*' && item === tag);
}

function parseJson(buffer) {
  try {
    const value = JSON.parse(buffer.toString('utf8') || '{}');
    return value && typeof value === 'object' ? value : null;
  } catch {
    return null;
  }
}

// One multipart field's text value (the mock reads only the small text fields it needs).
function formField(body, name) {
  const match = new RegExp(`name="${name}"\\r\\n\\r\\n([^\\r]*)\\r\\n`).exec(body);
  return match ? match[1] : '';
}

// The uploaded file's name, if the upload carried a file.
function formFileName(body) {
  const match = /name="file"; filename="([^"\r\n]*)"/.exec(body);
  return match ? match[1] : '';
}

const iso = ms => new Date(ms).toISOString().replace(/\.\d{3}Z$/, 'Z');
const clone = value => JSON.parse(JSON.stringify(value));

// What the viewer shows of a played document, as the server builds it: a PDF or a text as uploaded; a Word file nothing
// until the coding review has converted it (here from its second read on), then that PDF.
function playedView(id, play) {
  const view = `/api/encounters/${id}/original?view=1`;
  if (play.mediaType !== DOCX_TYPE) {
    return { view_url: view, view_media_type: play.mediaType === 'application/pdf' ? 'application/pdf' : 'text/plain', converted: false };
  }
  play.converted = play.converted || play.reads > 1;
  return play.converted ? { view_url: view, view_media_type: 'application/pdf', converted: true } : { view_url: null, view_media_type: null, converted: false };
}

// An uploaded or retried document, one stage further on each read of it (advance), with its times taken from the upload
// or the retry.
function played(id, advance) {
  const play = plays.get(id);
  if (advance) play.reads += 1;
  const now = Date.now();
  const { reading, checking, asking, results } = fixtures;
  const stages = play.answered ? [[2, reading], [4, checking], [Infinity, results]] : [[2, reading], [5, checking], [Infinity, asking]];
  const base = clone(stages.find(([limit]) => play.reads <= limit)[1]);
  const done = !base.progress.busy;
  return {
    ...base, id, title: play.title, created_at: iso(play.at), updated_at: iso(now), context: play.context,
    document: {
      ...base.document, name: play.name, kind: play.kind, media_type: play.mediaType, size: play.size,
      original_url: play.kind === 'paste' ? null : `/api/encounters/${id}/original`, ...playedView(id, play),
    },
    progress: { ...base.progress, started_at: iso(play.started), server_time: iso(now), finished_at: done ? iso(now - 1000) : null },
    round: { number: play.round + (play.answered ? 1 : 0), trigger: play.answered ? 'answers' : play.trigger, finished_at: done ? iso(now - 1000) : null },
    answers: play.answers,
  };
}

// A document by id: a played one (only a read of the document itself moves it on), else a fixture.
function encounterFor(id, advance = false) {
  if (plays.has(id)) return played(id, advance);
  return fixtures.byId.get(id) || null;
}

// The play of a document from now on: an upload, or a retry of a fixture that offers one.
function startPlay(id, from) {
  plays.set(id, { reads: 0, started: Date.now() + 1000, answered: false, converted: false, ...from });
}

async function handleApi(req, res, url) {
  const method = req.method;
  const route = url.pathname;
  if (method === 'POST' && req.headers['x-csrftoken'] !== CSRF) {
    return send(res, 403, '<h1>Forbidden (403)</h1><p>CSRF verification failed. Request aborted.</p>', { 'Content-Type': 'text/html; charset=utf-8' });
  }
  if (flags.outdated) return json(res, 409, { error: 'CPT Studio was updated. Reload the page.', error_code: 'client_outdated' });
  const agent = req.headers['x-preview-session'] === 'agent';
  const session = agent ? fixtures.agent : fixtures.session;
  if (method === 'GET' && route === '/api/session') return json(res, 200, session);
  if (method === 'GET' && route === '/api/encounters') {
    const which = url.searchParams.has('list') ? url.searchParams.get('list') : 'documents';
    if (!['documents', 'queue', 'recent'].includes(which)) return json(res, 400, { error: LIST_UNKNOWN });
    const rows = practiceRows(req);
    const [status, payload] = listAnswer(which === 'queue' ? rows.filter(row => QUEUE_STATES.has(row.state)) : rows, which, url.searchParams.get('before'));
    return json(res, status, status === 200 ? { ...payload, workspace: session.workspace.id } : payload);  // the practice read (I1-2)
  }
  if (route === '/api/encounters/search') {
    if (method !== 'POST') return apiError(res, 405, 'Method not allowed.');
    const [status, payload] = searchAnswer(practiceRows(req), parseJson(await readBody(req)));
    return json(res, status, status === 200 ? { ...payload, workspace: session.workspace.id } : payload);
  }
  if (method === 'POST' && route === '/api/encounters') {
    const body = (await readBody(req)).toString('latin1');
    if (!/^multipart\/form-data/.test(req.headers['content-type'] || '')) return apiError(res, 400, 'Send the document as a file or as pasted text.');
    if (formField(body, 'synthetic_attestation') !== 'yes') return apiError(res, 400, 'Confirm that the document is synthetic.');
    if (!/name="(file|text)"/.test(body)) return apiError(res, 400, 'Attach a file or paste the text.');
    const insurance = formField(body, 'insurance') || 'unknown';
    if (!INSURANCE.has(insurance)) return apiError(res, 400, 'Choose the insurance, or Not sure.');
    const key = formField(body, 'client_key');
    if (!new RegExp(`^${UUID}$`).test(key)) return apiError(res, 400, 'This upload could not be identified. Reload the page and try again.');
    const seen = uploads.get(`${agent ? 'agent' : 'human'} ${key}`);
    if (seen) return json(res, 201, { id: seen });
    const id = fixtures.reading.id;
    const file = formFileName(body);
    const date = formField(body, 'service_date');
    // the played document keeps one type and size from the upload on, as a real one does
    const mediaType = file ? UPLOAD_TYPES[(/\.(pdf|docx|txt)$/i.exec(file) || [])[1]?.toLowerCase()] || 'text/plain' : 'text/plain';
    const shown = documentFor({ document: { name: file, kind: file ? 'upload' : 'paste', media_type: mediaType } });
    uploads.set(`${agent ? 'agent' : 'human'} ${key}`, id);
    startPlay(id, {
      at: Date.now(), answers: [], round: 1, trigger: 'upload',
      title: file ? file.replace(/\.(pdf|docx|txt)$/i, '') : 'Pasted clinical text', name: file || null, kind: file ? 'upload' : 'paste',
      mediaType, size: documentBytes(shown).bytes.length,
      context: { service_date: /^\d{4}-\d{2}-\d{2}$/.test(date) ? date : null, insurance },
    });
    return json(res, 201, { id });
  }
  let match = new RegExp(`^/api/encounters/(${UUID})$`).exec(route);
  if (match && method === 'GET') {
    if (flags.offline) return apiError(res, 503, 'The service is not available right now.');
    const doc = encounterFor(match[1], true);
    return doc ? json(res, 200, doc) : apiError(res, 404, 'Not found.');
  }
  match = new RegExp(`^/api/encounters/(${UUID})/original$`).exec(route);
  if (match && method === 'GET') {
    const doc = encounterFor(match[1]);
    if (!doc) return apiError(res, 404, 'Not found.');
    const view = url.searchParams.get('view') === '1';
    if (view && !doc.document.view_url) return apiError(res, 404, 'Not found.');
    if (!view && !doc.document.original_url) return apiError(res, 404, 'This document was pasted, so there is no original file.');
    const name = documentFor(doc);
    const filename = doc.document.name || 'pasted-text.txt';
    if (!view) {
      const { bytes, type } = documentBytes(name);
      return send(res, 200, bytes, { 'Content-Type': type, 'Content-Disposition': `attachment; filename="${filename}"` });
    }
    // a converted Word document is served as the PDF it became, under the Word file's name (studio/customer.py)
    const { bytes, type } = viewBytes(name);
    const shownName = doc.document.converted === true ? `${filename.replace(/\.[^.]*$/, '')}.pdf` : filename;
    // R2-15: a PDF view carries its tag, and the copy the page holds is answered 304, with no body and no type
    const tag = type === 'application/pdf' ? viewTag(match[1], bytes) : '';
    if (tag && namesTag(req.headers['if-none-match'], tag)) {
      return send(res, 304, '', { ETag: tag, 'X-Frame-Options': 'SAMEORIGIN', 'Content-Security-Policy': VIEW_CSP });
    }
    return send(res, 200, bytes, {
      'Content-Type': type, 'Content-Disposition': `inline; filename="${shownName}"`, 'X-Frame-Options': 'SAMEORIGIN', 'Content-Security-Policy': VIEW_CSP,
      ...(tag ? { ETag: tag } : {}),
    });
  }
  match = new RegExp(`^/api/encounters/(${UUID})/(answers|decisions|stop|resume|retry|reports)$`).exec(route);
  if (match) {
    const doc = encounterFor(match[1]);
    if (!doc) return apiError(res, 404, 'Not found.');
    if (method !== 'POST') return apiError(res, 405, 'Method not allowed.');
    const body = parseJson(await readBody(req));
    if (!body) return apiError(res, 400, 'This could not be saved. Reload the page and try again.');
    return handleChange(res, doc, match[2], body, session);
  }
  match = new RegExp(`^/api/reports/(${UUID})/download$`).exec(route);
  if (match && method === 'GET') {
    const report = reports.get(match[1]);
    if (!report) return apiError(res, 404, 'Not found.');
    return send(res, 200, report.content, { 'Content-Type': report.type, 'Content-Disposition': `attachment; filename="${report.filename}"` });
  }
  return apiError(res, 404, 'Not found.');
}

// Whether `round` is the number of `doc`'s latest coding review and that review has finished: what a decision and a
// download must name.
function latestFinished(doc, round) {
  return doc.progress?.phase === 'done' && Number.isInteger(doc.round?.number) && round === doc.round.number;
}

// [status, payload] of POST decisions on `doc`, as the server answers it: 409 CHANGED unless `round` is the number of the
// document's latest coding review, that review has finished, `line` is one of its lines and `code` is that line's code;
// then the line's own allowed actions, the exact approval statement, and for an Undo the id of the line's current
// decision (an Undo naming another one is 409 CHANGED: it would undo a decision the member never saw). Nothing here
// changes a fixture.
function decisionAnswer(doc, body, session) {
  const line = latestFinished(doc, body.round) ? (doc.codes || []).find(item => item.line === body.line) : null;
  if (!line || line.code !== body.code) return [409, { error: CHANGED, details: {} }];
  if (!ACTIONS.has(body.action)) return [400, { error: 'Choose approve, reject or undo.', details: {} }];
  if (!line.allowed_actions.includes(body.action)) return [409, { error: 'This action is not available for this line right now.', details: {} }];
  if (body.action === 'revoke' && (typeof body.decision !== 'string' || body.decision !== line.decision?.id)) return [409, { error: CHANGED, details: {} }];
  if (body.action === 'approve' && body.acknowledgement !== session.acknowledgement) return [400, { error: 'An approval needs the exact confirmation statement.', details: {} }];
  return [201, { line: line.line, code: line.code, id: crypto.randomUUID(), action: body.action, by: session.user.label, at: iso(Date.now()), note: typeof body.note === 'string' ? body.note : '' }];
}

// [status, payload] of POST reports on `doc`, as the server answers it: 400 (the server's sentence) for a kind or format
// it does not make (any but the PDF, owner direction 2026-11-21); 409 CHANGED unless `round` is the number of the document's latest coding review and that review has
// finished; 409 with the readiness blockers when the download asked for is not available; else 201 with the report as
// the page lists it. The download is a mock (registered in `reports`): for a PDF a one-page PDF made here
// (syntheticPdf), served as application/pdf, never the server's physician report; nothing here changes a fixture.
const FORMAT_REQUIRED = 'Choose a draft or an approved PDF report.';
const REPORT_TYPES = { pdf: 'application/pdf' };

function reportAnswer(doc, body) {
  if (!['draft', 'approved'].includes(body.kind) || typeof body.fmt !== 'string' || !Object.hasOwn(REPORT_TYPES, body.fmt)) return [400, { error: FORMAT_REQUIRED, details: {} }];
  if (!latestFinished(doc, body.round)) return [409, { error: CHANGED, details: {} }];
  if (body.kind === 'approved' && doc.readiness?.approved !== true) {
    return [409, { error: 'The approved download is not available yet.', details: { blockers: doc.readiness?.blockers || [] } }];
  }
  if (body.kind === 'draft' && doc.readiness?.draft !== true) return [409, { error: 'Nothing can be downloaded yet.', details: { blockers: doc.readiness?.blockers || [] } }];
  const id = crypto.randomUUID();
  const filename = `cpt-studio-preview-${body.kind}.${body.fmt}`;
  const lines = ['SYNTHETIC - NOT FOR BILLING', `CPT Studio preview mock download (${body.kind}).`, 'The real download is built by the server from the saved decisions.'];
  const content = syntheticPdf([lines]);
  reports.set(id, { content, filename, type: REPORT_TYPES[body.fmt] });
  return [201, { id, kind: body.kind, fmt: body.fmt, filename, generated_at: iso(Date.now()), download_url: `/api/reports/${id}/download`, current: true }];
}

// A download the preview registered: {content, filename, type}, or null.
function reportFile(id) {
  return reports.get(id) || null;
}

function handleChange(res, doc, action, body, session) {
  if (action === 'answers') {
    const answers = Array.isArray(body.answers) ? body.answers : [];
    if (!answers.length) return apiError(res, 400, 'Write an answer to at least one question.');
    const questions = new Map((doc.questions || []).map(question => [question.id, question]));
    for (const answer of answers) {
      if (!questions.has(answer?.question_id)) return apiError(res, 409, 'A question is no longer asked. Reload the page.');
      const value = typeof answer.text === 'string' ? answer.text.trim() : '';
      if (!value || [...value].length > MAX_ANSWER_CHARS) return apiError(res, 400, 'Each answer needs text, up to 2,000 characters.');
    }
    const play = plays.get(doc.id);
    if (play) {
      play.answered = true;
      play.reads = 0;
      play.started = Date.now() + 1000;
      play.answers = answers.map(answer => ({ question: questions.get(answer.question_id).text, answer: answer.text.trim(), by: session.user.label, at: iso(Date.now()) }));
    }
    return json(res, 201, { round: { number: (doc.round?.number || 0) + 1, trigger: 'answers', finished_at: null } });
  }
  if (action === 'decisions') {
    const [status, payload] = decisionAnswer(doc, body, session);
    return json(res, status, payload);
  }
  if (action === 'stop') return doc.progress?.can_stop ? json(res, 200, { stopped: true }) : apiError(res, 409, 'Nothing is running for this document.');
  if (action === 'resume') return doc.progress?.can_resume ? json(res, 201, { resumed: true }) : apiError(res, 409, 'There is nothing to resume for this document.');
  if (action === 'retry') {
    if (!doc.progress?.can_retry) return apiError(res, 409, 'This document cannot be retried right now.');
    // a new coding review of the document (an earlier review's first): played forward from here, as an upload is
    const number = (doc.round?.number || 0) + 1;
    startPlay(doc.id, {
      at: Date.parse(doc.created_at), answers: doc.answers || [], round: number, trigger: 'retry', title: doc.title,
      name: doc.document.name, kind: doc.document.kind, mediaType: doc.document.media_type, size: doc.document.size, context: doc.context,
    });
    return json(res, 201, { round: { number, trigger: 'retry', finished_at: null } });
  }
  const [status, payload] = reportAnswer(doc, body);
  return json(res, status, payload);
}

async function handle(req, res) {
  let url;
  try {
    url = new URL(req.url, `http://${HOST}`);
  } catch {
    return send(res, 400, 'Bad request');
  }
  if (url.pathname.startsWith('/api/')) return handleApi(req, res, url);
  if (req.method === 'POST' && url.pathname === '/__preview__/reset') {
    uploads.clear();
    plays.clear();
    flags.outdated = false;
    flags.offline = false;
    return send(res, 204, '');
  }
  if (req.method === 'POST' && url.pathname === '/__preview__/outdated') {
    flags.outdated = true;
    return send(res, 204, '');
  }
  if (req.method === 'POST' && url.pathname === '/__preview__/offline') {
    flags.offline = true;
    return send(res, 204, '');
  }
  if (req.method === 'GET' && url.pathname === '/') {
    // the shell as studio.views.index renders it, carrying the session GET /api/session would answer this request
    const session = req.headers['x-preview-session'] === 'agent' ? fixtures.agent : fixtures.session;
    const shell = renderTemplate('index.html', { specialty: fixtures.session.workspace.specialty, session_json: JSON.stringify(session) });
    return send(res, 200, shell, {
      'Content-Type': 'text/html; charset=utf-8', 'Set-Cookie': `cptstudio_csrf=${CSRF}; Path=/; SameSite=Strict`,
    });
  }
  if (url.pathname === '/login/') {
    if (req.method === 'POST') return send(res, 302, '', { Location: '/' });
    const context = { error: url.searchParams.has('error') ? 'The username or password is not correct.' : '', username: url.searchParams.get('username') || '', next: url.searchParams.get('next') || '' };
    return send(res, 200, renderTemplate('login.html', context), {
      'Content-Type': 'text/html; charset=utf-8', 'Set-Cookie': `cptstudio_csrf=${CSRF}; Path=/; SameSite=Strict`,
    });
  }
  if (req.method === 'POST' && url.pathname === '/logout/') return send(res, 302, '', { Location: '/login/' });
  if (url.pathname === '/session/activity') {
    // as the site answers it: a POST past the CSRF check, any other method 405
    if (req.method !== 'POST') return send(res, 405, '', { Allow: 'POST', 'Content-Type': 'text/html; charset=utf-8' });
    if (req.headers['x-csrftoken'] !== CSRF) {
      return send(res, 403, '<h1>Forbidden (403)</h1><p>CSRF verification failed. Request aborted.</p>', { 'Content-Type': 'text/html; charset=utf-8' });
    }
    return json(res, 200, ACTIVITY);
  }
  const name = url.pathname.startsWith('/static/studio/') ? url.pathname.slice('/static/studio/'.length) : '';
  if (req.method === 'GET' && Object.hasOwn(STATIC_TYPES, name)) {
    return send(res, 200, fs.readFileSync(path.join(STATIC, name)), { 'Content-Type': STATIC_TYPES[name] });
  }
  if (req.method === 'GET' && PDF_LIB_FILES.has(name)) return sendLibraryFile(res, name);
  return send(res, 404, 'Not found', { 'Content-Type': 'text/plain; charset=utf-8' });
}

function listen(ports) {
  fixtures = fixtures || loadFixtures();
  const [port, ...rest] = ports;
  if (port === undefined) {
    process.stderr.write('No free port.\n');
    process.exit(1);
  }
  const server = http.createServer((req, res) => {
    handle(req, res).catch(error => {
      process.stderr.write(`${req.method} ${req.url} failed: ${error.message}\n`);
      if (!res.headersSent) send(res, 500, 'Preview server error', { 'Content-Type': 'text/plain; charset=utf-8' });
    });
  });
  server.once('error', error => {
    if (error.code === 'EADDRINUSE') listen(rest);
    else throw error;
  });
  server.listen(port, HOST, () => {
    process.stdout.write(`CPT Studio dev preview (mock API, not production): http://${HOST}:${port}/ pid ${process.pid}\n`);
  });
  const stop = () => {
    server.closeAllConnections();
    server.close(() => process.exit(0));
  };
  process.once('SIGINT', stop);
  process.once('SIGTERM', stop);
}

if (require.main === module) {
  const asked = process.argv.map(arg => /^--port=(\d{2,5})$/.exec(arg)).find(Boolean);
  listen(asked ? [Number(asked[1])] : PORTS);
}

module.exports = { SYNTHETIC_DOCUMENTS, syntheticPdf, syntheticDocx, documentBytes, viewBytes, documentFor, decisionAnswer, reportAnswer, reportFile, CHANGED, FORMAT_REQUIRED, STATIC_CSP,
  viewTag, namesTag, listAnswer, searchAnswer, rowText };
