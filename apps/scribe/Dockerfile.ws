# ============================================================================
# Scribe WebSocket sidecar — runs src/ws-server.ts via tsx on port 3003
# ----------------------------------------------------------------------------
# M7 slim rewrite (was 1.98 GB). Same pattern as Dockerfile.worker but
# without ffmpeg (the WS server never touches audio files — it proxies
# binary frames straight through to Deepgram).
#
# Target: <400 MB. Report `docker images | grep scribe-ws` after build.
# ============================================================================

# ── Stage 1: full-deps ──
FROM node:22-alpine AS full-deps
WORKDIR /app
COPY package.json package-lock.json ./
COPY apps/meddoc-pro/package.json ./apps/meddoc-pro/package.json
COPY apps/scribe/package.json ./apps/scribe/package.json
COPY packages/db/package.json ./packages/db/package.json
COPY packages/auth/package.json ./packages/auth/package.json
COPY packages/types/package.json ./packages/types/package.json
COPY packages/ai/package.json ./packages/ai/package.json
RUN npm ci

# ── Stage 2: prod-deps ──
FROM node:22-alpine AS prod-deps
WORKDIR /app
COPY package.json package-lock.json ./
COPY apps/meddoc-pro/package.json ./apps/meddoc-pro/package.json
COPY apps/scribe/package.json ./apps/scribe/package.json
COPY packages/db/package.json ./packages/db/package.json
COPY packages/auth/package.json ./packages/auth/package.json
COPY packages/types/package.json ./packages/types/package.json
COPY packages/ai/package.json ./packages/ai/package.json
RUN npm ci --omit=dev

# ── Stage 3: prisma-generate ──
FROM full-deps AS prisma-generate
WORKDIR /app
COPY packages/db/prisma ./packages/db/prisma
COPY packages/db/src ./packages/db/src
COPY packages/db/prisma.config.ts ./packages/db/prisma.config.ts
RUN npm run generate -w @meddoc/db

# ── Stage 4: runtime ──
FROM node:22-alpine AS runner
WORKDIR /app

ENV NODE_ENV=production

COPY --from=prod-deps /app/node_modules ./node_modules
COPY --from=prisma-generate /app/node_modules/.prisma ./node_modules/.prisma
COPY --from=prisma-generate /app/node_modules/@prisma ./node_modules/@prisma

COPY package.json package-lock.json tsconfig.base.json ./

COPY apps/scribe/package.json ./apps/scribe/package.json
COPY apps/scribe/tsconfig.json ./apps/scribe/tsconfig.json
COPY apps/scribe/src ./apps/scribe/src
COPY apps/scribe/sentry.server.config.ts ./apps/scribe/sentry.server.config.ts

COPY packages/db/package.json ./packages/db/package.json
COPY packages/db/src ./packages/db/src
COPY packages/db/prisma ./packages/db/prisma
COPY packages/db/prisma.config.ts ./packages/db/prisma.config.ts
COPY packages/auth/package.json ./packages/auth/package.json
COPY packages/auth/src ./packages/auth/src
COPY packages/types/package.json ./packages/types/package.json
COPY packages/types/src ./packages/types/src
COPY packages/ai/package.json ./packages/ai/package.json
COPY packages/ai/src ./packages/ai/src

RUN addgroup --system --gid 1001 nodejs && \
    adduser --system --uid 1001 wsuser
USER wsuser

EXPOSE 3003
WORKDIR /app/apps/scribe
CMD ["npx", "tsx", "src/ws-server.ts"]
