import path from 'node:path';
import { defineConfig } from 'prisma/config';

// Best-effort .env loading for host CLI runs from packages/db. Inside
// the docker runner image we don't ship dotenv (production deps only)
// and DATABASE_URL is injected via docker-compose env, so we swallow
// MODULE_NOT_FOUND here and fall through to whatever's already on
// process.env. Either way, the `datasource.url` below resolves.
try {
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const { config: loadDotenv } = require('dotenv') as typeof import('dotenv');
  loadDotenv({ path: path.resolve(__dirname, '..', '..', '.env') });
} catch {
  // dotenv not installed in this runtime — rely on process.env as-is.
}

export default defineConfig({
  schema: path.join(__dirname, 'prisma', 'schema.prisma'),
  migrations: {
    path: path.join(__dirname, 'prisma', 'migrations'),
  },
  datasource: {
    url: process.env.DATABASE_URL,
  },
});
