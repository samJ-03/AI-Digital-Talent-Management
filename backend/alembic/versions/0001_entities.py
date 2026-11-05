"""Initial immutable recruitment schema; generated once from reviewed v1 design."""
import sqlalchemy as sa
from sqlalchemy.dialects import mysql
from alembic import op

revision="0001_entities"
down_revision=None
branch_labels=None
depends_on=None

def upgrade():
    op.create_table("departments",
        sa.Column("id", mysql.BIGINT(unsigned=True), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("created_at", mysql.DATETIME(fsp=6), nullable=False, server_default=sa.func.current_timestamp(6)),
        sa.Column("updated_at", mysql.DATETIME(fsp=6), nullable=False, server_default=sa.func.current_timestamp(6)),
        sa.Column("row_version", mysql.INTEGER(unsigned=True), nullable=False, server_default='1'),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("parent_id", mysql.BIGINT(unsigned=True), nullable=True),
        sa.Column("status", sa.String(24), nullable=False, server_default="active"),
        sa.ForeignKeyConstraint(["parent_id"], ["departments.id"], name="fk_departments_parent_id_departments", ondelete='RESTRICT'),
        sa.CheckConstraint("status IN ('active','disabled')", name="ck_departments_status"),
        mysql_charset="utf8mb4", mysql_collate="utf8mb4_0900_ai_ci", comment="部门")
    op.create_index("ix_departments_parent_id", "departments", ["parent_id"])
    op.create_table("users",
        sa.Column("id", mysql.BIGINT(unsigned=True), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("created_at", mysql.DATETIME(fsp=6), nullable=False, server_default=sa.func.current_timestamp(6)),
        sa.Column("updated_at", mysql.DATETIME(fsp=6), nullable=False, server_default=sa.func.current_timestamp(6)),
        sa.Column("row_version", mysql.INTEGER(unsigned=True), nullable=False, server_default='1'),
        sa.Column("department_id", mysql.BIGINT(unsigned=True), nullable=True),
        sa.Column("login_name", sa.String(100), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="active"),
        sa.Column("auth_version", mysql.INTEGER(unsigned=True), nullable=False, server_default="1"),
        sa.ForeignKeyConstraint(["department_id"], ["departments.id"], name="fk_users_department_id_departments", ondelete='RESTRICT'),
        sa.UniqueConstraint("login_name", name="uq_users_login_name"),
        sa.CheckConstraint("status IN ('active','disabled')", name="ck_users_status"),
        mysql_charset="utf8mb4", mysql_collate="utf8mb4_0900_ai_ci", comment="后台账号")
    op.create_index("ix_users_department_id", "users", ["department_id"])
    op.create_table("roles",
        sa.Column("id", mysql.BIGINT(unsigned=True), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("created_at", mysql.DATETIME(fsp=6), nullable=False, server_default=sa.func.current_timestamp(6)),
        sa.Column("updated_at", mysql.DATETIME(fsp=6), nullable=False, server_default=sa.func.current_timestamp(6)),
        sa.Column("row_version", mysql.INTEGER(unsigned=True), nullable=False, server_default='1'),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("permission_codes", sa.JSON(), nullable=False),
        sa.Column("data_scope", sa.String(24), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="active"),
        sa.UniqueConstraint("code", name="uq_roles_code"),
        sa.CheckConstraint("data_scope IN ('department','company')", name="ck_roles_data_scope"),
        sa.CheckConstraint("status IN ('active','disabled')", name="ck_roles_status"),
        mysql_charset="utf8mb4", mysql_collate="utf8mb4_0900_ai_ci", comment="角色")
    op.create_table("user_roles",
        sa.Column("id", mysql.BIGINT(unsigned=True), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("created_at", mysql.DATETIME(fsp=6), nullable=False, server_default=sa.func.current_timestamp(6)),
        sa.Column("updated_at", mysql.DATETIME(fsp=6), nullable=False, server_default=sa.func.current_timestamp(6)),
        sa.Column("row_version", mysql.INTEGER(unsigned=True), nullable=False, server_default='1'),
        sa.Column("user_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("role_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_user_roles_user_id_users", ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], name="fk_user_roles_role_id_roles", ondelete='RESTRICT'),
        sa.UniqueConstraint("user_id", "role_id", name="uq_user_roles_user_id_role_id"),
        mysql_charset="utf8mb4", mysql_collate="utf8mb4_0900_ai_ci", comment="账号角色")
    op.create_index("ix_user_roles_user_id", "user_roles", ["user_id"])
    op.create_index("ix_user_roles_role_id", "user_roles", ["role_id"])
    op.create_table("stored_files",
        sa.Column("id", mysql.BIGINT(unsigned=True), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("created_at", mysql.DATETIME(fsp=6), nullable=False, server_default=sa.func.current_timestamp(6)),
        sa.Column("updated_at", mysql.DATETIME(fsp=6), nullable=False, server_default=sa.func.current_timestamp(6)),
        sa.Column("row_version", mysql.INTEGER(unsigned=True), nullable=False, server_default='1'),
        sa.Column("bucket", sa.String(100), nullable=False),
        sa.Column("object_key", sa.String(500, collation='utf8mb4_bin'), nullable=False),
        sa.Column("sha256", sa.CHAR(64, collation='utf8mb4_bin'), nullable=False),
        sa.Column("original_name", sa.String(255), nullable=False),
        sa.Column("mime_type", sa.String(120), nullable=False),
        sa.Column("size_bytes", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("uploader_id", mysql.BIGINT(unsigned=True), nullable=True),
        sa.Column("status", sa.String(24), nullable=False, server_default="staged"),
        sa.ForeignKeyConstraint(["uploader_id"], ["users.id"], name="fk_stored_files_uploader_id_users", ondelete='RESTRICT'),
        sa.CheckConstraint("status IN ('staged','ready','quarantined','deleted')", name="ck_stored_files_status"),
        sa.UniqueConstraint("bucket", "object_key", name="uq_stored_files_bucket_object_key"),
        mysql_charset="utf8mb4", mysql_collate="utf8mb4_0900_ai_ci", comment="私有文件")
    op.create_index("ix_stored_files_uploader_id", "stored_files", ["uploader_id"])
    op.create_index("ix_stored_files_sha256", "stored_files", ["sha256"])
    op.create_table("jobs",
        sa.Column("id", mysql.BIGINT(unsigned=True), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("created_at", mysql.DATETIME(fsp=6), nullable=False, server_default=sa.func.current_timestamp(6)),
        sa.Column("updated_at", mysql.DATETIME(fsp=6), nullable=False, server_default=sa.func.current_timestamp(6)),
        sa.Column("row_version", mysql.INTEGER(unsigned=True), nullable=False, server_default='1'),
        sa.Column("department_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("owner_hr_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("headcount", mysql.INTEGER(unsigned=True), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="draft"),
        sa.Column("current_version_id", mysql.BIGINT(unsigned=True), nullable=True),
        sa.Column("auto_invite_enabled", sa.Boolean(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["department_id"], ["departments.id"], name="fk_jobs_department_id_departments", ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(["owner_hr_id"], ["users.id"], name="fk_jobs_owner_hr_id_users", ondelete='RESTRICT'),
        sa.CheckConstraint("headcount > 0", name="ck_jobs_headcount_positive"),
        sa.CheckConstraint("status IN ('draft','open','paused','closed')", name="ck_jobs_status"),
        mysql_charset="utf8mb4", mysql_collate="utf8mb4_0900_ai_ci", comment="岗位主对象")
    op.create_index("ix_jobs_department_id", "jobs", ["department_id"])
    op.create_index("ix_jobs_owner_hr_id", "jobs", ["owner_hr_id"])
    op.create_index("ix_jobs_current_version_id", "jobs", ["current_version_id"])
    op.create_index("ix_jobs_department_id_status", "jobs", ["department_id","status"])
    op.create_table("import_batches",
        sa.Column("id", mysql.BIGINT(unsigned=True), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("created_at", mysql.DATETIME(fsp=6), nullable=False, server_default=sa.func.current_timestamp(6)),
        sa.Column("updated_at", mysql.DATETIME(fsp=6), nullable=False, server_default=sa.func.current_timestamp(6)),
        sa.Column("row_version", mysql.INTEGER(unsigned=True), nullable=False, server_default='1'),
        sa.Column("job_id", mysql.BIGINT(unsigned=True), nullable=True),
        sa.Column("created_by", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="queued"),
        sa.Column("request_key", sa.String(100, collation='utf8mb4_bin'), nullable=False),
        sa.Column("file_count", mysql.INTEGER(unsigned=True), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], name="fk_import_batches_job_id_jobs", ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], name="fk_import_batches_created_by_users", ondelete='RESTRICT'),
        sa.CheckConstraint("status IN ('queued','processing','completed','partial_failed')", name="ck_import_batches_status"),
        sa.UniqueConstraint("created_by", "request_key", name="uq_import_batches_created_by_request_key"),
        mysql_charset="utf8mb4", mysql_collate="utf8mb4_0900_ai_ci", comment="导入批次")
    op.create_index("ix_import_batches_job_id", "import_batches", ["job_id"])
    op.create_index("ix_import_batches_created_by", "import_batches", ["created_by"])
    op.create_table("candidates",
        sa.Column("id", mysql.BIGINT(unsigned=True), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("created_at", mysql.DATETIME(fsp=6), nullable=False, server_default=sa.func.current_timestamp(6)),
        sa.Column("updated_at", mysql.DATETIME(fsp=6), nullable=False, server_default=sa.func.current_timestamp(6)),
        sa.Column("row_version", mysql.INTEGER(unsigned=True), nullable=False, server_default='1'),
        sa.Column("display_name", sa.String(120), nullable=False),
        sa.Column("email", sa.String(254), nullable=True),
        sa.Column("email_normalized", sa.String(254, collation='utf8mb4_bin'), nullable=True),
        sa.Column("email_valid", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("phone", sa.String(64), nullable=True),
        sa.Column("phone_normalized", sa.String(64, collation='utf8mb4_bin'), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending_email"),
        sa.Column("current_resume_version_id", mysql.BIGINT(unsigned=True), nullable=True),
        sa.Column("current_profile_id", mysql.BIGINT(unsigned=True), nullable=True),
        sa.Column("merged_into_id", mysql.BIGINT(unsigned=True), nullable=True),
        sa.ForeignKeyConstraint(["merged_into_id"], ["candidates.id"], name="fk_candidates_merged_into_id_candidates", ondelete='RESTRICT'),
        sa.CheckConstraint("status IN ('pending_email','duplicate_review','ready','archived','merged')", name="ck_candidates_status"),
        mysql_charset="utf8mb4", mysql_collate="utf8mb4_0900_ai_ci", comment="人才身份")
    op.create_index("ix_candidates_current_resume_version_id", "candidates", ["current_resume_version_id"])
    op.create_index("ix_candidates_current_profile_id", "candidates", ["current_profile_id"])
    op.create_index("ix_candidates_merged_into_id", "candidates", ["merged_into_id"])
    op.create_table("resume_versions",
        sa.Column("id", mysql.BIGINT(unsigned=True), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("created_at", mysql.DATETIME(fsp=6), nullable=False, server_default=sa.func.current_timestamp(6)),
        sa.Column("updated_at", mysql.DATETIME(fsp=6), nullable=False, server_default=sa.func.current_timestamp(6)),
        sa.Column("row_version", mysql.INTEGER(unsigned=True), nullable=False, server_default='1'),
        sa.Column("candidate_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("file_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("version_no", mysql.INTEGER(unsigned=True), nullable=False),
        sa.Column("parent_version_id", mysql.BIGINT(unsigned=True), nullable=True),
        sa.Column("raw_text", mysql.LONGTEXT(), nullable=True),
        sa.Column("structured_data", sa.JSON(), nullable=False),
        sa.Column("field_sources", sa.JSON(), nullable=False),
        sa.Column("parser_revision", sa.String(100), nullable=False),
        sa.Column("state", sa.String(24), nullable=False, server_default="extracted"),
        sa.Column("change_reason", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidates.id"], name="fk_resume_versions_candidate_id_candidates", ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(["file_id"], ["stored_files.id"], name="fk_resume_versions_file_id_stored_files", ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(["parent_version_id"], ["resume_versions.id"], name="fk_resume_versions_parent_version_id_resume_versions", ondelete='RESTRICT'),
        sa.CheckConstraint("state IN ('extracted','confirmed','superseded')", name="ck_resume_versions_state"),
        sa.UniqueConstraint("candidate_id", "version_no", name="uq_resume_versions_candidate_id_version_no"),
        mysql_charset="utf8mb4", mysql_collate="utf8mb4_0900_ai_ci", comment="简历与校正版本")
    op.create_index("ix_resume_versions_candidate_id", "resume_versions", ["candidate_id"])
    op.create_index("ix_resume_versions_file_id", "resume_versions", ["file_id"])
    op.create_index("ix_resume_versions_parent_version_id", "resume_versions", ["parent_version_id"])
    op.create_index("ix_resume_versions_candidate_id_created_at", "resume_versions", ["candidate_id","created_at"])
    op.create_table("import_items",
        sa.Column("id", mysql.BIGINT(unsigned=True), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("created_at", mysql.DATETIME(fsp=6), nullable=False, server_default=sa.func.current_timestamp(6)),
        sa.Column("updated_at", mysql.DATETIME(fsp=6), nullable=False, server_default=sa.func.current_timestamp(6)),
        sa.Column("row_version", mysql.INTEGER(unsigned=True), nullable=False, server_default='1'),
        sa.Column("batch_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("file_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("resume_version_id", mysql.BIGINT(unsigned=True), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="uploaded"),
        sa.Column("error_code", sa.String(64), nullable=True),
        sa.Column("error_detail_safe", sa.Text(), nullable=True),
        sa.Column("source_order", mysql.INTEGER(unsigned=True), nullable=False),
        sa.ForeignKeyConstraint(["batch_id"], ["import_batches.id"], name="fk_import_items_batch_id_import_batches", ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(["file_id"], ["stored_files.id"], name="fk_import_items_file_id_stored_files", ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(["resume_version_id"], ["resume_versions.id"], name="fk_import_items_resume_version_id_resume_versions", ondelete='RESTRICT'),
        sa.CheckConstraint("status IN ('uploaded','queued','parsing','parsed','failed')", name="ck_import_items_status"),
        sa.UniqueConstraint("batch_id", "source_order", name="uq_import_items_batch_id_source_order"),
        mysql_charset="utf8mb4", mysql_collate="utf8mb4_0900_ai_ci", comment="每份文件的导入处理")
    op.create_index("ix_import_items_batch_id", "import_items", ["batch_id"])
    op.create_index("ix_import_items_file_id", "import_items", ["file_id"])
    op.create_index("ix_import_items_resume_version_id", "import_items", ["resume_version_id"])
    op.create_index("ix_import_items_batch_id_status", "import_items", ["batch_id","status"])
    op.create_table("duplicate_cases",
        sa.Column("id", mysql.BIGINT(unsigned=True), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("created_at", mysql.DATETIME(fsp=6), nullable=False, server_default=sa.func.current_timestamp(6)),
        sa.Column("updated_at", mysql.DATETIME(fsp=6), nullable=False, server_default=sa.func.current_timestamp(6)),
        sa.Column("row_version", mysql.INTEGER(unsigned=True), nullable=False, server_default='1'),
        sa.Column("candidate_a_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("candidate_b_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="pending"),
        sa.Column("resolved_by", mysql.BIGINT(unsigned=True), nullable=True),
        sa.Column("resolution_reason", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["candidate_a_id"], ["candidates.id"], name="fk_duplicate_cases_candidate_a_id_candidates", ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(["candidate_b_id"], ["candidates.id"], name="fk_duplicate_cases_candidate_b_id_candidates", ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(["resolved_by"], ["users.id"], name="fk_duplicate_cases_resolved_by_users", ondelete='RESTRICT'),
        sa.CheckConstraint("status IN ('pending','same_person','different_person')", name="ck_duplicate_cases_status"),
        sa.UniqueConstraint("candidate_a_id", "candidate_b_id", name="uq_duplicate_cases_candidate_a_id_candidate_b_id"),
        mysql_charset="utf8mb4", mysql_collate="utf8mb4_0900_ai_ci", comment="疑似重复与合并审计")
    op.create_index("ix_duplicate_cases_candidate_a_id", "duplicate_cases", ["candidate_a_id"])
    op.create_index("ix_duplicate_cases_candidate_b_id", "duplicate_cases", ["candidate_b_id"])
    op.create_index("ix_duplicate_cases_resolved_by", "duplicate_cases", ["resolved_by"])
    op.create_table("applications",
        sa.Column("id", mysql.BIGINT(unsigned=True), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("created_at", mysql.DATETIME(fsp=6), nullable=False, server_default=sa.func.current_timestamp(6)),
        sa.Column("updated_at", mysql.DATETIME(fsp=6), nullable=False, server_default=sa.func.current_timestamp(6)),
        sa.Column("row_version", mysql.INTEGER(unsigned=True), nullable=False, server_default='1'),
        sa.Column("candidate_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("job_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("source", sa.String(24), nullable=False),
        sa.Column("stage", sa.String(32), nullable=False),
        sa.Column("current_evaluation_id", mysql.BIGINT(unsigned=True), nullable=True),
        sa.Column("current_round", mysql.INTEGER(unsigned=True), nullable=False, server_default="1"),
        sa.Column("ended_at", mysql.DATETIME(fsp=6), nullable=True),
        sa.Column("relationship_state", sa.String(24), nullable=False),
        sa.Column("canonical_application_id", mysql.BIGINT(unsigned=True), nullable=True),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidates.id"], name="fk_applications_candidate_id_candidates", ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], name="fk_applications_job_id_jobs", ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(["canonical_application_id"], ["applications.id"], name="fk_applications_canonical_application_id_applications", ondelete='RESTRICT'),
        sa.CheckConstraint("source IN ('import','talent_pool')", name="ck_applications_source"),
        sa.CheckConstraint("stage IN ('evaluating','assessment','hr_review','interview_pending','interview_passed','offer_pending','hired','rejected','withdrawn')", name="ck_applications_stage"),
        sa.CheckConstraint("relationship_state IN ('active','merged')", name="ck_applications_relationship_state"),
        sa.UniqueConstraint("candidate_id", "job_id", name="uq_applications_candidate_id_job_id"),
        mysql_charset="utf8mb4", mysql_collate="utf8mb4_0900_ai_ci", comment="人×岗位招聘关系")
    op.create_index("ix_applications_candidate_id", "applications", ["candidate_id"])
    op.create_index("ix_applications_job_id", "applications", ["job_id"])
    op.create_index("ix_applications_current_evaluation_id", "applications", ["current_evaluation_id"])
    op.create_index("ix_applications_canonical_application_id", "applications", ["canonical_application_id"])
    op.create_index("ix_applications_job_id_stage", "applications", ["job_id","stage"])
    op.create_index("ix_applications_candidate_id_created_at", "applications", ["candidate_id","created_at"])
    op.create_table("recruitment_events",
        sa.Column("id", mysql.BIGINT(unsigned=True), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("created_at", mysql.DATETIME(fsp=6), nullable=False, server_default=sa.func.current_timestamp(6)),
        sa.Column("updated_at", mysql.DATETIME(fsp=6), nullable=False, server_default=sa.func.current_timestamp(6)),
        sa.Column("row_version", mysql.INTEGER(unsigned=True), nullable=False, server_default='1'),
        sa.Column("application_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("from_stage", sa.String(32), nullable=True),
        sa.Column("to_stage", sa.String(32), nullable=True),
        sa.Column("content", sa.JSON(), nullable=False),
        sa.Column("actor_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.ForeignKeyConstraint(["application_id"], ["applications.id"], name="fk_recruitment_events_application_id_applications", ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], name="fk_recruitment_events_actor_id_users", ondelete='RESTRICT'),
        mysql_charset="utf8mb4", mysql_collate="utf8mb4_0900_ai_ci", comment="阶段与面试评价历史")
    op.create_index("ix_recruitment_events_application_id", "recruitment_events", ["application_id"])
    op.create_index("ix_recruitment_events_actor_id", "recruitment_events", ["actor_id"])
    op.create_index("ix_recruitment_events_application_id_created_at", "recruitment_events", ["application_id","created_at"])
    op.create_table("question_banks",
        sa.Column("id", mysql.BIGINT(unsigned=True), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("created_at", mysql.DATETIME(fsp=6), nullable=False, server_default=sa.func.current_timestamp(6)),
        sa.Column("updated_at", mysql.DATETIME(fsp=6), nullable=False, server_default=sa.func.current_timestamp(6)),
        sa.Column("row_version", mysql.INTEGER(unsigned=True), nullable=False, server_default='1'),
        sa.Column("department_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="active"),
        sa.Column("created_by", mysql.BIGINT(unsigned=True), nullable=False),
        sa.ForeignKeyConstraint(["department_id"], ["departments.id"], name="fk_question_banks_department_id_departments", ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], name="fk_question_banks_created_by_users", ondelete='RESTRICT'),
        sa.CheckConstraint("status IN ('active','archived')", name="ck_question_banks_status"),
        mysql_charset="utf8mb4", mysql_collate="utf8mb4_0900_ai_ci", comment="题库")
    op.create_index("ix_question_banks_department_id", "question_banks", ["department_id"])
    op.create_index("ix_question_banks_created_by", "question_banks", ["created_by"])
    op.create_index("ix_question_banks_department_id_status", "question_banks", ["department_id","status"])
    op.create_table("questions",
        sa.Column("id", mysql.BIGINT(unsigned=True), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("created_at", mysql.DATETIME(fsp=6), nullable=False, server_default=sa.func.current_timestamp(6)),
        sa.Column("updated_at", mysql.DATETIME(fsp=6), nullable=False, server_default=sa.func.current_timestamp(6)),
        sa.Column("row_version", mysql.INTEGER(unsigned=True), nullable=False, server_default='1'),
        sa.Column("bank_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("logical_key", sa.CHAR(36, collation='utf8mb4_bin'), nullable=False),
        sa.Column("revision_no", mysql.INTEGER(unsigned=True), nullable=False),
        sa.Column("question_type", sa.String(24), nullable=False),
        sa.Column("stem", sa.Text(), nullable=False),
        sa.Column("options", sa.JSON(), nullable=True),
        sa.Column("answer_key", sa.JSON(), nullable=True),
        sa.Column("rubric", sa.JSON(), nullable=False),
        sa.Column("reference_sources", sa.JSON(), nullable=False),
        sa.Column("state", sa.String(24), nullable=False, server_default="draft"),
        sa.ForeignKeyConstraint(["bank_id"], ["question_banks.id"], name="fk_questions_bank_id_question_banks", ondelete='RESTRICT'),
        sa.CheckConstraint("question_type IN ('single_choice','multiple_choice','short_answer')", name="ck_questions_question_type"),
        sa.CheckConstraint("state IN ('draft','approved','archived')", name="ck_questions_state"),
        sa.UniqueConstraint("logical_key", "revision_no", name="uq_questions_logical_key_revision_no"),
        mysql_charset="utf8mb4", mysql_collate="utf8mb4_0900_ai_ci", comment="题库题目修订")
    op.create_index("ix_questions_bank_id", "questions", ["bank_id"])
    op.create_index("ix_questions_bank_id_state", "questions", ["bank_id","state"])
    op.create_table("papers",
        sa.Column("id", mysql.BIGINT(unsigned=True), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("created_at", mysql.DATETIME(fsp=6), nullable=False, server_default=sa.func.current_timestamp(6)),
        sa.Column("updated_at", mysql.DATETIME(fsp=6), nullable=False, server_default=sa.func.current_timestamp(6)),
        sa.Column("row_version", mysql.INTEGER(unsigned=True), nullable=False, server_default='1'),
        sa.Column("department_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("created_by", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="active"),
        sa.ForeignKeyConstraint(["department_id"], ["departments.id"], name="fk_papers_department_id_departments", ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], name="fk_papers_created_by_users", ondelete='RESTRICT'),
        sa.CheckConstraint("status IN ('active','archived')", name="ck_papers_status"),
        mysql_charset="utf8mb4", mysql_collate="utf8mb4_0900_ai_ci", comment="试卷主对象")
    op.create_index("ix_papers_department_id", "papers", ["department_id"])
    op.create_index("ix_papers_created_by", "papers", ["created_by"])
    op.create_index("ix_papers_department_id_status", "papers", ["department_id","status"])
    op.create_table("paper_versions",
        sa.Column("id", mysql.BIGINT(unsigned=True), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("created_at", mysql.DATETIME(fsp=6), nullable=False, server_default=sa.func.current_timestamp(6)),
        sa.Column("updated_at", mysql.DATETIME(fsp=6), nullable=False, server_default=sa.func.current_timestamp(6)),
        sa.Column("row_version", mysql.INTEGER(unsigned=True), nullable=False, server_default='1'),
        sa.Column("paper_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("version_no", mysql.INTEGER(unsigned=True), nullable=False),
        sa.Column("duration_minutes", mysql.INTEGER(unsigned=True), nullable=False),
        sa.Column("total_score", sa.Numeric(6, 2), nullable=False),
        sa.Column("reference_pass_score", sa.Numeric(6, 2), nullable=True),
        sa.Column("status", sa.String(24), nullable=False, server_default="draft"),
        sa.Column("published_by", mysql.BIGINT(unsigned=True), nullable=True),
        sa.Column("published_at", mysql.DATETIME(fsp=6), nullable=True),
        sa.ForeignKeyConstraint(["paper_id"], ["papers.id"], name="fk_paper_versions_paper_id_papers", ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(["published_by"], ["users.id"], name="fk_paper_versions_published_by_users", ondelete='RESTRICT'),
        sa.CheckConstraint("duration_minutes > 0", name="ck_paper_versions_duration_minutes_positive"),
        sa.CheckConstraint("total_score > 0", name="ck_paper_versions_total_score_positive"),
        sa.CheckConstraint("status IN ('draft','published')", name="ck_paper_versions_status"),
        sa.UniqueConstraint("paper_id", "version_no", name="uq_paper_versions_paper_id_version_no"),
        mysql_charset="utf8mb4", mysql_collate="utf8mb4_0900_ai_ci", comment="试卷版本")
    op.create_index("ix_paper_versions_paper_id", "paper_versions", ["paper_id"])
    op.create_index("ix_paper_versions_published_by", "paper_versions", ["published_by"])
    op.create_table("job_versions",
        sa.Column("id", mysql.BIGINT(unsigned=True), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("created_at", mysql.DATETIME(fsp=6), nullable=False, server_default=sa.func.current_timestamp(6)),
        sa.Column("updated_at", mysql.DATETIME(fsp=6), nullable=False, server_default=sa.func.current_timestamp(6)),
        sa.Column("row_version", mysql.INTEGER(unsigned=True), nullable=False, server_default='1'),
        sa.Column("job_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("version_no", mysql.INTEGER(unsigned=True), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("conditions", sa.JSON(), nullable=False),
        sa.Column("match_weights", sa.JSON(), nullable=False),
        sa.Column("invite_threshold", sa.Numeric(5, 2), nullable=False),
        sa.Column("paper_version_id", mysql.BIGINT(unsigned=True), nullable=True),
        sa.Column("invite_valid_hours", mysql.INTEGER(unsigned=True), nullable=False),
        sa.Column("mail_template", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="draft"),
        sa.Column("published_by", mysql.BIGINT(unsigned=True), nullable=True),
        sa.Column("published_at", mysql.DATETIME(fsp=6), nullable=True),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], name="fk_job_versions_job_id_jobs", ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(["paper_version_id"], ["paper_versions.id"], name="fk_job_versions_paper_version_id_paper_versions", ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(["published_by"], ["users.id"], name="fk_job_versions_published_by_users", ondelete='RESTRICT'),
        sa.CheckConstraint("invite_threshold >= 0 AND invite_threshold <= 100", name="ck_job_versions_invite_threshold_range"),
        sa.CheckConstraint("invite_valid_hours > 0", name="ck_job_versions_invite_valid_hours_positive"),
        sa.CheckConstraint("status IN ('draft','published')", name="ck_job_versions_status"),
        sa.UniqueConstraint("job_id", "version_no", name="uq_job_versions_job_id_version_no"),
        mysql_charset="utf8mb4", mysql_collate="utf8mb4_0900_ai_ci", comment="岗位发布版本")
    op.create_index("ix_job_versions_job_id", "job_versions", ["job_id"])
    op.create_index("ix_job_versions_paper_version_id", "job_versions", ["paper_version_id"])
    op.create_index("ix_job_versions_published_by", "job_versions", ["published_by"])
    op.create_table("paper_items",
        sa.Column("id", mysql.BIGINT(unsigned=True), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("created_at", mysql.DATETIME(fsp=6), nullable=False, server_default=sa.func.current_timestamp(6)),
        sa.Column("updated_at", mysql.DATETIME(fsp=6), nullable=False, server_default=sa.func.current_timestamp(6)),
        sa.Column("row_version", mysql.INTEGER(unsigned=True), nullable=False, server_default='1'),
        sa.Column("paper_version_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("source_question_id", mysql.BIGINT(unsigned=True), nullable=True),
        sa.Column("position_no", mysql.INTEGER(unsigned=True), nullable=False),
        sa.Column("question_type", sa.String(24), nullable=False),
        sa.Column("stem", sa.Text(), nullable=False),
        sa.Column("options", sa.JSON(), nullable=True),
        sa.Column("max_score", sa.Numeric(6, 2), nullable=False),
        sa.Column("answer_key", sa.JSON(), nullable=True),
        sa.Column("rubric", sa.JSON(), nullable=False),
        sa.Column("reference_sources", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["paper_version_id"], ["paper_versions.id"], name="fk_paper_items_paper_version_id_paper_versions", ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(["source_question_id"], ["questions.id"], name="fk_paper_items_source_question_id_questions", ondelete='RESTRICT'),
        sa.CheckConstraint("max_score >= 0", name="ck_paper_items_max_score_nonnegative"),
        sa.UniqueConstraint("paper_version_id", "position_no", name="uq_paper_items_paper_version_id_position_no"),
        mysql_charset="utf8mb4", mysql_collate="utf8mb4_0900_ai_ci", comment="冻结试题与评分标准")
    op.create_index("ix_paper_items_paper_version_id", "paper_items", ["paper_version_id"])
    op.create_index("ix_paper_items_source_question_id", "paper_items", ["source_question_id"])
    op.create_table("knowledge_documents",
        sa.Column("id", mysql.BIGINT(unsigned=True), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("created_at", mysql.DATETIME(fsp=6), nullable=False, server_default=sa.func.current_timestamp(6)),
        sa.Column("updated_at", mysql.DATETIME(fsp=6), nullable=False, server_default=sa.func.current_timestamp(6)),
        sa.Column("row_version", mysql.INTEGER(unsigned=True), nullable=False, server_default='1'),
        sa.Column("logical_key", sa.CHAR(36, collation='utf8mb4_bin'), nullable=False),
        sa.Column("version_no", mysql.INTEGER(unsigned=True), nullable=False),
        sa.Column("file_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("category", sa.String(50), nullable=False),
        sa.Column("scope", sa.String(24), nullable=False),
        sa.Column("department_id", mysql.BIGINT(unsigned=True), nullable=True),
        sa.Column("state", sa.String(24), nullable=False, server_default="draft"),
        sa.ForeignKeyConstraint(["file_id"], ["stored_files.id"], name="fk_knowledge_documents_file_id_stored_files", ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(["department_id"], ["departments.id"], name="fk_knowledge_documents_department_id_departments", ondelete='RESTRICT'),
        sa.CheckConstraint("category IN ('job','technical','rubric','reference')", name="ck_knowledge_documents_category"),
        sa.CheckConstraint("scope IN ('company','department')", name="ck_knowledge_documents_scope"),
        sa.CheckConstraint("state IN ('draft','processing','published','failed','archived')", name="ck_knowledge_documents_state"),
        sa.UniqueConstraint("logical_key", "version_no", name="uq_knowledge_documents_logical_key_version_no"),
        mysql_charset="utf8mb4", mysql_collate="utf8mb4_0900_ai_ci", comment="招聘资料版本")
    op.create_index("ix_knowledge_documents_file_id", "knowledge_documents", ["file_id"])
    op.create_index("ix_knowledge_documents_department_id", "knowledge_documents", ["department_id"])
    op.create_index("ix_knowledge_documents_scope_department_id_state", "knowledge_documents", ["scope","department_id","state"])
    op.create_table("knowledge_chunks",
        sa.Column("id", mysql.BIGINT(unsigned=True), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("created_at", mysql.DATETIME(fsp=6), nullable=False, server_default=sa.func.current_timestamp(6)),
        sa.Column("updated_at", mysql.DATETIME(fsp=6), nullable=False, server_default=sa.func.current_timestamp(6)),
        sa.Column("row_version", mysql.INTEGER(unsigned=True), nullable=False, server_default='1'),
        sa.Column("document_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("chunk_no", mysql.INTEGER(unsigned=True), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("source_locator", sa.JSON(), nullable=False),
        sa.Column("content_hash", sa.CHAR(64, collation='utf8mb4_bin'), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["knowledge_documents.id"], name="fk_knowledge_chunks_document_id_knowledge_documents", ondelete='RESTRICT'),
        sa.UniqueConstraint("document_id", "chunk_no", name="uq_knowledge_chunks_document_id_chunk_no"),
        mysql_charset="utf8mb4", mysql_collate="utf8mb4_0900_ai_ci", comment="带来源切片")
    op.create_index("ix_knowledge_chunks_document_id", "knowledge_chunks", ["document_id"])
    op.create_table("model_configs",
        sa.Column("id", mysql.BIGINT(unsigned=True), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("created_at", mysql.DATETIME(fsp=6), nullable=False, server_default=sa.func.current_timestamp(6)),
        sa.Column("updated_at", mysql.DATETIME(fsp=6), nullable=False, server_default=sa.func.current_timestamp(6)),
        sa.Column("row_version", mysql.INTEGER(unsigned=True), nullable=False, server_default='1'),
        sa.Column("logical_key", sa.String(100, collation='utf8mb4_bin'), nullable=False),
        sa.Column("revision_no", mysql.INTEGER(unsigned=True), nullable=False),
        sa.Column("provider_type", sa.String(32), nullable=False),
        sa.Column("base_url", sa.String(500), nullable=False),
        sa.Column("model_name", sa.String(150), nullable=False),
        sa.Column("model_digest", sa.String(255), nullable=True),
        sa.Column("capabilities", sa.JSON(), nullable=False),
        sa.Column("embedding_dimension", mysql.INTEGER(unsigned=True), nullable=True),
        sa.Column("secret_ciphertext", sa.Text(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="0"),
        sa.CheckConstraint("provider_type IN ('ollama','compatible_http')", name="ck_model_configs_provider_type"),
        sa.UniqueConstraint("logical_key", "revision_no", name="uq_model_configs_logical_key_revision_no"),
        mysql_charset="utf8mb4", mysql_collate="utf8mb4_0900_ai_ci", comment="模型连接及修订")
    op.create_table("prompt_versions",
        sa.Column("id", mysql.BIGINT(unsigned=True), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("created_at", mysql.DATETIME(fsp=6), nullable=False, server_default=sa.func.current_timestamp(6)),
        sa.Column("updated_at", mysql.DATETIME(fsp=6), nullable=False, server_default=sa.func.current_timestamp(6)),
        sa.Column("row_version", mysql.INTEGER(unsigned=True), nullable=False, server_default='1'),
        sa.Column("task_type", sa.String(50), nullable=False),
        sa.Column("revision_no", mysql.INTEGER(unsigned=True), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("output_schema", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="draft"),
        sa.Column("published_by", mysql.BIGINT(unsigned=True), nullable=True),
        sa.ForeignKeyConstraint(["published_by"], ["users.id"], name="fk_prompt_versions_published_by_users", ondelete='RESTRICT'),
        sa.CheckConstraint("status IN ('draft','published')", name="ck_prompt_versions_status"),
        sa.UniqueConstraint("task_type", "revision_no", name="uq_prompt_versions_task_type_revision_no"),
        mysql_charset="utf8mb4", mysql_collate="utf8mb4_0900_ai_ci", comment="提示词版本")
    op.create_index("ix_prompt_versions_published_by", "prompt_versions", ["published_by"])
    op.create_table("workflow_configs",
        sa.Column("id", mysql.BIGINT(unsigned=True), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("created_at", mysql.DATETIME(fsp=6), nullable=False, server_default=sa.func.current_timestamp(6)),
        sa.Column("updated_at", mysql.DATETIME(fsp=6), nullable=False, server_default=sa.func.current_timestamp(6)),
        sa.Column("row_version", mysql.INTEGER(unsigned=True), nullable=False, server_default='1'),
        sa.Column("task_type", sa.String(50), nullable=False),
        sa.Column("model_config_id", mysql.BIGINT(unsigned=True), nullable=True),
        sa.Column("prompt_version_id", mysql.BIGINT(unsigned=True), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("timeout_seconds", mysql.INTEGER(unsigned=True), nullable=False),
        sa.Column("max_retries", mysql.INTEGER(unsigned=True), nullable=False),
        sa.Column("config_revision", mysql.INTEGER(unsigned=True), nullable=False),
        sa.ForeignKeyConstraint(["model_config_id"], ["model_configs.id"], name="fk_workflow_configs_model_config_id_model_configs", ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(["prompt_version_id"], ["prompt_versions.id"], name="fk_workflow_configs_prompt_version_id_prompt_versions", ondelete='RESTRICT'),
        sa.UniqueConstraint("task_type", name="uq_workflow_configs_task_type"),
        mysql_charset="utf8mb4", mysql_collate="utf8mb4_0900_ai_ci", comment="固定流程配置")
    op.create_index("ix_workflow_configs_model_config_id", "workflow_configs", ["model_config_id"])
    op.create_index("ix_workflow_configs_prompt_version_id", "workflow_configs", ["prompt_version_id"])
    op.create_table("background_jobs",
        sa.Column("id", mysql.BIGINT(unsigned=True), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("created_at", mysql.DATETIME(fsp=6), nullable=False, server_default=sa.func.current_timestamp(6)),
        sa.Column("updated_at", mysql.DATETIME(fsp=6), nullable=False, server_default=sa.func.current_timestamp(6)),
        sa.Column("row_version", mysql.INTEGER(unsigned=True), nullable=False, server_default='1'),
        sa.Column("job_type", sa.String(50), nullable=False),
        sa.Column("entity_type", sa.String(50), nullable=False),
        sa.Column("entity_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("idempotency_key", sa.String(190, collation='utf8mb4_bin'), nullable=False),
        sa.Column("input_refs", sa.JSON(), nullable=False),
        sa.Column("state", sa.String(24), nullable=False, server_default="queued"),
        sa.Column("attempt_count", mysql.INTEGER(unsigned=True), nullable=False, server_default="0"),
        sa.Column("lease_owner", sa.String(100), nullable=True),
        sa.Column("lease_until", mysql.DATETIME(fsp=6), nullable=True),
        sa.Column("next_run_at", mysql.DATETIME(fsp=6), nullable=True),
        sa.Column("error_code", sa.String(64), nullable=True),
        sa.UniqueConstraint("idempotency_key", name="uq_background_jobs_idempotency_key"),
        sa.CheckConstraint("state IN ('queued','running','succeeded','retry','failed','cancelled')", name="ck_background_jobs_state"),
        mysql_charset="utf8mb4", mysql_collate="utf8mb4_0900_ai_ci", comment="持久任务与租约")
    op.create_index("ix_background_jobs_state_next_run_at", "background_jobs", ["state","next_run_at"])
    op.create_table("outbox_events",
        sa.Column("id", mysql.BIGINT(unsigned=True), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("created_at", mysql.DATETIME(fsp=6), nullable=False, server_default=sa.func.current_timestamp(6)),
        sa.Column("updated_at", mysql.DATETIME(fsp=6), nullable=False, server_default=sa.func.current_timestamp(6)),
        sa.Column("row_version", mysql.INTEGER(unsigned=True), nullable=False, server_default='1'),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("aggregate_type", sa.String(50), nullable=False),
        sa.Column("aggregate_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("event_key", sa.String(190, collation='utf8mb4_bin'), nullable=False),
        sa.Column("payload_refs", sa.JSON(), nullable=False),
        sa.Column("private_payload_ciphertext", sa.Text(), nullable=True),
        sa.Column("state", sa.String(24), nullable=False, server_default="pending"),
        sa.Column("lease_until", mysql.DATETIME(fsp=6), nullable=True),
        sa.Column("next_attempt_at", mysql.DATETIME(fsp=6), nullable=True),
        sa.Column("expires_at", mysql.DATETIME(fsp=6), nullable=True),
        sa.UniqueConstraint("event_key", name="uq_outbox_events_event_key"),
        sa.CheckConstraint("state IN ('pending','processing','sent','failed','unknown','cancelled')", name="ck_outbox_events_state"),
        mysql_charset="utf8mb4", mysql_collate="utf8mb4_0900_ai_ci", comment="事务外发事件")
    op.create_index("ix_outbox_events_state_next_attempt_at", "outbox_events", ["state","next_attempt_at"])
    op.create_table("ai_runs",
        sa.Column("id", mysql.BIGINT(unsigned=True), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("created_at", mysql.DATETIME(fsp=6), nullable=False, server_default=sa.func.current_timestamp(6)),
        sa.Column("updated_at", mysql.DATETIME(fsp=6), nullable=False, server_default=sa.func.current_timestamp(6)),
        sa.Column("row_version", mysql.INTEGER(unsigned=True), nullable=False, server_default='1'),
        sa.Column("background_job_id", mysql.BIGINT(unsigned=True), nullable=True),
        sa.Column("task_type", sa.String(50), nullable=False),
        sa.Column("model_config_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("prompt_version_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("input_hash", sa.CHAR(64, collation='utf8mb4_bin'), nullable=False),
        sa.Column("source_refs", sa.JSON(), nullable=False),
        sa.Column("validated_output", sa.JSON(), nullable=True),
        sa.Column("state", sa.String(24), nullable=False, server_default="running"),
        sa.Column("duration_ms", mysql.INTEGER(unsigned=True), nullable=True),
        sa.Column("error_code", sa.String(64), nullable=True),
        sa.ForeignKeyConstraint(["background_job_id"], ["background_jobs.id"], name="fk_ai_runs_background_job_id_background_jobs", ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(["model_config_id"], ["model_configs.id"], name="fk_ai_runs_model_config_id_model_configs", ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(["prompt_version_id"], ["prompt_versions.id"], name="fk_ai_runs_prompt_version_id_prompt_versions", ondelete='RESTRICT'),
        sa.CheckConstraint("state IN ('running','succeeded','invalid','failed')", name="ck_ai_runs_state"),
        mysql_charset="utf8mb4", mysql_collate="utf8mb4_0900_ai_ci", comment="模型运行证据")
    op.create_index("ix_ai_runs_background_job_id", "ai_runs", ["background_job_id"])
    op.create_index("ix_ai_runs_model_config_id", "ai_runs", ["model_config_id"])
    op.create_index("ix_ai_runs_prompt_version_id", "ai_runs", ["prompt_version_id"])
    op.create_index("ix_ai_runs_task_type_created_at", "ai_runs", ["task_type","created_at"])
    op.create_table("candidate_profiles",
        sa.Column("id", mysql.BIGINT(unsigned=True), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("created_at", mysql.DATETIME(fsp=6), nullable=False, server_default=sa.func.current_timestamp(6)),
        sa.Column("updated_at", mysql.DATETIME(fsp=6), nullable=False, server_default=sa.func.current_timestamp(6)),
        sa.Column("row_version", mysql.INTEGER(unsigned=True), nullable=False, server_default='1'),
        sa.Column("candidate_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("resume_version_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("version_no", mysql.INTEGER(unsigned=True), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("skills", sa.JSON(), nullable=False),
        sa.Column("experiences", sa.JSON(), nullable=False),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.Column("source_record_refs", sa.JSON(), nullable=False),
        sa.Column("ai_run_id", mysql.BIGINT(unsigned=True), nullable=True),
        sa.Column("confirmed_by", mysql.BIGINT(unsigned=True), nullable=True),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidates.id"], name="fk_candidate_profiles_candidate_id_candidates", ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(["resume_version_id"], ["resume_versions.id"], name="fk_candidate_profiles_resume_version_id_resume_versions", ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(["ai_run_id"], ["ai_runs.id"], name="fk_candidate_profiles_ai_run_id_ai_runs", ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(["confirmed_by"], ["users.id"], name="fk_candidate_profiles_confirmed_by_users", ondelete='RESTRICT'),
        sa.UniqueConstraint("candidate_id", "version_no", name="uq_candidate_profiles_candidate_id_version_no"),
        mysql_charset="utf8mb4", mysql_collate="utf8mb4_0900_ai_ci", comment="通用人才画像版本")
    op.create_index("ix_candidate_profiles_candidate_id", "candidate_profiles", ["candidate_id"])
    op.create_index("ix_candidate_profiles_resume_version_id", "candidate_profiles", ["resume_version_id"])
    op.create_index("ix_candidate_profiles_ai_run_id", "candidate_profiles", ["ai_run_id"])
    op.create_index("ix_candidate_profiles_confirmed_by", "candidate_profiles", ["confirmed_by"])
    op.create_table("evaluation_runs",
        sa.Column("id", mysql.BIGINT(unsigned=True), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("created_at", mysql.DATETIME(fsp=6), nullable=False, server_default=sa.func.current_timestamp(6)),
        sa.Column("updated_at", mysql.DATETIME(fsp=6), nullable=False, server_default=sa.func.current_timestamp(6)),
        sa.Column("row_version", mysql.INTEGER(unsigned=True), nullable=False, server_default='1'),
        sa.Column("application_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("resume_version_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("profile_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("job_version_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("state", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("screening_result", sa.String(16), nullable=True),
        sa.Column("override_by", mysql.BIGINT(unsigned=True), nullable=True),
        sa.Column("override_reason", sa.Text(), nullable=True),
        sa.Column("invitation_mode", sa.String(24), nullable=False),
        sa.Column("error_code", sa.String(64), nullable=True),
        sa.ForeignKeyConstraint(["application_id"], ["applications.id"], name="fk_evaluation_runs_application_id_applications", ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(["resume_version_id"], ["resume_versions.id"], name="fk_evaluation_runs_resume_version_id_resume_versions", ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(["profile_id"], ["candidate_profiles.id"], name="fk_evaluation_runs_profile_id_candidate_profiles", ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(["job_version_id"], ["job_versions.id"], name="fk_evaluation_runs_job_version_id_job_versions", ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(["override_by"], ["users.id"], name="fk_evaluation_runs_override_by_users", ondelete='RESTRICT'),
        sa.CheckConstraint("state IN ('pending','screening','needs_review','screened_out','matching','matched','evaluation_failed')", name="ck_evaluation_runs_state"),
        sa.CheckConstraint("screening_result IN ('pass','fail','unknown')", name="ck_evaluation_runs_screening_result"),
        sa.CheckConstraint("invitation_mode IN ('auto_allowed','manual_only')", name="ck_evaluation_runs_invitation_mode"),
        mysql_charset="utf8mb4", mysql_collate="utf8mb4_0900_ai_ci", comment="一次粗筛匹配快照")
    op.create_index("ix_evaluation_runs_application_id", "evaluation_runs", ["application_id"])
    op.create_index("ix_evaluation_runs_resume_version_id", "evaluation_runs", ["resume_version_id"])
    op.create_index("ix_evaluation_runs_profile_id", "evaluation_runs", ["profile_id"])
    op.create_index("ix_evaluation_runs_job_version_id", "evaluation_runs", ["job_version_id"])
    op.create_index("ix_evaluation_runs_override_by", "evaluation_runs", ["override_by"])
    op.create_index("ix_evaluation_runs_application_id_created_at", "evaluation_runs", ["application_id","created_at"])
    op.create_table("screening_details",
        sa.Column("id", mysql.BIGINT(unsigned=True), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("created_at", mysql.DATETIME(fsp=6), nullable=False, server_default=sa.func.current_timestamp(6)),
        sa.Column("updated_at", mysql.DATETIME(fsp=6), nullable=False, server_default=sa.func.current_timestamp(6)),
        sa.Column("row_version", mysql.INTEGER(unsigned=True), nullable=False, server_default='1'),
        sa.Column("evaluation_run_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("condition_key", sa.String(100), nullable=False),
        sa.Column("required", sa.Boolean(), nullable=False),
        sa.Column("expected", sa.JSON(), nullable=False),
        sa.Column("actual", sa.JSON(), nullable=True),
        sa.Column("result", sa.String(16), nullable=False),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["evaluation_run_id"], ["evaluation_runs.id"], name="fk_screening_details_evaluation_run_id_evaluation_runs", ondelete='RESTRICT'),
        sa.CheckConstraint("result IN ('met','unmet','unknown')", name="ck_screening_details_result"),
        sa.UniqueConstraint("evaluation_run_id", "condition_key", name="uq_screening_details_evaluation_run_id_condition_key"),
        mysql_charset="utf8mb4", mysql_collate="utf8mb4_0900_ai_ci", comment="粗筛逐条件证据")
    op.create_index("ix_screening_details_evaluation_run_id", "screening_details", ["evaluation_run_id"])
    op.create_table("match_results",
        sa.Column("id", mysql.BIGINT(unsigned=True), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("created_at", mysql.DATETIME(fsp=6), nullable=False, server_default=sa.func.current_timestamp(6)),
        sa.Column("updated_at", mysql.DATETIME(fsp=6), nullable=False, server_default=sa.func.current_timestamp(6)),
        sa.Column("row_version", mysql.INTEGER(unsigned=True), nullable=False, server_default='1'),
        sa.Column("evaluation_run_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("ai_run_id", mysql.BIGINT(unsigned=True), nullable=True),
        sa.Column("total_score", sa.Numeric(5, 2), nullable=True),
        sa.Column("dimension_scores", sa.JSON(), nullable=False),
        sa.Column("strengths", sa.JSON(), nullable=False),
        sa.Column("gaps", sa.JSON(), nullable=False),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.Column("state", sa.String(24), nullable=False, server_default="valid"),
        sa.ForeignKeyConstraint(["evaluation_run_id"], ["evaluation_runs.id"], name="fk_match_results_evaluation_run_id_evaluation_runs", ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(["ai_run_id"], ["ai_runs.id"], name="fk_match_results_ai_run_id_ai_runs", ondelete='RESTRICT'),
        sa.UniqueConstraint("evaluation_run_id", name="uq_match_results_evaluation_run_id"),
        sa.CheckConstraint("total_score >= 0 AND total_score <= 100", name="ck_match_results_total_score_range"),
        sa.CheckConstraint("state IN ('valid','needs_review','failed')", name="ck_match_results_state"),
        mysql_charset="utf8mb4", mysql_collate="utf8mb4_0900_ai_ci", comment="岗位匹配结果")
    op.create_index("ix_match_results_evaluation_run_id", "match_results", ["evaluation_run_id"])
    op.create_index("ix_match_results_ai_run_id", "match_results", ["ai_run_id"])
    op.create_index("ix_match_results_state_total_score", "match_results", ["state","total_score"])
    op.create_table("exam_attempts",
        sa.Column("id", mysql.BIGINT(unsigned=True), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("created_at", mysql.DATETIME(fsp=6), nullable=False, server_default=sa.func.current_timestamp(6)),
        sa.Column("updated_at", mysql.DATETIME(fsp=6), nullable=False, server_default=sa.func.current_timestamp(6)),
        sa.Column("row_version", mysql.INTEGER(unsigned=True), nullable=False, server_default='1'),
        sa.Column("application_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("evaluation_run_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("paper_version_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("round_no", mysql.INTEGER(unsigned=True), nullable=False),
        sa.Column("email_snapshot", sa.String(254), nullable=False),
        sa.Column("invitation_token_hash", sa.CHAR(64, collation='utf8mb4_bin'), nullable=True),
        sa.Column("invite_status", sa.String(24), nullable=False, server_default="pending"),
        sa.Column("valid_until", mysql.DATETIME(fsp=6), nullable=False),
        sa.Column("state", sa.String(24), nullable=False, server_default="not_started"),
        sa.Column("started_at", mysql.DATETIME(fsp=6), nullable=True),
        sa.Column("deadline_at", mysql.DATETIME(fsp=6), nullable=True),
        sa.Column("submitted_at", mysql.DATETIME(fsp=6), nullable=True),
        sa.Column("submission_reason", sa.String(24), nullable=True),
        sa.Column("objective_score", sa.Numeric(6, 2), nullable=True),
        sa.Column("final_score", sa.Numeric(6, 2), nullable=True),
        sa.Column("finalized_at", mysql.DATETIME(fsp=6), nullable=True),
        sa.Column("finalized_by", mysql.BIGINT(unsigned=True), nullable=True),
        sa.Column("current_score_report_id", mysql.BIGINT(unsigned=True), nullable=True),
        sa.ForeignKeyConstraint(["application_id"], ["applications.id"], name="fk_exam_attempts_application_id_applications", ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(["evaluation_run_id"], ["evaluation_runs.id"], name="fk_exam_attempts_evaluation_run_id_evaluation_runs", ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(["paper_version_id"], ["paper_versions.id"], name="fk_exam_attempts_paper_version_id_paper_versions", ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(["finalized_by"], ["users.id"], name="fk_exam_attempts_finalized_by_users", ondelete='RESTRICT'),
        sa.UniqueConstraint("invitation_token_hash", name="uq_exam_attempts_invitation_token_hash"),
        sa.CheckConstraint("invite_status IN ('pending','sent','delivery_failed','delivery_unknown','revoked','expired')", name="ck_exam_attempts_invite_status"),
        sa.CheckConstraint("state IN ('not_started','in_progress','submitted','grading','pending_review','finalized','no_show')", name="ck_exam_attempts_state"),
        sa.CheckConstraint("submission_reason IN ('manual','timeout')", name="ck_exam_attempts_submission_reason"),
        sa.UniqueConstraint("application_id", "round_no", name="uq_exam_attempts_application_id_round_no"),
        mysql_charset="utf8mb4", mysql_collate="utf8mb4_0900_ai_ci", comment="邀请与个人考次")
    op.create_index("ix_exam_attempts_application_id", "exam_attempts", ["application_id"])
    op.create_index("ix_exam_attempts_evaluation_run_id", "exam_attempts", ["evaluation_run_id"])
    op.create_index("ix_exam_attempts_paper_version_id", "exam_attempts", ["paper_version_id"])
    op.create_index("ix_exam_attempts_finalized_by", "exam_attempts", ["finalized_by"])
    op.create_index("ix_exam_attempts_current_score_report_id", "exam_attempts", ["current_score_report_id"])
    op.create_index("ix_exam_attempts_state_deadline_at", "exam_attempts", ["state","deadline_at"])
    op.create_index("ix_exam_attempts_invite_status_valid_until", "exam_attempts", ["invite_status","valid_until"])
    op.create_table("exam_answers",
        sa.Column("id", mysql.BIGINT(unsigned=True), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("created_at", mysql.DATETIME(fsp=6), nullable=False, server_default=sa.func.current_timestamp(6)),
        sa.Column("updated_at", mysql.DATETIME(fsp=6), nullable=False, server_default=sa.func.current_timestamp(6)),
        sa.Column("row_version", mysql.INTEGER(unsigned=True), nullable=False, server_default='1'),
        sa.Column("attempt_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("paper_item_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("answer", sa.JSON(), nullable=True),
        sa.Column("answer_revision", mysql.INTEGER(unsigned=True), nullable=False, server_default="0"),
        sa.Column("saved_at", mysql.DATETIME(fsp=6), nullable=False),
        sa.Column("objective_score", sa.Numeric(6, 2), nullable=True),
        sa.Column("ai_suggested_score", sa.Numeric(6, 2), nullable=True),
        sa.Column("ai_reason", sa.JSON(), nullable=True),
        sa.Column("review_state", sa.String(24), nullable=False, server_default="not_required"),
        sa.Column("final_score", sa.Numeric(6, 2), nullable=True),
        sa.Column("ai_run_id", mysql.BIGINT(unsigned=True), nullable=True),
        sa.ForeignKeyConstraint(["attempt_id"], ["exam_attempts.id"], name="fk_exam_answers_attempt_id_exam_attempts", ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(["paper_item_id"], ["paper_items.id"], name="fk_exam_answers_paper_item_id_paper_items", ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(["ai_run_id"], ["ai_runs.id"], name="fk_exam_answers_ai_run_id_ai_runs", ondelete='RESTRICT'),
        sa.CheckConstraint("review_state IN ('not_required','pending','reviewed')", name="ck_exam_answers_review_state"),
        sa.UniqueConstraint("attempt_id", "paper_item_id", name="uq_exam_answers_attempt_id_paper_item_id"),
        mysql_charset="utf8mb4", mysql_collate="utf8mb4_0900_ai_ci", comment="个人答案与评分")
    op.create_index("ix_exam_answers_attempt_id", "exam_answers", ["attempt_id"])
    op.create_index("ix_exam_answers_paper_item_id", "exam_answers", ["paper_item_id"])
    op.create_index("ix_exam_answers_ai_run_id", "exam_answers", ["ai_run_id"])
    op.create_table("score_reviews",
        sa.Column("id", mysql.BIGINT(unsigned=True), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("created_at", mysql.DATETIME(fsp=6), nullable=False, server_default=sa.func.current_timestamp(6)),
        sa.Column("updated_at", mysql.DATETIME(fsp=6), nullable=False, server_default=sa.func.current_timestamp(6)),
        sa.Column("row_version", mysql.INTEGER(unsigned=True), nullable=False, server_default='1'),
        sa.Column("answer_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("reviewer_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("revision_no", mysql.INTEGER(unsigned=True), nullable=False),
        sa.Column("score", sa.Numeric(6, 2), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("previous_score", sa.Numeric(6, 2), nullable=True),
        sa.ForeignKeyConstraint(["answer_id"], ["exam_answers.id"], name="fk_score_reviews_answer_id_exam_answers", ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(["reviewer_id"], ["users.id"], name="fk_score_reviews_reviewer_id_users", ondelete='RESTRICT'),
        sa.CheckConstraint("score >= 0", name="ck_score_reviews_score_nonnegative"),
        sa.UniqueConstraint("answer_id", "revision_no", name="uq_score_reviews_answer_id_revision_no"),
        mysql_charset="utf8mb4", mysql_collate="utf8mb4_0900_ai_ci", comment="人工主观评分修订")
    op.create_index("ix_score_reviews_answer_id", "score_reviews", ["answer_id"])
    op.create_index("ix_score_reviews_reviewer_id", "score_reviews", ["reviewer_id"])
    op.create_table("index_records",
        sa.Column("id", mysql.BIGINT(unsigned=True), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("created_at", mysql.DATETIME(fsp=6), nullable=False, server_default=sa.func.current_timestamp(6)),
        sa.Column("updated_at", mysql.DATETIME(fsp=6), nullable=False, server_default=sa.func.current_timestamp(6)),
        sa.Column("row_version", mysql.INTEGER(unsigned=True), nullable=False, server_default='1'),
        sa.Column("entity_type", sa.String(32), nullable=False),
        sa.Column("entity_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("model_config_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("collection_name", sa.String(120), nullable=False),
        sa.Column("vector_key", sa.String(190, collation='utf8mb4_bin'), nullable=False),
        sa.Column("content_hash", sa.CHAR(64, collation='utf8mb4_bin'), nullable=False),
        sa.Column("state", sa.String(24), nullable=False, server_default="pending"),
        sa.ForeignKeyConstraint(["model_config_id"], ["model_configs.id"], name="fk_index_records_model_config_id_model_configs", ondelete='RESTRICT'),
        sa.CheckConstraint("entity_type IN ('profile','knowledge_chunk','job_version')", name="ck_index_records_entity_type"),
        sa.CheckConstraint("state IN ('pending','ready','failed','stale','deleted')", name="ck_index_records_state"),
        sa.UniqueConstraint("entity_type", "entity_id", "model_config_id", name="uq_index_records_entity_type_entity_id_model_config_id"),
        sa.UniqueConstraint("collection_name", "vector_key", name="uq_index_records_collection_name_vector_key"),
        mysql_charset="utf8mb4", mysql_collate="utf8mb4_0900_ai_ci", comment="关系数据与向量索引映射")
    op.create_index("ix_index_records_model_config_id", "index_records", ["model_config_id"])
    op.create_table("audit_logs",
        sa.Column("id", mysql.BIGINT(unsigned=True), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("created_at", mysql.DATETIME(fsp=6), nullable=False, server_default=sa.func.current_timestamp(6)),
        sa.Column("updated_at", mysql.DATETIME(fsp=6), nullable=False, server_default=sa.func.current_timestamp(6)),
        sa.Column("row_version", mysql.INTEGER(unsigned=True), nullable=False, server_default='1'),
        sa.Column("actor_type", sa.String(24), nullable=False),
        sa.Column("actor_user_id", mysql.BIGINT(unsigned=True), nullable=True),
        sa.Column("actor_candidate_id", mysql.BIGINT(unsigned=True), nullable=True),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("entity_type", sa.String(50), nullable=False),
        sa.Column("entity_id", mysql.BIGINT(unsigned=True), nullable=True),
        sa.Column("request_id", sa.CHAR(36), nullable=False),
        sa.Column("change_summary", sa.JSON(), nullable=False),
        sa.Column("result", sa.String(24), nullable=False),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], name="fk_audit_logs_actor_user_id_users", ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(["actor_candidate_id"], ["candidates.id"], name="fk_audit_logs_actor_candidate_id_candidates", ondelete='RESTRICT'),
        sa.CheckConstraint("actor_type IN ('admin','hr','candidate','system')", name="ck_audit_logs_actor_type"),
        sa.CheckConstraint("result IN ('success','denied','failed')", name="ck_audit_logs_result"),
        mysql_charset="utf8mb4", mysql_collate="utf8mb4_0900_ai_ci", comment="操作与权限审计")
    op.create_index("ix_audit_logs_actor_user_id", "audit_logs", ["actor_user_id"])
    op.create_index("ix_audit_logs_actor_candidate_id", "audit_logs", ["actor_candidate_id"])
    op.create_index("ix_audit_logs_entity_type_entity_id_created_at", "audit_logs", ["entity_type","entity_id","created_at"])
    op.create_index("ix_audit_logs_actor_user_id_created_at", "audit_logs", ["actor_user_id","created_at"])
    op.create_table("score_reports",
        sa.Column("id", mysql.BIGINT(unsigned=True), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("created_at", mysql.DATETIME(fsp=6), nullable=False, server_default=sa.func.current_timestamp(6)),
        sa.Column("updated_at", mysql.DATETIME(fsp=6), nullable=False, server_default=sa.func.current_timestamp(6)),
        sa.Column("row_version", mysql.INTEGER(unsigned=True), nullable=False, server_default='1'),
        sa.Column("attempt_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.Column("version_no", mysql.INTEGER(unsigned=True), nullable=False),
        sa.Column("objective_score", sa.Numeric(6, 2), nullable=False),
        sa.Column("subjective_score", sa.Numeric(6, 2), nullable=False),
        sa.Column("total_score", sa.Numeric(6, 2), nullable=False),
        sa.Column("item_score_snapshot", sa.JSON(), nullable=False),
        sa.Column("confirmed_by", mysql.BIGINT(unsigned=True), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["attempt_id"], ["exam_attempts.id"], name="fk_score_reports_attempt_id_exam_attempts", ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(["confirmed_by"], ["users.id"], name="fk_score_reports_confirmed_by_users", ondelete='RESTRICT'),
        sa.UniqueConstraint("attempt_id", "version_no", name="uq_score_reports_attempt_id_version_no"),
        mysql_charset="utf8mb4", mysql_collate="utf8mb4_0900_ai_ci", comment="正式成绩不可变版本")
    op.create_index("ix_score_reports_attempt_id", "score_reports", ["attempt_id"])
    op.create_index("ix_score_reports_confirmed_by", "score_reports", ["confirmed_by"])
    op.create_table("idempotency_records",
        sa.Column("id", mysql.BIGINT(unsigned=True), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("created_at", mysql.DATETIME(fsp=6), nullable=False, server_default=sa.func.current_timestamp(6)),
        sa.Column("updated_at", mysql.DATETIME(fsp=6), nullable=False, server_default=sa.func.current_timestamp(6)),
        sa.Column("row_version", mysql.INTEGER(unsigned=True), nullable=False, server_default='1'),
        sa.Column("actor_scope", sa.String(100, collation='utf8mb4_bin'), nullable=False),
        sa.Column("operation", sa.String(100, collation='utf8mb4_bin'), nullable=False),
        sa.Column("request_key", sa.String(100, collation='utf8mb4_bin'), nullable=False),
        sa.Column("request_hash", sa.CHAR(64, collation='utf8mb4_bin'), nullable=False),
        sa.Column("state", sa.String(24), nullable=False, server_default="processing"),
        sa.Column("result_refs", sa.JSON(), nullable=True),
        sa.Column("expires_at", mysql.DATETIME(fsp=6), nullable=False),
        sa.CheckConstraint("state IN ('processing','completed','failed')", name="ck_idempotency_records_state"),
        sa.UniqueConstraint("actor_scope", "operation", "request_key", name="uq_idempotency_records_actor_scope_operation_request_key"),
        mysql_charset="utf8mb4", mysql_collate="utf8mb4_0900_ai_ci", comment="关键命令幂等记录")
    op.create_table("mail_configs",
        sa.Column("id", mysql.BIGINT(unsigned=True), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("created_at", mysql.DATETIME(fsp=6), nullable=False, server_default=sa.func.current_timestamp(6)),
        sa.Column("updated_at", mysql.DATETIME(fsp=6), nullable=False, server_default=sa.func.current_timestamp(6)),
        sa.Column("row_version", mysql.INTEGER(unsigned=True), nullable=False, server_default='1'),
        sa.Column("revision_no", mysql.INTEGER(unsigned=True), nullable=False),
        sa.Column("smtp_host", sa.String(255), nullable=False),
        sa.Column("smtp_port", mysql.INTEGER(unsigned=True), nullable=False),
        sa.Column("tls_mode", sa.String(24), nullable=False),
        sa.Column("sender_address", sa.String(254), nullable=False),
        sa.Column("username", sa.String(255), nullable=True),
        sa.Column("secret_ciphertext", sa.Text(), nullable=True),
        sa.Column("public_base_url", sa.String(500), nullable=False),
        sa.Column("state", sa.String(24), nullable=False, server_default="draft"),
        sa.UniqueConstraint("revision_no", name="uq_mail_configs_revision_no"),
        sa.CheckConstraint("tls_mode IN ('starttls','tls')", name="ck_mail_configs_tls_mode"),
        sa.CheckConstraint("state IN ('draft','verified','active','disabled')", name="ck_mail_configs_state"),
        mysql_charset="utf8mb4", mysql_collate="utf8mb4_0900_ai_ci", comment="邮件连接修订")
    op.create_table("notifications",
        sa.Column("id", mysql.BIGINT(unsigned=True), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("created_at", mysql.DATETIME(fsp=6), nullable=False, server_default=sa.func.current_timestamp(6)),
        sa.Column("updated_at", mysql.DATETIME(fsp=6), nullable=False, server_default=sa.func.current_timestamp(6)),
        sa.Column("row_version", mysql.INTEGER(unsigned=True), nullable=False, server_default='1'),
        sa.Column("attempt_id", mysql.BIGINT(unsigned=True), nullable=True),
        sa.Column("event_key", sa.String(190, collation='utf8mb4_bin'), nullable=False),
        sa.Column("purpose", sa.String(32), nullable=False),
        sa.Column("recipient_snapshot", sa.String(254), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="pending"),
        sa.Column("provider_message_id", sa.String(255), nullable=True),
        sa.Column("attempt_count", mysql.INTEGER(unsigned=True), nullable=False, server_default="0"),
        sa.Column("last_error_code", sa.String(64), nullable=True),
        sa.Column("sent_at", mysql.DATETIME(fsp=6), nullable=True),
        sa.Column("mail_config_id", mysql.BIGINT(unsigned=True), nullable=False),
        sa.ForeignKeyConstraint(["attempt_id"], ["exam_attempts.id"], name="fk_notifications_attempt_id_exam_attempts", ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(["mail_config_id"], ["mail_configs.id"], name="fk_notifications_mail_config_id_mail_configs", ondelete='RESTRICT'),
        sa.UniqueConstraint("event_key", name="uq_notifications_event_key"),
        sa.CheckConstraint("purpose IN ('exam_invite','verify_code')", name="ck_notifications_purpose"),
        sa.CheckConstraint("status IN ('pending','sending','accepted','failed','unknown','cancelled')", name="ck_notifications_status"),
        mysql_charset="utf8mb4", mysql_collate="utf8mb4_0900_ai_ci", comment="邮件发送记录")
    op.create_index("ix_notifications_attempt_id", "notifications", ["attempt_id"])
    op.create_index("ix_notifications_mail_config_id", "notifications", ["mail_config_id"])
    op.create_index("ix_notifications_status_created_at", "notifications", ["status","created_at"])

def downgrade():
    op.drop_table("notifications")
    op.drop_table("mail_configs")
    op.drop_table("idempotency_records")
    op.drop_table("score_reports")
    op.drop_table("audit_logs")
    op.drop_table("index_records")
    op.drop_table("score_reviews")
    op.drop_table("exam_answers")
    op.drop_table("exam_attempts")
    op.drop_table("match_results")
    op.drop_table("screening_details")
    op.drop_table("evaluation_runs")
    op.drop_table("candidate_profiles")
    op.drop_table("ai_runs")
    op.drop_table("outbox_events")
    op.drop_table("background_jobs")
    op.drop_table("workflow_configs")
    op.drop_table("prompt_versions")
    op.drop_table("model_configs")
    op.drop_table("knowledge_chunks")
    op.drop_table("knowledge_documents")
    op.drop_table("paper_items")
    op.drop_table("job_versions")
    op.drop_table("paper_versions")
    op.drop_table("papers")
    op.drop_table("questions")
    op.drop_table("question_banks")
    op.drop_table("recruitment_events")
    op.drop_table("applications")
    op.drop_table("duplicate_cases")
    op.drop_table("import_items")
    op.drop_table("resume_versions")
    op.drop_table("candidates")
    op.drop_table("import_batches")
    op.drop_table("jobs")
    op.drop_table("stored_files")
    op.drop_table("user_roles")
    op.drop_table("roles")
    op.drop_table("users")
    op.drop_table("departments")
