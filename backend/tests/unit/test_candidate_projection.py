from app.assessment.schemas import PaperItemView
from app.assessment.projections import candidate_item

def test_candidate_item_constructs_only_safe_fields():
    source=PaperItemView(id='1',source_question_id='2',position_no=1,type='short_answer',stem='Explain',options=None,max_score='10.00',answer_key=None,
        rubric={'reference_answer':'INTERNAL_ONLY','criteria':[{'key':'secret'}]},reference_sources=[{'source_id':'PRIVATE'}])
    result=candidate_item(source).model_dump_json()
    assert 'INTERNAL_ONLY' not in result and 'PRIVATE' not in result
    assert set(candidate_item(source).model_dump())=={'id','type','stem','options','max_score'}
