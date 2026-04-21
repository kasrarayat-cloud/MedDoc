# ============================================================================
# TranscribeMD Marketing — Multi-stage Production Dockerfile (monorepo)
# ----------------------------------------------------------------------------
# Standalone Next.js output. Listens on PORT 3010 (matches the compose
# service mapping + the dev script in package.json). Build context is
# the monorepo root — `context: .` in docker-compose.yml.
#
# IMPORTANT: we COPY every workspace's package.json before `npm ci` so
# the workspace graph is complete. Omitting a sibling workspace's
# package.json is what caused the ioredis regression (see commit
# 1efd1b2); don't repeat that here.
# ============================================================================

# ── Stage 1: Dependencies (prod only, for runtime copy) ──
FROM node:22-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
COPY apps/meddoc-pro/package.json ./apps/meddoc-pro/package.json
COPY apps/marketing/package.json ./apps/marketing/package.json
COPY packages/db/package.json ./packages/db/package.json
COPY packages/auth/package.json ./packages/auth/package.json
COPY packages/types/package.json ./packages/types/package.json
COPY packages/ai/package.json ./packages/ai/package.json
RUN npm ci --omit=dev

# ── Stage 2: Build (full deps, runs next build) ──
FROM node:22-alpine AS builder
WORKDIR /app
COPY package.json package-lock.json ./
COPY apps/meddoc-pro/package.json ./apps/meddoc-pro/package.json
COPY apps/marketing/package.json ./apps/marketing/package.json
COPY packages/db/package.json ./packages/db/package.json
COPY packages/auth/package.json ./packages/auth/package.json
COPY packages/types/package.json ./packages/types/package.json
COPY packages/ai/package.json ./packages/ai/package.json
RUN npm ci

COPY . .

# T-M19.2: NEXT_PUBLIC_* need to be in the build environment so the
# `next build` step inlines them into the client bundle + ISR'd HTML.
# Compose passes these via `build.args:` so a domain cutover is a
# single edit at the compose level — no .env-in-monorepo-root
# contamination dance required (npm workspaces runs `next build` from
# apps/marketing/ where root .env files aren't picked up).
ARG NEXT_PUBLIC_TRANSCRIBE_MD_APP_URL
ARG NEXT_PUBLIC_MARKETING_URL
ENV NEXT_PUBLIC_TRANSCRIBE_MD_APP_URL=${NEXT_PUBLIC_TRANSCRIBE_MD_APP_URL}
ENV NEXT_PUBLIC_MARKETING_URL=${NEXT_PUBLIC_MARKETING_URL}

ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build -w marketing

# ── Stage 3: Production Runner ──
FROM node:22-alpine AS runner
WORKDIR /app

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

RUN addgroup --system --gid 1001 nodejs && \
    adduser --system --uid 1001 nextjs

# Standalone output bundles just what the runtime needs — no deps dir
# copy required. public/ + static/ live alongside the server.
COPY --from=builder /app/apps/marketing/public ./apps/marketing/public
COPY --from=builder /app/apps/marketing/.next/standalone ./
COPY --from=builder /app/apps/marketing/.next/static ./apps/marketing/.next/static

USER nextjs

EXPOSE 3010
ENV PORT=3010
ENV HOSTNAME="0.0.0.0"

CMD ["node", "apps/marketing/server.js"]
