"""Pure input/seal controls only. No application, DB, credentials or provider imports."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import ast
import json
import shutil
import socket
import unittest
from transfer_inputs import GROUPS, ROOT, SEALS, load, sha


class Preparation(unittest.TestCase):
    def test_all_sixteen_sealed_inputs_and_fixed_packets(self):
        self.assertEqual(sum(len(x) for x in GROUPS.values()),16)
        self.assertEqual(set().union(*map(set,GROUPS.values())),set(range(2,16))|{17,19})
        with patch.object(socket.socket,'connect',side_effect=AssertionError('No network')):
            for attempt in list(range(2,16))+[17,19]:
                with self.subTest(attempt=attempt):
                    row=load(attempt);self.assertTrue(row['hashes'])
                    self.assertEqual(row['request']['model'],'claude-sonnet-5-5')
                    self.assertEqual(row['request']['max_tokens'],20000)
                    self.assertEqual(row['notes'],row['payload']['notes'])

    def test_unknown_attempt_refuses_before_any_file_read(self):
        for attempt in [1,16,18,20,0,-1]:
            with self.subTest(attempt=attempt), self.assertRaises(ValueError):load(attempt,Path('/absent'))

    def test_actual_callback_duration_reads_the_sealed_http_response_body(self):
        tree=ast.parse(Path(__file__).with_name('cached_provider_transfer.py').read_text())
        callbacks=[node for node in ast.walk(tree) if isinstance(node,ast.FunctionDef) and node.name=='transcription']
        self.assertEqual(len(callbacks),1)
        returned=next(node for node in ast.walk(callbacks[0]) if isinstance(node,ast.Return))
        units=returned.value.elts[2]
        for attempt in (17,19):
            with self.subTest(attempt=attempt):
                voice=load(attempt)['voice']
                observed=eval(compile(ast.Expression(units),'<actual-fixture-callback-units>','eval'),
                              {'voice':voice,'submitted':{'submitted_seconds':'synthetic-control'}})
                body=json.loads((voice['folder']/'provider-response.body').read_bytes())
                self.assertEqual(observed['duration_seconds'],str(body['metadata']['duration']))
                self.assertNotIn('metadata',voice['response'])

    def test_changed_closed_manifest_is_refused(self):
        with TemporaryDirectory(prefix='quillmd-transfer-input-control-') as temporary:
            root=Path(temporary);shutil.copytree(ROOT/'002',root/'002')
            path=root/'002/manifest.json';data=json.loads(path.read_text());data['runner']['commit']='0'*40
            path.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError,'sealed paid attempt'):load(2,root)

    def test_changed_notes_or_mapping_or_provider_bytes_are_refused(self):
        with TemporaryDirectory(prefix='quillmd-transfer-input-control-') as temporary:
            root=Path(temporary);shutil.copytree(ROOT/'002',root/'002')
            for name in ('case/notes.txt','case/mapping.json','provider-result.json','request.json'):
                path=root/'002'/name;original=path.read_bytes();path.write_bytes(original+b' ')
                with self.subTest(name=name),self.assertRaisesRegex(ValueError,'Changed retained evidence'):load(2,root)
                path.write_bytes(original)

    def test_invalid_profile_refuses_even_in_explicit_test_only_resealed_copy(self):
        with TemporaryDirectory(prefix='quillmd-transfer-input-control-') as temporary:
            root=Path(temporary);shutil.copytree(ROOT/'002',root/'002')
            path=root/'002/request.json';request=json.loads(path.read_text());request['body_json']['max_tokens']=8000
            path.write_text(json.dumps(request))
            manifest=root/'002/manifest.json';data=json.loads(manifest.read_text())
            data['evidence']['request.json']=sha(path.read_bytes());manifest.write_text(json.dumps(data))
            with patch.dict(SEALS,{'002':sha(manifest.read_bytes())}):
                with self.assertRaisesRegex(ValueError,'qualified profile'):load(2,root)

    def test_literal_scripts_parse_and_do_not_invoke_paid_campaign(self):
        for name in ('cached_provider_transfer.py','run_cached_provider_transfer.py','transfer_inputs.py'):
            body=Path(__file__).with_name(name).read_text();tree=ast.parse(body)
            forbidden={'qa-signing-key','ANTHROPIC_API_KEY','load_credential','access.json'}
            self.assertTrue(all(item not in body for item in forbidden))
            self.assertFalse(any(isinstance(node,ast.Import) and any(alias.name=='standing_qa' for alias in node.names)
                                 or isinstance(node,ast.ImportFrom) and node.module=='standing_qa' for node in ast.walk(tree)))
            self.assertFalse(any(isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute)
                                 and node.func.attr in ('urlopen','create_completion') for node in ast.walk(tree)))


if __name__=='__main__':unittest.main(verbosity=2)
