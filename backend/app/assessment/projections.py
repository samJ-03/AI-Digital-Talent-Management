"""题库、试卷与考试：构造候选人专用白名单投影，隐藏标准答案与量表。"""
from app.assessment.schemas import CandidatePaperItem,PaperItemView

def candidate_item(item: PaperItemView) -> CandidatePaperItem:
    # Construct an allowlisted candidate DTO; never serialize an internal answer/rubric view.
    """只投影候选人允许查看的题目信息。"""
    return CandidatePaperItem(id=item.id,type=item.type,stem=item.stem,options=item.options,max_score=item.max_score)
