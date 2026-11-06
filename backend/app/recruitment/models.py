"""招聘关系与历史：定义持久化模型、约束和索引。"""
from __future__ import annotations
from datetime import datetime
from decimal import Decimal
from typing import Any
import sqlalchemy as sa
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import Mapped, mapped_column
from app.core.db import Base

class Application(Base):
    """applications：人×岗位招聘关系。字段外键保护持久化引用，业务权限和状态转换由服务层控制。"""
    __tablename__ = "applications"
    candidate_id: Mapped[int] = mapped_column(mysql.BIGINT(unsigned=True), sa.ForeignKey("candidates.id", name="fk_applications_candidate_id_candidates", ondelete='RESTRICT'), nullable=False, comment='所属人才身份ID')
    job_id: Mapped[int] = mapped_column(mysql.BIGINT(unsigned=True), sa.ForeignKey("jobs.id", name="fk_applications_job_id_jobs", ondelete='RESTRICT'), nullable=False, comment='所属招聘岗位ID')
    source: Mapped[str] = mapped_column(sa.String(24), nullable=False, info={"allowed_values":["import","talent_pool"]}, comment='招聘关系来源；允许值：import,talent_pool')
    stage: Mapped[str] = mapped_column(sa.String(32), nullable=False, info={"allowed_values":["evaluating","assessment","hr_review","interview_pending","interview_passed","offer_pending","hired","rejected","withdrawn"]}, comment='招聘关系当前阶段；允许值：evaluating,assessment,hr_review,interview_pending,interview_passed,offer_pending,hired,rejected,withdrawn')
    current_evaluation_id: Mapped[int | None] = mapped_column(mysql.BIGINT(unsigned=True), sa.ForeignKey("evaluation_runs.id", name="fk_applications_current_evaluation_id_evaluation_runs", ondelete='RESTRICT', use_alter=True), nullable=True, comment='当前生效的筛选匹配运行ID')
    current_round: Mapped[int] = mapped_column(mysql.INTEGER(unsigned=True), nullable=False, default=1, server_default="1", comment='当前招聘考试轮次')
    ended_at: Mapped[datetime | None] = mapped_column(mysql.DATETIME(fsp=6), nullable=True, comment='招聘关系结束时间（UTC）')
    relationship_state: Mapped[str] = mapped_column(sa.String(24), nullable=False, info={"allowed_values":["active","merged"]}, comment='招聘关系的有效或合并状态；允许值：active,merged')
    canonical_application_id: Mapped[int | None] = mapped_column(mysql.BIGINT(unsigned=True), sa.ForeignKey("applications.id", name="fk_applications_canonical_application_id_applications", ondelete='RESTRICT'), nullable=True, comment='合并后保留的规范招聘关系ID')
    __table_args__ = (
        sa.CheckConstraint("source IN ('import','talent_pool')", name="ck_applications_source"),
        sa.CheckConstraint("stage IN ('evaluating','assessment','hr_review','interview_pending','interview_passed','offer_pending','hired','rejected','withdrawn')", name="ck_applications_stage"),
        sa.CheckConstraint("relationship_state IN ('active','merged')", name="ck_applications_relationship_state"),
        sa.UniqueConstraint("candidate_id", "job_id", name="uq_applications_candidate_id_job_id"),
        sa.Index("ix_applications_candidate_id", "candidate_id"),
        sa.Index("ix_applications_job_id", "job_id"),
        sa.Index("ix_applications_current_evaluation_id", "current_evaluation_id"),
        sa.Index("ix_applications_canonical_application_id", "canonical_application_id"),
        sa.Index("ix_applications_job_id_stage", "job_id", "stage"),
        sa.Index("ix_applications_candidate_id_created_at", "candidate_id", "created_at"),
        {"mysql_charset":"utf8mb4","mysql_collate":"utf8mb4_0900_ai_ci","comment":"人×岗位招聘关系"},
    )

class RecruitmentEvent(Base):
    """recruitment_events：阶段与面试评价历史。字段外键保护持久化引用，业务权限和状态转换由服务层控制。"""
    __tablename__ = "recruitment_events"
    application_id: Mapped[int] = mapped_column(mysql.BIGINT(unsigned=True), sa.ForeignKey("applications.id", name="fk_recruitment_events_application_id_applications", ondelete='RESTRICT'), nullable=False, comment='人才与岗位招聘关系ID')
    event_type: Mapped[str] = mapped_column(sa.String(50), nullable=False, comment='业务事件类型')
    from_stage: Mapped[str | None] = mapped_column(sa.String(32), nullable=True, comment='事件发生前招聘阶段')
    to_stage: Mapped[str | None] = mapped_column(sa.String(32), nullable=True, comment='事件发生后招聘阶段')
    content: Mapped[Any] = mapped_column(sa.JSON(), nullable=False, default=dict, comment='领域结构化内容或文本；按所属表解释')
    actor_id: Mapped[int] = mapped_column(mysql.BIGINT(unsigned=True), sa.ForeignKey("users.id", name="fk_recruitment_events_actor_id_users", ondelete='RESTRICT'), nullable=False, comment='执行操作的后台账号ID')
    __table_args__ = (
        sa.Index("ix_recruitment_events_application_id", "application_id"),
        sa.Index("ix_recruitment_events_actor_id", "actor_id"),
        sa.Index("ix_recruitment_events_application_id_created_at", "application_id", "created_at"),
        {"mysql_charset":"utf8mb4","mysql_collate":"utf8mb4_0900_ai_ci","comment":"阶段与面试评价历史"},
    )

