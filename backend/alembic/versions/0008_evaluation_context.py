"""Persist reproducible screening context without rewriting historical runs."""
import sqlalchemy as sa
from alembic import op
revision='0008_evaluation_context'
down_revision='0007_import_upload_failures'
branch_labels=None
depends_on=None

def upgrade():
    """Existing rows remain explicit unverified empty contexts."""
    op.add_column('evaluation_runs',sa.Column('screening_context',sa.JSON(),nullable=False,server_default=sa.text('(JSON_OBJECT())'),comment='冻结的评估日期、规则修订和来源摘要；旧记录为空不可重新解释'))

def downgrade():
    """Refuse loss of historical context before executing DDL."""
    if op.get_bind().scalar(sa.text('SELECT COUNT(*) FROM evaluation_runs WHERE JSON_LENGTH(screening_context)>0')):
        raise RuntimeError('Cannot downgrade: evaluation screening contexts still exist')
    op.drop_column('evaluation_runs','screening_context')
