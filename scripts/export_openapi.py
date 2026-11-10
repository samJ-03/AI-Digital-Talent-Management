"""Export real FastAPI schemas; never invoke business, provider or email operations."""
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts.check_contract_coverage import normalize_path,operations,response_shape


def export_openapi(output_path: Path|None) -> dict:
    """Assemble the current application without serving requests or mutating data."""
    from app.main import create_app
    from app.core.settings import Settings
    from fastapi.routing import APIRoute
    app=create_app(Settings.load());schema=app.openapi();seen=set();duplicates=[]
    try:
        for route in app.routes:
            if not isinstance(route,APIRoute) or not route.path.startswith('/api/v1/'):continue
            for method in route.methods:
                key=(method,normalize_path(route.path))
                if key in seen:duplicates.append(method+' '+route.path)
                seen.add(key)
        schema['x-runtime-duplicate-operations']=duplicates
        if output_path is not None:
            output_path.parent.mkdir(parents=True,exist_ok=True)
            output_path.write_text(json.dumps(schema,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
        return schema
    finally:
        app.state.identity.close()
        probe=getattr(app.state.readiness_probe,'__self__',None)
        if probe:probe.close()
        if app.state.file_service and getattr(app.state.file_service,'store',None):app.state.file_service.store.close()


def main():
    """Refresh manifest only when explicitly requested after a reviewed contract change."""
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,default=Path('artifacts/openapi.json'));parser.add_argument('--refresh-manifest',type=Path)
    args=parser.parse_args();stdout_mode=args.output==Path('-');schema=export_openapi(None if stdout_mode else args.output)
    if args.refresh_manifest:
        manifest=json.loads(args.refresh_manifest.read_text('utf8'));active=operations(schema)
        for record in manifest['operations']:
            actual=active.get((record['method'],normalize_path(record['path'])))
            record['implemented']=actual is not None
            if actual:
                record['actual_path']=actual[0];record['response_fields'],record['nested_response_fields']=response_shape(actual[1],schema)
        args.refresh_manifest.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    if stdout_mode:print(json.dumps(schema,ensure_ascii=False,indent=2))
    else:print('OpenAPI exported; business/provider operations not executed')

if __name__=='__main__':main()
