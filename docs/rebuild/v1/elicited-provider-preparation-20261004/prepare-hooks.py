from pathlib import Path
import difflib,hashlib,json
W=Path('/opt/meddoc-pro/.worktrees/v1-elicited-campaign5-bd82576d');O=Path(__file__).parent
old=(W/'rebuild/ops/standing_qa.py').read_text();s=old
changes=[
("              'notes_qualification': 'ordinary_notes',", "              'notes_qualification': 'ordinary_notes', 'elicited_qualification': 'ordinary_notes',"),
("                 'notes_qualification': ('ordinary_notes', 'ordinary_notes_field_relations'),", "                 'notes_qualification': ('ordinary_notes', 'ordinary_notes_field_relations'),\n                 'elicited_qualification': ('ordinary_notes_field_relations',),"),
("               'notes_qualification': {**_ALL_OFF, 'QUILLMD_WORD_ENGINE': 'v3'},", "               'notes_qualification': {**_ALL_OFF, 'QUILLMD_WORD_ENGINE': 'v3'},\n               'elicited_qualification': {**_ALL_OFF, 'QUILLMD_WORD_ENGINE': 'v3'},"),
("    'rebuild/ops/standing_qa.py', 'rebuild/ops/standing_qa_transcription.py',", "    'rebuild/ops/standing_qa.py', 'rebuild/ops/standing_qa_transcription.py',\n    'rebuild/ops/standing_qa_elicited.py', 'rebuild/ops/fixtures/elicited-qualification-v1.json',"),
("    if 'notes_qualification' in ids:\n", "    if 'elicited_qualification' in ids:\n        require(one('elicited_fixture_manifest', r'([0-9a-f]{64})') == elicited_module().MANIFEST_SHA256\n                and next(stage.sends for stage in stages if stage.id == 'elicited_qualification') == 5,\n                'The elicited stage requires its exact separately declared five-case synthetic freeze.')\n    elif re.search(r'^elicited_fixture_manifest:', text, re.M):\n        raise Refused('An elicited fixture declaration requires its own stage.')\n    if 'notes_qualification' in ids:\n"),
("def send_inputs(send, inputs):", "def elicited_module():\n    try:\n        from . import standing_qa_elicited\n    except ImportError:\n        import standing_qa_elicited\n    return standing_qa_elicited\n\n\ndef send_inputs(send, inputs):"),
("    if send.path in batch_module().PATHS:\n", "    if send.group == 'elicited_qualification':\n        return elicited_module().send_inputs(send, inputs)\n    if send.path in batch_module().PATHS:\n"),
("    if stage == 'ordinary_batch':\n        return batch_module().plan_sends(inputs)", "    if stage == 'elicited_qualification':\n        return elicited_module().plan_sends(inputs)\n    if stage == 'ordinary_batch':\n        return batch_module().plan_sends(inputs)"),
("        own_inputs = batch_module().frozen_inputs() if stage == 'ordinary_batch' else inputs", "        own_inputs = (batch_module().frozen_inputs() if stage == 'ordinary_batch'\n                      else elicited_module().frozen_inputs() if stage == 'elicited_qualification' else inputs)"),
("    if stage == 'model_check':\n        return None\n", "    if stage == 'model_check':\n        return None\n    if stage == 'elicited_qualification':\n        require(declaration.stage(stage).sends == 5, 'The declaration does not admit the complete elicited plan.')\n        return elicited_module().frozen_inputs()\n"),
("    if stage == 'ordinary_batch':\n        return batch_module().price_sends(sends, inputs, state_dir, declaration, limits)", "    if stage == 'elicited_qualification':\n        return elicited_module().price_sends(sends, inputs, state_dir, declaration, limits)\n    if stage == 'ordinary_batch':\n        return batch_module().price_sends(sends, inputs, state_dir, declaration, limits)"),
("    if stage != 'notes_qualification' or stops:", "    if stage not in ('notes_qualification', 'elicited_qualification') or stops:"),
("    if stage == 'notes_qualification':\n        cap = min(cap, 1)", "    if stage in ('notes_qualification', 'elicited_qualification'):\n        cap = min(cap, 1)"),
("                 else batch_module().build_forms(root / 'forms' / stage, inputs) if stage == 'ordinary_batch'", "                 else elicited_module().build_forms(root / 'forms' / stage, inputs) if stage == 'elicited_qualification'\n                 else batch_module().build_forms(root / 'forms' / stage, inputs) if stage == 'ordinary_batch'"),
("            worker_class = batch_module().BatchRun if stage == 'ordinary_batch' else stages.Run", "            worker_class = (elicited_module().ElicitedRun if stage == 'elicited_qualification'\n                            else batch_module().BatchRun if stage == 'ordinary_batch' else stages.Run)"),
("name in ('ordinary_batch', 'notes_qualification')", "name in ('ordinary_batch', 'notes_qualification', 'elicited_qualification')"),
]
records=[]
for a,b in changes:
 n=s.count(a);assert n==1 or a=="name in ('ordinary_batch', 'notes_qualification')" and n==3,(a,n)
 records.append({'before':a,'after':b,'occurrences':n});s=s.replace(a,b)
compile(s,'pending-standing-qa.py','exec')
(O/'pending-standing_qa.source').write_text(s)
patch=''.join(difflib.unified_diff(old.splitlines(keepends=True),s.splitlines(keepends=True),fromfile='a/rebuild/ops/standing_qa.py',tofile='b/rebuild/ops/standing_qa.py'))
(O/'standing-hook.patch').write_text(patch)
(O/'hook-bindings.json').write_text(json.dumps({'root_file_unchanged':True,'base_sha256':hashlib.sha256(old.encode()).hexdigest(),'pending_sha256':hashlib.sha256(s.encode()).hexdigest(),'patch_sha256':hashlib.sha256(patch.encode()).hexdigest(),'replacements':records},indent=2)+'\n')
print(json.dumps({'pending_sha256':hashlib.sha256(s.encode()).hexdigest(),'patch_sha256':hashlib.sha256(patch.encode()).hexdigest(),'lines':len(patch.splitlines())}))
