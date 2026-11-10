"""The new-path call-guard matrix (Gemini migration slice S12; design/FINAL.md 10.4(1) and (3), as
design/ADJUDICATION.md R-6 amends them; DECISIONS D17 and D22). Synthetic data only; nothing is sent.

On the new path Gemini is the only interpreter (P1): no code object of the legacy reader executes during new-path work.
The matrix runs every way into the application on new-path encounters in every state FINAL 10.4(1) names, and the
production sentinel - its CALL-level checks on, as tests run it - counts what ran (tests/guard_support.py).

What each class proves:
- GeneratedTests: the matrix is generated, never hand-listed - from cptstudio/urls.py's patterns, jobs.STAGES' keys and
  the scripts and commands ops/install.py runs in an image of the app - so a pattern, a stage kind or an in-image script
  added there and not driven is reported missing (a planted one of each is, in every form the installer can name one:
  positional or keyword, a list spelled out, a local assigned one, a function returning one, an entrypoint role); a form
  the generator cannot read raises naming its line, never dropped (fail-closed: a planted one of each); an exemption
  names something the installer runs and says why it reads no encounter row.
- NewPathOnlyDatabaseTests (R-6): on a database that holds ONLY new-path encounters, every generated item runs and the
  sentinel counts NOTHING under any label - new_path, other, unscoped, or legacy_record - so neither the list, session
  and operator-list loops (which label per row) nor the in-image scripts (which run with no scope, and meet two members'
  answers left standing: UNDO_HAZARDS names exactly those) run legacy code on a new-path row; FINAL 10.4(1)'s list
  (FACETS) is met entry by entry, and no write gate tripped.
- BesideLegacyRecordsTests: the same matrix where the database also holds encounters the legacy reader read (the
  test-only legacy chain): zero new_path executions, and nothing under other or unscoped either, while the legacy
  rows' own reads in the matrix's lists ran legacy code as legacy_record (the archived reader serving the records it
  made, which D22 reports as residual legacy execution).
- PositiveControlTests (FINAL 10.4(3); an instrument that never fires proves nothing): the legacy chain run inside a
  new_path scope records hits in every class - a gi function, an engine or reconcile function, a legacy regex (CALL) and
  a legacy cache wrapper (CALL); and the matrix's own recorder turns red for each class under each label it judges - a
  request naming a new-path encounter (new_path), a request naming none (other), a stage (new_path) and an in-image
  script (unscoped).
"""
from __future__ import annotations

import re
from unittest import mock

from django.http import HttpResponse
from django.test import SimpleTestCase
from django.urls import URLPattern, get_resolver, path

from studio import customer_api, jobs, models, review
from studio.gi import cues, structure
from studio.interpretation import readers, sentinel
from studio.validation import reconcile
from tests import guard_support
from tests.guard_support import (APP, CACHE, CODE, IN_IMAGE_EXEMPT, INSTALL, LABELS, LEGACY, NEW, OTHER, REGEX,
                                 UNSCOPED, WORKER, GuardCase, LegacyWorld, Matrix, World, generated, in_image,
                                 in_process_children, installer, legacy_chain, stage_kinds, tagged, url_routes)
from tests.support import factories as f
from tests.test_pipeline_assess_events import two_procedures


class GeneratedTests(SimpleTestCase):
    def test_the_items_are_read_from_the_url_map_the_stages_and_the_installer(self):
        measured = [str(pattern.pattern) for pattern in get_resolver().url_patterns if isinstance(pattern, URLPattern)]
        self.assertEqual(url_routes(), measured)
        self.assertEqual(len(set(measured)), len(measured))
        self.assertIn('api/encounters/<uuid:encounter_id>/retry-reading', measured)
        self.assertEqual(stage_kinds(), sorted(jobs.STAGES))
        self.assertIn(jobs.INTERPRET, stage_kinds())
        found = in_image()
        # FINAL 10.4(1) names three; each is generated from the installer's own calls, with the others it runs
        for name in ('RECOMPUTE_STATES', 'CLOSE_STAGES', 'UNDO_HAZARDS_READ'):
            self.assertEqual(found[('script', name)], 'app_script')
        self.assertTrue(installer().UNDO_HAZARDS_READ.startswith(installer().UNDO_HAZARDS))
        self.assertIn(('command', 'interpretation_report'), found)
        self.assertNotIn(('script', 'source'), found)  # app_script's own local is its plumbing, not a script
        items = generated()
        self.assertEqual(len(items), len(set(items)))
        self.assertEqual([item for item in items if item[0] == 'worker'], [('worker', name) for name in WORKER])

    def test_every_exemption_names_what_the_installer_runs_and_says_why(self):
        found = in_image()
        for item, why in IN_IMAGE_EXEMPT.items():
            with self.subTest(item=item):
                self.assertIn(item, found)
                self.assertIn('no encounter row', why)

    def test_an_item_added_and_not_driven_is_missing(self):
        matrix = Matrix(self)
        # nothing observed: every item is missing
        self.assertEqual(set(matrix.missing()), set(generated()) - set(IN_IMAGE_EXEMPT))
        from cptstudio import urls

        planted_view = path('planted-s12/', lambda request: HttpResponse('planted'))
        # each form the installer can name a script or a command in: positional and keyword, a list, a local bound to
        # one, a function returning one, and the entrypoint's own migrate role
        source = INSTALL.read_text(encoding='utf-8') + (
            "\n\ndef planted_phase(image_id, env):\n"
            "    app_script(image_id, env, APP_SCRIPT_ANSWER, {}, what='a planted script')\n"
            "    app_script(image_id, env, body=APP_SCRIPT_PRELUDE, params={}, what='a planted keyword script')\n"
            "    oneshot(image_id, command=['manage', 'planted_keyword_command'], env_bytes=env)\n"
            "    command = ['manage', 'planted_local_command', '--flag']\n"
            "    oneshot(image_id, command, env)\n"
            "    oneshot(image_id, planted_command_list('x'), env)\n"
            "    extended = ['manage', 'planted_extended_command']\n"
            "    extended = extended + ['--flag']\n"
            "    oneshot(image_id, extended, env)\n"
            "    return oneshot(image_id, ['manage', 'planted_command'], env)\n"
            "\n\ndef planted_command_list(value):\n"
            "    return ['manage', 'planted_returned_command', value] + []\n")
        with mock.patch.object(urls, 'urlpatterns', urls.urlpatterns + [planted_view]), \
                mock.patch.dict(jobs.STAGES, {'planted': lambda job: {}}):
            missing = set(matrix.missing(source))
        for item in (('url', 'planted-s12/'), ('stage', 'planted'), ('script', 'APP_SCRIPT_ANSWER'),
                     ('script', 'APP_SCRIPT_PRELUDE'), ('command', 'planted_keyword_command'),
                     ('command', 'planted_local_command'), ('command', 'planted_returned_command'),
                     ('command', 'planted_extended_command'), ('command', 'planted_command')):
            with self.subTest(item=item):
                self.assertIn(item, missing)
        matrix.observations.append(type('Seen', (), {'key': ('url', 'no-such-route/')})())
        self.assertEqual(matrix.unknown(), [('url', 'no-such-route/')])

    def test_a_form_the_generator_cannot_read_fails_closed(self):
        # the review of S12, finding 3: an in-image script or command the generator cannot resolve to a module-level
        # script or a literal command raises, naming its line - it is never dropped (the matrix would stay green over a
        # script it never ran)
        base = INSTALL.read_text(encoding='utf-8')
        forms = {
            'a concatenated body': "app_script(image_id, env, UNDO_HAZARDS + APP_SCRIPT_ANSWER, {}, what='x')",
            'a starred command': "oneshot(image_id, [*['manage'], 'planted_command'], env)",
            'a computed command name': "oneshot(image_id, ['manage', name], env)",
            'a starred argument before the body': "app_script(*arguments, what='x')",
            'a body passed by **': 'app_script(image_id, env, **options)',
            'a manage list with no command': "oneshot(image_id, ['manage'] + rest, env)",
            'a shell script that is no module script': "oneshot(image_id, ['manage', 'shell', '-c', body], env)",
            'an entrypoint role it does not know': "oneshot(image_id, ['planted_role'], env)",
            'a command passed in': 'oneshot(image_id, command, env)',
            'a command bound by a loop': 'for each in commands:\n        oneshot(image_id, each, env)',
            'a command bound by a handler': 'try:\n        pass\n    except Exception as caught:\n'
                                            '        oneshot(image_id, caught, env)',
            'a command that only extends itself': "grown = grown + ['--flag']\n    oneshot(image_id, grown, env)",
            'an alias of oneshot': "run_once = oneshot\n    run_once(image_id, ['manage', 'planted_alias'], env)",
            'a partial of app_script': 'functools.partial(app_script, image_id)',
        }
        for what, statement in forms.items():
            with self.subTest(form=what):
                source = base + ('\n\ndef planted_phase(image_id, env, name, body, arguments, options, rest, command, '
                                 f'commands):\n    {statement}\n')
                with self.assertRaisesRegex(ValueError, r'ops/install\.py:\d+: .* the matrix cannot tell what'):
                    in_image(source)
        self.assertTrue(in_image())  # the installer's own source reads whole

    def test_the_entrypoint_roles_it_resolves_are_the_images_own(self):
        # a one-shot given an entrypoint role (deploy/entrypoint.sh) runs what that role execs: each role the generator
        # resolves is a `python manage.py <command>` arm of the entrypoint, and the item is that command
        text = (APP / 'deploy' / 'entrypoint.sh').read_text(encoding='utf-8')
        arms = dict(re.findall(r'^ {4}([a-z]+)\)\n(?: {8}.*\n)*? {8}exec (.*)$', text, re.MULTILINE))
        self.assertEqual(set(arms), {'web', 'worker', 'migrate', 'manage'})
        self.assertTrue(guard_support.ENTRYPOINT_ROLES)
        for role, item in guard_support.ENTRYPOINT_ROLES.items():
            with self.subTest(role=role):
                self.assertEqual(item[0], 'command')
                self.assertTrue(arms[role].startswith(f'python manage.py {item[1]} '), arms[role])
                self.assertIn(item, in_image())


class NewPathOnlyDatabaseTests(GuardCase):
    def test_every_generated_item_runs_in_every_state_and_nothing_is_counted_under_any_label(self):
        matrix = Matrix(self)
        with sentinel.call_checks():
            world = World(self, matrix).run()
        # a database of new-path encounters only (R-6): every encounter is the world's, and labelled new_path
        encounters = list(models.Encounter.objects.all())
        self.assertEqual({str(item.pk) for item in encounters}, set(world.ids.values()))
        self.assertEqual({readers.label_of(item) for item in encounters}, {NEW})
        self.assertFalse(models.Assessment.objects.exclude(engine_version__startswith='cpt-studio-events@').exists())
        self.assertEqual(matrix.missing(), [])
        self.assertEqual(matrix.unknown(), [])
        self.assertEqual([name for name, found in matrix.satisfied().items() if not found], [])
        self.assertEqual(matrix.red(LABELS), [], matrix.report(LABELS))
        self.assertFalse(models.AuditEvent.objects.filter(event=sentinel.TRIPPED).exists())
        self.assertEqual(sentinel.status()['state'], 'ok')
        self.assertGreater(len(matrix.observations), 250)


class BesideLegacyRecordsTests(GuardCase):
    def test_zero_new_path_executions_where_legacy_records_are_listed_beside_new_ones(self):
        matrix = Matrix(self)
        with sentinel.call_checks():
            world = World(self, matrix, legacy_rows=True).run()
        legacy = models.Encounter.objects.filter(pk__in=world.legacy_ids)
        self.assertEqual(legacy.count(), len(LegacyWorld.SCENARIOS))
        self.assertEqual({readers.label_of(item) for item in legacy}, {LEGACY})
        self.assertEqual(matrix.missing(), [])
        self.assertEqual([name for name, found in matrix.satisfied().items() if not found], [])
        self.assertEqual(matrix.red((NEW,)), [], matrix.report((NEW,)))
        # and every legacy execution there is the legacy rows' own, labelled legacy_record: none under other or unscoped
        self.assertEqual(matrix.red((OTHER, UNSCOPED)), [], matrix.report((OTHER, UNSCOPED)))
        self.assertFalse(models.AuditEvent.objects.filter(event=sentinel.TRIPPED).exists())
        # the lists met the legacy rows, and their own reads ran the legacy reader as legacy_record
        lists = (('url', 'api/encounters'), ('url', 'api/session'), ('url', 'ops/api/encounters'))
        listed = [item for item in matrix.observations if item.key in lists]
        self.assertTrue(any(item.count(LEGACY) for item in listed))


class PositiveControlTests(GuardCase):
    def test_the_legacy_chain_in_a_new_path_scope_records_a_hit_in_every_class(self):
        # FINAL 10.4(3): its stages' bounded children run in this process here, so their reading is counted too
        _, text = tagged(two_procedures, 'P0')()
        with sentinel.call_checks(), in_process_children(), legacy_chain(), \
                sentinel.scope(NEW, entry='positive control: the legacy chain') as opened:
            encounter = models.Encounter.objects.create(workspace=self.ws, title='Synthetic', created_by=self.user)
            revision = f.pasted_revision(encounter, self.user, text, extract=False)
            jobs.start_pipeline(revision, self.user)
            ran = []
            while (job := jobs.claim_next()) is not None:
                ran.append(jobs.run_job(job))
            encounter.refresh_from_db()
            review.effective_view(encounter.current_assessment)
        self.assertEqual([(job.kind, job.state) for job in ran], [('extract', 'succeeded'), ('analyze', 'succeeded'),
                                                                  ('predict', 'succeeded'), ('assess', 'succeeded')])
        kinds = opened.by_kind(NEW)
        self.assertTrue(all(kinds[kind] > 0 for kind in (CODE, REGEX, CACHE)), kinds)
        described = '\n'.join(opened.describe(NEW))
        self.assertIn('studio/gi/', described)  # a gi function
        self.assertTrue(any(name in described for name in ('studio/validation/engine.py',
                                                           'studio/validation/reconcile.py')), described[:2000])
        self.assertIn('(cache)', described)
        self.assertEqual(sentinel.refusal(opened), 'executed')
        self.assertGreater(opened.count(LEGACY), 0)  # the legacy overlay's own read, relabelled by its reader

    def test_the_matrix_turns_red_for_each_class_under_each_label_it_judges(self):
        matrix = Matrix(self)
        world = World(self, matrix)
        with sentinel.call_checks():
            pk = world.upload('E1', tagged(two_procedures, 'E1'))
            world.drain('E1')
            clean = len(matrix.observations)

            def planted(target, name, call):
                real = getattr(target, name)

                def run(*args, **kwargs):
                    call()
                    return real(*args, **kwargs)

                return mock.patch.object(target, name, side_effect=run)

            def twice():
                structure._course_start.cache_clear()
                structure._course_start()
                structure._course_start()  # a hit: only the CALL check sees it

            with planted(customer_api, 'limitations', lambda: cues.page_number_line('3')):
                world.detail('E1', tag='a gi function')  # a request naming a new-path encounter: new_path, code
            with planted(customer_api, 'session_json', lambda: cues.PAGE_NUMBER_LINE.search('3')):
                world.get('/api/session', tag='a legacy regex')  # a request naming none: other, regex
            world.post(f'/api/encounters/{pk}/context', {'setting': 'asc'}, tag='a re-check')
            with planted(jobs, '_retrieval', lambda: reconcile.mention_label('snare')):
                world.drain('a reconcile function', expect=None)  # a stage: new_path, code (its write gate refuses)
            with planted(review, 'refresh_state', twice):
                world.matrix.script('RECOMPUTE_STATES', {}, tag='a legacy cache')  # a script: unscoped, cache
        self.assertEqual([item for item in matrix.observations[:clean] if item.count(LABELS)], [])  # clean before
        expected = (('a gi function', NEW, CODE, 'studio/gi/cues.py'),
                    ('a legacy regex', OTHER, REGEX, 'studio.gi.cues.PAGE_NUMBER_LINE'),
                    ('a reconcile function', NEW, CODE, 'studio/validation/reconcile.py'),
                    ('a legacy cache', UNSCOPED, CACHE, 'studio.gi.structure._course_start (cache)'))
        for tag, label, kind, named in expected:
            with self.subTest(planted=tag):
                [red] = [item for item in matrix.observations if tag in item.tag and item.count(LABELS)]
                self.assertGreater(red.count(label), 0, red.describe())
                self.assertGreater(red.kinds(label)[kind], 0, red.describe())
                self.assertIn(named, red.describe())
                self.assertIn(red, matrix.red(LABELS))
        # a red new_path entry prints the file, the qualname and the first new-path frame (FINAL 10.4(1))
        report = matrix.report((NEW,))
        self.assertRegex(report, r'studio/gi/cues\.py:\d+ page_number_line')
        self.assertIn('entered: ', report)
        self.assertTrue(models.AuditEvent.objects.filter(event=sentinel.TRIPPED).exists())  # the stage's gate refused
