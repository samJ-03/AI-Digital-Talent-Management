"""真实Milvus SDK适配器；模型代际与实体类型隔离，固定服务端过滤。"""
import math
import re
from hashlib import sha256
from pymilvus import MilvusClient,DataType
from app.core.errors import DomainError
from app.search.schemas import VectorHit

class MilvusStore:
    """拥有SDK连接；有限超时、显式schema、Strong一致性。"""
    def __init__(self,uri=None,prefix='talent',timeout=8):
        if uri is None:
            from app.core.settings import Settings
            uri=Settings.load().milvus_uri
        if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,50}',prefix):raise ValueError('Invalid collection prefix')
        self.prefix=prefix;self.timeout=timeout;self.created=set()
        try:self.client=MilvusClient(uri=uri,timeout=timeout)
        except Exception:raise DomainError('SEMANTIC_INDEX_UNAVAILABLE',503,'语义索引连接不可用') from None

    def collection(self,model_id,revision,dimension,digest=None):
        """云端无权重digest时不伪造，依模型配置修订隔离。"""
        suffix=sha256((digest or 'cloud-config').encode()).hexdigest()[:10]
        return f'{self.prefix}_profile_m{model_id}_r{revision}_d{dimension}_{suffix}'

    def _require_name(self,name):
        if not re.fullmatch(re.escape(self.prefix)+r'_profile_m[0-9]+_r[0-9]+_d[0-9]+_[a-f0-9]{10}',name):raise ValueError('Foreign collection')

    def _ensure(self,name,dimension):
        self._require_name(name)
        if self.client.has_collection(name,timeout=self.timeout):return
        schema=self.client.create_schema(auto_id=False,enable_dynamic_field=False)
        for field,length in [('key',190),('entity_type',32),('scope',24),('content_hash',64)]:schema.add_field(field,DataType.VARCHAR,max_length=length,is_primary=field=='key')
        schema.add_field('entity_id',DataType.INT64);schema.add_field('department_id',DataType.INT64)
        schema.add_field('vector',DataType.FLOAT_VECTOR,dim=dimension)
        params=self.client.prepare_index_params();params.add_index(field_name='vector',index_type='AUTOINDEX',metric_type='COSINE')
        try:self.client.create_collection(name,schema=schema,index_params=params,consistency_level='Strong',timeout=self.timeout)
        except Exception:
            if not self.client.has_collection(name,timeout=self.timeout):raise
        self.created.add(name)

    def upsert(self,collection,records):
        """幂等写引用和向量；失败明确不可用，不能报同步成功。"""
        if not records:return
        try:
            dimension=len(records[0].vector)
            if not 2<=dimension<=32768:raise ValueError('Invalid dimension')
            rows=[]
            for row in records:
                if row.entity_type!='profile' or row.scope!='shared' or row.department_id is not None or len(row.vector)!=dimension or not all(math.isfinite(v) for v in row.vector) or not any(row.vector):raise ValueError('Invalid shared vector')
                rows.append({'key':row.key,'entity_id':row.entity_id,'entity_type':row.entity_type,'scope':row.scope,'department_id':0,'content_hash':row.content_hash,'vector':row.vector})
            self._ensure(collection,dimension);self.client.upsert(collection,data=rows,timeout=self.timeout)
        except Exception:raise DomainError('SEMANTIC_INDEX_UNAVAILABLE',503,'语义索引暂不可用') from None

    def search(self,collection,vector,filters,top_k):
        """只允许共享profile过滤；未来知识检索须另行定义专属集合。"""
        if filters.entity_type!='profile' or not filters.shared or filters.department_ids:raise ValueError('Invalid shared scope')
        if not 1<=top_k<=1000:raise ValueError('Invalid top_k')
        try:
            self._require_name(collection)
            if not self.client.has_collection(collection,timeout=self.timeout):raise DomainError('SEMANTIC_INDEX_UNAVAILABLE',503,'当前模型索引尚未建立')
            hits=self.client.search(collection,data=[vector],anns_field='vector',filter='entity_type == "profile" and scope == "shared" and department_id == 0',limit=top_k,output_fields=['entity_id','content_hash','key'],search_params={'metric_type':'COSINE','params':{}},consistency_level='Strong',timeout=self.timeout)[0]
            return [VectorHit(int(h['entity']['entity_id']),float(h['distance']),str(h['entity']['key']),str(h['entity']['content_hash'])) for h in hits]
        except Exception:raise DomainError('SEMANTIC_INDEX_UNAVAILABLE',503,'语义索引暂不可用') from None

    def close(self):
        """释放SDK连接。"""
        self.client.close()
