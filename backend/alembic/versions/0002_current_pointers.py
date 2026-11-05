"""Attach nullable current-version pointers after both ends exist."""
from alembic import op

revision="0002_current_pointers"
down_revision="0001_entities"
branch_labels=None
depends_on=None

def upgrade():
    op.create_foreign_key("fk_jobs_current_version_id_job_versions", "jobs", "job_versions", ["current_version_id"], ["id"], ondelete="RESTRICT")
    op.create_foreign_key("fk_candidates_current_resume_version_id_resume_versions", "candidates", "resume_versions", ["current_resume_version_id"], ["id"], ondelete="RESTRICT")
    op.create_foreign_key("fk_candidates_current_profile_id_candidate_profiles", "candidates", "candidate_profiles", ["current_profile_id"], ["id"], ondelete="RESTRICT")
    op.create_foreign_key("fk_applications_current_evaluation_id_evaluation_runs", "applications", "evaluation_runs", ["current_evaluation_id"], ["id"], ondelete="RESTRICT")
    op.create_foreign_key("fk_exam_attempts_current_score_report_id_score_reports", "exam_attempts", "score_reports", ["current_score_report_id"], ["id"], ondelete="RESTRICT")

def downgrade():
    op.drop_constraint("fk_exam_attempts_current_score_report_id_score_reports", "exam_attempts", type_="foreignkey")
    op.drop_constraint("fk_applications_current_evaluation_id_evaluation_runs", "applications", type_="foreignkey")
    op.drop_constraint("fk_candidates_current_profile_id_candidate_profiles", "candidates", type_="foreignkey")
    op.drop_constraint("fk_candidates_current_resume_version_id_resume_versions", "candidates", type_="foreignkey")
    op.drop_constraint("fk_jobs_current_version_id_job_versions", "jobs", type_="foreignkey")
