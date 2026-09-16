// Stage 5 (certify — fidelity half) — ask the form-detect sidecar to compare the
// original vs the filled render and count pixels changed OUTSIDE the detected
// boxes (#326). "Pixel-identical outside the boxes" ⇔ every page reports 0.

import { formDetectUrl } from '@/config/form-detect-fill';

import type { DetectedForm } from './types';
import { FormDetectError } from './detect-fields';

export interface FidelityPage {
  page: number;
  outsideBoxChangedPx: number;
  outsideBoxTotalPx: number;
  insideBoxChangedPx: number;
  boxAreaPct: number;
}

export interface FidelityResult {
  pages: FidelityPage[];
  dpi: number;
}

const VERIFY_TIMEOUT_MS = 120_000;

/** True iff no page changed a single pixel outside the detected boxes AND every
 *  page actually rendered a fill inside a box (a blank fill is not a proof). */
export function isPixelIdenticalOutsideBoxes(r: FidelityResult): boolean {
  return (
    r.pages.length > 0 &&
    r.pages.every((p) => p.outsideBoxChangedPx === 0) &&
    r.pages.some((p) => p.insideBoxChangedPx > 0)
  );
}

export async function verifyFidelity(
  original: Uint8Array,
  filled: Uint8Array,
  form: DetectedForm,
  dpi = 150,
): Promise<FidelityResult> {
  const body = JSON.stringify({
    original: Buffer.from(original).toString('base64'),
    filled: Buffer.from(filled).toString('base64'),
    boxes: form.pages.map((p) => ({ boxes: p.boxes })),
    dpi,
  });

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), VERIFY_TIMEOUT_MS);
  let res: Response;
  try {
    res = await fetch(`${formDetectUrl()}/verify`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body,
      signal: controller.signal,
    });
  } catch (e) {
    const aborted = e instanceof Error && e.name === 'AbortError';
    throw new FormDetectError(aborted ? 'timeout' : 'detector_error', String(e));
  } finally {
    clearTimeout(timer);
  }
  if (!res.ok) throw new FormDetectError('detector_error', `form-detect /verify HTTP ${res.status}`);

  const json = (await res.json()) as { pages?: unknown; dpi?: unknown };
  if (!Array.isArray(json.pages)) {
    throw new FormDetectError('bad_response', 'form-detect /verify missing pages');
  }
  const pages: FidelityPage[] = json.pages.map((raw) => {
    const p = raw as Record<string, unknown>;
    return {
      page: Number(p.page),
      outsideBoxChangedPx: Number(p.outside_box_changed_px ?? p.outsideBoxChangedPx),
      outsideBoxTotalPx: Number(p.outside_box_total_px ?? p.outsideBoxTotalPx),
      insideBoxChangedPx: Number(p.inside_box_changed_px ?? p.insideBoxChangedPx),
      boxAreaPct: Number(p.box_area_pct ?? p.boxAreaPct),
    };
  });
  return { pages, dpi: Number(json.dpi ?? dpi) };
}
