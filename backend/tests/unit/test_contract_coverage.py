"""一期契约门：区分实现丢失、结构漂移与明确延期。"""
from copy import deepcopy
from app.core.errors import DomainError


def sample():
    record={'id':'API-041','method':'GET','path':'/api/v1/evaluations/{id}','phase':'phase1','owner':'evaluation','implemented':True,'response_fields':['id','match'],'nested_response_fields':{'match':['dimensions','state']}}
    match={'type':'object','properties':{'state':{'type':'string'},'dimensions':{'type':'array','items':{'type':'object'}}}}
    data={'type':'object','properties':{'id':{'type':'string'},'match':{'anyOf':[match,{'type':'null'}]}}}
    schema={'type':'object','properties':{'data':data}}
    operation={'responses':{'200':{'content':{'application/json':{'schema':schema}}}}}
    api={'paths':{'/api/v1/evaluations/{run_id}':{'get':operation}}}
    return {'operations':[record]},api


def test_existing_contract_missing_is_error():
    from scripts.check_contract_coverage import check_contract_coverage
    manifest,api=sample();api['paths']={}
    result=check_contract_coverage(manifest,api)
    assert not result['passed'] and result['missing']==['API-041']


def test_nested_match_wire_drift_is_error():
    from scripts.check_contract_coverage import check_contract_coverage
    manifest,api=sample();obj=api['paths']['/api/v1/evaluations/{run_id}']['get']['responses']['200']['content']['application/json']['schema']['properties']['data']['properties']['match']['anyOf'][0]['properties']
    obj['dimension_scores']=obj.pop('dimensions')
    result=check_contract_coverage(manifest,api)
    assert not result['passed'] and result['schema_mismatches']==['API-041']


def test_core_pending_and_phase2_are_distinct():
    from scripts.check_contract_coverage import check_contract_coverage
    manifest,api=sample()
    manifest['operations'] += [{'id':'API-059','method':'POST','path':'/api/v1/applications/{id}/invitations','phase':'phase1','owner':'assessment','implemented':False},{'id':'API-084','method':'POST','path':'/api/v1/knowledge/ask','phase':'phase2','owner':'knowledge','implemented':False}]
    result=check_contract_coverage(manifest,api)
    assert result['passed'] and result['pending_phase1']==['API-059'] and result['deferred_phase2']==['API-084']
    assert not check_contract_coverage(manifest,api,require_complete=True)['passed']


def test_normalized_parameter_name_and_extra_route():
    from scripts.check_contract_coverage import check_contract_coverage
    manifest,api=sample();assert check_contract_coverage(manifest,api)['passed']
    api['paths']['/api/v1/unknown']={'get':{'responses':{}}}
    assert check_contract_coverage(manifest,api)['unexpected']==['GET /api/v1/unknown']


def test_export_stdout_works_from_read_only_checkout():
    """CI非root容器只读挂载源码，schema应由宿主接收而非容器写checkout。"""
    import subprocess,sys,json
    from pathlib import Path
    root=Path(__file__).resolve().parents[3]
    result=subprocess.run([sys.executable,str(root/'scripts/export_openapi.py'),'--output','-'],cwd=root,capture_output=True,text=True,timeout=30)
    assert result.returncode==0,result.stderr
    api=json.loads(result.stdout)
    assert api['openapi'] and '/api/v1/evaluations/{run_id}' in api['paths']
