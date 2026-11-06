"""邮件配置与交付：限制SMTP主机、TLS和候选人入口地址。"""
from urllib.parse import urlsplit
from app.core.errors import DomainError

class MailPolicy:
    """MailPolicy：邮件配置与交付中的协作类型。"""
    def __init__(self,settings): self.settings=settings
    def require(self,host,port,tls_mode,public_base_url):
        """验证权限或地址策略，不满足时失败关闭。"""
        if host not in self.settings.allowed_smtp_hosts:
            raise DomainError('SMTP_HOST_DENIED',422,'SMTP目标不在允许范围内')
        local=self.settings.environment in {'dev','test'} and host=='mailpit' and port==1025
        if tls_mode=='none' and not local: raise DomainError('SMTP_TLS_REQUIRED',422,'正式邮件连接必须使用TLS')
        try: url=urlsplit(public_base_url)
        except ValueError: raise DomainError('INVALID_PUBLIC_URL',422,'候选人访问地址无效') from None
        if url.username or url.password or url.query or url.fragment or url.path not in {'','/'}:
            raise DomainError('INVALID_PUBLIC_URL',422,'候选人访问地址无效')
        if url.scheme=='https' and url.hostname and url.hostname not in {'localhost','127.0.0.1'}: return
        if local and public_base_url.rstrip('/') in {'http://localhost:13000','http://127.0.0.1:13000'}: return
        raise DomainError('PUBLIC_HTTPS_REQUIRED',422,'正式候选人访问地址必须使用HTTPS')
