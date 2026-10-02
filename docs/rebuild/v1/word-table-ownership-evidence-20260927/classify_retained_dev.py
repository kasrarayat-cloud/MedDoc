"""Read-only original DEV evidence classification. No engine, model, render or score execution."""
import json,math,hashlib
from collections import Counter
from pathlib import Path
R=Path(__file__).parent;B=Path('/opt/meddoc-pro/rebuild/.runtime/v1-word-corpus')
ledger=json.loads((B/'custodian-20260927/metadata/053-original-dev40-exact-rights-ledger.json').read_text())['records']
old=B/'results/dev-79a5b2ec6597-frozen';result=json.loads((old/'results.json').read_text());rows=[]
for rec in ledger:
 if not rec['offline_filled_copy_replay_supported']:continue
 stem=Path(rec['corpus_file']).stem;prior=next(d for d in result['documents'] if d['stem']==stem)
 expected=json.loads(Path(rec['prior_expected_map_path']).read_text());mapping=json.loads((old/'detect'/(stem+'.json')).read_text())
 fields=mapping.get('fields',[]);kinds=Counter(a['kind'] for a in expected['answer_areas']);eligible=sum(n for k,n in kinds.items() if k not in ('signature','initials'))
 rows.append({'id':rec['development_id'],'lineage':rec['lineage'],'source_org':rec['source_org'],'original_sha256':rec['sha256'],'title':expected['form_title'],'families':expected.get('families_observed',[]),'expected_areas':len(expected['answer_areas']),'expected_kind_counts':dict(kinds),'expected_areas_excluding_signature_initials':eligible,'historical_actual_fields':len(fields),'historical_actual_answerable':sum(f['kind'] not in ('signature','initials') and not f.get('write_protected') for f in fields),'historical_failures':prior['reasons'],'historical_detection':{k:prior[k] for k in ('missed','wrong','extras')},'historical_export_ok':prior['export_ok'],'render_record':prior.get('render',{}),'actual_full_app_acceptance':'not established by historical harness','potential_100_field_limit':eligible>100,'illustrative_independent_100_field_chunks':math.ceil(eligible/100),'chunk_count_is_not_an_implemented_plan':True})
(R/'16-retained-dev-pipeline.json').write_text(json.dumps({'scope':'33 rights-supported original DEV only; existing results; no new compatibility score','source_result_sha256':hashlib.sha256((old/'results.json').read_bytes()).hexdigest(),'rows':rows},ensure_ascii=False,indent=2))
for r in rows:print(r['id'],r['expected_areas'],r['expected_areas_excluding_signature_initials'],r['historical_actual_answerable'],r['historical_detection'], '; '.join(r['historical_failures'][1:]))
