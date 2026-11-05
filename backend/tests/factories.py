from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4
from sqlalchemy import Boolean, DateTime, Integer, JSON, Numeric, String
from app.models import TABLE_MODELS

def make_row(session, table_name: str, **overrides):
    model=TABLE_MODELS.get(table_name)
    assert model is not None, 'ORM entity not implemented: '+table_name
    values=dict(overrides)
    for column in model.__table__.columns:
        if column.name in values or column.primary_key or column.default is not None or column.server_default is not None or column.nullable:
            continue
        foreigns=list(column.foreign_keys)
        if foreigns:
            parent=make_row(session,foreigns[0].column.table.name)
            values[column.name]=parent.id
        elif isinstance(column.type, Boolean): values[column.name]=False
        elif isinstance(column.type, Integer): values[column.name]=1
        elif isinstance(column.type, Numeric): values[column.name]=Decimal('1.00')
        elif isinstance(column.type, DateTime): values[column.name]=datetime.now(timezone.utc).replace(tzinfo=None)
        elif isinstance(column.type, JSON): values[column.name]={}
        else:
            choices=column.info.get('allowed_values')
            values[column.name]=choices[0] if choices else uuid4().hex[:min(column.type.length or 32,32)]
    row=model(**values)
    session.add(row)
    session.flush()
    return row
