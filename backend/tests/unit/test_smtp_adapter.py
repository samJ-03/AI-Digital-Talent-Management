"""平台开发工具：验证smtp adapter的正常与失败场景；测试数据仅用于隔离环境。"""
from app.notifications.smtp_adapter import SmtpAdapter,MailConnection,MailMessage

MESSAGE=MailMessage('synthetic@example.com','Synthetic','No real invitation','<synthetic@talent.local>')

def test_timeout_after_tcp_connect_is_unknown_even_before_greeting():
    class GreetingTimeout:
        sock=None
        def __init__(self,*args,**kwargs):
            if args:
                self.sock=object()
                raise TimeoutError('greeting timeout')
        def connect(self,*args): self.sock=object();raise TimeoutError('greeting timeout')
        def close(self): pass
    result=SmtpAdapter(smtp_factory=GreetingTimeout).send(MailConnection(1,'mailpit',1025,'none','sender@example.com'),MESSAGE)
    assert result.status=='unknown' and result.error_code=='SMTP_DELIVERY_UNKNOWN'

def test_connect_failure_before_any_socket_is_failed():
    class NoConnection:
        sock=None
        def __init__(self,*args,**kwargs):
            if args: raise ConnectionRefusedError('refused')
        def connect(self,*args): raise ConnectionRefusedError('refused')
        def close(self): pass
    assert SmtpAdapter(smtp_factory=NoConnection).send(MailConnection(1,'mailpit',1025,'none','sender@example.com'),MESSAGE).status=='failed'


import pytest

@pytest.mark.parametrize('mode',['tls','starttls'])
def test_deferred_connect_preserves_tls_hostname_and_certificate_verification(mode):
    import ssl
    class Client:
        sock=None
        def __init__(self,*args,**kwargs):
            self._host=''
            if 'context' in kwargs:
                assert kwargs['context'].check_hostname and kwargs['context'].verify_mode==ssl.CERT_REQUIRED
        def connect(self,host,port):
            assert self._host==host
            self.sock=object()
        def ehlo(self): pass
        def starttls(self,context): assert context.check_hostname and context.verify_mode==ssl.CERT_REQUIRED
        def send_message(self,*args,**kwargs): return {}
        def close(self): pass
    result=SmtpAdapter(smtp_factory=Client,ssl_factory=Client).send(MailConnection(1,'smtp.example.com',465 if mode=='tls' else 587,mode,'sender@example.com'),MESSAGE)
    assert result.status=='accepted'
