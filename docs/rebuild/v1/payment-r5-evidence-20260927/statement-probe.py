"""Synthetic transactional PostgreSQL catalog probe; all created objects roll back."""
import ast, hashlib, importlib.util, os, re
from pathlib import Path
import psycopg
root=Path('/opt/meddoc-pro/.worktrees/v1-blockers/rebuild')
conn=psycopg.connect(host='127.0.0.1',port=os.environ['QUILLMD_DB_PORT'],dbname='postgres',
                     user=os.environ['QUILLMD_DB_USER'],password=os.environ['QUILLMD_DB_PASSWORD'])
assert os.environ['QUILLMD_DB_PORT']=='55702'
tree=ast.parse((root/'core/billing.py').read_text())
names={'PAYMENT_EVIDENCE_GUARDS','PAYMENT_GUARD_FUNCTION_SHA256','missing_payment_evidence_guards'}
nodes=[n for n in tree.body if isinstance(n,(ast.FunctionDef,ast.Assign)) and
       (n.name if isinstance(n,ast.FunctionDef) else n.targets[0].id if isinstance(n.targets[0],ast.Name) else '') in names]
ns={'connection':conn,'hashlib':hashlib};exec(compile(ast.Module(body=nodes,type_ignores=[]),'billing-proof','exec'),ns)
try:
 with conn.cursor() as c:
  c.execute('CREATE SCHEMA astra_recovery_r5_probe')
  c.execute('SET LOCAL search_path=astra_recovery_r5_probe,pg_catalog')
  c.execute('CREATE TABLE core_payment (id int, livemode boolean, wallet_id int, amount_cents int, stripe_intent text, status text)')
  c.execute('CREATE TABLE core_ledgerentry (id int)')
  c.execute('CREATE TABLE core_webhookevent (id int,livemode boolean,event_id text,kind text,payload_hash text,semantic_hash text,object_data jsonb)')
  for filename in ('0003_immutable_records.py','0008_payment_event_evidence.py','0020_payment_livemode.py'):
   text=(root/'core/migrations'/filename).read_text()
   for function,body in re.findall(r'(CREATE FUNCTION (quillmd_\w+)\(\) RETURNS trigger LANGUAGE plpgsql AS \$\$.*?\$\$;)',text,re.S):
    if body in ns['PAYMENT_GUARD_FUNCTION_SHA256']:c.execute(function)
  for table,name,function,kind in ns['PAYMENT_EVIDENCE_GUARDS']:
   event={27:'UPDATE OR DELETE',19:'UPDATE',34:'TRUNCATE'}[kind]
   c.execute(f'CREATE TRIGGER {name} BEFORE {event} ON {table} FOR EACH '+('ROW' if kind&1 else 'STATEMENT')+f' EXECUTE FUNCTION {function}()')
  print('baseline',ns['missing_payment_evidence_guards'](),flush=True)
  c.execute("CREATE FUNCTION r5_relabel_statement() RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER AS $$ BEGIN PERFORM set_config('session_replication_role','replica',true); UPDATE core_payment SET livemode=true; PERFORM set_config('session_replication_role','origin',true); RETURN NULL; END; $$")
  c.execute('CREATE TRIGGER hidden_relabel AFTER INSERT ON core_payment FOR EACH STATEMENT EXECUTE FUNCTION r5_relabel_statement()')
  print('after_statement_trigger',ns['missing_payment_evidence_guards'](),flush=True)
  c.execute("INSERT INTO core_payment VALUES (1,false,1,1000,'pi_synthetic','paid')")
  c.execute('SELECT livemode FROM core_payment WHERE id=1');print('input_false_stored',c.fetchone()[0],flush=True)
  print('after_relabel',ns['missing_payment_evidence_guards'](),flush=True)
finally:
 conn.rollback();conn.close();print('transaction rolled back',flush=True)
