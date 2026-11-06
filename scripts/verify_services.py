"""Real protocol read/write probes against this project's isolated services only."""
from __future__ import annotations
import io
import json
import os
import smtplib
from uuid import uuid4
from sqlalchemy import create_engine, select, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, Session
from redis import Redis
from minio import Minio
from pymilvus import MilvusClient

class ProbeBase(DeclarativeBase):
    """ProbeBase：平台开发工具中的协作类型。"""
    pass

class EnvironmentProbe(ProbeBase):
    """EnvironmentProbe：平台开发工具中的协作类型。"""
    __tablename__ = 'talent_environment_probe'
    __table_args__ = {'prefixes':['TEMPORARY']}
    id: Mapped[str] = mapped_column(String(40),primary_key=True)
    value: Mapped[str] = mapped_column(String(100))

def mysql_probe():
    """在本项目数据库连接中创建临时探针表，验证读写并清理。"""
    engine=create_engine(os.environ['TALENT_DATABASE_URL'],connect_args={'connect_timeout':5})
    try:
        with engine.connect() as connection:
            EnvironmentProbe.__table__.create(connection)
            try:
                with Session(bind=connection) as session:
                    key=uuid4().hex
                    session.add(EnvironmentProbe(id=key,value='protocol-read-write'))
                    session.flush()
                    assert session.scalar(select(EnvironmentProbe.value).where(EnvironmentProbe.id==key)) == 'protocol-read-write'
                    session.rollback()
            finally:
                EnvironmentProbe.__table__.drop(connection)
    finally:
        engine.dispose()

def redis_probe():
    """验证带过期时间的合成键读写，完成后只删除自己的键。"""
    client=Redis.from_url(os.environ['TALENT_REDIS_URL'],socket_timeout=5)
    key='talent:preflight:'+uuid4().hex
    try:
        client.set(key,b'protocol-read-write',ex=60)
        assert client.get(key)==b'protocol-read-write'
    finally:
        client.delete(key)
        client.close()

def minio_probe():
    """在专用探针桶验证合成对象读写，完成后删除自己的对象。"""
    client=Minio('minio:9000',access_key=os.environ['TALENT_MINIO_USER'],secret_key=os.environ['TALENT_MINIO_PASSWORD'],secure=False)
    bucket='talent-preflight'
    key=uuid4().hex
    if not client.bucket_exists(bucket): client.make_bucket(bucket)
    try:
        client.put_object(bucket,key,io.BytesIO(b'protocol-read-write'),19)
        response=client.get_object(bucket,key)
        try:
            assert response.read()==b'protocol-read-write'
        finally:
            response.close(); response.release_conn()
    finally:
        client.remove_object(bucket,key)

def milvus_probe():
    """创建独立的8维探针集合验证写入和近邻检索，随后删除集合。"""
    client=MilvusClient(uri='http://milvus:19530',timeout=30)
    name='preflight_'+uuid4().hex[:20]
    try:
        client.create_collection(collection_name=name,dimension=8,metric_type='COSINE',consistency_level='Strong')
        client.insert(collection_name=name,data=[{'id':1,'vector':[1.,0.,0.,0.,0.,0.,0.,0.]},{'id':2,'vector':[0.,1.,0.,0.,0.,0.,0.,0.]}])
        result=client.search(collection_name=name,data=[[1.,0.,0.,0.,0.,0.,0.,0.]],limit=1)
        assert result[0][0]['id']==1
    finally:
        if client.has_collection(collection_name=name): client.drop_collection(collection_name=name)
        client.close()

def mail_probe():
    """只通过SMTP NOOP验证本地Mailpit协议，不发送邮件。"""
    with smtplib.SMTP('mailpit',1025,timeout=5) as client:
        assert client.noop()[0]==250

results=[]
for name,fn in [('mysql',mysql_probe),('redis',redis_probe),('minio',minio_probe),('milvus',milvus_probe),('mail',mail_probe)]:
    try:
        fn(); results.append({'service':name,'ok':True})
    except Exception as error:
        results.append({'service':name,'ok':False,'error_type':type(error).__name__})
print(json.dumps({'profile':'infrastructure','ready':all(r['ok'] for r in results),'checks':results,'not_yet_verified':['model_quality','OCR','business_workflows']},indent=2))
raise SystemExit(0 if all(r['ok'] for r in results) else 1)
