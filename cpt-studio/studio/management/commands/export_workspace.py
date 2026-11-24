"""Return a whole practice's data (release 1, D2; studio.record_bundle.export_practice). A ruled act, run only through
the installer's --phase manage with a committed declaration (A6).

    export_workspace --workspace <id> --out <new folder> --by <name> --reason-file F [--authorization-ref R]

Writes one folder per document - its original, its converted PDF, every stored report, record.json and manifest.json -
and the practice's manifest in JSON and CSV (documents, codes, decisions with who and when, answers, the audit trail,
the sha256 of every file) and SHA256SUMS, into a folder that must not exist yet: made 0700, every file 0600, written
once. One DisposalEvent 'exported' records the documents, the counts and the manifest's sha256. The output is counts and
digests only, never a title or a file name.

Delivery is the termination runbook's step, not this command's: encrypted, through a time-limited link, and logged;
this copy is destroyed once the practice confirms receipt (ORG-18 (4); OWNER DECISION D14). The practice keeps its
access until then (dispose --close leaves reading on).
"""
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from studio import disposal, models, record_bundle
from studio.storage import OriginalCorrupted


class Command(BaseCommand):
    help = "Write a whole practice's data - documents, reports, records and manifests - into a new folder."

    def add_arguments(self, parser):
        parser.add_argument('--workspace', required=True, help="The practice's id.")
        parser.add_argument('--out', required=True, help='The folder to write (it must not exist; its parent must).')
        parser.add_argument('--by', required=True, help='The person who runs the export.')
        parser.add_argument('--reason-file', required=True, help='The reason, read from this file.')
        parser.add_argument('--authorization-ref', default='',
                            help='The ruled act this rests on (the committed declaration and its commit).')

    def handle(self, *args, **options):
        try:
            by = disposal.person(options['by'])
            authorization_ref = disposal.authorization(options['authorization_ref'], required=False)
            try:
                text = Path(options['reason_file']).read_text(encoding='utf-8')
            except (OSError, UnicodeDecodeError) as exc:
                raise CommandError(f'The reason file cannot be read ({type(exc).__name__}).')
            reason = disposal.reason_text(text)
            workspace = models.Workspace.objects.filter(pk=disposal._uuid(options['workspace'], 'The practice')).first()
        except disposal.Refused as exc:
            raise CommandError(' '.join(exc.reasons))
        if workspace is None:
            raise CommandError(f'No practice has the id {options["workspace"]}; nothing was written.')
        try:
            summary = record_bundle.export_practice(workspace, options['out'])
        except record_bundle.ExportRefused as exc:
            raise CommandError(f'{exc} Nothing was written.')
        except (OriginalCorrupted, OSError) as exc:  # the half-written folder is already gone (export_practice)
            raise CommandError(f'A stored file could not be read back unchanged, or lies outside the practice\'s folder '
                               f'({type(exc).__name__}); the export was abandoned and nothing was kept.')
        event = models.DisposalEvent.objects.create(
            stage=models.DisposalEvent.EXPORTED, scope=models.DisposalEvent.WORKSPACE, workspace_id=workspace.pk,
            encounter_ids=summary['encounter_ids'],
            counts={name: summary[name] for name in ('documents', 'destroyed', 'reports', 'decisions', 'answers',
                                                     'audit_rows')},
            files={'files': summary['files'], 'bytes': summary['bytes']}, manifest_digest=summary['manifest_sha256'],
            reason=reason, run_by=by, authorization_ref=authorization_ref)
        self.stdout.write(f'Exported practice {workspace.pk}: {summary["documents"]} document(s) '
                          f'({summary["destroyed"]} destroyed earlier, listed only), {summary["reports"]} report(s), '
                          f'{summary["decisions"]} decision(s), {summary["answers"]} answer(s), {summary["audit_rows"]} '
                          f'audit row(s); {summary["files"]} file(s), {summary["bytes"]} bytes; manifest sha256 '
                          f'{summary["manifest_sha256"]}. DisposalEvent {event.pk} (exported).')
        self.stdout.write('Deliver it through the termination runbook: encrypted, through a time-limited link, logged; '
                          'destroy this copy once the practice confirms receipt.')
