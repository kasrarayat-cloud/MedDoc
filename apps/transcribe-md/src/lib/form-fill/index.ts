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

// Stage 3 (map) + Slice B certify/export/store — the detected-form pipeline.
export {
  mapFieldsToConcepts,
  conceptMapOf,
  deterministicConceptFor,
  type FieldConcept,
} from './map-fields';
export {
  persistDetectedForm,
  markDetectedFormCertified,
  readDetectedForm,
  isDetectedFormCertified,
  type StoredDetectedForm,
  type StoredDetectedField,
} from './detected-form-store';
export {
  fillFromNote,
  headerKeyForConcept,
  DETERMINISTICALLY_FILLED_HEADER_KEYS,
  type NoteFillContext,
  type FillFromNoteResult,
} from './fill-from-note';
export {
  fillFromFacts,
  synthesizeTemplateField,
  synthesizeMapping,
  syntheticFieldId,
  type FactValueResult,
} from './fill-from-facts';
export { deriveDetectedFormValues, type DeriveValuesResult } from './derive-values';
export {
  certifyDetectedForm,
  DetectedFormCertifyError,
  fieldExpectedToFill,
  buildSyntheticDetectedNote,
  type CertifyDetectedFormResult,
} from './certify-detected-form';
export {
  detectedFormExport,
  type DetectedFormResult,
  type DetectedFormReason,
} from './export-detected';
