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
# ⚠️ npm's DEFAULTS ARE 2 RETRIES AND A 60s CEILING, WHICH A REGISTRY BLIP
# OUTLASTS. On 2026-08-10, after 18 of 18 consecutive green e2e runs, THREE
# independent image builds on three different branches all died inside twelve
# minutes on `npm error code ECONNRESET` / `network aborted` during `npm ci`.
# Zero test failures in any of them — the image simply never built, so the gate
# could not report on the code at all.
#
# Set as NPM_CONFIG_* ON THE STAGE, not as flags on the one command below, so
# any npm invocation added to this stage later inherits it rather than having to
# remember. A per-command flag list is a hand-kept list, and hand-kept lists are
# wrong eventually.
ENV NPM_CONFIG_FETCH_RETRIES=5 \
    NPM_CONFIG_FETCH_RETRY_MINTIMEOUT=20000 \
    NPM_CONFIG_FETCH_RETRY_MAXTIMEOUT=120000
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
# Registry-blip retry budget — see the note on the first install stage above.
ENV NPM_CONFIG_FETCH_RETRIES=5 \
    NPM_CONFIG_FETCH_RETRY_MINTIMEOUT=20000 \
    NPM_CONFIG_FETCH_RETRY_MAXTIMEOUT=120000
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

# Standalone `docker run` healthcheck (compose-level healthcheck in
# docker-compose.yml provides the same signal for the orchestrator;
# this line covers `docker run` users + makes the image self-describing).
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
  CMD wget --quiet --tries=1 --spider http://127.0.0.1:3000/api/health || exit 1

# Standalone output puts server.js at apps/meddoc-pro/server.js when the
# source app lives under apps/meddoc-pro in the workspace.
CMD ["node", "apps/meddoc-pro/server.js"]
