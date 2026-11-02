"""Unit tests for the harness@2 additions to ops/install.py (cpt-studio/HARNESS.md section 11): the license-note phase,
the peer-review stages on an undo, and migration 0008 in the image phase's receipt. No Docker, sudo or network.

Run from cpt-studio/:  python3 -B -m unittest discover -s ops -p 'test_*.py' -v

Every refusal is proven to refuse BEFORE it acts: the acting call (the in-image correction, the close) is recorded and
asserted not to have happened. The in-image scripts themselves (LICENSE_NOTE_FIX, CLOSE_STAGES) also run, as
`manage shell -c` runs them, on a real PostgreSQL database when one is configured the way CI configures it
(CPT_STUDIO_DB_* naming a port that is not the live database's): these tests create a throwaway database there and drop
it again. Without one those tests are skipped, never passed. Synthetic data only.
"""
import ast
import base64
import datetime as dt
import hashlib
import io
import json
import os
import sys
import tarfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import install  # noqa: E402
from test_install import TemporaryDirectoryTest  # noqa: E402

APP_ROOT = Path(__file__).resolve().parents[1]
REVISION = 'a' * 40
OTHER = 'b' * 40
IMAGE = 'sha256:' + 'c' * 64
OLDER_IMAGE = 'sha256:' + 'd' * 64
# The owner's texts (2026-11-01), as the task that ordered this phase gave them.
OLD_NOTE = ('CPT codes are copyright the American Medical Association; descriptors are not imported or displayed. Used '
            'for internal synthetic evaluation only; commercial CPT use requires an AMA license.')
NEW_NOTE = ('CPT codes are copyright the American Medical Association; descriptors are not imported or displayed. CPT '
            'Studio holds no AMA licence; whether its use of CPT content needs one is an open owner decision.')
MIGRATION_0008 = '0008_harness2_exchanges_tools_confirmations'
WHY_0008 = ['FindingConfirmation: a new table no older revision reads',
            'ProviderExchange: a new table no older revision reads',
            'ToolCall: a new table no older revision reads',
            'providerexchange: a constraint on a table this migration creates',
            'toolcall: a constraint on a table this migration creates']


def module_constants(path, names, *, within=None):
    """Literal values of the names assigned in ``path`` (at module level, or in class ``within``), read with ast: no
    Django code is imported here. A tuple of earlier names is resolved."""
    tree = ast.parse(Path(path).read_text(encoding='utf-8'))
    body = tree.body
    if within:
        body = next(node.body for node in body if isinstance(node, ast.ClassDef) and node.name == within)
    found = {}
    for node in body:
        if not (isinstance(node, ast.Assign) and len(node.targets) == 1):
            continue
        target, value = node.targets[0], node.value
        pairs = (list(zip(target.elts, value.elts)) if isinstance(target, ast.Tuple) and isinstance(value, ast.Tuple)
                 else [(target, value)])
        for name, item in pairs:
            if not isinstance(name, ast.Name):
                continue
            if isinstance(item, ast.Tuple) and all(isinstance(e, ast.Name) and e.id in found for e in item.elts):
                found[name.id] = tuple(found[e.id] for e in item.elts)
            else:
                try:
                    found[name.id] = ast.literal_eval(item)
                except (ValueError, TypeError, SyntaxError, MemoryError, RecursionError):
                    pass
    return {name: found[name] for name in names}


def job_kinds():
    return module_constants(APP_ROOT / 'studio' / 'models.py', ('PARTICIPANT_KINDS', 'PEER_KINDS'), within='Job')


# --- the notes --------------------------------------------------------------------------------------------------------

class LicenseNoteTextTests(unittest.TestCase):
    def test_the_two_notes_are_the_owners_texts_exactly(self):
        self.assertEqual(install.LICENSE_NOTE_OLD, OLD_NOTE)
        self.assertEqual(install.LICENSE_NOTE_NEW, NEW_NOTE)
        # the corrected note states a fact, never a permission (HARNESS.md 11.6)
        for wording in ('internal synthetic evaluation', 'commercial', 'requires an AMA license'):
            self.assertNotIn(wording, install.LICENSE_NOTE_NEW)

    def test_the_importer_writes_one_of_the_two_notes_and_never_a_third(self):
        # The phase runs only where the image's importer writes the corrected note (LICENSE_NOTE_FIX refuses otherwise),
        # so the installer's texts must be the importer's: the old one until the importer's correction is merged, the
        # new one after. A third wording is drift between the two packages.
        note = module_constants(APP_ROOT / 'studio' / 'reference' / 'importers.py', ('LICENSE_NOTE',))['LICENSE_NOTE']
        self.assertIn(note, (install.LICENSE_NOTE_OLD, install.LICENSE_NOTE_NEW))


# --- arguments and the phase table ------------------------------------------------------------------------------------

class LicenseNoteArgumentTests(unittest.TestCase):
    BASE = ['--revision', REVISION, '--receipts', '/tmp/receipts', '--phase', 'license-note']

    def test_the_phase_takes_no_argument_of_its_own(self):
        with mock.patch('sys.stderr', io.StringIO()):
            self.assertEqual(install.parse_args(self.BASE).phase, 'license-note')
        self.assertIs(install.PHASES['license-note'], install.phase_license_note)
        for extra in (('--pfs-zip', '/x/a.zip'), ('--provider-mode', 'disabled'), ('--astra-mode', 'live'),
                      ('--access-check',), ('--owner-username', 'owner'), ('--reset-passwords',)):
            with self.subTest(extra=extra), self.assertRaises(SystemExit) as caught, \
                    mock.patch('sys.stderr', io.StringIO()):
                install.parse_args([*self.BASE, *extra])
            self.assertEqual(caught.exception.code, 2)


# --- the phase, with its surroundings replaced ------------------------------------------------------------------------

def counts_answer(**overrides):
    answer = {'rows': 3, 'before': {'old': 2, 'new': 0, 'other': 1}, 'after': {'old': 0, 'new': 2, 'other': 1},
              'updated': 2, 'updated_keys': ['cms-mue-practitioner-2026-q4', 'cms-pfs-rvu26d'],
              'other_keys': ['cms-pfs-synthetic'], 'assessments_with_old_note': 5}
    answer.update(overrides)
    return answer


class LicenseNotePhaseTests(TemporaryDirectoryTest):
    """The REAL phase_license_note; Docker, the database and the in-image script are replaced and recorded."""

    def setUp(self):
        super().setUp()
        self.calls, self.migrated, self.answer = [], 0, counts_answer()

    def oneshot(self, image_id, command, env_bytes, **kwargs):
        self.calls.append(('oneshot', image_id, command, kwargs))
        return SimpleNamespace(returncode=self.migrated, stdout=b'', stderr=b'')

    def app_script(self, image_id, env_bytes, body, params, **kwargs):
        self.calls.append(('script', image_id, body, params, kwargs))
        return self.answer

    def run_phase(self, **patches):
        ctx = install.Context(SimpleNamespace(phase='license-note', revision=REVISION), self.tmp)
        defaults = {'installed_image': mock.Mock(return_value=IMAGE), 'require_db': mock.Mock(),
                    'read_protected_env': mock.Mock(return_value=b'CPT_STUDIO_SECRET_KEY=synthetic\n'),
                    'oneshot': self.oneshot, 'app_script': self.app_script}
        defaults.update(patches)
        with mock.patch.multiple(install, **defaults):
            return install.phase_license_note(ctx)

    def acted(self):
        return [call for call in self.calls if call[0] == 'script']

    def test_it_checks_the_schema_then_corrects_in_this_revisions_image_and_records_the_counts(self):
        details = self.run_phase()
        self.assertEqual([call[0] for call in self.calls], ['oneshot', 'script'])
        _, image, command, kwargs = self.calls[0]
        self.assertEqual((image, command, kwargs), (IMAGE, ['manage', 'migrate', '--check'], {'timeout': 120}))
        _, image, body, params, kwargs = self.calls[1]
        self.assertEqual((image, body), (IMAGE, install.LICENSE_NOTE_FIX))
        self.assertEqual(params, {'old': OLD_NOTE, 'new': NEW_NOTE})
        self.assertEqual(kwargs, {'what': 'Correcting the reference licence note'})
        self.assertEqual({key: details[key] for key in install.LICENSE_NOTE_ANSWER}, counts_answer())
        self.assertEqual((details['old_note'], details['new_note']), (OLD_NOTE, NEW_NOTE))
        self.assertEqual(details['old_note_sha256'], hashlib.sha256(OLD_NOTE.encode()).hexdigest())
        self.assertEqual(details['new_note_sha256'], hashlib.sha256(NEW_NOTE.encode()).hexdigest())
        self.assertEqual(details['image_id'], IMAGE)
        self.assertEqual(details['summary'], 'licence note corrected on 2 reference source(s): '
                                             'cms-mue-practitioner-2026-q4, cms-pfs-rvu26d')

    def test_with_no_old_note_left_it_changes_nothing_and_says_so(self):
        self.answer = counts_answer(before={'old': 0, 'new': 2, 'other': 1}, updated=0, updated_keys=[])
        details = self.run_phase()
        self.assertEqual(details['summary'], 'no reference source holds the old licence note; nothing changed')
        self.assertEqual((details['updated'], details['before'], details['after']),
                         (0, {'old': 0, 'new': 2, 'other': 1}, {'old': 0, 'new': 2, 'other': 1}))
        self.answer = counts_answer(rows=0, before={'old': 0, 'new': 0, 'other': 0},
                                    after={'old': 0, 'new': 0, 'other': 0}, updated=0, updated_keys=[], other_keys=[],
                                    assessments_with_old_note=0)
        self.assertIn('nothing changed', self.run_phase()['summary'])  # no source imported yet

    def test_every_refusal_comes_before_the_correction(self):
        refusals = {
            'no image of this revision': {'installed_image': mock.Mock(side_effect=install.InstallError(
                'No successful --phase image receipt for this revision.'))},
            'no database': {'require_db': mock.Mock(side_effect=install.InstallError(
                'cpt-studio-db is not present; run --phase db first.'))},
            'no secrets': {'read_protected_env': mock.Mock(side_effect=install.InstallError(
                'A protected environment file lacks: CPT_STUDIO_DB_PASSWORD.'))},
        }
        for label, patches in refusals.items():
            self.calls.clear()
            with self.subTest(label), self.assertRaises(install.InstallError):
                self.run_phase(**patches)
            self.assertEqual(self.calls, [])  # not even the schema check ran
        self.calls.clear()
        self.migrated = 1  # migrations pending
        with self.assertRaises(install.InstallError) as caught:
            self.run_phase()
        self.assertIn('run --phase app first. Nothing was changed.', str(caught.exception))
        self.assertEqual(self.acted(), [])

    def test_an_image_whose_importer_writes_another_note_is_refused_with_nothing_changed(self):
        reason = ('this image writes another note on a source it imports (studio.reference.importers.LICENSE_NOTE is '
                  'not the corrected text), so its next import would undo the correction')
        self.answer = {'refused': reason}
        with self.assertRaises(install.InstallError) as caught:
            self.run_phase()
        self.assertEqual(str(caught.exception), f'{reason}; nothing was changed. Install a revision whose importer '
                                                'writes the corrected note, then run this phase.')
        self.assertEqual(caught.exception.details, {'refused': reason})

    def test_an_answer_that_does_not_add_up_fails_the_phase(self):
        cases = {
            'not the counts': {'closed': 2},
            'not a dict': ['rows', 3],
            'a count that is not a number': counts_answer(updated='2'),
            'more updated than were old': counts_answer(updated=3),
            'an old note left': counts_answer(after={'old': 1, 'new': 1, 'other': 1}),
            'another note changed': counts_answer(after={'old': 0, 'new': 3, 'other': 0}),
            'a row gained': counts_answer(rows=4),
            'keys that do not match the count': counts_answer(updated_keys=['cms-pfs-rvu26d']),
            'other keys that do not match the count': counts_answer(other_keys=[]),
            'no assessment count': {key: value for key, value in counts_answer().items()
                                    if key != 'assessments_with_old_note'},
        }
        for label, answer in cases.items():
            self.answer = answer
            with self.subTest(label), self.assertRaises(install.InstallError) as caught:
                self.run_phase()
            self.assertIn('The licence note correction answered, but', str(caught.exception))
            self.assertIn('Run --phase license-note again', str(caught.exception))
            self.assertEqual(caught.exception.details, {'answer': answer})

    def test_the_problem_reader(self):
        self.assertEqual(install.license_note_problem(counts_answer()), '')
        self.assertEqual(install.license_note_problem(counts_answer(before={'old': 0, 'new': 2, 'other': 1},
                                                                    updated=0, updated_keys=[])), '')
        self.assertEqual(install.license_note_problem(None), 'its answer is not the counts this phase reads')
        self.assertEqual(install.license_note_problem(counts_answer(before={'old': 2, 'new': 0})),
                         'its answer is not the counts this phase reads')
        self.assertIn('do not add up', install.license_note_problem(counts_answer(updated=1)))

    def test_through_main_the_receipt_records_both_texts_and_the_counts(self):
        receipts = self.tmp / 'receipts'
        stdout = io.StringIO()
        umask = os.umask(0o077)
        os.umask(umask)
        try:
            with mock.patch.multiple(install, installed_image=mock.Mock(return_value=IMAGE), require_db=mock.Mock(),
                                     read_protected_env=mock.Mock(return_value=b''), oneshot=self.oneshot,
                                     app_script=self.app_script,
                                     check_door=mock.Mock(return_value={'declaration_commit': OTHER}),
                                     check_tree=mock.Mock(return_value={'mode': 'exact'})), \
                    mock.patch('sys.stdout', stdout):
                code = install.main(['--phase', 'license-note', '--revision', REVISION, '--receipts', str(receipts)])
        finally:
            os.umask(umask)
        self.assertEqual(code, 0, stdout.getvalue())
        line = json.loads(stdout.getvalue())
        self.assertEqual((line['phase'], line['ok']), ('license-note', True))
        record = json.loads(Path(line['receipt']).read_text())
        self.assertEqual(Path(line['receipt']).name[:len('license-note-')], 'license-note-')
        self.assertTrue(record['ok'])
        for key, value in counts_answer().items():
            self.assertEqual(record['details'][key], value)
        self.assertEqual((record['details']['old_note'], record['details']['new_note']), (OLD_NOTE, NEW_NOTE))


# --- the peer reviews on an undo --------------------------------------------------------------------------------------

class PeerStagesOnUndoTests(TemporaryDirectoryTest):
    """harness@2's stage kinds astra_peer and fable_peer (Job.PEER_KINDS) are closed, as astra and fable are, by every
    undo whose next worker does not run them; one that does keeps them."""

    def pair(self, revision=REVISION, image=IMAGE):
        return {role: {'Id': f'{role}-id', 'Image': image, 'Created': '2026-11-01T12:00:00.000000Z',
                       'State': {'Running': True},
                       'Config': {'Labels': {install.LABEL: '1', install.ROLE_LABEL: role,
                                             install.REVISION_LABEL: revision}}}
                for role in ('web', 'worker')}

    def test_the_peer_kinds_are_the_models_and_no_worker_before_harness2_runs_them(self):
        kinds = job_kinds()
        self.assertEqual(kinds, {'PARTICIPANT_KINDS': ('astra', 'fable'), 'PEER_KINDS': ('astra_peer', 'fable_peer')})
        for kind in kinds['PARTICIPANT_KINDS'] + kinds['PEER_KINDS']:
            self.assertNotIn(kind, install.COMMON_STAGE_KINDS)
        # with no next worker to ask, the close keeps only the four common kinds: every harness stage is closed
        self.assertEqual(install.stage_kinds_of(None, b''), list(install.COMMON_STAGE_KINDS))
        self.assertEqual(install.stage_kinds_of('not-an-image-id', b''), list(install.COMMON_STAGE_KINDS))
        with mock.patch.object(install, 'app_script', side_effect=install.InstallError('the image did not answer')):
            self.assertEqual(install.stage_kinds_of(OLDER_IMAGE, b''), list(install.COMMON_STAGE_KINDS))
        self.assertIn('Job.objects.exclude(kind__in=kept)', install.CLOSE_STAGES)

    def rollback(self, parked_kinds):
        """phase_rollback_app over this revision's pair, a parked pair whose worker runs ``parked_kinds``."""
        live = {install.SERVICES[role]: container for role, container in self.pair().items()}
        live.update({install.SERVICES[role] + '-previous': container
                     for role, container in self.pair(OTHER, OLDER_IMAGE).items()})
        closed = {}

        def docker(*args, **kwargs):
            if args[0] == 'rm':
                for name, container in list(live.items()):
                    if container['Id'] == args[2] and not name.endswith('-previous'):
                        del live[name]
            return SimpleNamespace(returncode=0, stdout=b'', stderr=b'')

        def script(image_id, env_bytes, body, params, **kwargs):
            self.assertEqual((image_id, body), (OLDER_IMAGE, install.UNRUNNABLE_STAGES))  # asked of the next worker
            return {'known': parked_kinds, 'stuck': 0, 'kinds': []}

        def close(image_id, env_bytes, since, revision, reason, kinds):
            closed.update(image=image_id, kinds=kinds)
            return {'closed': 2, 'kinds': ['astra_peer', 'fable_peer'], 'hazards': {}, 'relabel': []}
        with mock.patch.multiple(install, inspect=mock.Mock(side_effect=lambda kind, name: live.get(name)),
                                 docker=docker, read_protected_env=mock.Mock(return_value=b''),
                                 require_db=mock.Mock(), undo_hazards=mock.Mock(return_value={}),
                                 app_script=script, close_undone_stages=close,
                                 put_back_states=mock.Mock(return_value={'encounters': 0, 'changed': {}})):
            details = install.phase_rollback_app(install.Context(SimpleNamespace(phase='rollback-app',
                                                                                 revision=REVISION), self.tmp))
        return closed, details

    def test_rollback_app_closes_with_the_next_workers_own_kinds(self):
        # a next worker that runs the participants' first readings but no peer review keeps astra and fable stages and
        # closes the peer reviews; one before the harness runs neither
        harness1 = ['analyze', 'assess', 'astra', 'extract', 'fable', 'predict', 'review2']
        for kinds in (harness1, ['analyze', 'assess', 'extract', 'predict', 'review2']):
            with self.subTest(kinds=kinds):
                closed, details = self.rollback(kinds)
                self.assertEqual(closed, {'image': IMAGE, 'kinds': kinds})  # closed with the undone pair's image
                for peer in job_kinds()['PEER_KINDS']:
                    self.assertNotIn(peer, closed['kinds'])
                self.assertEqual(details['stages_closed']['kinds'], ['astra_peer', 'fable_peer'])

    def test_a_failed_replacement_closes_with_the_parked_workers_kinds(self):
        old = self.pair(OTHER, OLDER_IMAGE)
        live = {install.SERVICES[role]: container for role, container in old.items()}
        closed = {}

        def docker(*args, **kwargs):
            if args[0] == 'rename':
                live[args[2]] = live.pop(args[1])
            elif args[0] == 'run':
                name = args[args.index('--name') + 1]
                role = 'web' if name == install.SERVICES['web'] else 'worker'
                live[name] = {**old[role], 'Id': f'new-{role}', 'Image': IMAGE}
            elif args[0] == 'rm':
                for name, container in list(live.items()):
                    if container['Id'] == args[2]:
                        del live[name]
            return SimpleNamespace(returncode=0, stdout=b'', stderr=b'')

        def wait(role, revision, image_id):
            if role == 'worker':
                raise install.InstallError('cpt-studio-worker did not become ready')
            return {'id': 'new-web'}

        def close(image_id, env_bytes, since, revision, reason, kinds):
            closed.update(image=image_id, kinds=kinds, reason=reason)
            return {'closed': 1, 'kinds': ['astra_peer'], 'hazards': {}, 'relabel': []}
        parked_kinds = ['analyze', 'assess', 'extract', 'predict', 'review2']
        ctx = install.Context(SimpleNamespace(phase='app', revision=REVISION), self.tmp)
        with mock.patch.multiple(install, inspect=mock.Mock(side_effect=lambda kind, name: live.get(name)),
                                 docker=docker, wait_service=wait, close_undone_stages=close,
                                 app_script=mock.Mock(return_value={'known': parked_kinds, 'stuck': 0, 'kinds': []}),
                                 put_back_states=mock.Mock(return_value={'encounters': 0, 'changed': {}})), \
                self.assertRaises(install.InstallError):
            install.replace_services(ctx, IMAGE, b'', 'disabled', '', {'astra': 'live', 'fable': 'live'})
        self.assertEqual(closed['image'], IMAGE)
        self.assertEqual(closed['kinds'], parked_kinds)
        self.assertEqual(closed['reason'], 'its installation failed and the previous revision was restored')
        self.assertEqual({name: container['Id'] for name, container in live.items()},
                         {install.SERVICES['web']: 'web-id', install.SERVICES['worker']: 'worker-id'})


# --- migration 0008 in the image phase's receipt ----------------------------------------------------------------------

class MigrationReceiptTests(TemporaryDirectoryTest):
    def archive(self):
        """git archive of a revision whose migrations are the committed ones, as the image phase reads it."""
        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode='w') as tar:
            for directory in ('cpt-studio', 'cpt-studio/studio', 'cpt-studio/studio/migrations', 'cpt-studio/deploy'):
                info = tarfile.TarInfo(directory)
                info.type = tarfile.DIRTYPE
                info.mode = 0o755
                tar.addfile(info)
            files = {f'cpt-studio/studio/migrations/{path.name}': path.read_bytes()
                     for path in sorted((APP_ROOT / 'studio' / 'migrations').glob('*.py'))}
            files.update({'cpt-studio/deploy/.dockerignore': b'', 'cpt-studio/deploy/Dockerfile': b'FROM synthetic\n'})
            for name, data in files.items():
                info = tarfile.TarInfo(name)
                info.size, info.mode = len(data), 0o644
                tar.addfile(info, io.BytesIO(data))
        return buffer.getvalue()

    def test_the_image_phase_accepts_0008_and_its_receipt_says_why(self):
        image = {'Id': IMAGE, 'Size': 1,
                 'Config': {'User': f'{install.APP_UID}:{install.APP_UID}',
                            'Env': [f'CPT_STUDIO_RELEASE_SHA={REVISION}'],
                            'Labels': {install.LABEL: '1', install.ROLE_LABEL: 'app-image',
                                       install.REVISION_LABEL: REVISION}}}
        built = []

        def docker(*args, **kwargs):
            built.append(args[0] if args[0] == 'build' else args[-1])
            if '--list-langs' in args:
                return SimpleNamespace(returncode=0, stdout=b'List of available languages (2):\neng\nosd\n', stderr=b'')
            if '--version' in args:
                return SimpleNamespace(returncode=0, stdout=b'tesseract 5.3.4\n', stderr=b'')
            if 'pdftoppm' in args:
                return SimpleNamespace(returncode=0, stdout=b'', stderr=b'pdftoppm version 24.02.0\n')
            return SimpleNamespace(returncode=0, stdout=b'', stderr=b'')
        receipts = self.tmp / 'receipts'
        stdout = io.StringIO()
        umask = os.umask(0o077)
        os.umask(umask)
        try:
            with mock.patch.multiple(install, run=mock.Mock(return_value=SimpleNamespace(returncode=0,
                                                                                       stdout=self.archive())),
                                     docker=docker, inspect=mock.Mock(return_value=image),
                                     check_door=mock.Mock(return_value={'declaration_commit': OTHER}),
                                     check_tree=mock.Mock(return_value={'mode': 'exact'})), \
                    mock.patch('sys.stdout', stdout):
                code = install.main(['--phase', 'image', '--revision', REVISION, '--receipts', str(receipts)])
        finally:
            os.umask(umask)
        self.assertEqual(code, 0, stdout.getvalue())
        self.assertEqual(built[0], 'build')  # the gate passed: the build ran
        record = json.loads(Path(json.loads(stdout.getvalue())['receipt']).read_text())
        migrations = record['details']['migrations']
        self.assertEqual(migrations['baseline'], '0005')
        self.assertEqual(sorted(migrations['after_baseline']), ['0006_services_completeness_second_review',
                                                                '0007_harness_participants_retrieval', MIGRATION_0008])
        self.assertEqual(migrations['after_baseline'][MIGRATION_0008], {'safe': True, 'why': WHY_0008})
        self.assertTrue(all(verdict['safe'] for verdict in migrations['after_baseline'].values()))

    def test_0008_adds_no_column_to_an_existing_table(self):
        tree = ast.parse((APP_ROOT / 'studio' / 'migrations' / f'{MIGRATION_0008}.py').read_text(encoding='utf-8'))
        migration = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == 'Migration')
        operations = next(item.value for item in migration.body
                          if isinstance(item, ast.Assign) and item.targets[0].id == 'operations')
        kinds = [install._call(element)[0] for element in operations.elts]
        self.assertEqual(kinds, ['CreateModel', 'CreateModel', 'CreateModel', 'AddConstraint', 'AddConstraint'])
        # control: the same check refuses 0008 with a NOT NULL column added to an existing table
        source = (APP_ROOT / 'studio' / 'migrations' / f'{MIGRATION_0008}.py').read_text(encoding='utf-8')
        anchor = '    operations = [\n'
        self.assertEqual(source.count(anchor), 1)
        mutated = source.replace(anchor, anchor + "        migrations.AddField(model_name='providerrun', name='loop', "
                                                  "field=models.CharField(default='', max_length=8)),\n")
        self.assertNotEqual(mutated, source)
        verdict = install.migration_verdict(mutated)
        self.assertFalse(verdict['safe'])
        self.assertEqual(verdict['why'], ['providerrun.loop: NOT NULL with no database default, so an older pair\'s '
                                          'insert is refused'])


# --- the in-image scripts on a real database --------------------------------------------------------------------------

LIVE_DB_PORT = install.DB_PORT  # the live database's port, also the settings' default: never connected to here
_DATABASE = {}


def port_number(value):
    try:
        return int(str(value).strip())
    except ValueError:
        return None


def database_problem() -> str:
    """Why the database tests cannot run here ('' when they can): they need the variables CI sets, naming a disposable
    PostgreSQL, never the live database."""
    needed = ('CPT_STUDIO_SECRET_KEY', 'CPT_STUDIO_DB_PASSWORD', 'CPT_STUDIO_DB_HOST', 'CPT_STUDIO_DB_PORT')
    missing = [name for name in needed if not os.environ.get(name)]
    if missing:
        return 'no disposable database is configured (' + ', '.join(missing) + ' not set)'
    port = port_number(os.environ['CPT_STUDIO_DB_PORT'])
    if port is None or port == LIVE_DB_PORT:
        return f'CPT_STUDIO_DB_PORT is not a disposable database\'s port (the live one is {LIVE_DB_PORT}); refused'
    if os.environ.get('CPT_STUDIO_PROVIDER_MODE', 'disabled') != 'disabled':
        return 'these tests run with CPT_STUDIO_PROVIDER_MODE=disabled only'
    if os.environ.get('DJANGO_SETTINGS_MODULE', 'cptstudio.settings') != 'cptstudio.settings':
        return 'DJANGO_SETTINGS_MODULE names other settings'
    try:
        import django  # noqa: F401
    except ImportError:
        return 'Django is not installed here'
    return ''


def database():
    """The throwaway database these tests share (migrated; created once, dropped by tearDownModule). Its name is the
    run's test-database name with '_installer' appended, so a Django suite running beside it never shares it."""
    if 'connection' not in _DATABASE:
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'cptstudio.settings')
        if str(APP_ROOT) not in sys.path:
            sys.path.insert(0, str(APP_ROOT))
        import django
        django.setup()
        from django.conf import settings
        from django.db import connection
        if port_number(settings.DATABASES['default']['PORT']) in (None, LIVE_DB_PORT):
            raise unittest.SkipTest('the settings name the live database, or no port; refused')
        test = dict(connection.settings_dict.get('TEST') or {})
        test['NAME'] = f"test_cptstudio_{os.environ.get('CPT_STUDIO_TEST_DB_SUFFIX') or 'default'}_installer"
        connection.settings_dict['TEST'] = test
        _DATABASE['old_name'] = connection.creation.create_test_db(verbosity=0, autoclobber=True, serialize=False)
        _DATABASE['connection'] = connection
    return _DATABASE['connection']


def tearDownModule():
    if 'connection' in _DATABASE:
        connection = _DATABASE.pop('connection')
        connection.creation.destroy_test_db(_DATABASE.pop('old_name'), verbosity=0)


def run_in_image(body, params):
    """``body`` as `manage shell -c` runs it in the image (app_script's prelude first), here, on the test database."""
    payload = base64.b64encode(json.dumps(params).encode()).decode()
    lines = []
    namespace = {'print': lambda *args, **kwargs: lines.append(' '.join(str(a) for a in args))}
    exec(compile(install.APP_SCRIPT_PRELUDE.format(payload=payload, answer=install.APP_SCRIPT_ANSWER) + body,
                 '<app-script>', 'exec'), namespace)
    answers = [line for line in lines if line.startswith(install.APP_SCRIPT_ANSWER)]
    assert len(answers) == 1, lines
    return json.loads(answers[0][len(install.APP_SCRIPT_ANSWER):])


class DatabaseGuardTests(unittest.TestCase):
    def test_the_live_database_is_never_used_and_an_unset_one_is_a_skip(self):
        base = {'CPT_STUDIO_SECRET_KEY': 'synthetic-key', 'CPT_STUDIO_DB_PASSWORD': 'synthetic-password',
                'CPT_STUDIO_DB_HOST': '127.0.0.1', 'CPT_STUDIO_PROVIDER_MODE': 'disabled'}
        for port in ('55451', ' 55451', '055451', 'live', ''):
            with self.subTest(port=port), mock.patch.dict(os.environ, {**base, 'CPT_STUDIO_DB_PORT': port}, clear=True):
                self.assertTrue(database_problem())
        with mock.patch.dict(os.environ, base, clear=True):
            self.assertIn('CPT_STUDIO_DB_PORT not set', database_problem())
        with mock.patch.dict(os.environ, {**base, 'CPT_STUDIO_DB_PORT': '55461', 'CPT_STUDIO_PROVIDER_MODE': 'live'},
                             clear=True):
            self.assertIn('disabled only', database_problem())
        with mock.patch.dict(os.environ, {**base, 'CPT_STUDIO_DB_PORT': '55461'}, clear=True):
            self.assertIn(database_problem(), ('', 'Django is not installed here'))


class DatabaseTest(unittest.TestCase):
    """Each test runs in a transaction that is rolled back when it ends."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        problem = database_problem()
        if problem:
            raise unittest.SkipTest(problem)
        database()

    def setUp(self):
        super().setUp()
        from django.db import transaction
        atomic = transaction.atomic()
        atomic.__enter__()

        def rollback():
            transaction.set_rollback(True)
            atomic.__exit__(None, None, None)
        self.addCleanup(rollback)

    def encounter(self, tag):
        """A workspace, member, encounter and its current revision (pasted, not yet extracted). Synthetic."""
        from django.utils import timezone
        from studio import models
        category, _ = models.Category.objects.get_or_create(slug='synthetic-gi', defaults={
            'name': 'Synthetic GI', 'profiles_version': 'synthetic@1'})
        workspace = models.Workspace.objects.create(name=f'Synthetic {tag}', category=category)
        user = models.User.objects.create(username=f'synthetic-{tag}')
        encounter = models.Encounter.objects.create(workspace=workspace, title=f'Synthetic {tag}', created_by=user)
        revision = models.SourceRevision.objects.create(
            encounter=encounter, number=1, kind=models.SourceRevision.PASTE, pasted_text='Synthetic colonoscopy note.',
            synthetic_attested_by=user, synthetic_attested_at=timezone.now(), created_by=user)
        encounter.current_revision = revision
        encounter.save(update_fields=['current_revision', 'updated_at'])
        return encounter


class LicenseNoteOnTheDatabaseTests(DatabaseTest):
    """LICENSE_NOTE_FIX on real rows: exactly the old note becomes exactly the new one, nothing else changes, and a
    second run changes nothing."""

    def source(self, key, note, **fields):
        from studio import models
        values = dict(key=key, kind='cms-pfs', publisher='Centers for Medicare & Medicaid Services (CMS)',
                      title=f'Synthetic source {key}', release='SYN1',
                      url='https://www.cms.gov/files/zip/synthetic.zip',
                      sha256=hashlib.sha256(key.encode()).hexdigest(),
                      retrieved_at=dt.datetime(2026, 10, 23, 20, 59, tzinfo=dt.timezone.utc),
                      effective_start=dt.date(2026, 10, 1), effective_end=dt.date(2026, 12, 31), license_note=note,
                      scope_note='Synthetic scope note', row_count=3)
        values.update(fields)
        return models.ReferenceSource.objects.create(**values)

    def rows(self):
        from studio import models
        return list(models.ReferenceSource.objects.order_by('key').values())

    def fix(self, importer_note=NEW_NOTE):
        with mock.patch('studio.reference.importers.LICENSE_NOTE', importer_note):
            return run_in_image(install.LICENSE_NOTE_FIX, {'old': install.LICENSE_NOTE_OLD,
                                                           'new': install.LICENSE_NOTE_NEW})

    def test_exactly_the_old_note_is_replaced_and_a_second_run_changes_nothing(self):
        from studio import models
        self.source('cms-pfs-rvu26d', OLD_NOTE)
        self.source('cms-mue-practitioner-2026-q4', OLD_NOTE, kind='cms-mue-practitioner')
        self.source('cms-pfs-already', NEW_NOTE, release='SYN2')
        self.source('cms-pfs-spaced', OLD_NOTE + ' ', release='SYN3')  # differs by one space: another note
        self.source('cms-pfs-other', 'Recorded licence wording.', release='SYN4')
        passage = models.PassageSource.objects.create(
            key='cms-synthetic-passages', kind='cms-ncci-policy-manual', publisher='CMS', title='Synthetic passages',
            release='SYN', url='https://www.cms.gov/files/synthetic.pdf', sha256='0' * 64,
            retrieved_at=dt.datetime(2026, 11, 1, tzinfo=dt.timezone.utc), effective_start=dt.date(2026, 1, 1),
            effective_end=dt.date(2026, 12, 31), license_note=OLD_NOTE, scope_note='Synthetic')
        before = self.rows()
        answer = self.fix()
        self.assertEqual(answer, {
            'rows': 5, 'before': {'old': 2, 'new': 1, 'other': 2}, 'after': {'old': 0, 'new': 3, 'other': 2},
            'updated': 2, 'updated_keys': ['cms-mue-practitioner-2026-q4', 'cms-pfs-rvu26d'],
            'other_keys': ['cms-pfs-other', 'cms-pfs-spaced'], 'assessments_with_old_note': 0})
        self.assertEqual(install.license_note_problem(answer), '')
        after = self.rows()
        corrected = {'cms-mue-practitioner-2026-q4', 'cms-pfs-rvu26d'}
        self.assertEqual(after, [dict(row, license_note=NEW_NOTE) if row['key'] in corrected else row
                                 for row in before])  # every other column of every row, and every other row, as it was
        self.assertEqual(models.PassageSource.objects.get(pk=passage.pk).license_note, OLD_NOTE)  # never touched
        again = self.fix()
        self.assertEqual(again, {
            'rows': 5, 'before': {'old': 0, 'new': 3, 'other': 2}, 'after': {'old': 0, 'new': 3, 'other': 2},
            'updated': 0, 'updated_keys': [], 'other_keys': ['cms-pfs-other', 'cms-pfs-spaced'],
            'assessments_with_old_note': 0})
        self.assertEqual(self.rows(), after)

    def test_with_no_source_it_answers_zero_and_changes_nothing(self):
        self.assertEqual(self.fix(), {'rows': 0, 'before': {'old': 0, 'new': 0, 'other': 0},
                                      'after': {'old': 0, 'new': 0, 'other': 0}, 'updated': 0, 'updated_keys': [],
                                      'other_keys': [], 'assessments_with_old_note': 0})

    def test_an_importer_still_writing_the_old_note_is_refused_before_anything_changes(self):
        self.source('cms-pfs-rvu26d', OLD_NOTE)
        before = self.rows()
        for importer_note in (OLD_NOTE, NEW_NOTE + ' ', None):
            with self.subTest(importer_note=importer_note):
                answer = self.fix(importer_note)
                self.assertEqual(list(answer), ['refused'])
                self.assertIn('so its next import would undo the correction', answer['refused'])
                self.assertEqual(self.rows(), before)

    def test_recorded_assessments_keep_the_note_they_were_made_with_and_are_counted(self):
        from studio import models
        source = self.source('cms-pfs-rvu26d', OLD_NOTE)
        encounter = self.encounter('assessed')
        revision = encounter.current_revision
        context = models.EncounterContext.objects.create(encounter=encounter, revision=revision, facts={},
                                                         version='synthetic@1', sha256='1' * 64)
        routing = models.RoutingRun.objects.create(revision=revision, version='synthetic@1', result={}, sha256='2' * 64)
        entries = [{'key': source.key, 'license_note': OLD_NOTE, 'scope_note': 'Synthetic scope note'},
                   {'key': 'ama-cpt', 'license_note': 'No CPT edition is licensed.', 'scope_note': 'NOT CONNECTED'}]
        assessment = models.Assessment.objects.create(
            encounter=encounter, revision=revision, context=context, routing=routing, profiles_version='synthetic@1',
            engine_version='synthetic@1', reference_sources=entries, sha256='3' * 64)
        answer = self.fix()
        self.assertEqual((answer['updated'], answer['assessments_with_old_note']), (1, 1))
        self.assertEqual(models.Assessment.objects.get(pk=assessment.pk).reference_sources, entries)  # never rewritten

    def test_a_correction_that_would_change_anything_else_is_rolled_back(self):
        # A trigger (synthetic, rolled back with the test) changes another column whenever a note changes: the script's
        # own before-and-after reading must refuse that and leave every row as it was.
        from django.db import connection
        self.source('cms-pfs-rvu26d', OLD_NOTE)
        before = self.rows()
        with connection.cursor() as cursor:
            cursor.execute("CREATE FUNCTION synthetic_touch() RETURNS trigger AS $$ BEGIN "
                           "NEW.scope_note := NEW.scope_note || ' (touched)'; RETURN NEW; END $$ LANGUAGE plpgsql")
            cursor.execute('CREATE TRIGGER synthetic_touch BEFORE UPDATE ON studio_referencesource '
                           'FOR EACH ROW EXECUTE FUNCTION synthetic_touch()')
        with self.assertRaisesRegex(RuntimeError, 'would have changed more than the old notes; nothing was changed'):
            self.fix()
        self.assertEqual(self.rows(), before)


class PeerStagesOnTheDatabaseTests(DatabaseTest):
    """CLOSE_STAGES on real rows: a peer-review stage the next worker cannot run is closed as failed with the
    installer's message; one it can run, and the participants' first readings when it runs them, are kept."""

    NOTE = 'Closed by the installer: its web and worker were removed (rollback-app) (revision aaaaaaaaaaaa), so this ' \
           'stage will not run. Change the context, add an addendum or upload the document again to process it.'

    def job(self, encounter, kind, state):
        from django.utils import timezone
        from studio import models
        return models.Job.objects.create(
            encounter=encounter, revision=encounter.current_revision, kind=kind, state=state,
            idempotency_key=f'{kind}:{encounter.pk}:{state}', deadline_at=timezone.now() + dt.timedelta(minutes=10),
            started_at=timezone.now() if state == models.Job.RUNNING else None)

    def close(self, kinds):
        from django.utils import timezone
        since = timezone.now()  # every job below was created before: only the kinds decide what is closed
        return run_in_image(install.CLOSE_STAGES, {'since': since.isoformat(), 'note': self.NOTE, 'kinds': kinds})

    def stages(self, encounters):
        from studio import models
        return {(job.encounter_id, job.kind): (job.state, job.error)
                for job in models.Job.objects.filter(encounter__in=encounters)}

    def scenario(self):
        from studio import models
        queued = self.encounter('queued')
        for kind in ('astra', 'fable', 'astra_peer'):
            self.job(queued, kind, models.Job.QUEUED)
        running = self.encounter('running')
        self.job(running, 'fable_peer', models.Job.RUNNING)
        stopped = self.encounter('stopped')  # a peer review a member stopped: its encounter's latest stage, resumable
        self.job(stopped, 'astra_peer', models.Job.CANCELLED)
        return queued, running, stopped

    def test_a_next_worker_without_peer_reviews_has_them_closed_and_keeps_the_first_readings(self):
        from studio import models
        queued, running, stopped = self.scenario()
        kinds = sorted([*install.COMMON_STAGE_KINDS, 'astra', 'fable', 'review2'])
        answer = self.close(kinds)
        self.assertEqual((answer['closed'], answer['kinds'], answer['encounters']),
                         (3, ['astra_peer', 'fable_peer'], 3))
        failed = (models.Job.FAILED, self.NOTE)
        self.assertEqual(self.stages([queued, running, stopped]), {
            (queued.pk, 'astra'): (models.Job.QUEUED, ''), (queued.pk, 'fable'): (models.Job.QUEUED, ''),
            (queued.pk, 'astra_peer'): failed, (running.pk, 'fable_peer'): failed, (stopped.pk, 'astra_peer'): failed})

    def test_with_no_next_worker_to_ask_every_harness_stage_is_closed(self):
        from studio import models
        queued, running, stopped = self.scenario()
        answer = self.close(list(install.COMMON_STAGE_KINDS))
        self.assertEqual(answer['kinds'], ['astra', 'astra_peer', 'fable', 'fable_peer'])
        self.assertEqual(set(self.stages([queued, running, stopped]).values()), {(models.Job.FAILED, self.NOTE)})

    def test_controls_a_next_worker_that_runs_them_keeps_them_all(self):
        from studio import models
        queued, running, stopped = self.scenario()
        before = self.stages([queued, running, stopped])
        kinds = sorted([*install.COMMON_STAGE_KINDS, 'astra', 'astra_peer', 'fable', 'fable_peer', 'review2'])
        answer = self.close(kinds)
        self.assertEqual((answer['closed'], answer['kinds']), (0, []))
        self.assertEqual(self.stages([queued, running, stopped]), before)
        self.assertNotIn(models.Job.FAILED, {state for state, _ in before.values()})


if __name__ == '__main__':
    unittest.main()
