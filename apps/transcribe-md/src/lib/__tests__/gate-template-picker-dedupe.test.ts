// ============================================================================
// RE-UPLOAD DISPLACEMENT (owner finding) — the picker offers ONE form per name.
// ----------------------------------------------------------------------------
// A re-upload mints a NEW lineage (new id, SAME name) and certifies it, so the
// picker accumulated indistinguishable certified duplicates. `displacedByReupload`
// returns the ids to drop. Each arm plants the OPPOSITE case so a vacuous pass
// cannot hide a regression.
// ============================================================================
import { describe, expect, it } from 'vitest';

import { displacedByReupload, type PickerTemplateRow } from '../template-picker-dedupe';

const at = (iso: string) => new Date(iso);

/** A certified row by default; `certified: false` for the draft/non-certified case.
 *  Same doctor + null encounterType by default — the owner-practice shape, where
 *  same-name certified rows ARE re-uploads and SHOULD collapse. */
function row(over: Partial<PickerTemplateRow> & Pick<PickerTemplateRow, 'id'>): PickerTemplateRow {
  return {
    doctorId: 'doc-owner',
    encounterType: null,
    name: 'Gastroenterology Consultation',
    status: 'inactive',
    createdAt: at('2026-09-01T00:00:00.000Z'),
    certified: true,
    ...over,
  };
}

describe('displacedByReupload', () => {
  it('a single certified row displaces NOTHING (the common case)', () => {
    const d = displacedByReupload([row({ id: 'a' })], null);
    expect([...d]).toEqual([]);
  });

  it('two same-named certified rows → the OLDER is displaced, the re-upload survives', () => {
    // The real DB shape: GI Consultation Note 939aa9ea (2026-09-07) and
    // 3877d5cf (2026-09-09), both CERTIFIED, same name. Latest wins.
    const older = row({ id: 'old', createdAt: at('2026-09-07T00:00:00.000Z') });
    const newer = row({ id: 'new', createdAt: at('2026-09-09T00:00:00.000Z') });
    const d = displacedByReupload([older, newer], null);
    expect([...d]).toEqual(['old']);
    // OPPOSITE ASSERTION: the survivor is NOT displaced.
    expect(d.has('new')).toBe(false);
  });

  it('⚠️ the PRACTICE DEFAULT is never displaced, even when it is the OLDER row', () => {
    // The practice's explicit choice wins over recency — a stale default is a
    // different problem (the default guard governs its validity), and silently
    // dropping the practice's chosen form from its own picker is the worse error.
    const olderDefault = row({ id: 'default-old', createdAt: at('2026-09-07T00:00:00.000Z') });
    const newer = row({ id: 'reupload', createdAt: at('2026-09-09T00:00:00.000Z') });
    const d = displacedByReupload([olderDefault, newer], 'default-old');
    expect(d.has('default-old')).toBe(false);
    expect([...d]).toEqual(['reupload']);
  });

  it('DIFFERENT names never collide — two distinct certified forms both survive', () => {
    const gi = row({ id: 'gi', name: 'GI Consultation Note' });
    const gastro = row({ id: 'gastro', name: 'Gastroenterology Consultation' });
    const d = displacedByReupload([gi, gastro], null);
    expect([...d]).toEqual([]);
  });

  it('⚠️ a NON-certified row (a draft) sharing a name is NEVER displaced', () => {
    // Drafts are the doctor's own WIP, few, and must stay choosable even when a
    // certified form shares the name. Only certified rows are grouped.
    const draft = row({ id: 'draft', certified: false, status: 'draft' });
    const certified = row({ id: 'cert', certified: true });
    const d = displacedByReupload([draft, certified], null);
    // Only one certified row in the group → nothing displaced, and the draft is
    // untouched regardless.
    expect([...d]).toEqual([]);
  });

  it('a draft AND two certified duplicates: the certified older is displaced, the draft survives', () => {
    const draft = row({ id: 'draft', certified: false, status: 'draft' });
    const older = row({ id: 'c-old', createdAt: at('2026-09-07T00:00:00.000Z') });
    const newer = row({ id: 'c-new', createdAt: at('2026-09-09T00:00:00.000Z') });
    const d = displacedByReupload([draft, older, newer], null);
    expect(d.has('draft')).toBe(false);
    expect(d.has('c-new')).toBe(false);
    expect([...d]).toEqual(['c-old']);
  });

  it('is DETERMINISTIC on a createdAt tie — higher id wins, lower id displaced', () => {
    const same = '2026-09-09T00:00:00.000Z';
    const a = row({ id: 'aaa', createdAt: at(same) });
    const b = row({ id: 'bbb', createdAt: at(same) });
    const d1 = displacedByReupload([a, b], null);
    const d2 = displacedByReupload([b, a], null);
    // Order-independent: 'bbb' survives, 'aaa' is displaced, both input orders.
    expect([...d1]).toEqual(['aaa']);
    expect([...d2]).toEqual(['aaa']);
  });

  it('⚠️ ADVERSARIAL: two DIFFERENT doctors, SAME name → NEITHER is displaced', () => {
    // The confirmed finding: name-only grouping hid one doctor's own certified
    // form and offered the other doctor's genuinely-different form under the
    // identical label (#318 offers all practice-certified templates cross-doctor,
    // and `name` has no uniqueness constraint). Grouping by (doctorId,
    // encounterType, name) keeps both — the wrong-form pin cannot happen.
    const mine = row({ id: 'mine', doctorId: 'doc-A', createdAt: at('2026-01-10T00:00:00.000Z') });
    const theirs = row({ id: 'theirs', doctorId: 'doc-B', createdAt: at('2026-03-01T00:00:00.000Z') });
    const d = displacedByReupload([mine, theirs], null);
    expect([...d]).toEqual([]);
  });

  it('⚠️ ADVERSARIAL: ONE doctor, SAME name, DIFFERENT encounterType → NEITHER displaced', () => {
    // One doctor may hold two genuinely-different certified forms of the same
    // name for different encounters (active-uniqueness is per (doctorId,
    // encounterType)). Those are not re-uploads of one lineage; collapsing them
    // would hide a legitimate choice and could fill from the wrong encounter's
    // form.
    const consult = row({ id: 'consult', encounterType: 'office_visit', createdAt: at('2026-01-10T00:00:00.000Z') });
    const scope = row({ id: 'scope', encounterType: 'procedure', createdAt: at('2026-03-01T00:00:00.000Z') });
    const d = displacedByReupload([consult, scope], null);
    expect([...d]).toEqual([]);
  });

  it('same doctor + same encounterType + same name → the re-upload STILL collapses', () => {
    // The fix must not over-correct: genuine re-uploads (one doctor, one
    // encounter, one name, several certified lineages) still collapse to latest.
    const older = row({ id: 'old', encounterType: 'office_visit', createdAt: at('2026-09-07T00:00:00.000Z') });
    const newer = row({ id: 'new', encounterType: 'office_visit', createdAt: at('2026-09-09T00:00:00.000Z') });
    const d = displacedByReupload([older, newer], null);
    expect([...d]).toEqual(['old']);
  });

  it('⚠️ the ACTIVE row survives over a NEWER inactive one (respects re-activation)', () => {
    // A doctor's active template is their working default for the slot; a newer
    // inactive re-upload they did not activate must not displace it and be
    // surfaced as inactive. Survivor precedence: default, then active, then newest.
    const activeOlder = row({ id: 'active-old', status: 'active', createdAt: at('2026-09-07T00:00:00.000Z') });
    const inactiveNewer = row({ id: 'inactive-new', status: 'inactive', createdAt: at('2026-09-09T00:00:00.000Z') });
    const d = displacedByReupload([activeOlder, inactiveNewer], null);
    expect(d.has('active-old')).toBe(false);
    expect([...d]).toEqual(['inactive-new']);
  });

  it('the practice default STILL beats an active sibling (explicit choice wins)', () => {
    const active = row({ id: 'active', status: 'active', createdAt: at('2026-09-09T00:00:00.000Z') });
    const defaultInactive = row({ id: 'the-default', status: 'inactive', createdAt: at('2026-09-01T00:00:00.000Z') });
    const d = displacedByReupload([active, defaultInactive], 'the-default');
    expect(d.has('the-default')).toBe(false);
    expect([...d]).toEqual(['active']);
  });

  it('three same-named certified rows collapse to ONE (the latest)', () => {
    const rows = [
      row({ id: 'r1', createdAt: at('2026-09-05T00:00:00.000Z') }),
      row({ id: 'r2', createdAt: at('2026-09-07T00:00:00.000Z') }),
      row({ id: 'r3', createdAt: at('2026-09-09T00:00:00.000Z') }),
    ];
    const d = displacedByReupload(rows, null);
    expect([...d].sort()).toEqual(['r1', 'r2']);
    expect(d.has('r3')).toBe(false);
  });
});
