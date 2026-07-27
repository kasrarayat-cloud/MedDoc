-- One audit row per chat-editor turn, so a chat-driven change is
-- distinguishable from a button-driven one after the fact.
ALTER TYPE "AuditAction" ADD VALUE IF NOT EXISTS 'CHAT_EDIT_TURN';
