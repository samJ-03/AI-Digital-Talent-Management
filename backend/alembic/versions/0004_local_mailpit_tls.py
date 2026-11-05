"""Allow plaintext only as a stored local Mailpit mode; service rejects it elsewhere."""
from alembic import op
revision='0004_local_mailpit_tls'
down_revision='0003_fixed_workflows'
branch_labels=None
depends_on=None

def upgrade():
    op.drop_constraint('ck_mail_configs_tls_mode','mail_configs',type_='check')
    op.create_check_constraint('ck_mail_configs_tls_mode','mail_configs',"tls_mode IN ('starttls','tls','none')")

def downgrade():
    op.execute("UPDATE mail_configs SET tls_mode='starttls',state='disabled' WHERE tls_mode='none'")
    op.drop_constraint('ck_mail_configs_tls_mode','mail_configs',type_='check')
    op.create_check_constraint('ck_mail_configs_tls_mode','mail_configs',"tls_mode IN ('starttls','tls')")
