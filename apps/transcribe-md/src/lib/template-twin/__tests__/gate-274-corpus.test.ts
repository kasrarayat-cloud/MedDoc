// ============================================================================
// RULING #274 · THE CORPUS — BOTH REAL DOCUMENTS, FIVE TRANSFORMATIONS EACH.
// ----------------------------------------------------------------------------
// ⚠️ THIS FILE EXISTS BECAUSE THE SAME MISTAKE WAS MADE THREE TIMES: a property
// measured on ONE document and stated as universal.
//
//   ROUND 1 · the key was positional (`path` + `ordinal`). Inserting one control
//     into `WM IOV Template.docx` mis-paired 3 of 3 certified dispositions.
//   ROUND 2 · the replacement claimed "a collision never mis-transfers". False:
//     two controls sharing a key both claimed one certified row, and a LEFT leg
//     finding was certified to print the RIGHT leg's concept.
//   ROUND 3 · `sdtId` was called STABLE on the strength of `28/80, 28 distinct`
//     — measured on WM IOV, whose ids are Word-generated randoms. The OWNER'S
//     form assigns them with `nextId += 1` per control IN DOCUMENT ORDER, so a
//     single dropped clause renumbered everything and walked the exam narrative
//     one organ system sideways, 15 rows, all `certified`.
//
//     A CLAIM MEASURED ON ONE DOCUMENT IS NOT A CLAIM.
//
// So the corpus is BOTH real documents, and every transformation asserts ZERO
// mis-pairs — not a transfer count, which is the number that stayed right while
// the pairing was wrong in all three rounds.
//
// ── ON THE SECOND DOCUMENT'S PROVENANCE, STATED PLAINLY ─────────────────────
// The owner's blank 53-control source is NOT in this repository; only production
// holds those bytes, and `regenerate-consult-form.ts` refuses any others by sha.
// So its arm is built from the generator's OWN exported vocabulary — `sdt()`,
// `ROS_CLAUSES`, `EXAM_CLAUSES`, `FIRST_ADDED_SDT_ID` — imported, never retyped.
// That is what makes it evidence: the id progression under test is the shipped
// one, and a fixture free to get `nextId += 1` wrong could never have caught the
// defect that motivated this file.
// ============================================================================
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { deflateRawSync, inflateRawSync } from 'node:zlib';

import { describe, expect, it } from 'vitest';

import {
  EXAM_CLAUSES,
  FIRST_ADDED_SDT_ID,
  ROS_CLAUSES,
  sdt,
} from '../../../../scripts/regenerate-consult-form';
import { compileTemplateDocx } from '@/lib/note-template-docx';
import { planTransfer } from '../ingest-plan';
import type { SemanticMapping, TemplateDocIR } from '../ir';

const WM_IOV = resolve(__dirname, '../../../../../../WM IOV Template.docx');

// ── a minimal, dependency-free zip reader/writer for the .docx package ───────
function readZip(bytes: Buffer): Map<string, Buffer> {
  const files = new Map<string, Buffer>();
  let end = bytes.length - 22;
  while (end >= 0 && bytes.readUInt32LE(end) !== 0x06054b50) end -= 1;
  const count = bytes.readUInt16LE(end + 10);
  let p = bytes.readUInt32LE(end + 16);
  for (let i = 0; i < count; i += 1) {
    const nameLen = bytes.readUInt16LE(p + 28);
    const extraLen = bytes.readUInt16LE(p + 30);
    const commentLen = bytes.readUInt16LE(p + 32);
    const local = bytes.readUInt32LE(p + 42);
    const name = bytes.subarray(p + 46, p + 46 + nameLen).toString('utf8');
    const method = bytes.readUInt16LE(local + 8);
    const csize = bytes.readUInt32LE(p + 20);
    const lNameLen = bytes.readUInt16LE(local + 26);
    const lExtraLen = bytes.readUInt16LE(local + 28);
    const dataAt = local + 30 + lNameLen + lExtraLen;
    const raw = bytes.subarray(dataAt, dataAt + csize);
    files.set(name, method === 8 ? inflateRawSync(raw) : Buffer.from(raw));
    p += 46 + nameLen + extraLen + commentLen;
  }
  return files;
}

function writeZip(files: Map<string, Buffer>): Buffer {
  const locals: Buffer[] = [];
  const centrals: Buffer[] = [];
  let offset = 0;
  const crcTable = (() => {
    const t = new Int32Array(256);
    for (let n = 0; n < 256; n += 1) {
      let c = n;
      for (let k = 0; k < 8; k += 1) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
      t[n] = c;
    }
    return t;
  })();
  const crc32 = (buf: Buffer): number => {
    let c = -1;
    for (const b of buf) c = crcTable[(c ^ b) & 0xff]! ^ (c >>> 8);
    return (c ^ -1) >>> 0;
  };
  for (const [name, content] of files) {
    const nameBuf = Buffer.from(name, 'utf8');
    const deflated = deflateRawSync(content);
    const crc = crc32(content);
    const local = Buffer.alloc(30);
    local.writeUInt32LE(0x04034b50, 0);
    local.writeUInt16LE(20, 4);
    local.writeUInt16LE(8, 8);
    local.writeUInt32LE(crc, 14);
    local.writeUInt32LE(deflated.length, 18);
    local.writeUInt32LE(content.length, 22);
    local.writeUInt16LE(nameBuf.length, 26);
    locals.push(local, nameBuf, deflated);
    const central = Buffer.alloc(46);
    central.writeUInt32LE(0x02014b50, 0);
    central.writeUInt16LE(20, 4);
    central.writeUInt16LE(20, 6);
    central.writeUInt16LE(8, 10);
    central.writeUInt32LE(crc, 16);
    central.writeUInt32LE(deflated.length, 20);
    central.writeUInt32LE(content.length, 24);
    central.writeUInt16LE(nameBuf.length, 28);
    central.writeUInt32LE(offset, 42);
    centrals.push(central, nameBuf);
    offset += 30 + nameBuf.length + deflated.length;
  }
  const centralSize = centrals.reduce((n, b) => n + b.length, 0);
  const end = Buffer.alloc(22);
  end.writeUInt32LE(0x06054b50, 0);
  end.writeUInt16LE(files.size, 8);
  end.writeUInt16LE(files.size, 10);
  end.writeUInt32LE(centralSize, 12);
  end.writeUInt32LE(offset, 16);
  return Buffer.concat([...locals, ...centrals, end]);
}

function editDocumentXml(bytes: Buffer, edit: (xml: string) => string): Buffer {
  const files = readZip(bytes);
  const xml = files.get('word/document.xml')!.toString('utf8');
  const next = edit(xml);
  expect(next, 'the transformation was a NO-OP — the arm would prove nothing').not.toBe(xml);
  files.set('word/document.xml', Buffer.from(next, 'utf8'));
  return writeZip(files);
}

/**
 * The marker a control is certified to, and it is the control's STABLE
 * identity — its semantic tag where it has one, its label otherwise.
 *
 * ⚠️ THE FIRST VERSION USED THE LABEL ALONE, AND THE MEASURE WAS WRONG RATHER
 * THAN THE CODE. On the rename arm it reported:
 *
 *     "Lungs:  (reworded)  <-  CONCEPT::Lungs"
 *
 * as a mis-pair. That is the tag path WORKING: the doctor re-worded the
 * question, the semantic tag still names the control, and its certified
 * disposition correctly followed. A measure keyed on the label calls every
 * legitimate rename a defect — which would have pushed me to "fix" the one
 * behaviour the tag path exists to provide.
 *
 *   A CONTROL'S CERTIFICATION FOLLOWS ITS IDENTITY, SO THE MEASURE MUST TOO.
 *
 * A control WITHOUT a tag falls back to its label, which is correct for exactly
 * the same reason: with no tag, the label IS part of its identity, so a rename
 * genuinely makes it a control the transfer can no longer recognise — and it
 * must re-propose rather than inherit.
 */
function stableMarker(f: TemplateDocIR['fields'][number]): string {
  return f.rendererBinding.tag ?? f.originalLabel;
}

/** Certify every field to a concept naming ITSELF, so a mis-pair is visible. */
function certifyAll(ir: TemplateDocIR): Map<string, SemanticMapping> {
  return new Map(
    ir.fields.map((f) => [
      f.fieldId,
      {
        fieldId: f.fieldId,
        clinicalConcept: `CONCEPT::${stableMarker(f)}`,
        status: 'certified',
      } as unknown as SemanticMapping,
    ]),
  );
}

/**
 * THE MEASUREMENT, and it is deliberately NOT a transfer count.
 *
 * ⚠️ THE COUNT WAS RIGHT IN ALL THREE ROUNDS WHILE THE PAIRING WAS WRONG. Round
 * three transferred 52 of 52 with fifteen concepts on the wrong controls, and
 * `expectTransferCount` passed. Only "did this control get ITS OWN concept"
 * distinguishes them.
 */
function misPairs(source: TemplateDocIR, target: TemplateDocIR): string[] {
  const certified = certifyAll(source);
  const plan = planTransfer({ target, sourceIr: source, certifiedByFieldId: certified });
  const markerOf = new Map(target.fields.map((f) => [f.fieldId, stableMarker(f)]));
  const labelOf = new Map(target.fields.map((f) => [f.fieldId, f.originalLabel]));
  return plan.transferred
    .filter((t) => t.mapping.clinicalConcept !== `CONCEPT::${markerOf.get(t.fieldId)}`)
    .map((t) => `${labelOf.get(t.fieldId)} <- ${t.mapping.clinicalConcept}`);
}

function transferCount(source: TemplateDocIR, target: TemplateDocIR): number {
  return planTransfer({ target, sourceIr: source, certifiedByFieldId: certifyAll(source) })
    .transferred.length;
}

const ARM_BUDGET_MS = 60_000;

// ══════════════════════════════════════════════════════════════════════════════
// DOCUMENT 1 · `WM IOV Template.docx` — REAL BYTES, 80 controls, random sdtIds
// ══════════════════════════════════════════════════════════════════════════════
describe('#274 CORPUS · WM IOV Template.docx (real bytes)', () => {
  const base = readFileSync(WM_IOV);
  const baseIr = compileTemplateDocx(base);

  it('POSITIVE CONTROL — the document compiled and carries controls to mis-pair', () => {
    // Without this, "zero mis-pairs" is also what an empty document returns.
    expect(baseIr.fields.length).toBeGreaterThan(50);
  });

  it('1 · IDENTICAL bytes — everything transfers, nothing mis-paired', () => {
    expect(misPairs(baseIr, compileTemplateDocx(base))).toEqual([]);
    expect(transferCount(baseIr, compileTemplateDocx(base))).toBe(baseIr.fields.length);
  }, ARM_BUDGET_MS);

  it('2 · one control INSERTED at the top', () => {
    const mutated = editDocumentXml(base, (xml) =>
      xml.replace(
        /(<w:body[^>]*>)/,
        `$1<w:p>${sdt('INSERTED PROBE', 'inserted_probe', 990001, 'x')}</w:p>`,
      ),
    );
    const ir = compileTemplateDocx(mutated);
    expect(ir.fields.length).toBe(baseIr.fields.length + 1);
    expect(misPairs(baseIr, ir), 'an insert walked a concept sideways').toEqual([]);
  }, ARM_BUDGET_MS);

  it('3 · one control DROPPED — the renumber case', () => {
    const mutated = editDocumentXml(base, (xml) => xml.replace(/<w:sdt>[\s\S]*?<\/w:sdt>/, ''));
    const ir = compileTemplateDocx(mutated);
    expect(ir.fields.length).toBeLessThan(baseIr.fields.length);
    expect(misPairs(baseIr, ir), 'a drop walked a concept sideways').toEqual([]);
  }, ARM_BUDGET_MS);

  it('4 · a COPY-PASTED control — same id, same label, twice', () => {
    const mutated = editDocumentXml(base, (xml) => {
      const m = /<w:sdt>[\s\S]*?<\/w:sdt>/.exec(xml)!;
      return xml.replace(m[0], `${m[0]}${m[0]}`);
    });
    const ir = compileTemplateDocx(mutated);
    expect(misPairs(baseIr, ir), 'a copy-paste claimed a certified disposition').toEqual([]);
  }, ARM_BUDGET_MS);

  it('5 · a LABEL RENAME — the doctor re-words a question', () => {
    const mutated = editDocumentXml(base, (xml) =>
      xml.replace(/<w:alias w:val="([^"]+)"\/>/, '<w:alias w:val="$1 (reworded)"/>'),
    );
    expect(misPairs(baseIr, compileTemplateDocx(mutated)), 'a rename mis-paired').toEqual([]);
  }, ARM_BUDGET_MS);
});

// ══════════════════════════════════════════════════════════════════════════════
// DOCUMENT 2 · the OWNER'S 53-control form — POSITIONAL sdtIds, semantic tags
// ══════════════════════════════════════════════════════════════════════════════
describe("#274 CORPUS · the owner's consult form (generator's own vocabulary)", () => {
  /**
   * The 18 controls the rule ADDS, at the ids and tags it assigns them.
   *
   * ⚠️ `sdt`, `ROS_CLAUSES`, `EXAM_CLAUSES` and `FIRST_ADDED_SDT_ID` are
   * IMPORTED. Retyping them would test the copy, and `nextId += 1` per control
   * IN DOCUMENT ORDER is the exact detail that made `sdtId` positional.
   */
  function buildAdded(dropRosIndex: number | null, renameTag: string | null): string {
    let id = FIRST_ADDED_SDT_ID;
    const parts: string[] = [];
    ROS_CLAUSES.forEach(([tag, sentence], i) => {
      if (i === dropRosIndex) return;
      const alias = renameTag === tag ? `${sentence} (reworded)` : sentence;
      parts.push(`<w:p>${sdt(alias.replace(/\.$/, ''), tag, id, sentence)}</w:p>`);
      id += 1;
    });
    EXAM_CLAUSES.forEach(([tag, label, value]) => {
      const alias = renameTag === tag ? `${label} (reworded)` : label;
      parts.push(`<w:p>${sdt(alias.replace(/:\s*$/, ''), tag, id, value)}</w:p>`);
      id += 1;
    });
    parts.push(`<w:p>${sdt('Telehealth consent', 'telehealth_consent', id, 'consent')}</w:p>`);
    id += 1;
    parts.push(`<w:p>${sdt('Total time minutes', 'total_time_minutes', id, '______')}</w:p>`);
    return parts.join('');
  }

  const base = readFileSync(WM_IOV);
  const pack = (added: string): TemplateDocIR =>
    compileTemplateDocx(
      editDocumentXml(base, (xml) => xml.replace(/(<w:body[^>]*>)/, `$1${added}`)),
    );

  const sourceIr = pack(buildAdded(null, null));

  it('POSITIVE CONTROL — the ids really are DENSE SEQUENTIAL, and tags are present', () => {
    // ⚠️ If this ever fails, the corpus has stopped reproducing the property it
    // was built for and every arm below is measuring something else.
    // ⚠️ SELECTED BY TAG, NOT BY AN ID RANGE. The first version filtered on
    // `Number(sdtId) >= FIRST_ADDED_SDT_ID`, which also swept up WM IOV's
    // Word-generated randoms (2004953067 > 900036) and made the density check
    // measure a set it was never about.
    const addedTags = new Set<string>([
      ...ROS_CLAUSES.map(([t]) => t),
      ...EXAM_CLAUSES.map(([t]) => t),
      'telehealth_consent',
      'total_time_minutes',
    ]);
    const added = sourceIr.fields.filter(
      (f) => f.rendererBinding.tag !== null && addedTags.has(f.rendererBinding.tag),
    );
    expect(added.length).toBeGreaterThanOrEqual(18);
    const ids = added.map((f) => Number(f.rendererBinding.sdtId)).sort((a, b) => a - b);
    expect(ids[ids.length - 1]! - ids[0]!, 'the ids are not dense — not the shipped shape').toBe(
      ids.length - 1,
    );
    expect(added.every((f) => f.rendererBinding.tag), 'a rule-added control lost its tag').toBe(true);
  }, ARM_BUDGET_MS);

  it('1 · IDENTICAL bytes', () => {
    expect(misPairs(sourceIr, pack(buildAdded(null, null)))).toEqual([]);
  }, ARM_BUDGET_MS);

  it('⚠️ 3 · one ROS clause DROPPED — EVERY downstream sdtId shifts by one', () => {
    // THE ROUND-THREE DEFECT. Before the label pairing and the tag path, this
    // transferred 52 of 52 with FIFTEEN concepts on the wrong controls, every
    // one `certified`, and all three bijection guards satisfied.
    const target = pack(buildAdded(2, null));
    const wrong = misPairs(sourceIr, target);
    expect(wrong, 'a renumber walked the exam narrative sideways').toEqual([]);
  }, ARM_BUDGET_MS);

  it('⚠️ 5 · a LABEL RENAME — the TAG must still carry it', () => {
    // The rename defeats the sdtId+label fallback by design; only the semantic
    // tag survives, which is why the tag path exists.
    const target = pack(buildAdded(null, 'exam_lungs'));
    expect(misPairs(sourceIr, target), 'a rename mis-paired').toEqual([]);
    const renamed = target.fields.find((f) => f.rendererBinding.tag === 'exam_lungs')!;
    const plan = planTransfer({
      target,
      sourceIr,
      certifiedByFieldId: certifyAll(sourceIr),
    });
    const carried = plan.transferred.find((t) => t.fieldId === renamed.fieldId);
    expect(carried, 'the renamed control lost its certification — the tag path is dead').toBeDefined();
  }, ARM_BUDGET_MS);

  it('⚠️ 3+5 · a DROP **and** a RENAME together — ids shift AND the label moves', () => {
    // Neither fallback can carry this: the id renumbered and the label changed.
    // Only the tag names the control, and this is the arm that proves the
    // precedence order is doing real work rather than being decoration.
    const target = pack(buildAdded(2, 'exam_lungs'));
    expect(misPairs(sourceIr, target), 'drop + rename mis-paired').toEqual([]);
  }, ARM_BUDGET_MS);
});
