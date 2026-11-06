"""平台开发工具：验证model validation的正常与失败场景；测试数据仅用于隔离环境。"""
import json
import pytest
from pydantic import BaseModel, ConfigDict
from app.ai_runtime.validation import validate_output, validate_vectors, OutputInvalid

class Answer(BaseModel):
    """Answer：平台开发工具中的输入输出数据契约。"""
    model_config = ConfigDict(extra='forbid', strict=True)
    answer: str
    citations: list[dict[str, str]]

SCHEMA = Answer.model_json_schema()
EVIDENCE = [{'source_type':'resume','source_id':'7','locator':'page1','quote':'Python开发三年'}]

def valid():
    return {'answer':'有Python经验','citations':[dict(EVIDENCE[0])]}

def test_valid_evidence_and_typed_result():
    assert validate_output(json.dumps(valid()), Answer, SCHEMA, EVIDENCE).answer == '有Python经验'

@pytest.mark.parametrize('content', ['no json', '{"answer":"a","answer":"b","citations":[]}', '{"answer":NaN,"citations":[]}'])
def test_malformed_duplicate_nonfinite_json_rejected(content):
    with pytest.raises(OutputInvalid): validate_output(content, Answer, SCHEMA, EVIDENCE)

@pytest.mark.parametrize('mutation', ['invented_source','invented_quote','missing','extra','wrong_type'])
def test_untrusted_output_rejected(mutation):
    value=valid()
    if mutation=='invented_source': value['citations'][0]['source_id']='99'
    if mutation=='invented_quote': value['citations'][0]['quote']='Java十年'
    if mutation=='missing': value['citations']=[]
    if mutation=='extra': value['execute']='send_mail'
    if mutation=='wrong_type': value['answer']=123
    with pytest.raises(OutputInvalid): validate_output(json.dumps(value), Answer, SCHEMA, EVIDENCE)

def test_published_schema_also_applies():
    schema={**SCHEMA,'properties':{**SCHEMA['properties'],'answer':{'const':'other'}}}
    with pytest.raises(OutputInvalid): validate_output(json.dumps(valid()), Answer, schema, EVIDENCE)

@pytest.mark.parametrize('vectors', [[[1,0],[1]], [[0,0],[1,2]], [[True,1],[1,2]], [[float('nan'),1],[1,2]], [[1,2]]])
def test_invalid_embedding_batch(vectors):
    with pytest.raises(OutputInvalid): validate_vectors(vectors, 2, 2)

def test_valid_entire_embedding_batch():
    assert validate_vectors([[1,0],[0,1],[1,1]], 3, 2)==2
