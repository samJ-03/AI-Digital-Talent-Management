import json
import socket
import sys
from sqlalchemy import text
from app.core.uow import make_uow

def main(kind: str) -> int:
    ready=False
    try:
        if kind=='worker':
            from app.runtime.worker import celery_app
            destination='celery@'+socket.gethostname()
            replies=celery_app.control.ping(destination=[destination],timeout=3)
            ready=any(reply.get(destination,{}).get('ok')=='pong' for reply in replies)
        elif kind=='scheduler':
            with make_uow() as uow:
                ready=uow.session.scalar(text('SELECT IS_USED_LOCK(:name) IS NOT NULL'),{'name':'ai-talent:scheduler'})==1
    except Exception:
        ready=False
    print(json.dumps({'ready':ready}))
    return 0 if ready else 1

if __name__=='__main__': raise SystemExit(main(sys.argv[1] if len(sys.argv)>1 else ''))
