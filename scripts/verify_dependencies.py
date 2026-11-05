from __future__ import annotations
import importlib
import json
import sys
from importlib.metadata import version

modules = {'fastapi':'fastapi','pydantic':'pydantic','pydantic-settings':'pydantic_settings','SQLAlchemy':'sqlalchemy','alembic':'alembic','PyMySQL':'pymysql','redis':'redis','celery':'celery','httpx':'httpx','minio':'minio','pymilvus':'pymilvus','langgraph':'langgraph.graph','pypdf':'pypdf','python-docx':'docx','cryptography':'cryptography','argon2-cffi':'argon2','pytest':'pytest'}
results = []
for package, module in modules.items():
    try:
        importlib.import_module(module)
        results.append({'package':package,'version':version(package),'ok':True})
    except Exception as error:
        results.append({'package':package,'ok':False,'error_type':type(error).__name__})
print(json.dumps({'python':sys.version.split()[0],'platform':sys.platform,'imports':results}, indent=2))
raise SystemExit(0 if all(r['ok'] for r in results) else 1)
