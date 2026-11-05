"""Seed the seven fixed disabled workflows; no dynamic script graph."""
from alembic import op
import sqlalchemy as sa

revision='0003_fixed_workflows'
down_revision='0002_current_pointers'
branch_labels=None
depends_on=None

TASK_TYPES=('extract','profile','match','question_generation','grade','knowledge_ask','embedding')

def upgrade():
    table=sa.table('workflow_configs',sa.column('task_type',sa.String),sa.column('enabled',sa.Boolean),
        sa.column('timeout_seconds',sa.Integer),sa.column('max_retries',sa.Integer),sa.column('config_revision',sa.Integer))
    op.bulk_insert(table,[{'task_type':task,'enabled':False,'timeout_seconds':60,'max_retries':1,'config_revision':1} for task in TASK_TYPES])

def downgrade():
    op.execute(sa.text("DELETE FROM workflow_configs WHERE task_type IN ('extract','profile','match','question_generation','grade','knowledge_ask','embedding')"))
