import { execFileSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import path from 'node:path';

import { beforeAll, describe, it, expect } from 'vitest';

import { detectFormFields } from '../detect-fields';
import { groupDetectedFields } from '../group-fields';
import { fillDetectedForm } from '../fill-boxes';
import { verifyFidelity, isPixelIdenticalOutsideBoxes } from '../verify-fidelity';
import { formDetectUrl } from '@/config/form-detect-fill';

// Ruling #326, Slice A — the full pipeline (detect → group → fill → verify) end
// to end against the LIVE form-detect sidecar, on the committed blank fixture.
// SKIPS when the sidecar is unreachable (i.e. in CI) — set FORM_DETECT_URL to a
// running sidecar (e.g. http://127.0.0.1:8899) to exercise it.

const REPO_ROOT = execFileSync('git', ['rev-parse', '--show-toplevel'], {
  encoding: 'utf8',
}).trim();
const FIXTURE = path.join(REPO_ROOT, 'colon_blank_answers.pdf');

let reachable = false;
beforeAll(async () => {
  try {
    const res = await fetch(`${formDetectUrl()}/health`, {
      signal: AbortSignal.timeout(3000),
    });
    reachable = res.ok;
  } catch {
    reachable = false;
  }
});

describe('form detect→fill end to end (live sidecar)', () => {
  it('detects, fills, and stays pixel-identical outside the boxes', async () => {
    if (!reachable) {
      // no sidecar (CI): nothing to assert. The pure gates cover the logic.
      return;
    }
    const pdf = new Uint8Array(readFileSync(FIXTURE));

    const form = await detectFormFields(pdf);
    expect(form.weightsSha).toMatch(/^[0-9a-f]{64}$/);
    expect(form.pages[0]!.boxes.length).toBeGreaterThan(0);

    const fields = groupDetectedFields(form);
    expect(fields.length).toBeGreaterThan(0);

    const values = new Map(fields.map((f, i) => [f.id, `Sample ${i}`]));
    const { pdf: filled, filledFields } = await fillDetectedForm({
      originalPdf: pdf,
      fields,
      values,
    });
    expect(filledFields).toBeGreaterThan(0);

    const fidelity = await verifyFidelity(pdf, filled, form);
    // every page: 0 pixels changed outside the boxes, something changed inside
    for (const p of fidelity.pages) expect(p.outsideBoxChangedPx).toBe(0);
    expect(isPixelIdenticalOutsideBoxes(fidelity)).toBe(true);
  }, 180_000);
});
