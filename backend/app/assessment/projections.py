from app.assessment.schemas import CandidatePaperItem,PaperItemView

def candidate_item(item: PaperItemView) -> CandidatePaperItem:
    # Construct an allowlisted candidate DTO; never serialize an internal answer/rubric view.
    return CandidatePaperItem(id=item.id,type=item.type,stem=item.stem,options=item.options,max_score=item.max_score)
