import path from 'node:path';
import url from 'node:url';

import '@testing-library/jest-dom/vitest';

// pdf-generator.ts reads its TTFs from PDF_FONTS_DIR which defaults
// to /app/apps/transcribe-md/fonts (the docker layout). Tests run on
// the host where that path doesn't exist; point at the repo-local
// fonts/ next to this setup file so generator tests can mint a real
// PDF instead of crashing in pdfkit's font loader.
process.env.PDF_FONTS_DIR ??= path.resolve(
  path.dirname(url.fileURLToPath(import.meta.url)),
  'fonts'
);
