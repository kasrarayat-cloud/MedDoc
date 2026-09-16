// ONE-PIPELINE form detect→fill (ruling #326, Slice A).
// Additive — nothing is routed onto this until Slice B/C behind
// NEXT_PUBLIC_FORM_DETECT_FILL. Stages: detect (sidecar) → group multi-line →
// map (stage 3, later) → fill (pdf-lib) → verify fidelity (sidecar).

export * from './types';
export { detectFormFields, FormDetectError, type FormDetectFailure } from './detect-fields';
export { groupDetectedFields, groupPageFields } from './group-fields';
export { fillDetectedForm, type FillDetectedInput, type FillDetectedResult } from './fill-boxes';
export {
  verifyFidelity,
  isPixelIdenticalOutsideBoxes,
  type FidelityResult,
  type FidelityPage,
} from './verify-fidelity';
