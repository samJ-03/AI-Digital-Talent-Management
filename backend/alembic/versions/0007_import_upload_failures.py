"""Allow durable per-file validation failures without inventing stored-file rows."""
import sqlalchemy as sa
from sqlalchemy.dialects import mysql
from alembic import op
revision='0007_import_upload_failures'
down_revision='0006_comment_semantics'
branch_labels=None
depends_on=None
OLD='私有原始文件ID'
NEW='私有原始文件ID；仅上传前置失败时可空且状态必须failed'
def upgrade():
    """Keep the FK and column definition; null is legal only for failed items."""
    op.alter_column('import_items','file_id',existing_type=mysql.BIGINT(unsigned=True),existing_nullable=False,nullable=True,existing_comment=OLD,comment=NEW,existing_autoincrement=False)
    op.create_check_constraint('ck_import_items_failed_without_file','import_items',"file_id IS NOT NULL OR status = 'failed'")
def downgrade():
    """Refuse lossy downgrade before any DDL when upload failures still exist."""
    if op.get_bind().scalar(sa.text('SELECT COUNT(*) FROM import_items WHERE file_id IS NULL')):
        raise RuntimeError('Cannot downgrade: failed upload items without a file still exist')
    op.drop_constraint('ck_import_items_failed_without_file','import_items',type_='check')
    op.alter_column('import_items','file_id',existing_type=mysql.BIGINT(unsigned=True),existing_nullable=True,nullable=False,existing_comment=NEW,comment=OLD,existing_autoincrement=False)
