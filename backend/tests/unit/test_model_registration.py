"""平台开发工具：验证model registration的正常与失败场景；测试数据仅用于隔离环境。"""
import os
import subprocess
import sys
from pathlib import Path

def test_standalone_default_uow_loads_all_foreign_key_targets():
    env=dict(os.environ)
    env['PYTHONPATH']=str(Path(__file__).resolve().parents[2])
    env['TALENT_DATABASE_URL']=env['TALENT_TEST_DATABASE_URL']
    env['TALENT_ENVIRONMENT']='test'
    env['TALENT_MONITOR_TOKEN']='synthetic-monitor-only'
    code='from app.core.uow import default_session_factory; from app.core.db import Base; default_session_factory(); assert len(Base.metadata.tables)==40; assert all(fk.column.table is not None for table in Base.metadata.tables.values() for fk in table.foreign_keys)'
    result=subprocess.run([sys.executable,'-c',code],env=env,capture_output=True,text=True)
    assert result.returncode==0,'Standalone ORM registry is incomplete; inspect local CLI registration before capability probe'
