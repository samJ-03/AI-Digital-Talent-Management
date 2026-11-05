from datetime import timezone
from sqlalchemy import select
from app.assessment.models.papers import PaperItem
from app.assessment.schemas import QuestionView,QuestionBankView,PaperView,PaperVersionView,PaperItemView

def bank_view(row):
    return QuestionBankView(id=str(row.id),name=row.name,department_id=str(row.department_id),status=row.status,version=row.row_version)

def question_view(row):
    return QuestionView(id=str(row.id),bank_id=str(row.bank_id),logical_key=row.logical_key,revision_no=row.revision_no,type=row.question_type,
        stem=row.stem,options=row.options,answer_key=row.answer_key,rubric=row.rubric,reference_sources=row.reference_sources,state=row.state,version=row.row_version)

def paper_view(row):
    return PaperView(id=str(row.id),name=row.name,department_id=str(row.department_id),status=row.status,version=row.row_version)

def paper_item_view(row):
    return PaperItemView(id=str(row.id),source_question_id=str(row.source_question_id) if row.source_question_id else None,position_no=row.position_no,
        type=row.question_type,stem=row.stem,options=row.options,max_score=row.max_score,answer_key=row.answer_key,rubric=row.rubric,reference_sources=row.reference_sources)

def version_view(session,row):
    items=list(session.scalars(select(PaperItem).where(PaperItem.paper_version_id==row.id).order_by(PaperItem.position_no,PaperItem.id)))
    return PaperVersionView(id=str(row.id),paper_id=str(row.paper_id),version_no=row.version_no,duration_minutes=row.duration_minutes,total_score=row.total_score,
        reference_pass_score=row.reference_pass_score,status=row.status,published_at=row.published_at.replace(tzinfo=timezone.utc) if row.published_at else None,
        items=[paper_item_view(i) for i in items],version=row.row_version)
