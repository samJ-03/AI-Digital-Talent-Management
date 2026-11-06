"""公共基础设施：加密连接凭据并生成幂等所需的安全指纹。"""
import hashlib,hmac
from cryptography.fernet import Fernet,InvalidToken
from app.core.errors import DomainError

class SecretCipher:
    """SecretCipher：公共基础设施中的协作类型。"""
    def __init__(self,key: str):
        self._fingerprint_key=hashlib.sha256(b'talent-idempotency:'+key.encode()).digest()
        try: self.fernet=Fernet(key.encode())
        except (ValueError,TypeError):
            raise DomainError('SECRET_KEY_UNAVAILABLE',503,'加密配置不可用') from None

    def encrypt(self,plaintext: str) -> str:
        """用项目主密钥加密凭据，返回版本化密文。"""
        if not plaintext or len(plaintext)>8192:
            raise DomainError('INVALID_SECRET',422,'凭据无效')
        return 'v1.'+self.fernet.encrypt(plaintext.encode()).decode()

    def decrypt(self,ciphertext: str) -> str:
        """解密本项目保存的凭据；明文不得写入日志或响应。"""
        try:
            if not ciphertext.startswith('v1.'): raise ValueError()
            return self.fernet.decrypt(ciphertext[3:].encode()).decode()
        except (InvalidToken,ValueError,UnicodeError,TypeError):
            raise DomainError('SECRET_DECRYPT_FAILED',503,'凭据无法解密，请核对加密配置') from None

    def fingerprint(self,plaintext: str) -> str:
        """生成不暴露秘密的稳定指纹，用于幂等请求比较。"""
        return hmac.new(self._fingerprint_key,plaintext.encode(),hashlib.sha256).hexdigest()
