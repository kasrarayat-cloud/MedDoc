"""Finite offline controls: no database, service, provider or native host."""
import ast
from contextlib import nullcontext
import copy
from datetime import datetime, timedelta, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace, ModuleType
import unittest
from unittest.mock import patch
from ops import activate_outpatient_coding as op


def table():
    return {'rows': 1, 'sha256': 'a'*64, 'old_rows': 'a'*64, 'columns': ['id'],
        'old_columns': [['id','uuid','NO',None,None]], 'definitions': [['id','uuid',True,None,'','',True]],
        'owner_acl': [['quillmd_owner',None,False,False,'r']],
        'privileges': [['quillmd_owner','quillmd_runtime','SELECT',False]]}


def population():
    names = ['django_migrations','django_content_type','auth_permission','core_auditevent',
             'django_session','core_encounter'] + ['original_'+str(i) for i in range(35)]
    tables = {n:table() for n in names}
    for name in ('django_migrations','django_content_type','auth_permission','core_auditevent'):
        tables[name]['ids'] = [1] if name != 'core_auditevent' else ['10000000-0000-0000-0000-000000000001']
    schema = {'functions': {'old_f_'+str(i): {'body':'unchanged'} for i in range(27)},
        'triggers': {'old:t_'+str(i): {'definition':'unchanged'} for i in range(28)},
        'constraints': {'old:pk': {'definition':'PRIMARY KEY (id)'}},
        'indexes': {'old:pk': {'definition':'original'}}, 'policies': [],
        'default_acl': [['quillmd_owner','public','r','original']],
        'sequence_metadata': [['django_migrations_id_seq','quillmd_owner']],
        'sequences': {'django_migrations_id_seq': [[44,True]], 'other_id_seq': [[10,True]]}}
    before = {'tables':tables, 'schema':schema, 'postgresql_server_version_num':'170011',
        'applied_core_migrations':['0027_cedar_synthetic_clinician'], 'invariants':{'unbalanced':0},
        'referenced_files':{'retained.docx':'f'*64},
        'expected_new_table_privileges':tables['core_encounter']['privileges'],
        'coding':{'histories':{'casey_finalized':'a'*64,'kasra_5':'b'*64},'references':{},'reference_ids':{},'new_audits':[]}}
    contract = {'postgresql_server_version_num':'170011', 'tables':{n:table() for n in op.NEW_TABLES},
        'functions':{op.NEW_FUNCTION:{'body':'new exact guard'}},
        'triggers':{n:{'definition':'new exact trigger'} for n in op.NEW_TRIGGERS},
        'constraints':{'core_codingrun:pk':{'definition':'PRIMARY KEY (id)'}},
        'indexes':{'core_codingrun:pk':{'definition':'new exact index'}}, 'references':{}}
    after=copy.deepcopy(before)
    for name in op.NEW_TABLES:
        after['tables'][name]=table()
        after['tables'][name].update(rows=3 if name=='core_codingrelease' else 0,
            sha256='b'*64 if name=='core_codingrelease' else op.EMPTY_SHA)
    after['tables']['django_migrations']['rows']+=1
    after['tables']['core_auditevent']['rows']+=3
    after.update(applied_core_migrations=before['applied_core_migrations']+[op.MIGRATION],
        added_migrations=[['core',op.MIGRATION]],added_content_types=[],added_permissions=[])
    for category in ('functions','triggers','constraints','indexes'):
        after['schema'][category].update(copy.deepcopy(contract[category]))
    after['schema']['sequences']['django_migrations_id_seq']=[[45,True]]
    for i,pin in enumerate(op.REFERENCE_PINS.values()):
        release='00000000-0000-0000-0000-'+str(i+1).zfill(12)
        identifier='10000000-0000-0000-0000-'+str(i+1).zfill(12)
        row={'digest':'c'*64,'index_sha256':'d'*64,'tabular_sha256':'e'*64,'provenance_sha256':'f'*64,
            'manifest_sha256':pin,'audit_details':{'release':release,'version':'synthetic','system':'ICD-10-CM'}}
        contract['references'][release]=row
        after['coding']['references'][release]=copy.deepcopy(row)
        after['coding']['reference_ids'][release]=identifier
        after['coding']['new_audits'].append({'action':'coding.reference_import','target':identifier,
            'actor_id':None,'organization_id':None,'department_id':None,'details':row['audit_details']})
    return before,after,contract


class PreservationTests(unittest.TestCase):
    def test_exact_additive_population(self):
        self.assertEqual(op.database_preserved(*population())['new_tables'],4)

    def test_every_old_table_row_and_metadata(self):
        before,after,contract=population()
        for name in before['tables']:
            for key,value in [('old_rows','0'*64),('columns',['renamed']),('privileges',[]),
                ('owner_acl',[['foreign',None,False,False,'r']])]:
                broken=copy.deepcopy(after);broken['tables'][name][key]=value
                with self.subTest(table=name,key=key),self.assertRaises(op.Refusal):
                    op.database_preserved(before,broken,contract)

    def test_catalog_mutations_extra_objects(self):
        before,after,contract=population()
        for category in before['schema']:
            broken=copy.deepcopy(after)
            if isinstance(broken['schema'][category],dict):broken['schema'][category]['unexpected']={}
            else:broken['schema'][category].append(['unexpected'])
            with self.subTest(category=category),self.assertRaises(op.Refusal):
                op.database_preserved(before,broken,contract)
        for category in ('functions','triggers','constraints','indexes'):
            broken=copy.deepcopy(after);key=next(iter(before['schema'][category]))
            broken['schema'][category][key]={'replaced':True}
            with self.subTest(original=category),self.assertRaises(op.Refusal):
                op.database_preserved(before,broken,contract)

    def test_reference_audit_and_metadata_mutations(self):
        before,after,contract=population();first=next(iter(contract['references']))
        mutations=[lambda b:b['coding']['references'][first].update(index_sha256='0'*64),
            lambda b:b['coding']['references'][first].update(tabular_sha256='0'*64),
            lambda b:b['coding']['new_audits'][0].update(action='encounter.finalize'),
            lambda b:b['coding']['new_audits'][0].update(actor_id='unexpected'),
            lambda b:b['coding']['new_audits'][0].update(department_id='unexpected'),
            lambda b:b['coding']['histories'].update(kasra_5='0'*64),lambda b:b['coding']['new_audits'].pop(),
            lambda b:b['tables']['core_codingrun'].update(rows=1),
            lambda b:b['tables']['core_codingdecision'].update(rows=1),
            lambda b:b.update(added_content_types=[['core','codingrun']]),
            lambda b:b['schema']['sequences'].update(other_id_seq=[[11,True]])]
        for i,mutate in enumerate(mutations):
            broken=copy.deepcopy(after);mutate(broken)
            with self.subTest(i=i),self.assertRaises(op.Refusal):op.database_preserved(before,broken,contract)

    def test_existing_session_drain_only(self):
        before,_,_=population();after=copy.deepcopy(before)
        after['tables']['django_session'].update(rows=3,sha256='c'*64,old_rows='c'*64)
        self.assertTrue(op.prestop_preserved(before,after)['permitted_session_drain_change'])
        after['tables']['core_encounter']['sha256']='c'*64
        with self.assertRaises(op.Refusal):op.prestop_preserved(before,after)

    def test_pending_unmetered_coding_before_and_after_resume(self):
        for active,unknown in ((1,0),(0,1),(1,1)):
            values=iter([[('core_codingrun',)],[(active,)],[(unknown,)]])
            with self.subTest(active=active,unknown=unknown),self.assertRaises(op.Refusal):
                op.coding_pending(lambda _:next(values))
            values=iter([[('core_codingrun',)],[(active,)],[(unknown,)]])
            self.assertEqual(op.coding_pending(lambda _:next(values),after_resume=True)['unresolved'],unknown)
        statements=[];values=iter([[('core_codingrun',)],[(0,)],[(0,)]])
        op.coding_pending(lambda q:statements.append(q) or next(values))
        self.assertIn("q->>'sent'='true'",statements[-1]);self.assertIn("q->'actual_cost'='null'::jsonb",statements[-1])

    def test_forecast_actual_population_deadline(self):
        now=datetime(2026,1,1,tzinfo=timezone.utc)
        plan={'schedule':{'deadline':(now+timedelta(minutes=21)).isoformat()}}
        value={'observed_at_utc':now.isoformat(),'read_only':True,'all_seven_current_hour17_settled_successfully':True,
            'next_strict_watched_transition_utc':plan['schedule']['deadline'],'watched_foreign_file_population':103,
            'provider_calls':0,'service_actions':0,'database_queries':0,
            'actual_exact_unit_source_metadata':{str(i):{'sha256':str(i)} for i in range(167)}}
        config=copy.deepcopy(value['actual_exact_unit_source_metadata']);op.forecast(plan,value,config,now)
        with self.assertRaises(op.Refusal):op.forecast(plan,value,config,now+timedelta(minutes=2))
        config['166']['sha256']='changed'
        with self.assertRaises(op.Refusal):op.forecast(plan,value,config,now)
        value['provider_calls']=False
        with self.assertRaises(op.Refusal):op.forecast(plan,value,now=now)


class FakeAdapter:
    def __init__(self,fail=None):
        self.before,self.after,contract=population();self.artifacts={'schema':contract};self.events=[];self.fail=fail
    def action(self,name,value=None):
        self.events.append(name)
        if self.fail==name:raise op.Refusal('synthetic_failure')
        return value
    def hold(self):return nullcontext()
    def snapshot(self,label,before=None):
        data=self.after if label in ('post-schema','pre-resume','post-resume') else self.before
        return self.action(label,({'database':copy.deepcopy(data)},{}))
    def admission(self,snapshot):self.action('admit')
    def external(self,before,after):self.action('external')
    def stop(self):self.action('stop')
    def backup(self,before):return self.action('backup',{'run_id':'synthetic-backup'})
    def restore(self,backup):return self.action('restore',{'complete':True})
    def publish_source(self):self.action('publish_source')
    def migrate_references(self):self.action('transaction')
    def publish_static(self):self.action('publish_static')
    def configure(self):self.action('configure')
    def start(self):return self.action('start',{'ready':True})
    def finish(self):return self.action('finish',{'environment_sha256':'a'*64})


class LifecycleTests(unittest.TestCase):
    def test_finite_order_backup_restore_before_source(self):
        host=FakeAdapter();records=[]
        result=op.execute({'candidate':'a'*40},host,lambda n,v:records.append((n,v)))
        self.assertTrue(result['complete'])
        for earlier,later in [('backup','restore'),('restore','publish_source'),('transaction','publish_static'),('pre-resume','start')]:
            self.assertLess(host.events.index(earlier),host.events.index(later))
        self.assertEqual(host.events.count('transaction'),1)
        self.assertEqual(len({k for k,_ in records}),len(records))
        self.assertNotIn('installation-complete',[k for k,_ in records])

    def test_phase_failures_pending_no_replay_or_second_stop(self):
        for phase in ('admit','stop','backup','restore','publish_source','transaction','publish_static','configure','start','post-resume','finish'):
            host=FakeAdapter(phase);records=[]
            with self.subTest(phase=phase),self.assertRaises(op.Refusal):
                op.execute({'candidate':'a'*40},host,lambda n,v:records.append((n,v)))
            self.assertEqual(records[-1][0],'pending-recovery')
            self.assertFalse(records[-1][1]['automatic_retry']);self.assertFalse(records[-1][1]['destructive_database_rollback'])
            self.assertLessEqual(host.events.count('stop'),1);self.assertLessEqual(host.events.count('transaction'),1)
            if phase in ('backup','restore'):self.assertNotIn('publish_source',host.events)
            if phase in ('start','post-resume','finish'):self.assertTrue(records[-1][1]['services_may_have_resumed'])

    def test_entrypoints_inert_no_input_read(self):
        with patch.object(op,'read_file',side_effect=AssertionError('read')),patch('sys.stdout',new=io.StringIO()) as out:
            op.main(['--inputs','/does/not/exist'])
        self.assertTrue(json.loads(out.getvalue())['inert'])
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'adapter.py';p.write_bytes(op.render_private_adapter('/missing.py','a'*64,'/missing.json','b'*64))
            result=subprocess.run([sys.executable,'-B',str(p)],capture_output=True)
        self.assertEqual(result.returncode,0);self.assertTrue(json.loads(result.stdout)['inert'])

    def test_adapter_wrong_pin_under_optimization(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'bad.py';p.write_text('raise RuntimeError("EXECUTED")')
            wrapper=Path(d)/'adapter.py';wrapper.write_bytes(op.render_private_adapter(p,'a'*64,'/missing.json','b'*64))
            result=subprocess.run([sys.executable,'-O','-B',str(wrapper),'--execute'],capture_output=True)
        self.assertNotEqual(result.returncode,0);self.assertIn(b'module_pin',result.stderr)
        self.assertNotIn(b'RuntimeError: EXECUTED',result.stderr)

    def test_database_projection_exact_source_inverse(self):
        text=Path(op.__file__).with_name('word_milestone_delivery.py').read_text();tree=ast.parse(text)
        cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='NativeHost')
        fn=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='database')
        import textwrap
        original=textwrap.dedent('\n'.join(text.splitlines()[fn.lineno-1:fn.end_lineno]))+'\n'
        self.assertEqual(op.sha(original.encode()),op.DATABASE_SOURCE_SHA)
        def placeholder():pass
        fake=SimpleNamespace(NativeHost=SimpleNamespace(database=placeholder))
        with patch.object(op.inspect,'getsource',return_value=original):projected=op.project_database(fake)
        self.assertIn('core_auditevent',repr(projected.__code__.co_consts))
        with patch.object(op.inspect,'getsource',return_value=original+'\n'),self.assertRaises(op.Refusal):op.project_database(fake)

    def test_owner_transaction_executes_one_migration_three_imports_as_owner(self):
        code=op.owner_transaction_source({'candidate':'a'*40});compile(code,'<owner>','exec')
        self.assertNotIn('emit_post_migrate',code);self.assertNotIn('assert ',code);self.assertNotIn('coding_provider',code)
        events=[]
        class Cursor:
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def execute(self,q):events.append('role')
            def fetchone(self):return ('quillmd_fresh','quillmd_owner')
        class Executor:
            def __init__(self,c):pass
            def migration_plan(self,t):return [(SimpleNamespace(app_label='core',name=op.MIGRATION),False)]
            def migrate(self,t):events.append('migrate')
        django=ModuleType('django');django.setup=lambda:None
        db=ModuleType('django.db');db.connection=SimpleNamespace(cursor=Cursor);db.transaction=SimpleNamespace(atomic=nullcontext)
        exe=ModuleType('django.db.migrations.executor');exe.MigrationExecutor=Executor
        reference=ModuleType('core.management.commands.import_coding_reference')
        reference.prepare_reference=lambda p,h:events.append(('prepared',h)) or {}
        reference.save_reference=lambda d:events.append('import') or (None,True)
        modules={'django':django,'django.db':db,'django.db.migrations.executor':exe,'core.management.commands.import_coding_reference':reference}
        with patch.dict(sys.modules,modules),patch.object(subprocess,'check_output',return_value=b'a'*40),patch('sys.stdout',new=io.StringIO()):exec(code,{})
        self.assertEqual(events[0],'role');self.assertEqual(events.count('migrate'),1);self.assertEqual(events.count('import'),3)
        self.assertLess(events.index('migrate'),events.index('import'))


class SourcePlanTests(unittest.TestCase):
    """Exercise the constructor's source seam without constructing a native host."""
    @staticmethod
    def bind(adapter, plan, root, base):
        tree = ast.parse(Path(op.__file__).read_text())
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'NativeAdapter')
        constructor = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == '__init__')
        start = next(i for i, n in enumerate(constructor.body)
                     if isinstance(n, ast.Assign) and ast.unparse(n.targets[0]) == 'self.source')
        statements = constructor.body[start:start + 3]
        namespace = {'self': adapter, 'plan': plan, 'ROOT': root, 'BASE': base, 'Path': Path}
        exec(compile(ast.Module(body=statements, type_ignores=[]), '<constructor-source-binding>', 'exec'), namespace)

    def test_donor_scope_copy_preserves_publication_plan(self):
        root = Path('/synthetic/shared'); donor = Path('/synthetic/candidate')
        publication = {'repo': str(root), 'before': {'old': 'retained'}, 'after': {'new': 'retained'}}
        original = copy.deepcopy(publication)
        calls = []
        def make_plan(*args, **kwargs):
            calls.append((args, kwargs))
            return publication
        def validate(repo, scoped, revision):
            self.assertEqual(repo, donor)
            self.assertEqual(scoped, {**original, 'repo': str(donor)})
            self.assertIsNot(scoped, publication)
            self.assertEqual(revision, 'b' * 40)
        adapter = SimpleNamespace(guard=SimpleNamespace(make_plan=make_plan, validate_published=validate))
        self.bind(adapter, {'source_worktree': str(donor), 'candidate': 'b' * 40,
                            'source_sha256': {'rebuild/core/coding_service.py': 'c' * 64}}, root, 'a' * 40)
        self.assertIs(adapter.publication, publication)
        self.assertEqual(publication, original)
        self.assertEqual(calls, [((root, 'a' * 40, 'b' * 40,
                                  frozenset({'rebuild/core/coding_service.py'})),
                                 {'owner_uid': 1000, 'owner_gid': 1000,
                                  'service_uid': 996, 'service_gids': [988]})])

    def test_real_pinned_guard_on_temporary_repositories(self):
        path = Path('/opt/meddoc-pro/rebuild/.runtime/standing-testing-authority-20261009/'
                    'native-review-v1/source_publication_guard_standing_v3.py')
        if not path.exists():
            self.skipTest('Private pinned native guard unavailable; portable source-scope test still runs.')
        raw = path.read_bytes()
        self.assertEqual(op.sha(raw), '13be30775df7ae6f0fc0266e8c1b148ef2bd8aabac8fc954e26b8fdc18b00300')
        guard = ModuleType('_coding_actual_source_guard_test')
        exec(compile(raw, str(path), 'exec'), guard.__dict__)
        names = frozenset({'rebuild/core/coding_service.py', 'rebuild/core/coding_views.py'})
        guard.DECLARED_PATHS = names
        guard.GROUP_WRITABLE_BASE_PATHS = guard.DELETABLE_PATHS = frozenset()
        uid, gid = os.getuid(), os.getgid()
        if uid == 0 or gid == 0:
            self.skipTest('Native guard requires a non-root source owner.')
        env = {**os.environ, 'GIT_AUTHOR_NAME': 'Synthetic Fixture',
               'GIT_AUTHOR_EMAIL': 'fixture@example.invalid', 'GIT_COMMITTER_NAME': 'Synthetic Fixture',
               'GIT_COMMITTER_EMAIL': 'fixture@example.invalid', 'GIT_CONFIG_NOSYSTEM': '1'}
        def git(repo, *args):
            return subprocess.check_output(['git', '-c', 'core.hooksPath=/dev/null',
                '-c', 'commit.gpgsign=false', '-C', str(repo), *args], env=env, stderr=subprocess.PIPE).decode().strip()
        previous_umask = os.umask(0o077)
        try:
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory) / 'shared'; root.mkdir()
                donor = Path(directory) / 'candidate'
                git(root, 'init', '-q')
                first = root / 'rebuild/core/coding_service.py'; first.parent.mkdir(parents=True)
                first.write_text('# synthetic base\n'); first.chmod(0o644)
                git(root, 'add', '.'); git(root, 'commit', '-qm', 'synthetic base')
                base = git(root, 'rev-parse', 'HEAD')
                first.write_text('# synthetic candidate\n')
                second = root / 'rebuild/core/coding_views.py'
                second.write_text('# synthetic addition\n'); second.chmod(0o644)
                git(root, 'add', '.'); git(root, 'commit', '-qm', 'synthetic candidate')
                candidate = git(root, 'rev-parse', 'HEAD')
                git(root, 'worktree', 'add', '--detach', str(donor), candidate)
                git(root, 'reset', '--hard', base)
                for repo in (root, donor):
                    for name in names:
                        if (repo / name).exists():
                            (repo / name).chmod(0o644)
                publication = guard.make_plan(root, base, candidate, names,
                    owner_uid=uid, owner_gid=gid, service_uid=uid, service_gids=[gid])
                original = copy.deepcopy(publication)
                with self.assertRaisesRegex(guard.Refusal, '^source_plan_repository$'):
                    guard.validate_published(donor, publication, candidate)
                with self.assertRaisesRegex(guard.Refusal, '^source_base_head$'):
                    guard.make_plan(donor, base, candidate, names,
                        owner_uid=uid, owner_gid=gid, service_uid=uid, service_gids=[gid])
                # Keep actual validation unmocked; only substitute portable fixture
                # owner/service IDs for the constructor's production identities.
                def make_plan(repo, old, new, paths, **identity):
                    self.assertEqual((repo, old, new, paths), (root, base, candidate, names))
                    return publication
                adapter = SimpleNamespace(guard=SimpleNamespace(make_plan=make_plan,
                    validate_published=guard.validate_published))
                plan = {'source_worktree': str(donor), 'candidate': candidate,
                        'source_sha256': {name: 'a' * 64 for name in names}}
                self.bind(adapter, plan, root, base)
                self.assertEqual(publication, original)
                self.assertEqual(guard.validate_published(root, publication, base)['revision'], base)
                scoped = {**publication, 'repo': str(donor)}
                for violation, reason in [('head', 'source_published_head'),
                        ('bytes', 'source_file_bytes'), ('mode', 'source_file_mode'),
                        ('index', 'source_index_contract'), ('paths', 'source_exact_declared_delta'),
                        ('owner', 'source_file_identity')]:
                    checked = copy.deepcopy(scoped)
                    target = donor / 'rebuild/core/coding_service.py'
                    if violation == 'head': git(donor, 'checkout', '--detach', base)
                    if violation == 'bytes': target.write_text('# synthetic dirty\n')
                    if violation == 'mode': target.chmod(0o600)
                    if violation == 'index':
                        target.write_text('# synthetic staged\n'); git(donor, 'add', str(target))
                    if violation == 'paths': checked['paths'].pop()
                    if violation == 'owner': checked['owner_uid'] += 1
                    with self.subTest(violation=violation), self.assertRaisesRegex(guard.Refusal, '^' + reason + '$'):
                        guard.validate_published(donor, checked, candidate)
                    git(donor, 'reset', '--hard', candidate)
                    for name in names: (donor / name).chmod(0o644)
                self.assertEqual(guard.validate_published(donor, scoped, candidate)['revision'], candidate)
                self.assertEqual(publication, original)
        finally:
            os.umask(previous_umask)


class StaticTests(unittest.TestCase):
    def fixture(self,root):
        old={'paths':{'app.css':'app.old.css'},'version':'1.1','hash':'old'};raw=json.dumps(old).encode()
        (root/'previous-staticfiles.json').write_bytes(raw);before={'staticfiles.json':{'sha256':op.sha(raw)}}
        paths=dict(old['paths']);hashes={};staged={'.':{'kind':'directory','mode':493}}
        for name in op.STATIC_INPUTS:
            raw=('/* synthetic '+name+' */').encode();suffix=Path(name).suffix
            hashed=name[:-len(suffix)]+'.'+hashlib.md5(raw).hexdigest()[:12]+suffix
            paths[name]=hashed;hashes['rebuild/static/'+name]=op.sha(raw)
            for n in (name,hashed):(root/n).write_bytes(raw);staged[n]={'kind':'file','mode':420,'sha256':op.sha(raw)}
        manifest={'paths':paths,'version':'1.1','hash':hashlib.md5(json.dumps(sorted(paths.items())).encode()).hexdigest()[:12]}
        (root/'staticfiles.json').write_text(json.dumps(manifest));staged['staticfiles.json']={'kind':'file','mode':420}
        return before,staged,manifest,hashes
    def test_two_assets_and_original_routes(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);values=self.fixture(root);op.validate_static(root,*values)
            values[1]['unexpected.js']={'kind':'file','mode':420}
            with self.assertRaises(op.Refusal):op.validate_static(root,*values)
    def test_wrong_route_source_hash_mode(self):
        for change in ('old','source','compiled','mode'):
            with self.subTest(change=change),tempfile.TemporaryDirectory() as d:
                root=Path(d);values=self.fixture(root)
                if change=='old':values[2]['paths']['app.css']='replacement.css'
                if change=='source':values[3]['rebuild/static/coding.js']='0'*64
                if change=='compiled':(root/values[2]['paths']['coding.js']).write_bytes(b'wrong')
                if change=='mode':values[1]['coding.js']['mode']=0o666
                with self.assertRaises(op.Refusal):op.validate_static(root,*values)



class RoleWrapperTests(unittest.TestCase):
    def invoke(self, command, role='migrator'):
        from ops import with_db_role
        with tempfile.TemporaryDirectory() as d:
            source=Path(d);(source/'manage.py').write_text('# synthetic')
            data={'database':'quillmd_fresh','roles':{'migrator':{'name':'migrator','password':'fixture-only'},'backup':{'name':'backup','password':'fixture-only'}}}
            argv=['with_db_role','--credentials','/unused','--source',d,'--role',role,'--',*command]
            with patch.object(sys,'argv',argv),patch.object(with_db_role,'read_private',return_value=json.dumps(data).encode()),patch.object(with_db_role.os,'execve') as execute:
                with_db_role.main()
                return execute.call_args
    def test_reference_import_uses_owner_without_printing_credentials(self):
        args=self.invoke(['import_coding_reference','--manifest','/pinned.json','--manifest-sha256','a'*64])
        self.assertEqual(args.args[2]['PGOPTIONS'],'-c role=quillmd_owner')
        self.assertEqual(args.args[2]['QUILLMD_DB_PORT'],'55438')
        self.assertIn('import_coding_reference',args.args[1])
    def test_backup_role_and_worker_are_not_import_paths(self):
        for command,role in [(['import_coding_reference'],'backup'),(['worker'],'migrator'),(['shell'],'migrator')]:
            with self.subTest(command=command,role=role),self.assertRaises(Exception):self.invoke(command,role)
    def test_existing_read_only_check_stays_allowed(self):
        self.assertIn('check',self.invoke(['check']).args[1])


if __name__ == "__main__":
    unittest.main()
