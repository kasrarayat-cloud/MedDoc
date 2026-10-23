"""Run independently adjudicated, withheld cases through the real pipeline and score them per family.

Refuses manifests that are not marked adjudicated + withheld (studio.evaluation).
Provider usage follows the installation's provider mode and every send rule
(single flight, reuse of identical requests, no automatic retry).
"""
import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from studio import evaluation, jobs, models, serializers
from studio.access import active_membership
from studio.intake import create_encounter


class Command(BaseCommand):
    help = 'Score the pipeline on an adjudicated, withheld case manifest; per-family metrics only.'

    def add_arguments(self, parser):
        parser.add_argument('--manifest', required=True)
        parser.add_argument('--username', required=True, help='an owner/reviewer of the evaluation workspace')
        parser.add_argument('--out', required=True)

    def handle(self, *args, **options):
        try:
            cases = evaluation.load_manifest(options['manifest'])
        except evaluation.ManifestRefused as exc:
            raise CommandError(str(exc))
        user = models.User.objects.filter(username=options['username']).first()
        if user is None:
            raise CommandError('Unknown user.')
        membership = active_membership(user)
        if not membership.can_review:
            raise CommandError('The evaluation user must be an owner or reviewer.')
        base = Path(options['manifest']).resolve().parent
        scored = []
        for case in cases:
            path = (base / case.document).resolve()
            if base not in path.parents:
                raise CommandError(f'Case {case.case_id} document escapes the manifest directory.')
            if case.delivery == 'paste':
                encounter = create_encounter(membership=membership, user=user, title=f'Evaluation {case.case_id}',
                                             text=path.read_text(encoding='utf-8'))
            else:
                encounter = create_encounter(membership=membership, user=user, title=f'Evaluation {case.case_id}',
                                             data=path.read_bytes(), filename=path.name)
            while (job := jobs.claim_next()) is not None:
                jobs.run_job(job)
            encounter.refresh_from_db()
            detail = serializers.encounter_detail(encounter, membership)
            proposals = (detail['assessment'] or {}).get('proposals', [])
            scored.append({'case_id': case.case_id, 'encounter_id': str(encounter.pk), 'state': encounter.state,
                           'families': evaluation.score_case(case, proposals)})
            self.stdout.write(f'{case.case_id}: {encounter.state}')
        report = {'cases': scored, 'per_family': evaluation.aggregate(scored),
                  'note': 'Per-family metrics only; modifiers are never produced by this release.'}
        Path(options['out']).write_text(json.dumps(report, indent=2, sort_keys=True), encoding='utf-8')
        self.stdout.write(f'wrote {options["out"]}')
