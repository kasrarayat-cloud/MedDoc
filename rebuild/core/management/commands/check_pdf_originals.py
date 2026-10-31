"""Read-only: run the download safety check on every stored PDF template original.

Finding P1 (docs/rebuild/pypdf-6.21.4.md): originals accepted before the raw scan existed are
still stored, and the database forbids rewriting them. Serving is already gated
(core.views.template_original); this command says how many stored originals that gate would
refuse, and which, BEFORE anyone meets a refusal. It runs the same isolated worker check, writes
counts plus template ids and codes to a new JSON file, and writes nothing else: no database row
(the transaction is read-only), no audit event, no file change. No file contents and no names
are written.
"""
from collections import Counter
import hashlib
import json
import os
from pathlib import Path

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.utils import timezone

from core.models import Template
from core.security import private_path


class Command(BaseCommand):
    help = "Read-only: check every stored PDF template original for active content; write a JSON report."

    def add_arguments(self, parser):
        parser.add_argument("--output", required=True, help="New JSON file to create (never overwritten).")

    def handle(self, *args, **options):
        from documents import DocumentError, check_original
        output = Path(options["output"])
        if output.exists() or output.is_symlink():
            raise CommandError("The output file already exists; choose a new path.")
        rows = []
        with transaction.atomic():
            if connection.vendor == "postgresql":
                with connection.cursor() as cursor:
                    cursor.execute("SET TRANSACTION READ ONLY")
            for template in Template.objects.filter(format="pdf").order_by("created_at", "pk").only(
                    "pk", "original_path", "sha256"):
                rows.append({"template_id": str(template.pk), "code": self.code(template, check_original,
                                                                                  DocumentError)})
        counts = Counter(row["code"] for row in rows)
        report = {"checked_at": timezone.now().isoformat(), "pdf_originals": len(rows),
                  "served": counts.get("ok", 0), "refused": len(rows) - counts.get("ok", 0),
                  "counts": dict(sorted(counts.items())), "templates": rows}
        descriptor = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(descriptor, "w") as handle:
            json.dump(report, handle, indent=2, sort_keys=True)
            handle.write("\n")
        self.stdout.write(json.dumps({"pdf_originals": len(rows), "counts": report["counts"]}, sort_keys=True))

    @staticmethod
    def code(template, check_original, DocumentError):
        try:
            path = private_path(template.original_path)
            payload = path.read_bytes()
        except (OSError, ValidationError):
            return "source_unavailable"
        if hashlib.sha256(payload).hexdigest() != template.sha256:
            return "integrity_failed"
        try:
            check_original(path, expected_sha256=template.sha256)
        except DocumentError as exc:
            return exc.code
        return "ok"
