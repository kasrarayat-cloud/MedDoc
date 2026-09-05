#!/usr/bin/env node
// ============================================================================
// build-icd10cm.mjs — generate the ICD-10-CM FY2026 billable + header sets
// ----------------------------------------------------------------------------
// Reads the OFFICIAL CMS release and emits two generated TypeScript data
// modules plus a provenance record. Deterministic: same input zip -> byte
// identical output, every time.
//
// ⚠️ THIS SCRIPT PROVES ITS OWN APPLICATION. AGENTS.md, "A scripted edit PROVES
// ITS OWN APPLICATION": a `.replace()` on a non-match is a silent no-op that
// returns the original string and then reports success. Every quantity below is
// asserted against a value fixed BEFORE the file was read, and the emitted
// files are re-read and re-counted at the end. A mismatch ABORTS; it never
// warns and continues.
//
// Usage:
//   node scripts/data/build-icd10cm.mjs --zip <path/to/2026-code-descriptions-tabular-order.zip>
//   node scripts/data/build-icd10cm.mjs --zip <path> --check   (verify only, write nothing)
// ============================================================================

import { createHash } from 'node:crypto';
import { execFileSync } from 'node:child_process';
import { readFileSync, writeFileSync, mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));
const REPO = join(HERE, '..', '..');
const OUT_DIR = join(REPO, 'packages', 'ai', 'src', 'data');

// ── PINNED PROVENANCE ───────────────────────────────────────────────────────
// Retrieved 2026-09-04 from the URL the official CMS page links (verified: the
// page at cms.gov/medicare/coding-billing/icd-10-codes lists this exact path
// under "FY 2026 ... 2026 Code Descriptions in Tabular Order (ZIP)").
const SOURCE = {
  url: 'https://www.cms.gov/files/zip/2026-code-descriptions-tabular-order.zip',
  page: 'https://www.cms.gov/medicare/coding-billing/icd-10-codes',
  retrieved: '2026-09-04',
  zipSha256: '55a9124a27ca78a4a5c41e1101eda064ec2e08d105ff9e78d1fbd1a83298ef11',
  zipBytes: 2204985,
  codesFile: 'icd10cm_codes_2026.txt',
  orderFile: 'icd10cm_order_2026.txt',
  codesSha256: 'a7e2a77e4627ed55c8afe2b8a7ae22efcbab6b6b162d96cf145213772c1246ba',
  orderSha256: '6dc95c9c7e96c734806e1682f4bf9df76251d60e99199bba0d375ba3dd11026b',
  effectiveFrom: '2025-10-01',
  effectiveTo: '2026-09-30',
};

// ⚠️ EXPECTED QUANTITIES, FIXED BEFORE THE FILE IS READ.
// These are not "what we measured"; they are CMS's OWN published counts, taken
// verbatim from icd10cm_order_addenda_2026.txt in the April 1 2026 release:
//     "23467 headers in icd10cm_order_2026.txt"
//     "74719 codes in icd10cm_order_2026.txt"
// The point of writing them down here is that the comparison has exactly ONE
// correct answer, fixed before the evidence existed. Same discipline as the
// §2.5 deploy declaration.
const EXPECT = { billable: 74719, headers: 23467, total: 98186 };

const argv = process.argv.slice(2);
const zipPath = argv[argv.indexOf('--zip') + 1];
const checkOnly = argv.includes('--check');
if (!zipPath || argv.indexOf('--zip') === -1) {
  console.error('usage: build-icd10cm.mjs --zip <path-to-cms-zip> [--check]');
  process.exit(2);
}

const sha = (buf) => createHash('sha256').update(buf).digest('hex');
const die = (msg) => { console.error(`\nABORT: ${msg}\n`); process.exit(1); };
const ok = (label, actual, expected) => {
  const good = actual === expected;
  console.log(`  ${good ? 'ok  ' : 'FAIL'} ${label}: ${actual}${good ? '' : ` (expected ${expected})`}`);
  if (!good) die(`${label} mismatch — expected ${expected}, measured ${actual}`);
};

console.log('ICD-10-CM FY2026 ingestion\n');
console.log('[1/7] verifying the source archive against pinned provenance');
const zipBuf = readFileSync(zipPath);
ok('zip bytes', zipBuf.length, SOURCE.zipBytes);
ok('zip sha256', sha(zipBuf), SOURCE.zipSha256);

// ── extract ────────────────────────────────────────────────────────────────
const tmp = mkdtempSync(join(tmpdir(), 'icd10cm-'));
let codesRaw, orderRaw;
try {
  execFileSync('unzip', ['-o', '-q', '-j', zipPath, '-d', tmp], { stdio: 'pipe' });
  codesRaw = readFileSync(join(tmp, SOURCE.codesFile));
  orderRaw = readFileSync(join(tmp, SOURCE.orderFile));
} finally {
  rmSync(tmp, { recursive: true, force: true });
}
console.log('[2/7] verifying the extracted members');
ok('codes file sha256', sha(codesRaw), SOURCE.codesSha256);
ok('order file sha256', sha(orderRaw), SOURCE.orderSha256);

// ── parse the ORDER file by FIXED-WIDTH POSITION ───────────────────────────
// ⚠️ NOT by splitting on whitespace: the description columns contain spaces, so
// a whitespace split silently mis-columns every line with a multi-word title —
// which is all of them. Layout per CMS's icd10OrderFiles.pdf:
//   [0..5) order number | [6..13) code | [14] 0=header 1=valid-for-submission
//   [16..76) short description | [77..] long description
console.log('[3/7] parsing the order file');
const orderText = orderRaw.toString('utf8');
const billable = [];
const headers = [];
let lineNo = 0;
for (const rawLine of orderText.split('\n')) {
  const line = rawLine.replace(/\r$/, '');
  lineNo++;
  if (line.trim() === '') continue;
  const code = line.slice(6, 13).trim();
  const flag = line[14];
  // ⚠️ NEVER NORMALISE AN IMPOSSIBLE VALUE. A third flag value means the layout
  // assumption is wrong, and silently bucketing it would produce a plausible
  // count from a misparse. Abort loudly instead.
  if (flag !== '0' && flag !== '1') die(`order file line ${lineNo}: flag is ${JSON.stringify(flag)}, expected "0" or "1"`);
  if (!/^[0-9A-Z]{3,7}$/.test(code)) die(`order file line ${lineNo}: code ${JSON.stringify(code)} is not 3-7 chars of [0-9A-Z]`);
  (flag === '1' ? billable : headers).push(code);
}
ok('billable (flag=1)', billable.length, EXPECT.billable);
ok('headers  (flag=0)', headers.length, EXPECT.headers);
ok('total', billable.length + headers.length, EXPECT.total);
ok('billable are unique', new Set(billable).size, EXPECT.billable);
ok('headers are unique', new Set(headers).size, EXPECT.headers);
const headerSet = new Set(headers);
const billableSet = new Set(billable);
const overlap = billable.filter((c) => headerSet.has(c));
ok('billable ∩ headers is empty', overlap.length, 0);

// ── SECOND, INDEPENDENT ROUTE ──────────────────────────────────────────────
// AGENTS.md, "CONFIRM A FIGURE YOU WILL BUILD ON BY A SECOND, INDEPENDENT
// ROUTE": re-derive by a route that does not share the first one's failure
// mode, then check the two RECONCILE. `icd10cm_codes_2026.txt` is a separate
// CMS artifact with a different layout (code, then description, whitespace
// separated) and it contains the valid-for-submission set and nothing else. If
// the fixed-width column offsets above were wrong, this set would disagree.
//
// ⚠️ HONEST LIMIT, FOUND BY THE ADVERSARIAL PASS: this route corroborates the
// BILLABLE half ONLY. CMS publishes no second file listing the headers, so the
// 23,467 header codes are checked for count, uniqueness and disjointness from
// billable — and their IDENTITY is corroborated by nothing here. A corrupt
// order file that mutated a header code while preserving those three
// properties would emit a wrong header set and every gate in this script would
// still print ok. The payload digest pins header identity once a GOOD run has
// happened; it cannot validate a FIRST run. Said plainly so the FY2027
// re-ingest does not read this block as covering both halves.
console.log('[4/7] cross-checking against the independent codes file');
const codesSet = new Set();
let cLine = 0;
for (const rawLine of codesRaw.toString('utf8').split('\n')) {
  const line = rawLine.replace(/\r$/, '');
  cLine++;
  if (line.trim() === '') continue;
  const code = line.split(/\s/, 1)[0];
  if (!/^[0-9A-Z]{3,7}$/.test(code)) die(`codes file line ${cLine}: code ${JSON.stringify(code)} malformed`);
  codesSet.add(code);
}
ok('codes file size', codesSet.size, EXPECT.billable);
const onlyInOrder = billable.filter((c) => !codesSet.has(c));
const onlyInCodes = [...codesSet].filter((c) => !billableSet.has(c));
ok('in order-file but not codes-file', onlyInOrder.length, 0);
ok('in codes-file but not order-file', onlyInCodes.length, 0);

// ── dotting ────────────────────────────────────────────────────────────────
// CMS stores codes UNDOTTED (A000). This codebase has always stored them
// DOTTED (A00.0) and `ICD10_ALLOWLIST.has('K63.5')` is a live contract —
// icd10-allowlist-gastroenterology.test.ts calls it that way. So dot on
// ingest, and prove the transform is lossless before relying on it.
const dot = (c) => (c.length <= 3 ? c : `${c.slice(0, 3)}.${c.slice(3)}`);
const undot = (c) => c.replace('.', '');
console.log('[5/7] proving the dot transform is lossless and collision-free');
let roundTripFails = 0;
for (const c of [...billable, ...headers]) if (undot(dot(c)) !== c) roundTripFails++;
ok('undot(dot(c)) === c for every code', roundTripFails, 0);
const billableDotted = billable.map(dot).sort();
const headersDotted = headers.map(dot).sort();
ok('dotting introduces no collisions (billable)', new Set(billableDotted).size, EXPECT.billable);
ok('dotting introduces no collisions (headers)', new Set(headersDotted).size, EXPECT.headers);
// ⚠️ The emitted payload is a template literal. A backtick, a backslash or a
// `${` in the data would break out of it. The charset regex above already
// forbids all three — this asserts the property AT THE POINT IT MATTERS
// rather than trusting the earlier check to still be the one that applies.
const unsafe = [...billableDotted, ...headersDotted].filter((c) => !/^[0-9A-Z.]+$/.test(c));
ok('no template-literal-unsafe characters', unsafe.length, 0);

// ⚠️ DIGESTS OF THE EMITTED PAYLOAD, NOT OF THE SOURCE ARCHIVE. The source
// hashes above prove we read the right CMS file; they say NOTHING about what
// was written. A hand-edit, a bad merge or a partial write that preserves the
// LINE COUNT is invisible to every count assertion — the adversarial pass
// demonstrated exactly that by swapping one code for a fabricated one and
// watching all 212 tests stay green. These two digests are the artifact that
// binds the shipped 98,186 members to their content, and the gate test asserts
// them, so CI re-derives them on every run without needing the network.
const billablePayload = billableDotted.join('\n');
const headersPayload = headersDotted.join('\n');

// ── emit ───────────────────────────────────────────────────────────────────
const banner = (what, count, constName) => `// ============================================================================
// ${what} — ICD-10-CM FY2026 (GENERATED — DO NOT EDIT BY HAND)
// ----------------------------------------------------------------------------
// Generated by scripts/data/build-icd10cm.mjs from the official CMS release.
// Edit the generator, re-run it, and commit both — never this file alone.
//
//   source      ${SOURCE.url}
//   listed on   ${SOURCE.page}
//   retrieved   ${SOURCE.retrieved}
//   zip sha256  ${SOURCE.zipSha256}
//   effective   ${SOURCE.effectiveFrom} .. ${SOURCE.effectiveTo}
//   count       ${count}
//
// Codes are stored DOTTED and UPPERCASE (CMS ships them undotted; this
// codebase has always stored them dotted and \`ICD10_ALLOWLIST.has('K63.5')\`
// is a live contract). One code per line; the reader splits on "\\n". Storing
// them line-per-line rather than as an array literal keeps the file greppable
// (\`grep -c '^M54.51$'\`), diffable, and countable with \`wc -l\`.
// ============================================================================

export const ${constName} = \``;

console.log('[6/7] emitting generated modules');
const billableFile = join(OUT_DIR, 'icd10cm-fy2026-billable.generated.ts');
const headersFile = join(OUT_DIR, 'icd10cm-fy2026-headers.generated.ts');
const provFile = join(OUT_DIR, 'icd10cm-fy2026-provenance.json');

const billableOut =
  banner('BILLABLE / valid-for-submission codes', EXPECT.billable, 'ICD10CM_FY2026_BILLABLE_RAW') +
  billablePayload + '`;\n';
const headersOut =
  banner('HEADER codes — NOT valid for submission', EXPECT.headers, 'ICD10CM_FY2026_HEADERS_RAW') +
  headersPayload + '`;\n';
const provOut = JSON.stringify({
  ...SOURCE,
  counts: { ...EXPECT },
  payloadSha256: {
    billable: sha(Buffer.from(billablePayload, 'utf8')),
    headers: sha(Buffer.from(headersPayload, 'utf8')),
  },
  note: 'Counts are CMS\'s own, quoted verbatim from icd10cm_order_addenda_2026.txt. payloadSha256 digests the EMITTED code lists, which is what binds the committed data to this source.',
}, null, 2) + '\n';

if (checkOnly) {
  // ⚠️ --check USED TO SKIP THE ENTIRE RE-READ, so the mode named "verify only"
  // never opened the committed files at all. It now verifies the artifact ON
  // DISK against what this run derived from CMS — which is the only thing the
  // name ever promised.
  console.log('  --check: verifying the COMMITTED artifact against this run');
  const cmp = (path, constName, expected, label) => {
    const text = readFileSync(path, 'utf8');
    const m = text.match(new RegExp('export const ' + constName + ' = `([\\s\\S]*)`;\\n$'));
    if (!m) die(path + ': could not parse the committed template literal');
    ok(label + ' committed count', m[1].split('\n').length, expected.split('\n').length);
    ok(label + ' committed digest', sha(Buffer.from(m[1], 'utf8')), sha(Buffer.from(expected, 'utf8')));
  };
  cmp(billableFile, 'ICD10CM_FY2026_BILLABLE_RAW', billablePayload, 'billable');
  cmp(headersFile, 'ICD10CM_FY2026_HEADERS_RAW', headersPayload, 'headers');
  const committedProv = JSON.parse(readFileSync(provFile, 'utf8'));
  ok('committed provenance billable digest', committedProv.payloadSha256 && committedProv.payloadSha256.billable, sha(Buffer.from(billablePayload, 'utf8')));
  ok('committed provenance headers digest', committedProv.payloadSha256 && committedProv.payloadSha256.headers, sha(Buffer.from(headersPayload, 'utf8')));
} else {
  writeFileSync(billableFile, billableOut);
  writeFileSync(headersFile, headersOut);
  writeFileSync(provFile, provOut);
  console.log(`  wrote ${billableFile}`);
  console.log(`  wrote ${headersFile}`);
  console.log(`  wrote ${provFile}`);
}

// ── PROVE THE WRITE LANDED ─────────────────────────────────────────────────
// AGENTS.md: "assert the number it ACTUALLY changed". Re-READ from disk — not
// from the in-memory string that was just written — and re-derive the counts
// through the same `split('\n')` the runtime module will use. A write that
// silently truncated, or an OUT_DIR that does not exist, is caught here rather
// than by a test three steps later.
if (!checkOnly) {
  console.log('[7/7] re-reading the emitted files and re-counting');
  const reread = (path, constName) => {
    const text = readFileSync(path, 'utf8');
    const m = text.match(new RegExp(`export const ${constName} = \`([\\s\\S]*)\`;\\n$`));
    if (!m) die(`${path}: could not re-parse the emitted template literal`);
    return m[1].split('\n');
  };
  const rb = reread(billableFile, 'ICD10CM_FY2026_BILLABLE_RAW');
  const rh = reread(headersFile, 'ICD10CM_FY2026_HEADERS_RAW');
  ok('re-read billable', rb.length, EXPECT.billable);
  ok('re-read headers', rh.length, EXPECT.headers);
  ok('re-read billable has no empty member', rb.filter((x) => x === '').length, 0);
  ok('re-read headers has no empty member', rh.filter((x) => x === '').length, 0);
  ok('re-read billable matches in-memory', rb.join('\n') === billablePayload ? 1 : 0, 1);
  ok('re-read headers matches in-memory', rh.join('\n') === headersPayload ? 1 : 0, 1);
  // Digest the bytes that came BACK OFF DISK. The checks above compare to the
  // in-memory string; this one recomputes what the gate test will independently
  // assert, so a divergence surfaces here rather than in CI.
  const wroteProv = JSON.parse(readFileSync(provFile, 'utf8'));
  ok('re-read billable digest', sha(Buffer.from(rb.join('\n'), 'utf8')), wroteProv.payloadSha256.billable);
  ok('re-read headers digest', sha(Buffer.from(rh.join('\n'), 'utf8')), wroteProv.payloadSha256.headers);
} else {
  console.log('[7/7] skipped (--check)');
}

console.log('\nDONE. All quantities reconciled against CMS\'s own published counts.');
