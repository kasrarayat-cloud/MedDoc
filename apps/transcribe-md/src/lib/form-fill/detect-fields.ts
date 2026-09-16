// Stage 2 (detect) — the form-detect sidecar client (#326, Slice A).
// POSTs rendered-PDF bytes to the self-hosted FFDNet service and returns the
// detected boxes + nearest-text labels + the pinned weights sha. Fail-CLOSED:
// certification and detection must refuse on a null/failed detection (unlike the
// preview-only Gotenberg client, which fails open).

import { formDetectUrl } from '@/config/form-detect-fill';

import type {
  DetectedBox,
  DetectedForm,
  DetectedPage,
  DetectedWidgetType,
  DetectorSignature,
  LabelSource,
} from './types';

export type FormDetectFailure =
  | 'timeout'
  | 'detector_error'
  | 'empty_result'
  | 'bad_response';

export class FormDetectError extends Error {
  constructor(
    readonly reason: FormDetectFailure,
    message: string,
  ) {
    super(message);
    this.name = 'FormDetectError';
  }
}

const DETECT_TIMEOUT_MS = 120_000; // CPU inference of a multi-page form
const WIDGET_TYPES: ReadonlySet<string> = new Set([
  'TextBox',
  'ChoiceButton',
  'Signature',
]);

function num(v: unknown): number {
  return typeof v === 'number' && Number.isFinite(v) ? v : NaN;
}

function coerceBox(raw: unknown): DetectedBox {
  const b = raw as Record<string, unknown>;
  const x = num(b.x);
  const y = num(b.y);
  const w = num(b.w);
  const h = num(b.h);
  const type = String(b.type ?? '');
  if ([x, y, w, h].some(Number.isNaN) || !WIDGET_TYPES.has(type)) {
    throw new FormDetectError('bad_response', `malformed box: ${JSON.stringify(raw)}`);
  }
  const src = String(b.labelSource ?? b.label_source ?? '');
  const labelSource: LabelSource = src === 'left' || src === 'above' ? src : '';
  return {
    x,
    y,
    w,
    h,
    type: type as DetectedWidgetType,
    label: String(b.label ?? ''),
    labelSource,
  };
}

function coercePage(raw: unknown): DetectedPage {
  const p = raw as Record<string, unknown>;
  const index = num(p.index);
  const widthPt = num(p.widthPt ?? (p as Record<string, unknown>).width_pt);
  const heightPt = num(p.heightPt ?? (p as Record<string, unknown>).height_pt);
  if ([index, widthPt, heightPt].some(Number.isNaN) || !Array.isArray(p.boxes)) {
    throw new FormDetectError('bad_response', `malformed page: ${JSON.stringify(p.index)}`);
  }
  return { index, widthPt, heightPt, boxes: p.boxes.map(coerceBox) };
}

/**
 * Detect fillable-field boxes on the rendered PDF pages. Throws FormDetectError
 * on timeout / non-2xx / a response that does not parse to the expected shape —
 * the caller (certify, upload) must treat any failure as "cannot proceed", never
 * as "no fields".
 */
export async function detectFormFields(pdfBytes: Uint8Array): Promise<DetectedForm> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), DETECT_TIMEOUT_MS);
  let res: Response;
  try {
    res = await fetch(`${formDetectUrl()}/detect`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/pdf' },
      body: Buffer.from(pdfBytes),
      signal: controller.signal,
    });
  } catch (e) {
    const aborted = e instanceof Error && e.name === 'AbortError';
    throw new FormDetectError(
      aborted ? 'timeout' : 'detector_error',
      aborted ? `form-detect timed out after ${DETECT_TIMEOUT_MS}ms` : String(e),
    );
  } finally {
    clearTimeout(timer);
  }

  if (!res.ok) {
    throw new FormDetectError('detector_error', `form-detect HTTP ${res.status}`);
  }

  let json: Record<string, unknown>;
  try {
    json = (await res.json()) as Record<string, unknown>;
  } catch (e) {
    throw new FormDetectError('bad_response', `form-detect non-JSON: ${String(e)}`);
  }

  const weightsSha = String(json.weightsSha ?? json.weights_sha ?? '');
  const model = String(json.model ?? '');
  if (!weightsSha || !model || !Array.isArray(json.pages)) {
    throw new FormDetectError('bad_response', 'form-detect missing model/weights/pages');
  }
  const d = (json.detector ?? {}) as Record<string, unknown>;
  const detector: DetectorSignature = {
    model: String(d.model ?? model),
    weightsSha: String(d.weights_sha ?? d.weightsSha ?? weightsSha),
    confidence: num(d.confidence),
    imageSize: num(d.image_size ?? d.imageSize),
    commonformsVersion: String(d.commonforms_version ?? d.commonformsVersion ?? ''),
  };
  if (Number.isNaN(detector.confidence) || Number.isNaN(detector.imageSize)) {
    throw new FormDetectError('bad_response', 'form-detect signature missing confidence/image_size');
  }
  const pages = json.pages.map(coercePage);
  if (pages.every((p) => p.boxes.length === 0)) {
    throw new FormDetectError('empty_result', 'form-detect found no fields on any page');
  }
  return { model, weightsSha, detector, pages };
}
