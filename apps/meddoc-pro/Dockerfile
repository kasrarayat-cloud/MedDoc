# ============================================================================
# MedDoc Pro — Multi-stage Production Dockerfile (monorepo)
# ----------------------------------------------------------------------------
# Build context is the monorepo root (`docker build .` at the repo root, or
# `context: .` in docker-compose.yml). The Dockerfile lives under the app
# directory but operates on the whole workspace so npm workspaces resolve.
# ============================================================================

# ── Stage 1: Dependencies (production only) ──
FROM node:22-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
COPY apps/meddoc-pro/package.json ./apps/meddoc-pro/package.json
COPY packages/db/package.json ./packages/db/package.json
COPY packages/auth/package.json ./packages/auth/package.json
COPY packages/types/package.json ./packages/types/package.json
COPY packages/ai/package.json ./packages/ai/package.json
RUN npm ci --omit=dev

# ── Stage 2: Build ──
FROM node:22-alpine AS builder
WORKDIR /app

# Copy all package manifests first so npm can resolve the workspace graph
# without the full source tree (keeps this layer cacheable).
COPY package.json package-lock.json ./
COPY apps/meddoc-pro/package.json ./apps/meddoc-pro/package.json
COPY packages/db/package.json ./packages/db/package.json
COPY packages/auth/package.json ./packages/auth/package.json
COPY packages/types/package.json ./packages/types/package.json
COPY packages/ai/package.json ./packages/ai/package.json
RUN npm ci

# Copy the rest of the source
COPY . .

# Generate the Prisma client from packages/db
RUN npm run db:generate

# Build Next.js via the workspace script
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build -w meddoc-pro

# ── Stage 3: Production Runner ──
FROM node:22-alpine AS runner
WORKDIR /app

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

RUN addgroup --system --gid 1001 nodejs && \
    adduser --system --uid 1001 nextjs

# Next.js standalone output already bundles node_modules needed at runtime.
COPY --from=builder /app/apps/meddoc-pro/public ./public
COPY --from=builder /app/apps/meddoc-pro/.next/standalone ./
COPY --from=builder /app/apps/meddoc-pro/.next/static ./apps/meddoc-pro/.next/static

# Prisma schema + generated client for migrate deploy at boot.
COPY --from=builder /app/packages/db/prisma ./packages/db/prisma
COPY --from=builder /app/node_modules/.prisma ./node_modules/.prisma
COPY --from=builder /app/node_modules/@prisma ./node_modules/@prisma

# pdf-parse is a server external package (not bundled by Next standalone).
COPY --from=deps /app/node_modules/pdf-parse ./node_modules/pdf-parse

USER nextjs

EXPOSE 3000
ENV PORT=3000
ENV HOSTNAME="0.0.0.0"

# Standalone output puts server.js at apps/meddoc-pro/server.js when the
# source app lives under apps/meddoc-pro in the workspace.
CMD ["node", "apps/meddoc-pro/server.js"]
