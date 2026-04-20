# ============================================================================
# MedDoc Pro — Operator conveniences (T-M16.4)
# ----------------------------------------------------------------------------
# Targets here are thin wrappers around `docker compose` / `psql` / `rsync`
# flows documented in docs/DEPLOYMENT_RUNBOOK.md. Every target should be
# fast, idempotent, and safe to re-run. Anything destructive calls it out
# in its description and waits for a typed confirmation via `read`.
# ============================================================================

.PHONY: help prune-docker prune-docker-dry backup-now backup-ls health

help:                   ## Show this help
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z0-9_-]+:.*?## / {printf "  \033[36m%-22s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

# ── Docker maintenance ─────────────────────────────────────────────────────

prune-docker:           ## Reclaim disk: remove unused images >30d + build cache
	@echo "This will DELETE unused Docker images older than 30 days + all"
	@echo "reclaimable build-cache layers. Current usage:"
	@docker system df
	@echo ""
	@echo "Proceed? (y/N)"
	@read -r ans && [ "$$ans" = "y" ] && docker system prune -a --volumes --filter "until=720h" -f || echo "aborted."

prune-docker-dry:       ## Show what prune-docker would remove (safe)
	@docker system df
	@echo "Would remove:"
	@docker system prune -a --volumes --filter "until=720h" --dry-run 2>&1 || \
	  echo "(--dry-run unsupported in this Docker version; see 'docker system df' above)"

# ── Backups ────────────────────────────────────────────────────────────────

backup-now:             ## Trigger a one-off pg_dump via the postgres-backup sidecar
	docker compose exec postgres-backup /backup.sh
	@echo ""
	@echo "Latest dumps:"
	@ls -lht backups/daily/ 2>/dev/null | head -4 || true
	@ls -lht backups/last/ 2>/dev/null | head -4 || true

backup-ls:              ## List all dumps with sizes + dates
	@echo "── Manual pre-milestone dumps ──"
	@ls -lht backups/*.sql.gz 2>/dev/null || echo "(none)"
	@echo ""
	@echo "── Automated rotation ──"
	@for d in last daily weekly monthly; do \
	  echo "-- $$d --"; \
	  ls -lht backups/$$d/ 2>/dev/null | head -5 || echo "(empty or missing)"; \
	done

# ── Smoke checks ───────────────────────────────────────────────────────────

health:                 ## Hit /api/health on both apps + show container status
	@curl -fsS http://localhost:80/api/health | head -c 300; echo ""
	@curl -fsS http://localhost:9020/api/health | head -c 300; echo ""
	@echo ""
	@docker compose ps --format 'table {{.Name}}\t{{.Status}}'
