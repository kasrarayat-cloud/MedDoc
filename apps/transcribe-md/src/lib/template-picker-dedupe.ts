// ============================================================================
// RE-UPLOAD DISPLACEMENT — the new-visit picker offers ONE current form per name.
// ----------------------------------------------------------------------------
// A LEAF module, and that is the point: the rule lives here, the RSC page
// (`visits/new/page.tsx`) is its only runtime reader, and a gate imports THIS to
// exercise the rule directly — a page component cannot be unit-mounted, and a
// rule restated inside a test goes stale (the #289 lesson, one directory over).
//
// ⚠️ OWNER FINDING (blocking). Re-uploading a form does not edit the template in
// place — it mints a NEW lineage: a new NoteTemplate id carrying the SAME name,
// certified independently. So a practice accumulates several CERTIFIED templates
// that are indistinguishable in the picker (two "Gastroenterology Consultation"
// rows, and no way to tell which is current), and the older lineages never go
// away on their own — the picker offered every certified row regardless.
//
// This collapses same-named certified rows to the one the practice means. It is
// DISPLAY-ONLY and REVERSIBLE: no template row is edited, retired, or deleted;
// a wrong call is undone by reverting the caller. The lifecycle supersede
// (`note-template-lifecycle.ts`, maxActivePerSlot) touches ACTIVE status per
// (doctorId, encounterType); this is a different axis — the choosable set a
// doctor sees — and deliberately mutates nothing.
//
// ⚠️ THE GROUPING KEY IS (doctorId, encounterType, name), NOT name alone — the
// adversarial pass proved name-only over-groups. `name` has NO uniqueness
// constraint, and #318 makes every practice-certified template choosable across
// doctors, so two GENUINELY DIFFERENT certified forms can share a name: a second
// doctor's own form, or one doctor's two forms for different encounters. Name-only
// grouping would hide one of those and offer the other under the identical label —
// and a doctor picking it would fill from the WRONG form. Same name is evidence of
// a re-upload only WITHIN one (doctor, encounter).
// ============================================================================

/** The picker-relevant shape of one NoteTemplate row. */
export interface PickerTemplateRow {
  id: string;
  /** The uploading doctor. Part of the grouping key: a re-upload keeps the same
   *  doctorId, so two DIFFERENT doctors' same-named certified forms must NEVER
   *  collapse into one. */
  doctorId: string | null;
  /** The encounter type. Also part of the key: one doctor may hold two genuinely
   *  different certified forms of the same name for different encounters (the
   *  only active-uniqueness is per (doctorId, encounterType)), and those are not
   *  re-uploads of one form — collapsing them would hide a legitimate choice. */
  encounterType: string | null;
  /** The template's display name. A re-upload reuses it verbatim; same name
   *  WITHIN one (doctor, encounterType) is what identifies the duplicates. */
  name: string;
  /** NoteTemplate.status — 'active' | 'draft' | 'inactive'. Carried so the
   *  caller can label the survivor; the displacement itself ignores it. */
  status: string;
  createdAt: Date;
  /** Whether this row's compiled version is CERTIFIED — the exact condition the
   *  fill honours, computed by the caller from the compiled version. */
  certified: boolean;
}

/** The grouping key: same doctor, same encounter, same name. JSON-encoded as a
 *  tuple so a free-text `name` can never forge a collision with another
 *  (doctorId, encounterType) — the array delimiters and string escaping keep the
 *  three parts unambiguous. */
function groupKey(r: PickerTemplateRow): string {
  return JSON.stringify([r.doctorId, r.encounterType, r.name]);
}

/**
 * The ids of CERTIFIED templates that a same-(doctor, encounter, name),
 * more-current certified sibling displaces — i.e. the ones the picker must NOT
 * offer.
 *
 * The survivor within a group is chosen as:
 *   1. the practice default, when it is in the group — the practice's explicit
 *      choice is never displaced; else
 *   2. the ACTIVE row, when there is one — a doctor's active template is their
 *      working default for that (doctor, encounter) slot (there is at most one,
 *      by the active-uniqueness index), so a re-activated older version must win
 *      over a newer inactive one rather than being surfaced as inactive; else
 *   3. the most-recently-CREATED row — a re-upload displaces the form it
 *      replaced — tie-broken by id descending, so the result is deterministic
 *      even if two rows share a createdAt.
 *
 * A group of one displaces nothing. NON-certified rows (a doctor's own draft or
 * WIP) are never grouped or displaced: they are few, they are the caller's own,
 * and a draft under test must stay choosable even when a certified form shares
 * its name.
 *
 * Pure — no I/O, no clock, no globals — so it is fully determined by its inputs
 * and a gate can plant the exact duplicate shape and assert the survivor.
 */
export function displacedByReupload(
  rows: readonly PickerTemplateRow[],
  defaultTemplateId: string | null,
): Set<string> {
  const certifiedByKey = new Map<string, PickerTemplateRow[]>();
  for (const r of rows) {
    if (!r.certified) continue;
    const key = groupKey(r);
    const group = certifiedByKey.get(key);
    if (group) group.push(r);
    else certifiedByKey.set(key, [r]);
  }

  const displaced = new Set<string>();
  for (const group of certifiedByKey.values()) {
    if (group.length < 2) continue;
    const survivor =
      group.find((g) => g.id === defaultTemplateId) ??
      group.find((g) => g.status === 'active') ??
      [...group].sort(
        (a, b) =>
          b.createdAt.getTime() - a.createdAt.getTime() ||
          (a.id < b.id ? 1 : -1),
      )[0];
    for (const g of group) {
      if (g.id !== survivor.id) displaced.add(g.id);
    }
  }
  return displaced;
}
