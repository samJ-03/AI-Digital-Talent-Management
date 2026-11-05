from dataclasses import dataclass
from datetime import datetime
import io
import re
from minio import Minio
from minio.error import S3Error
from urllib3 import PoolManager,Timeout,Retry
from app.core.errors import DomainError

@dataclass(frozen=True,slots=True)
class StoredObject:
    key: str
    etag: str

class ObjectStream(io.IOBase):
    def __init__(self,response): self.response=response
    def read(self,size=-1): return self.response.read(size)
    def close(self):
        if not self.closed:
            try: self.response.close()
            finally: self.response.release_conn()
        super().close()

class S3FileStore:
    def __init__(self,endpoint,access_key,secret_key,bucket='talent-business',secure=False):
        if not re.fullmatch(r'talent-[a-z0-9-]{3,55}',bucket):
            raise ValueError('Business storage must use its own talent-prefixed bucket')
        self.bucket=bucket
        self.http=PoolManager(timeout=Timeout(connect=3,read=15),retries=Retry(total=1,allowed_methods=['GET','HEAD']))
        self.client=Minio(endpoint,access_key=access_key,secret_key=secret_key,secure=secure,http_client=self.http)

    @classmethod
    def from_settings(cls,settings,bucket=None):
        if not settings.minio_user or not settings.minio_password:
            raise DomainError('FILE_STORAGE_UNAVAILABLE',503,'文件服务未配置')
        return cls(settings.minio_endpoint,settings.minio_user.get_secret_value(),settings.minio_password.get_secret_value(),bucket or settings.minio_bucket,settings.minio_secure)

    def ensure_private_bucket(self):
        try:
            if not self.client.bucket_exists(self.bucket):
                try: self.client.make_bucket(self.bucket)
                except S3Error as error:
                    if error.code not in {'BucketAlreadyOwnedByYou','BucketAlreadyExists'}: raise
            try:
                policy=self.client.get_bucket_policy(self.bucket)
                if policy: raise DomainError('UNSAFE_BUCKET_POLICY',503,'业务文件桶必须禁止公共读取')
            except S3Error as error:
                if error.code!='NoSuchBucketPolicy': raise
        except DomainError: raise
        except Exception:
            raise DomainError('FILE_STORAGE_UNAVAILABLE',503,'文件服务暂不可用') from None

    def put(self,key,stream,content_type) -> StoredObject:
        self.ensure_private_bucket()
        try:
            result=self.client.put_object(self.bucket,key,stream,length=-1,part_size=5*1024*1024,content_type=content_type)
            return StoredObject(key,result.etag)
        except Exception:
            raise DomainError('FILE_STORAGE_UNAVAILABLE',503,'文件服务暂不可用') from None

    def get(self,key):
        try: return ObjectStream(self.client.get_object(self.bucket,key))
        except S3Error as error:
            if error.code in {'NoSuchKey','NoSuchObject','NoSuchBucket'}:
                raise DomainError('RESOURCE_NOT_FOUND',404,'文件不存在') from None
            raise DomainError('FILE_STORAGE_UNAVAILABLE',503,'文件服务暂不可用') from None
        except Exception:
            raise DomainError('FILE_STORAGE_UNAVAILABLE',503,'文件服务暂不可用') from None

    def delete(self,key):
        try: self.client.remove_object(self.bucket,key)
        except Exception:
            raise DomainError('FILE_STORAGE_UNAVAILABLE',503,'文件服务暂不可用') from None

    def expired_staged_objects(self,before: datetime):
        try:
            for item in self.client.list_objects(self.bucket,prefix='staged/',recursive=True):
                if item.last_modified and item.last_modified<before:
                    yield item.object_name
        except Exception:
            raise DomainError('FILE_STORAGE_UNAVAILABLE',503,'文件服务暂不可用') from None

    def close(self):
        self.http.clear()
