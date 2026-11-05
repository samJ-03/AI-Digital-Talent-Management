from dataclasses import dataclass,field
from email.message import EmailMessage
import smtplib
import ssl

@dataclass(frozen=True,slots=True)
class MailConnection:
    config_id: int
    host: str
    port: int
    tls_mode: str
    sender: str
    username: str|None=None
    credential_ref: str|None=field(default=None,repr=False)

@dataclass(frozen=True,slots=True)
class MailMessage:
    recipient: str=field(repr=False)
    subject: str
    body: str=field(repr=False)
    message_id: str

@dataclass(frozen=True,slots=True)
class DeliveryResult:
    status: str
    provider_message_id: str|None=None
    error_code: str|None=None

class SmtpAdapter:
    def __init__(self,cipher=None,smtp_factory=None,ssl_factory=None):
        self.cipher=cipher;self.smtp_factory=smtp_factory or smtplib.SMTP;self.ssl_factory=ssl_factory or smtplib.SMTP_SSL

    def send(self,config: MailConnection,message: MailMessage) -> DeliveryResult:
        client=None;connected=False
        try:
            if config.tls_mode=='tls': client=self.ssl_factory(timeout=5,context=ssl.create_default_context())
            else: client=self.smtp_factory(timeout=5)
            # smtplib3.11 keeps the constructor host for TLS SNI; deferred connect does not update it.
            client._host=config.host
            client.connect(config.host,config.port)
            connected=True
            client.ehlo()
            if config.tls_mode=='starttls':
                client.starttls(context=ssl.create_default_context());client.ehlo()
            if config.username:
                if self.cipher is None or not config.credential_ref: return DeliveryResult('failed',None,'SMTP_CREDENTIAL_UNAVAILABLE')
                client.login(config.username,self.cipher.decrypt(config.credential_ref))
            mail=EmailMessage();mail['From']=config.sender;mail['To']=message.recipient;mail['Subject']=message.subject;mail['Message-ID']=message.message_id;mail.set_content(message.body)
            refused=client.send_message(mail,from_addr=config.sender,to_addrs=[message.recipient])
            if refused: return DeliveryResult('failed',None,'SMTP_RECIPIENT_REJECTED')
            return DeliveryResult('accepted',message.message_id)
        except smtplib.SMTPAuthenticationError: return DeliveryResult('failed',None,'SMTP_AUTH_FAILED')
        except (smtplib.SMTPRecipientsRefused,smtplib.SMTPSenderRefused,smtplib.SMTPDataError): return DeliveryResult('failed',None,'SMTP_REJECTED')
        except (TimeoutError,smtplib.SMTPServerDisconnected,OSError):
            connected=connected or (client is not None and getattr(client,'sock',None) is not None)
            return DeliveryResult('unknown' if connected else 'failed',None,'SMTP_DELIVERY_UNKNOWN' if connected else 'SMTP_UNAVAILABLE')
        except Exception: return DeliveryResult('failed',None,'SMTP_CONFIGURATION_ERROR')
        finally:
            if client is not None:
                try: client.close()
                except Exception: pass
