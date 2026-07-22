import {
  compileTemplateDocx,
  type CompileTemplateDocxOptions,
} from '@/lib/note-template-docx';

import {
  TEMPLATE_TWIN_COMPILER_VERSION,
  type TemplateDocIR,
} from './ir';
import { DOCX_MIME_TYPE } from './storage';

/** Format-neutral boundary for future source compilers. Adding PDF or XLSX
 * requires a new implementation; it must not branch or weaken the DOCX
 * compiler's deterministic security contract. */
export interface TemplateArtifactCompiler<TOptions = unknown> {
  readonly sourceFormat: string;
  readonly mimeTypes: readonly string[];
  readonly compilerVersion: string;
  compile(source: Uint8Array, options?: TOptions): TemplateDocIR;
}

export const DOCX_TEMPLATE_COMPILER: TemplateArtifactCompiler<CompileTemplateDocxOptions> =
  Object.freeze({
    sourceFormat: 'docx',
    mimeTypes: Object.freeze([DOCX_MIME_TYPE]),
    compilerVersion: TEMPLATE_TWIN_COMPILER_VERSION,
    compile: compileTemplateDocx,
  });

export function compilerForTemplateSource(input: {
  extension: string;
  mimeType: string;
}): TemplateArtifactCompiler<CompileTemplateDocxOptions> | null {
  const extension = input.extension.trim().toLocaleLowerCase('en-US');
  return extension === '.docx' && DOCX_TEMPLATE_COMPILER.mimeTypes.includes(input.mimeType)
    ? DOCX_TEMPLATE_COMPILER
    : null;
}
