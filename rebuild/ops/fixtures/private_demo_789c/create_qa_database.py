"""Create (or, with --drop-confirm NAME, drop) the private QA demo database on the QA PostgreSQL. Proposal only.

Run THROUGH qa_launch.py with the candidate venv, so the connection values come from the fresh environment:
    python3 -B qa_launch.py -- <venv>/bin/python -B <this file>
    python3 -B qa_launch.py -- <venv>/bin/python -B <this file> --drop-confirm quillmd_qa_int_sol_789c0372

Refuses any server other than 127.0.0.1:55731, any role other than quillmd_qa, any name that does not start with
quillmd_qa_int_, and quillmd_qa_sonnet5 (the campaign database) in every case. Prints JSON; never prints the password.
"""
import argparse
import json
import os

import psycopg
from psycopg import sql

parser = argparse.ArgumentParser()
parser.add_argument('--drop-confirm', metavar='NAME')
args = parser.parse_args()
name = os.environ['QUILLMD_DB_NAME']
assert os.environ['QUILLMD_DB_HOST'] == '127.0.0.1' and os.environ['QUILLMD_DB_PORT'] == '55731', 'QA server only'
assert os.environ['QUILLMD_DB_USER'] == 'quillmd_qa', 'QA role only'
assert name.startswith('quillmd_qa_int_') and name != 'quillmd_qa_sonnet5' and len(name) < 40, 'demo name only'
with psycopg.connect(host='127.0.0.1', port=55731, user='quillmd_qa', password=os.environ['QUILLMD_DB_PASSWORD'],
                     dbname='postgres', autocommit=True, connect_timeout=5) as conn:
    exists = conn.execute('select 1 from pg_database where datname=%s', (name,)).fetchone() is not None
    if args.drop_confirm is not None:
        assert args.drop_confirm == name, 'the confirmation must repeat the exact database name'
        if exists:
            conn.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(name)))
        print(json.dumps({'database': name, 'existed': exists, 'dropped': exists}))
    else:
        if not exists:
            conn.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)))
        print(json.dumps({'database': name, 'existed': exists, 'created': not exists}))
