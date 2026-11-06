"""Clarify homonymous fields by domain; preserve the applied 0005 history."""
import sqlalchemy as sa
from alembic import op

revision='0006_comment_semantics'
down_revision='0005_schema_comments'
branch_labels=None
depends_on=None
CHANGES={
  "idempotency_records": {
    "request_key": [
      "批量导入请求幂等键",
      "请求幂等键；结合操作者范围与操作标识唯一"
    ]
  },
  "outbox_events": {
    "next_attempt_at": [
      "下一次邮件尝试时间（UTC）",
      "下一次Outbox事件投递尝试时间（UTC）"
    ]
  },
  "exam_attempts": {
    "final_score": [
      "人工复核后的单题正式分数",
      "本考次最终有效总分；正式结果以冻结成绩报告为准"
    ]
  },
  "exam_answers": {
    "final_score": [
      "人工复核后的单题正式分数",
      "本题最终有效得分；由评分与复核流程确认"
    ]
  },
  "match_results": {
    "total_score": [
      "冻结总分或正式成绩总分",
      "岗位匹配加权总分（0至100）；不等于考试成绩"
    ]
  },
  "paper_versions": {
    "total_score": [
      "冻结总分或正式成绩总分",
      "本版试卷满分；等于冻结题目满分之和"
    ]
  },
  "score_reports": {
    "total_score": [
      "冻结总分或正式成绩总分",
      "本次确认的考试正式总分"
    ]
  }
}

def _apply(restore=False):
    inspector=sa.inspect(op.get_bind())
    for table,fields in CHANGES.items():
        columns={c['name']:c for c in inspector.get_columns(table)}
        for name,pair in fields.items():
            column=columns[name];default=column.get('default')
            op.alter_column(table,name,comment=pair[0] if restore else pair[1],
                existing_type=column['type'],existing_nullable=column['nullable'],
                existing_server_default=sa.text(default) if default is not None else None,
                existing_autoincrement=column.get('autoincrement',False),existing_comment=column.get('comment'))

def upgrade():
    """Distinguish per-answer/exam totals, matching scores and general delivery keys."""
    _apply()

def downgrade():
    """Restore the exact descriptions applied in 0005 without changing business data."""
    _apply(restore=True)
