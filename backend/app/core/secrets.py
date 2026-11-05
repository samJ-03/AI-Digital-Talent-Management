from cryptography.fernet import Fernet,InvalidToken
from app.core.errors import DomainError

class SecretCipher:
    def __init__(self,key: str):
        try: self.fernet=Fernet(key.encode())
        except (ValueError,TypeError):
            raise DomainError('SECRET_KEY_UNAVAILABLE',503,'加密配置不可用') from None

    def encrypt(self,plaintext: str) -> str:
        if not plaintext or len(plaintext)>8192:
            raise DomainError('INVALID_SECRET',422,'凭据无效')
        return 'v1.'+self.fernet.encrypt(plaintext.encode()).decode()

    def decrypt(self,ciphertext: str) -> str:
        try:
            if not ciphertext.startswith('v1.'): raise ValueError()
            return self.fernet.decrypt(ciphertext[3:].encode()).decode()
        except (InvalidToken,ValueError,UnicodeError,TypeError):
            raise DomainError('SECRET_DECRYPT_FAILED',503,'凭据无法解密，请核对加密配置') from None
