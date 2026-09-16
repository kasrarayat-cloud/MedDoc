// Stage 2b (group) — collapse a free-prose multi-line section's stacked boxes
// into ONE field so its value flows across the lines and maps to ONE concept
// (ruling #326). Single-line fields and numbered list slots stay one box each.

import type { DetectedBox, DetectedForm, DetectedPage, FormField } from './types';

const NUMBERED = /^\s*\(?\d+\s*[.)]?\s*$/; // "1." "2)" "(3)" — a list slot marker

function isNumbered(label: string): boolean {
  return NUMBERED.test(label);
}

/** b sits directly beneath `prev`'s last box: left edges aligned and the
 *  vertical gap between them is under ~1.4 line-heights. */
function stackedBelow(prev: DetectedBox, b: DetectedBox): boolean {
  const xAligned = Math.abs(prev.x - b.x) <= 16;
  const gap = prev.y - (b.y + b.h); // prev is above (higher y), b below
  const lineH = Math.max(prev.h, b.h, 8);
  return xAligned && gap >= -2 && gap <= lineH * 1.4;
}

export function groupPageFields(page: DetectedPage): FormField[] {
  const fields: FormField[] = [];
  let cur: FormField | null = null;

  page.boxes.forEach((b, i) => {
    const standalone = (): FormField => ({
      id: `p${page.index}_f${i}`,
      label: b.label,
      page: page.index,
      boxes: [b],
      multiline: false,
    });

    // numbered slots and non-text widgets never merge — each is its own field.
    if (b.type !== 'TextBox' || isNumbered(b.label)) {
      cur = null;
      fields.push(standalone());
      return;
    }

    const last = cur?.boxes[cur.boxes.length - 1];
    // A SECTION is a field whose first box was labelled from a heading ABOVE
    // (label_source 'above') — CONSENT, DESCRIPTION, FINDINGS:, PLAN:, colon or
    // not. Only a section absorbs a stacked continuation (a repeated heading or
    // an unlabelled body line); a field:value box (label_source 'left', e.g.
    // "PATIENT NAME:") never absorbs the box below it (adv pass1 #3 / pass2 #2).
    const curIsSection = !!cur && cur.boxes[0]!.labelSource === 'above';
    const sameSection =
      !!cur &&
      !!last &&
      curIsSection &&
      stackedBelow(last, b) &&
      (b.label === '' || b.label === cur.label);

    if (cur && sameSection) {
      cur.boxes.push(b);
      cur.multiline = true;
      if (!cur.label && b.label) cur.label = b.label;
    } else {
      cur = standalone();
      fields.push(cur);
    }
  });

  return fields;
}

export function groupDetectedFields(form: DetectedForm): FormField[] {
  return form.pages.flatMap((p) => groupPageFields(p));
}
