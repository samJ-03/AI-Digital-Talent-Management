"""邮件配置与交付：定义输入输出类型、字段约束及序列化边界。"""
from typing import Literal
from pydantic import BaseModel,ConfigDict,EmailStr,Field,SecretStr,model_validator

class MailConfigWrite(BaseModel):
    """MailConfigWrite：邮件配置与交付中的输入输出数据契约。"""
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
        """校验SMTP用户名和秘密须配套提供。"""
        if bool(self.username)!=bool(self.secret): raise ValueError('Username and password must be configured together')
        return self

class TestRecipient(BaseModel):
    """TestRecipient：邮件配置与交付中的输入输出数据契约。"""
    model_config=ConfigDict(extra='forbid')
    test_recipient: EmailStr

class MailAction(BaseModel):
    """MailAction：邮件配置与交付中的输入输出数据契约。"""
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    reason: str=Field(min_length=1,max_length=500)

class MaskedMailConfig(BaseModel):
    """MaskedMailConfig：邮件配置与交付中的输入输出数据契约。"""
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
