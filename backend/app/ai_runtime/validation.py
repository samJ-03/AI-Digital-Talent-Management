"""Fail-closed validation; never persist raw provider responses."""
import json
import math
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError as SchemaValidationError
from pydantic import BaseModel, ValidationError

class OutputInvalid(Exception):
    pass

def _pairs(pairs):
    result={}
    for key,value in pairs:
        if key in result: raise OutputInvalid()
        result[key]=value
    return result

def _constant(_):
    raise OutputInvalid()

def validate_output(content: str, output_type: type[BaseModel], schema: dict, evidence: list[dict]):
    try:
        if not isinstance(content,str) or len(content.encode('utf8'))>256*1024: raise OutputInvalid()
        value=json.loads(content,object_pairs_hook=_pairs,parse_constant=_constant)
        Draft202012Validator(schema).validate(value)
        typed=output_type.model_validate(value,strict=True)
        if not isinstance(value,dict): raise OutputInvalid()
        citations=value.get('citations')
        if not isinstance(citations,list) or not citations: raise OutputInvalid()
        for citation in citations:
            if not isinstance(citation,dict) or set(citation)!={'source_type','source_id','locator','quote'}: raise OutputInvalid()
            if not all(isinstance(v,str) and v.strip() for v in citation.values()): raise OutputInvalid()
            if not any(all(citation[k]==source.get(k) for k in ('source_type','source_id','locator'))
                and citation['quote'] in source.get('quote','') for source in evidence): raise OutputInvalid()
        return typed
    except (ValueError,TypeError,KeyError,RecursionError,ValidationError,SchemaValidationError):
        raise OutputInvalid() from None

def validate_vectors(vectors, count: int, dimension: int|None) -> int:
    if not isinstance(vectors,list) or len(vectors)!=count or not vectors: raise OutputInvalid()
    actual=len(vectors[0]) if isinstance(vectors[0],list) else 0
    if not 1<=actual<=8192 or dimension is not None and actual!=dimension: raise OutputInvalid()
    for vector in vectors:
        if not isinstance(vector,list) or len(vector)!=actual: raise OutputInvalid()
        try:
            if any(type(n) not in (int,float) or not math.isfinite(n) for n in vector) or not any(n!=0 for n in vector): raise OutputInvalid()
        except OverflowError: raise OutputInvalid() from None
    return actual
