"""平台开发工具：实现env领域协作。"""
from alembic import context
from sqlalchemy import create_engine
from app.core.settings import Settings
from app.models import register_models

config = context.config
url = config.get_main_option('sqlalchemy.url') or Settings.load().database_url.get_secret_value()
metadata = register_models()
if context.is_offline_mode():
    context.configure(url=url,target_metadata=metadata,literal_binds=True)
    with context.begin_transaction(): context.run_migrations()
else:
    engine=create_engine(url)
    with engine.connect() as connection:
        context.configure(connection=connection,target_metadata=metadata,compare_type=True)
        with context.begin_transaction(): context.run_migrations()
    engine.dispose()
