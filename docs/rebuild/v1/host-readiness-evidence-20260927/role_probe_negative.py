"""Isolated PostgreSQL16 role proof; no cloud target, fixed fixture port55704 only.
Creates a uniquely named synthetic database/roles and drops exactly those in finally.
"""
import os,secrets,sys
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0,str(Path.cwd()))
import psycopg
from psycopg import sql
from psycopg.rows import dict_row
from ops.production_database_roles import apply_policy,verify_policy
assert os.environ['QUILLMD_DB_PORT']=='55704'
base=dict(host='127.0.0.1',port=55704,dbname='postgres',user=os.environ['QUILLMD_DB_USER'],password=os.environ['QUILLMD_DB_PASSWORD'],row_factory=dict_row)
prefix='hr_'+secrets.token_hex(5); database=prefix; admin=prefix+'_admin'; secret=secrets.token_urlsafe(30)
roles={kind:prefix+'_'+kind for kind in ('owner','runtime','migrator','backup')}
profile=SimpleNamespace(database_name=database,roles=roles)
credentials={'roles':{kind:{'name':name,'password':secrets.token_urlsafe(40)} for kind,name in roles.items() if kind!='owner'}}
control=psycopg.connect(**base,autocommit=True)
created_db=False; created_admin=False
try:
 assert control.execute('SELECT rolsuper FROM pg_roles WHERE rolname=current_user').fetchone()['rolsuper']
 control.execute(sql.SQL('CREATE ROLE {} LOGIN NOSUPERUSER CREATEDB CREATEROLE PASSWORD {}').format(sql.Identifier(admin),sql.Literal(secret)));created_admin=True
 control.execute(sql.SQL('CREATE DATABASE {} OWNER {}').format(sql.Identifier(database),sql.Identifier(admin)));created_db=True
 target=dict(base,dbname=database,user=admin,password=secret)
 with psycopg.connect(**target) as conn:
  assert conn.execute('SELECT rolsuper FROM pg_roles WHERE rolname=current_user').fetchone()['rolsuper'] is False
  result=apply_policy(conn,profile,admin,credentials)
  assert result['roles']==4
 print('NOSUPERUSER CREATEROLE policy apply passed')
 with psycopg.connect(**target) as conn:
  assert verify_policy(conn,profile)['migrator_explicit_owner']
  assert apply_policy(conn,profile,admin,credentials)['roles']==4
  conn.execute(sql.SQL('SET LOCAL ROLE {}').format(sql.Identifier(roles['owner'])))
  conn.execute('CREATE TABLE public.core_permission_probe(id bigserial PRIMARY KEY,value text)')
 print('idempotent apply and owner-created default-grant fixture passed')
 def attempt(kind,body,success):
  creds=credentials['roles'][kind]
  conn=psycopg.connect(**dict(base,dbname=database,user=creds['name'],password=creds['password']))
  try:
   try: conn.execute(body); passed=True
   except psycopg.Error: passed=False
   assert passed is success,(kind,success)
  finally: conn.rollback();conn.close()
 attempt('runtime',"INSERT INTO public.core_permission_probe(value) VALUES ('synthetic')",True)
 attempt('runtime','CREATE TABLE public.forbidden(id integer)',False)
 attempt('runtime','TRUNCATE public.core_permission_probe',False)
 attempt('runtime',sql.SQL('SET ROLE {}').format(sql.Identifier(roles['owner'])),False)
 attempt('backup','SELECT * FROM public.core_permission_probe',True)
 attempt('backup',"INSERT INTO public.core_permission_probe(value) VALUES ('synthetic')",False)
 attempt('migrator','CREATE TABLE public.forbidden(id integer)',False)
 attempt('migrator',sql.SQL('SET ROLE {}; CREATE TABLE public.allowed_probe(id integer)').format(sql.Identifier(roles['owner'])),True)
 print('8 runtime/backup/migrator privilege checks passed; all DML/DDL rolled back')
 from ops.production_operator import OperatorError
 controls=[
  ('backup table SELECT',sql.SQL('REVOKE SELECT ON public.core_permission_probe FROM {}').format(sql.Identifier(roles['backup']))),
  ('runtime table INSERT',sql.SQL('REVOKE INSERT ON public.core_permission_probe FROM {}').format(sql.Identifier(roles['runtime']))),
  ('runtime sequence USAGE',sql.SQL('REVOKE USAGE ON public.core_permission_probe_id_seq FROM {}').format(sql.Identifier(roles['runtime']))),
  ('backup sequence SELECT',sql.SQL('REVOKE SELECT ON public.core_permission_probe_id_seq FROM {}').format(sql.Identifier(roles['backup']))),
  ('runtime schema USAGE',sql.SQL('REVOKE USAGE ON SCHEMA public FROM {}').format(sql.Identifier(roles['runtime']))),
  ('future backup SELECT',sql.SQL('ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE SELECT ON TABLES FROM {}').format(sql.Identifier(roles['backup']))),
  ('future runtime USAGE',sql.SQL('ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE USAGE ON SEQUENCES FROM {}').format(sql.Identifier(roles['runtime']))),
  ('future PUBLIC EXECUTE',sql.SQL('ALTER DEFAULT PRIVILEGES GRANT EXECUTE ON FUNCTIONS TO PUBLIC')),
  ('runtime schema CREATE',sql.SQL('GRANT CREATE ON SCHEMA public TO {}').format(sql.Identifier(roles['runtime']))),
  ('runtime TRIGGER',sql.SQL('GRANT TRIGGER ON public.core_permission_probe TO {}').format(sql.Identifier(roles['runtime']))),
  ('future runtime grant option',sql.SQL('ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO {} WITH GRANT OPTION').format(sql.Identifier(roles['runtime']))),
 ]
 for label,mutation in controls:
  conn=psycopg.connect(**target)
  try:
   conn.execute(sql.SQL('SET LOCAL ROLE {}').format(sql.Identifier(roles['owner'])))
   conn.execute(mutation);conn.execute('RESET ROLE')
   try: verify_policy(conn,profile)
   except OperatorError: print('negative refused:',label)
   else: raise AssertionError('false green: '+label)
  finally: conn.rollback();conn.close()
 with psycopg.connect(**target) as conn: assert verify_policy(conn,profile)['roles']==4
 print('all11 negative controls refused; restored baseline passed')
finally:
 if created_db:control.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(database)))
 for name in [roles['runtime'],roles['backup'],roles['migrator'],roles['owner']]:
  control.execute(sql.SQL('DROP ROLE IF EXISTS {}').format(sql.Identifier(name)))
 if created_admin:control.execute(sql.SQL('DROP ROLE {}').format(sql.Identifier(admin)))
 control.close()
 print('isolated database and only its generated roles removed')
