"""Remove the empty RED-test migration stamp, never any domain table/data."""
import os
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect
from sqlalchemy.engine import make_url

url=os.environ['TALENT_TEST_DATABASE_URL']
assert make_url(url).database=='talent_test'
engine=create_engine(url)
try:
    assert set(inspect(engine).get_table_names()) <= {'alembic_version'}, 'Refusing: test database has domain tables'
finally:
    engine.dispose()
config=Config('alembic.ini')
config.set_main_option('sqlalchemy.url',url.replace('%','%%'))
command.downgrade(config,'base')
print('Empty RED revision stamp reset; no domain tables removed')
