"""从实际ORM导出可提交的数据库字典；不连接数据库、不读取任何业务记录。"""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from app.models import register_models
from sqlalchemy.dialects.mysql import dialect

def render() -> str:
    """返回包含全部表、字段、外键及索引的Markdown字典。"""
    metadata=register_models()
    lines=['# 数据库模型字典','',f'由 scripts/export_schema_docs.py 从当前SQLAlchemy元数据生成。共{len(metadata.tables)}张表、{sum(len(t.columns) for t in metadata.tables.values())}个字段；包含已实现与后续业务预建模型，存在表不代表相应业务接口已完成。','','统一约定：无符号自增ID通过API序列化为字符串；DATETIME(6)存UTC；row_version控制乐观锁；历史版本与审计不可随意覆盖；外键默认RESTRICT。','','字段中文说明通过0005_schema_comments及后续注释修订写入MySQL COMMENT；原始建表迁移不回写。','']
    for name,table in sorted(metadata.tables.items()):
        lines.extend(['## '+name+' — '+(table.comment or ''),'','| 字段 | MySQL类型 | 可空 | 默认值 | 说明 |','|---|---|---|---|---|'])
        for c in table.columns:
            argument=c.server_default.arg if c.server_default is not None else None
            default=str(argument.compile(dialect=dialect(),compile_kwargs={'literal_binds':True})) if hasattr(argument,'compile') else str(argument) if argument is not None else '—'
            if c.primary_key: default='AUTO_INCREMENT'
            lines.append('| '+c.name+' | '+str(c.type.compile(dialect=dialect())).replace('|','\\|')+' | '+('是' if c.nullable else '否')+' | '+default+' | '+(c.comment or '').replace('|','\\|')+' |')
        lines.append('')
        refs=sorted(fk.parent.name+' → '+fk.target_fullname+' (ON DELETE '+str(fk.ondelete)+')' for fk in table.foreign_keys)
        if refs: lines.extend(['外键：'+'；'.join(refs)+'。',''])
        constraints=[]
        for constraint in table.constraints:
            if constraint.__class__.__name__=='UniqueConstraint': constraints.append('UNIQUE('+','.join(c.name for c in constraint.columns)+')')
            if constraint.__class__.__name__=='CheckConstraint': constraints.append('CHECK '+str(constraint.sqltext))
        constraints.extend(('UNIQUE ' if index.unique else '')+'INDEX '+index.name+'('+','.join(c.name for c in index.columns)+')' for index in table.indexes)
        if constraints: lines.extend(['约束与索引：'+'；'.join(sorted(constraints))+'。',''])
    return '\n'.join(lines).rstrip()+'\n'

if __name__=='__main__': print(render(),end='')
