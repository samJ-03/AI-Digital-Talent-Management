"""Check current API contracts without treating deferred work as implemented."""
from __future__ import annotations
import argparse,json,re
from pathlib import Path

METHODS={'get','post','put','patch','delete','head','options'}

def normalize_path(path: str) -> str:
    """Parameter names may differ; method and resource path still identify an API."""
    return re.sub(r'\{[^}]+\}','{}',path)


def operations(openapi: dict) -> dict:
    """Collect public business operations, excluding documentation endpoints."""
    return {(method.upper(),normalize_path(path)):(path,operation) for path,item in openapi.get('paths',{}).items() if path.startswith('/api/v1/') for method,operation in item.items() if method in METHODS}


def object_schema(schema: dict,openapi: dict) -> dict:
    """Resolve local object/nullable refs only; never fetch remote schemas."""
    seen=set()
    while '$ref' in schema:
        ref=schema['$ref']
        if ref in seen or not ref.startswith('#/components/schemas/'):return {}
        seen.add(ref);schema=openapi.get('components',{}).get('schemas',{}).get(ref.rsplit('/',1)[1],{})
    if 'anyOf' in schema:
        for option in schema['anyOf']:
            value=object_schema(option,openapi)
            if value.get('type')=='object' or 'properties' in value:return value
        return {}
    return schema


def response_shape(operation: dict,openapi: dict) -> tuple[list[str],dict[str,list[str]]]:
    """Capture envelope data keys and one level of typed nested object fields."""
    responses=operation.get('responses',{})
    code=next((key for key in sorted(responses) if key.startswith('2')),None)
    if code is None:return [],{}
    envelope=object_schema(responses[code].get('content',{}).get('application/json',{}).get('schema',{}),openapi)
    data=object_schema(envelope.get('properties',{}).get('data',{}),openapi)
    properties=data.get('properties',{})
    nested={key:sorted(value.get('properties',{})) for key,schema in properties.items() if (value:=object_schema(schema,openapi)).get('properties')}
    return sorted(properties),nested


def check_contract_coverage(manifest: dict,openapi: dict,require_complete: bool=False) -> dict:
    """Fail on lost/drifting current APIs; report core pending and phase2 separately."""
    active=operations(openapi);seen=set();ids=set();missing=[];duplicates=[];mismatches=[];pending=[];deferred=[];unreviewed=[]
    for record in manifest['operations']:
        key=(record['method'].upper(),normalize_path(record['path']));api_id=record['id']
        if key in seen or api_id in ids:duplicates.append(api_id)
        seen.add(key);ids.add(api_id)
        actual=active.get(key)
        if actual is None:
            if record.get('implemented'):missing.append(api_id)
            elif record['phase']=='phase1':pending.append(api_id)
            elif record['phase']=='phase2':deferred.append(api_id)
            continue
        if not record.get('implemented'):
            unreviewed.append(api_id);continue
        fields,nested=response_shape(actual[1],openapi)
        if 'response_fields' in record and fields!=record['response_fields'] or 'nested_response_fields' in record and nested!=record['nested_response_fields']:mismatches.append(api_id)
    duplicates+=openapi.get('x-runtime-duplicate-operations',[])
    unexpected=sorted(method+' '+path for (method,key),(path,_) in active.items() if (method,key) not in seen)
    passed=not (missing or duplicates or mismatches or unexpected or unreviewed or require_complete and pending)
    return {'passed':passed,'checked_implemented':sum(bool(r.get('implemented')) for r in manifest['operations']),'missing':missing,'duplicates':duplicates,'schema_mismatches':mismatches,'unexpected':unexpected,'unreviewed_implementations':unreviewed,'pending_phase1':pending,'deferred_phase2':deferred}


def main():
    """Print a non-sensitive contract report; return nonzero on an actual gate failure."""
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest',type=Path,default=Path('docs/api-manifest.json'));parser.add_argument('--openapi',type=Path,default=Path('artifacts/openapi.json'));parser.add_argument('--require-complete',action='store_true')
    args=parser.parse_args();result=check_contract_coverage(json.loads(args.manifest.read_text('utf8')),json.loads(args.openapi.read_text('utf8')),args.require_complete)
    print(json.dumps(result,ensure_ascii=False,indent=2));raise SystemExit(0 if result['passed'] else 1)

if __name__=='__main__':main()
