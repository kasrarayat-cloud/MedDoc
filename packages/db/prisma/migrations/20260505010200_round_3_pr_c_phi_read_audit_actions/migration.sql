-- Round 3 PR-C — close §164.312(b) PHI-READ audit gap.
-- Audit finding A05-P0-004: GET endpoints and Server Components
-- that return PHI emitted ZERO rows; only mutations were audited.
-- This migration adds three enum values consumed by the new
-- logAudit() call sites in /api/visits/* (read), /api/patients/*
-- (read), /visits/* (RSC), /patients/* (RSC), /dictation/audio
-- (download).
ALTER TYPE "AuditAction" ADD VALUE IF NOT EXISTS 'VIEWED_VISIT';
ALTER TYPE "AuditAction" ADD VALUE IF NOT EXISTS 'VIEWED_VISIT_LIST';
ALTER TYPE "AuditAction" ADD VALUE IF NOT EXISTS 'VIEWED_VISIT_AUDIO';
