from typing import Literal
from pydantic import BaseModel,ConfigDict,EmailStr,Field,SecretStr,model_validator

class MailConfigWrite(BaseModel):
    model_config=ConfigDict(extra='forbid')
    smtp_host: str=Field(min_length=1,max_length=255,pattern=r'^[a-zA-Z0-9.-]+$')
    smtp_port: int=Field(ge=1,le=65535)
    tls_mode: Literal['starttls','tls','none']
    sender_address: EmailStr
    username: str|None=Field(default=None,min_length=1,max_length=255)
    secret: SecretStr|None=Field(default=None,min_length=1,max_length=8192)
    public_base_url: str=Field(min_length=1,max_length=500)
    @model_validator(mode='after')
    def paired_credentials(self):
        if bool(self.username)!=bool(self.secret): raise ValueError('Username and password must be configured together')
        return self

class TestRecipient(BaseModel):
    model_config=ConfigDict(extra='forbid')
    test_recipient: EmailStr

class MailAction(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    reason: str=Field(min_length=1,max_length=500)

class MaskedMailConfig(BaseModel):
    id: str
    revision_no: int
    smtp_host: str
    smtp_port: int
    tls_mode: str
    sender_address: str
    username_configured: bool
    secret_configured: bool
    public_base_url: str
    state: str
    version: int
