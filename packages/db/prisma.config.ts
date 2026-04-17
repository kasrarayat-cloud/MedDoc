import path from 'node:path';
import { config as loadDotenv } from 'dotenv';
import { defineConfig } from 'prisma/config';

// Resolve .env from the monorepo root so a single DATABASE_URL feeds both
// the running app and CLI operations run from this package directory.
loadDotenv({ path: path.resolve(__dirname, '..', '..', '.env') });

export default defineConfig({
  schema: path.join(__dirname, 'prisma', 'schema.prisma'),
  migrations: {
    path: path.join(__dirname, 'prisma', 'migrations'),
  },
  datasource: {
    url: process.env.DATABASE_URL,
  },
});
