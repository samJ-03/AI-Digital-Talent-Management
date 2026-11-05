"""Local synthetic file probe; never uploads real candidate material."""
import base64
import json
import re
import sys
from uuid import uuid4
from sqlalchemy import select,delete
from app.core.settings import Settings
from app.core.uow import make_uow
from app.files.models import StoredFile
from app.files.storage import S3FileStore
from app.files.service import FileService,UploadDescriptor
from app.identity.models import User
from app.identity.views import resolve_user
import io

PNG=base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=')

def main():
    settings=Settings.load()
    if settings.environment!='dev': raise RuntimeError('Local probe only')
    store=S3FileStore.from_settings(settings)
    service=FileService(store)
    try:
        with make_uow() as uow:
            user=uow.session.scalar(select(User).where(User.login_name=='hr-tech'))
            if user is None: raise RuntimeError('Local HR account is required')
            actor=resolve_user(uow.session,user)
        if len(sys.argv)==1:
            view=service.stage(actor,UploadDescriptor('local-file-probe-'+uuid4().hex+'.png','image/png',len(PNG),io.BytesIO(PNG)))
            print(json.dumps({'file_id':view.id}))
        elif len(sys.argv)==3 and sys.argv[1]=='cleanup':
            file_id=int(sys.argv[2])
            with make_uow() as uow:
                row=uow.session.scalar(select(StoredFile).where(StoredFile.id==file_id).with_for_update())
                if (row is None or row.bucket!=store.bucket or row.uploader_id!=actor.user_id or row.status!='staged'
                    or not re.fullmatch(r'local-file-probe-[a-f0-9]{32}\.png',row.original_name) or service._has_refs(uow.session,row.id)):
                    raise RuntimeError('Only an unreferenced synthetic probe file may be removed')
                store.delete(row.object_key)
                uow.session.delete(row);uow.commit()
            print(json.dumps({'cleaned':True}))
        else: raise ValueError('Invalid probe command')
    finally: store.close()

if __name__=='__main__': main()
