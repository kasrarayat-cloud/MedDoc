-- Certification could fail with no trace at all. The action's catch-all returned
-- "Certification failed. Please try again." for ANY error that was not a
-- TemplateTwinLifecycleError, logged nothing, and wrote no audit row — so a
-- hand-driven QA run reached the certify step, failed, and left no way to learn
-- why from either the database or the container log.
--
-- Metadata carries the error CLASS and MESSAGE only. Never document content:
-- a template is a customer's form, and its field labels are theirs.
ALTER TYPE "AuditAction" ADD VALUE IF NOT EXISTS 'TEMPLATE_TWIN_CERTIFY_FAILED';
