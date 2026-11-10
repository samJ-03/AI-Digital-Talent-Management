"""T21权重、证据与未知维度不使用模型或数据库。"""
from decimal import Decimal
import pytest

def test_weighted_50_35_15():
    from app.evaluation.match_scoring import MatchScorer,DimensionScore
    from app.jobs.schemas import MatchWeights
    dimensions=[DimensionScore(name=n,score=s,evidence=[]) for n,s in [('skills',80),('experience',60),('responsibilities',100)]]
    assert MatchScorer().aggregate(dimensions,MatchWeights(skills=50,experience=35,responsibilities=15))==Decimal('76.00')

def test_unknown_dimension_blocks_invite():
    from app.evaluation.match_scoring import MatchScorer,DimensionScore
    from app.jobs.schemas import MatchWeights
    from app.core.errors import DomainError
    dims=[DimensionScore(name=n,score=s,evidence=[]) for n,s in [('skills',80),('experience',None),('responsibilities',100)]]
    with pytest.raises(DomainError,match='MATCH_DIMENSION_UNKNOWN'):MatchScorer().aggregate(dims,MatchWeights(skills=50,experience=35,responsibilities=15))

@pytest.mark.parametrize('values',[[('skills',80),('skills',60),('responsibilities',100)],[('skills',80),('experience',60)]])
def test_missing_duplicate_dimensions_rejected(values):
    from app.evaluation.match_scoring import MatchScorer,DimensionScore
    from app.jobs.schemas import MatchWeights
    from app.core.errors import DomainError
    with pytest.raises(DomainError):MatchScorer().aggregate([DimensionScore(name=n,score=s,evidence=[]) for n,s in values],MatchWeights(skills=50,experience=35,responsibilities=15))

def test_foreign_or_job_only_score_becomes_unknown():
    from app.evaluation.match_scoring import MatchEvidenceValidator,MatchDraft
    from app.ai_runtime.generation_types import Evidence
    job=Evidence(source_type='job_version',source_id='1',locator='description',quote='Python')
    draft=MatchDraft(dimensions=[{'name':n,'score':80,'evidence':[job]} for n in ['skills','experience','responsibilities']],strengths=[],gaps=[],citations=[job])
    result=MatchEvidenceValidator().validate(draft,[job])
    assert not result.valid and set(result.unknown_dimensions)=={'skills','experience','responsibilities'}
