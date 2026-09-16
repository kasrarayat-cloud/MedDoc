// Types for the ONE-PIPELINE form detect→fill (ruling #326, Slice A).
// All coordinates are PDF points, bottom-left origin (pdf-lib space), as the
// form-detect sidecar returns them.

export type DetectedWidgetType = 'TextBox' | 'ChoiceButton' | 'Signature';

/** where the label came from: a field:value pair ('left'), a section heading
 *  above ('above'), or none ('') — lets grouping tell a section from a field. */
export type LabelSource = 'left' | 'above' | '';

export interface DetectedBox {
  x: number;
  y: number;
  w: number;
  h: number;
  type: DetectedWidgetType;
  /** nearest-text label (best effort; refined by stage-3 mapping) */
  label: string;
  labelSource: LabelSource;
}

export interface DetectedPage {
  index: number;
  widthPt: number;
  heightPt: number;
  boxes: DetectedBox[];
}

/**
 * The full detector identity that enters the certification signature (#326):
 * not just the weights sha, but every knob that moves the detected boxes, so a
 * change to any of them forces re-certification. Pinned deps freeze the rest.
 */
export interface DetectorSignature {
  model: string;
  weightsSha: string;
  confidence: number;
  imageSize: number;
  commonformsVersion: string;
}

export interface DetectedForm {
  /** FFDNet model name, e.g. "FFDNet-L" */
  model: string;
  /** sha256 of the pinned weights — part of the certification signature (#326) */
  weightsSha: string;
  /** the full detection identity for the certification signature */
  detector: DetectorSignature;
  pages: DetectedPage[];
}

/**
 * A grouped field: one concept-able field spanning one or more detected boxes.
 * Free-prose multi-line sections (CONSENT, DESCRIPTION OF PROCEDURE) collapse
 * their stacked boxes into ONE field so the value flows across the lines and
 * maps to ONE concept; single-line fields and numbered list slots stay one box.
 */
export interface FormField {
  id: string;
  label: string;
  page: number;
  boxes: DetectedBox[];
  multiline: boolean;
}
