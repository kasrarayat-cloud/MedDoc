export { compileTemplateDocx, computeStaticXmlSha256 } from './compiler';
export type { CompileTemplateDocxOptions } from './compiler';
export { TemplateDocxError } from './errors';
export type { TemplateDocxErrorCode } from './errors';
export {
  DEFAULT_TEMPLATE_DOCX_LIMITS,
  resolveTemplateDocxLimits,
} from './limits';
export type { TemplateDocxLimits } from './limits';
export { inspectDocxPackage } from './package-security';
export type {
  InspectedDocxPackage,
  OpcRelationship,
} from './package-security';
export { readVerifiedZipPackage } from './zip-directory';
export type { VerifiedZipEntry, VerifiedZipPackage } from './zip-directory';
export { renderTemplateDocx } from './renderer';
export { readbackTemplateDocxOutput } from './output-readback';
export type { ReadbackTemplateDocxOutputInput } from './output-readback';
export type {
  RenderTemplateDocxInput,
  RenderTemplateDocxResult,
} from './renderer';
export {
  TemplateDocxRenderError,
  verifyRenderedTemplateDocx,
} from './roundtrip-verify';
export type {
  TemplateDocxRenderErrorCode,
  TemplateDocxRoundTripVerification,
  VerifiedRenderedField,
  VerifyRenderedTemplateDocxInput,
} from './roundtrip-verify';
