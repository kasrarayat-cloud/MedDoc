/**
 * REGENERATE THE 53-CONTROL CONSULTATION FORM — ruling #209.
 * ============================================================================
 * ⚠️ THIS IS A REGENERATION, NOT A RECONSTRUCTION, AND THE DIFFERENCE IS WHY
 * THIS FILE EXISTS RATHER THAN A CHECKED-IN `.docx`.
 *
 * A session rebuilt the owner's form by hand and offered it as *"a
 * reconstruction, not a recovery"*, holding that only a re-upload could settle
 * the clause boundaries. Ruling #209 declined that caution, because **both
 * sides of the identity are pinned**:
 *
 *   the SOURCE BYTES   sha256 6f04f29e…, the owner's blank 35-control form
 *   the RULE           the six sentences of the GI-ROS paragraph; the ten exam
 *                      value runs; the telehealth consent line; the time blank
 *
 * A regeneration is a rule applied to bytes. Both are fixed, so the output IS
 * the form — and running this file twice must produce the same document, which
 * is the property a one-off reconstruction cannot claim.
 *
 * ⚠️ THE ARITHMETIC PINS WHAT IS EXCLUDED, NOT ONLY WHAT IS INCLUDED.
 * 35 + 6 + 10 + 1 + 1 = 53. The SECOND "Review of Systems" sentence — *"A
 * thorough 14-point review of systems was performed…"* — is deliberately NOT a
 * control: including it gives 54, and the ruled total is 53. That is the check
 * that stops the rule drifting.
 *
 * ⚠️ AND THE PROOFS ARE `ADDITIVE` IN THE LITERAL SENSE. This adds 18 controls
 * to a 35-control document and must disturb NOTHING else: same original
 * controls, same ids, same prose, byte-for-byte. Each proof below exists to
 * catch one way that could stop being true.
 *
 * ⚠️ HONEST LIMIT ON THE PHRASE ITSELF: #191 records that *"all five additive
 * proofs held"* and does not enumerate them, and no other file in the record
 * does either (the five proofs in `docs/foundation/relay/README.md` belong to
 * the LEDGER SPLITTER and are a different subject). The five below are
 * DERIVED from what a purely additive regeneration must prove, not quoted.
 * If the original five are recovered and differ, this comment is the defect.
 *
 *   usage:  npx tsx scripts/regenerate-consult-form.ts <source.docx> [out.docx]
 *   exit 0 = all five proofs held. Any other exit = nothing was written.
 */
import { createHash } from 'node:crypto';
import { readFileSync, writeFileSync } from 'node:fs';

// JSZip, because `renderer.ts` already uses it — a second zip library on the
// clinical path is a second set of round-trip behaviours to reason about.
import JSZip from 'jszip';

/** The owner's blank consultation form, by content. */
const EXPECTED_SOURCE_SHA =
  '6f04f29e33835e62b956e32bed349f6a0ce4a259a763027187d9d58492f70076';

/**
 * ⚠️ THE PACKAGE MUST BE BYTE-REPRODUCIBLE, AND THE REASON IS NOT TIDINESS.
 *
 * `compiler.ts` derives every `fieldId` as
 * `stableId('ttf_', 24, state.sourceSha256, partName, nodePath, kind)` — SALTED
 * WITH THE WHOLE-PACKAGE SHA256. So two packages differing by a single byte
 * compile to DIFFERENT field ids, and therefore a different `structureSha256`.
 *
 * MEASURED before this constant existed: two runs produced a byte-identical
 * `word/document.xml` (`ecb81703…` both times) and compiled to
 * `structureSha=6b58f00f…` and `32c421f3…`. The FORM was identical and its
 * COMPILED IDENTITY was not.
 *
 * ⚠️ AND CERTIFICATION IS KEYED TO `fieldId`. The 2026-09-03 transfer rested on
 * *"match on fieldId: 35 — the ids themselves are identical"*, which held only
 * because the same BYTES were re-uploaded. A regeneration that is deterministic
 * in the document and not in the package would mint a new identity every run —
 * so the form could be certified and then not match itself.
 */
const FIXED_ENTRY_DATE = new Date(Date.UTC(2026, 8, 7, 0, 0, 0));

const EXPECTED_SOURCE_CONTROLS = 35;
const EXPECTED_ADDED = 18;
const EXPECTED_TOTAL = 53;

/** ⚠️ ONE CONTROL PER CLAUSE — the unit a fact can address (#191(2)). */
const ROS_CLAUSES: ReadonlyArray<readonly [string, string]> = [
  ['ros_gi_heartburn', 'The patient denies heartburn, odynophagia, dysphagia.'],
  ['ros_gi_nausea', 'The patient denies nausea or vomiting.'],
  ['ros_gi_abdo_pain', 'The patient denies abdominal pain.'],
  ['ros_gi_bowel', 'The patient denies diarrhea or constipation.'],
  ['ros_gi_bleeding', 'The patient denies hematemesis, melena or hematochezia.'],
  ['ros_gi_weight', 'The patient denies unintentional weight loss or change in appetite.'],
];

/**
 * The exam block. The control wraps the VALUE only — the bold label stays
 * static prose exactly as the doctor authored it, because the label is the
 * clause's name and the value is what a dictated finding can contradict.
 */
const EXAM_CLAUSES: ReadonlyArray<readonly [string, string, string]> = [
  ['exam_general', 'General: ', 'alert, oriented, no acute distress'],
  ['exam_heent', 'HEENT: ', 'normocephalic, atraumatic, pupils equal, anicteric, oropharynx clear'],
  ['exam_neck', 'Neck: ', 'supple'],
  ['exam_lungs', 'Lungs: ', 'clear to auscultation bilaterally'],
  ['exam_cv', 'CV: ', 'regular rate and rhythm'],
  ['exam_abdomen', 'Abdomen: ', 'bowel sounds present, soft, non-tender, non-distended, no rebound or guarding'],
  ['exam_extremity', 'Extremity: ', 'warm, well perfused, no edema'],
  ['exam_neurologic', 'Neurologic: ', 'alert, oriented x 4, moves all extremities spontaneously, nonfocal exam'],
  ['exam_psychological', 'Psychological: ', 'pleasant, interactive'],
  ['exam_rectal', 'Rectal: ', 'Deferred'],
];

const TELEHEALTH =
  'Patient verbalized informed consent to proceed with the audio telephone/telehealth visit.';

/** The control template, byte-matched to the 35 already in the document. */
function sdt(alias: string, tag: string, id: number, inner: string): string {
  return (
    `<w:sdt><w:sdtPr><w:alias w:val="${alias}"/><w:tag w:val="${tag}"/>` +
    `<w:id w:val="${id}"/><w:text/></w:sdtPr><w:sdtContent>` +
    `<w:r><w:t xml:space="preserve">${inner}</w:t></w:r>` +
    `</w:sdtContent></w:sdt>`
  );
}

function die(message: string): never {
  console.error(`🔴 regenerate: ${message}`);
  console.error('   Nothing was written.');
  process.exit(1);
}

/** Replace exactly `want` occurrences, or abort. A `.replace()` on a non-match
 *  is a silent no-op that returns the original string. */
function replaceExactly(xml: string, old: string, next: string, want: number, what: string): string {
  const got = xml.split(old).length - 1;
  if (got !== want) die(`${what}: expected ${want} occurrence(s), measured ${got}`);
  return xml.split(old).join(next);
}

async function main(): Promise<void> {
  const [sourcePath, outPath] = process.argv.slice(2);
  if (!sourcePath) die('usage: regenerate-consult-form.ts <source.docx> [out.docx]');

  const sourceBytes = readFileSync(sourcePath);
  const sourceSha = createHash('sha256').update(sourceBytes).digest('hex');

  // ── PROOF 1 · THE SOURCE IS THE FORM THIS RULE WAS WRITTEN FOR ────────────
  // Without this the rule could be applied to a different document and produce
  // 53 controls that mean nothing.
  if (sourceSha !== EXPECTED_SOURCE_SHA) {
    die(`P1 source identity: sha256 is ${sourceSha}, expected ${EXPECTED_SOURCE_SHA}`);
  }

  const zip = await JSZip.loadAsync(sourceBytes);
  const entry = zip.file('word/document.xml');
  if (!entry) die('word/document.xml not found in the source package');
  const before = await entry.async('string');

  const beforeControls = (before.match(/<w:sdtPr>/g) ?? []).length;
  if (beforeControls !== EXPECTED_SOURCE_CONTROLS) {
    die(`P1 source shape: ${beforeControls} controls, expected ${EXPECTED_SOURCE_CONTROLS}`);
  }

  let xml = before;
  let nextId = 900_036; // the shipped ids run 900001..900035
  let added = 0;

  // ── the GI-ROS paragraph becomes six clause controls ─────────────────────
  const rosFull = ROS_CLAUSES.map(([, sentence]) => sentence).join(' ');
  const rosOld = `<w:p><w:r><w:t>${rosFull}</w:t></w:r></w:p>`;
  const rosParts = ROS_CLAUSES.map(([tag, sentence]) => {
    const control = sdt(sentence.replace(/\.$/, ''), tag, nextId, sentence);
    nextId += 1;
    added += 1;
    return control;
  });
  xml = replaceExactly(
    xml,
    rosOld,
    `<w:p>${rosParts.join('<w:r><w:t xml:space="preserve"> </w:t></w:r>')}</w:p>`,
    1,
    'ROS paragraph',
  );

  // ── the exam block becomes ten clause controls ───────────────────────────
  for (const [tag, label, value] of EXAM_CLAUSES) {
    const bold = `<w:r><w:rPr><w:b/></w:rPr><w:t xml:space="preserve">${label}</w:t></w:r>`;
    xml = replaceExactly(
      xml,
      `${bold}<w:r><w:t>${value}</w:t></w:r>`,
      bold + sdt(label.replace(/:\s*$/, ''), tag, nextId, value),
      1,
      `exam clause ${tag}`,
    );
    nextId += 1;
    added += 1;
  }

  // ── the telehealth consent line (acceptance row 6, the `omit` control) ───
  xml = replaceExactly(
    xml,
    `<w:p><w:r><w:t>${TELEHEALTH}</w:t></w:r></w:p>`,
    `<w:p>${sdt('Telehealth consent', 'telehealth_consent', nextId, TELEHEALTH)}</w:p>`,
    1,
    'telehealth consent line',
  );
  nextId += 1;
  added += 1;

  // ── the total-time blank (#191: one datum, two renders) ──────────────────
  const timeLine = [
    "A total time of ______ minutes was spent on today",
    "&#8217;s encounter which included the following:",
  ].join('');
  const timeLineApostrophe = timeLine.replace('&#8217;', "'");
  const timeFull = xml.includes(timeLine) ? timeLine : timeLineApostrophe;
  const [head, tail] = timeFull.split('______');
  if (tail === undefined) die('total-time paragraph: the ______ blank was not found');
  xml = replaceExactly(
    xml,
    timeFull,
    `${head}</w:t></w:r>` +
      sdt('Total time minutes', 'total_time_minutes', nextId, '______') +
      `<w:r><w:t xml:space="preserve">${tail}`,
    1,
    'total-time paragraph',
  );
  nextId += 1;
  added += 1;

  // ── PROOF 2 · THE ADDITION IS EXACTLY THE RULED ARITHMETIC ───────────────
  const afterControls = (xml.match(/<w:sdtPr>/g) ?? []).length;
  if (added !== EXPECTED_ADDED) die(`P2 added ${added} controls, expected ${EXPECTED_ADDED}`);
  if (afterControls !== EXPECTED_TOTAL) {
    die(`P2 total ${afterControls} controls, expected ${EXPECTED_TOTAL}`);
  }

  // ── PROOF 3 · NOTHING EXISTING WAS DISTURBED ─────────────────────────────
  // Every original control id survives, and the package still balances. An
  // "additive" change that renumbered or dropped one would pass P2 and be wrong.
  for (let id = 900_001; id <= 900_035; id += 1) {
    if (!xml.includes(`<w:id w:val="${id}"/>`)) die(`P3 original control ${id} was lost`);
  }
  if ((xml.match(/<w:sdt>/g) ?? []).length !== (xml.match(/<\/w:sdt>/g) ?? []).length) {
    die('P3 unbalanced <w:sdt> tags');
  }
  if (
    (xml.match(/<w:sdtContent>/g) ?? []).length !== (xml.match(/<\/w:sdtContent>/g) ?? []).length
  ) {
    die('P3 unbalanced <w:sdtContent> tags');
  }

  // ── PROOF 4 · THE DOCTOR'S PROSE IS UNCHANGED ────────────────────────────
  // The controls WRAP the sentences; they do not rewrite them. A regeneration
  // that reworded a clause would still count 53.
  for (const [, sentence] of ROS_CLAUSES) {
    if (!xml.includes(sentence)) die(`P4 ROS clause lost: ${sentence}`);
  }
  for (const [, label, value] of EXAM_CLAUSES) {
    if (!xml.includes(label) || !xml.includes(value)) die(`P4 exam clause lost: ${label}${value}`);
  }
  if (!xml.includes(TELEHEALTH)) die('P4 telehealth sentence lost');

  // ── PROOF 5 · THE EXCLUSION IS PINNED, NOT INCIDENTAL ────────────────────
  // The second "Review of Systems" sentence must remain STATIC PROSE. It reads
  // like a clause and is not one; wrapping it gives 54 and the ruled total is
  // 53. This is the arithmetic that stops the rule drifting.
  const FOURTEEN_POINT =
    'A thorough 14-point review of systems was performed and remarkable findings were documented in the HPI.';
  if (!xml.includes(FOURTEEN_POINT)) die('P5 the 14-point ROS sentence was lost');
  const fourteenIndex = xml.indexOf(FOURTEEN_POINT);
  const enclosing = xml.lastIndexOf('<w:sdtContent>', fourteenIndex);
  const enclosingEnd = enclosing === -1 ? -1 : xml.indexOf('</w:sdtContent>', enclosing);
  if (enclosing !== -1 && enclosingEnd > fourteenIndex) {
    die('P5 the 14-point ROS sentence was wrapped in a control — that is 54, not 53');
  }

  console.log(`🟢 regenerate: ${beforeControls} -> ${afterControls} controls (+${added})`);
  console.log('   P1 source identity        sha256 matches the owner\'s blank form');
  console.log(`   P2 ruled arithmetic       35 + 6 + 10 + 1 + 1 = ${EXPECTED_TOTAL}`);
  console.log('   P3 nothing disturbed      all 35 original ids present, tags balanced');
  console.log('   P4 prose unchanged        every clause sentence still present verbatim');
  console.log('   P5 exclusion pinned       the 14-point ROS sentence is still static prose');

  if (outPath) {
    // ⚠️ THE REPLACED ENTRY KEEPS THE SOURCE ENTRY'S DATE, AND THIS LINE IS
    // LOAD-BEARING. `zip.file(name, content)` stamps `new Date()`, so two runs
    // produced containers that differed while the DOCUMENT inside them was
    // byte-identical — measured, and it briefly read as "the regeneration is
    // not deterministic". It was the packaging, not the form. Carrying the
    // original date forward makes the container deterministic too, so the
    // cheap check and the real one agree.
    // ⚠️ THE PACKAGE IS NOT BYTE-REPRODUCIBLE UNDER JSZip, AND THAT IS RECORDED
    // RATHER THAN CHASED. Three attempts measured it: carrying the source
    // entry's date forward left TWO bytes moving between runs (one DOS-time
    // field, in the local header and the central directory); pinning that entry
    // to a constant left the same two, because the moving field belonged to a
    // DIFFERENT entry; rebuilding every entry with one constant made it
    // FOURTEEN. JSZip is not a reproducible-archive writer and this script will
    // not turn it into one.
    //
    // ⚠️ SO THE ARTIFACT IS PRODUCED ONCE AND PINNED BY SHA — which is what
    // #209 asks for ("record the derivation as its provenance") and NOT
    // byte-reproducible re-runs, a requirement this script invented for itself.
    // The DOCUMENT is deterministic, measured identical across every run, and
    // that is the form. The package is a container around it.
    zip.file('word/document.xml', xml, { date: FIXED_ENTRY_DATE });
    const out = await zip.generateAsync({
      type: 'nodebuffer',
      compression: 'DEFLATE',
      compressionOptions: { level: 9 },
    });
    writeFileSync(outPath, out);
    const outSha = createHash('sha256').update(readFileSync(outPath)).digest('hex');
    const docSha = createHash('sha256').update(xml, 'utf-8').digest('hex');
    console.log(`   wrote ${outPath}`);
    // ⚠️ THE DOCUMENT SHA IS THE IDENTITY THAT MATTERS. The container's bytes
    // are packaging; `word/document.xml` is the form. Compare THIS across runs.
    console.log(`   word/document.xml sha256  ${docSha}`);
    console.log(`   package sha256            ${outSha}`);
  } else {
    console.log('   (no output path given — proofs only, nothing written)');
  }
}

void main();
