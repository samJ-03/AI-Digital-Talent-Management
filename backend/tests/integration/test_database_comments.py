"""验证真实MySQL注释覆盖，及注释迁移不改变字段定义或业务数据。"""
from uuid import uuid4
from alembic import command
from alembic.config import Config
from pathlib import Path
from sqlalchemy import inspect, text
from tests.integration.test_schema_contract import db_engine
from app.models import register_models

def test_all_tables_and_columns_have_persisted_comments(db_engine):
    metadata=register_models();inspector=inspect(db_engine)
    assert len(metadata.tables)==40
    assert sum(len(t.columns) for t in metadata.tables.values())==478
    for table in metadata.tables.values():
        assert table.comment
        assert inspector.get_table_comment(table.name)['text']==table.comment
        actual={c['name']:c for c in inspector.get_columns(table.name)}
        for column in table.columns:
            assert column.comment, table.name+'.'+column.name
            assert actual[column.name]['comment']==column.comment

def test_comment_migration_preserves_definition_and_data(db_engine):
    cfg=Config(str(Path(__file__).resolve().parents[2]/'alembic.ini'))
    cfg.set_main_option('sqlalchemy.url',db_engine.url.render_as_string(hide_password=False).replace('%','%%'))
    marker='comment-test-'+uuid4().hex
    with db_engine.begin() as conn:
        row_id=conn.execute(text("INSERT INTO departments(name,status) VALUES (:name,'active')"),{'name':marker}).lastrowid
    def definitions():
        inspector=inspect(db_engine)
        return {t:{c['name']:(str(c['type']),c['nullable'],c.get('default'),c.get('autoincrement')) for c in inspector.get_columns(t)} for t in register_models().tables}
    try:
        original=definitions()
        command.downgrade(cfg,'0004_local_mailpit_tls')
        assert definitions()==original
        command.upgrade(cfg,'head')
        assert definitions()==original
        with db_engine.connect() as conn:
            assert conn.execute(text('SELECT name FROM departments WHERE id=:id'),{'id':row_id}).scalar_one()==marker
    finally:
        with db_engine.begin() as conn: conn.execute(text('DELETE FROM departments WHERE id=:id'),{'id':row_id})
