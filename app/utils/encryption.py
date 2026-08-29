import base64
import hashlib
import json
from typing import Any

from cryptography.fernet import Fernet, InvalidToken

from app.utils.config import get_settings


class EncryptionUnavailable(RuntimeError):
    pass


def _fernet() -> Fernet:
    settings = get_settings()
    material = settings.platform_encryption_key or settings.platform_api_key
    if not material:
        raise EncryptionUnavailable(
            "未配置 PLATFORM_ENCRYPTION_KEY，无法保存环境密钥；本地可设置任意高强度随机字符串"
        )
    key = base64.urlsafe_b64encode(hashlib.sha256(material.encode("utf-8")).digest())
    return Fernet(key)


def encrypt_mapping(value: dict[str, Any]) -> str:
    if not value:
        return ""
    payload = json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return _fernet().encrypt(payload).decode("ascii")


def decrypt_mapping(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    try:
        payload = _fernet().decrypt(value.encode("ascii"))
    except InvalidToken as exc:
        raise EncryptionUnavailable("环境密钥无法解密，请检查 PLATFORM_ENCRYPTION_KEY 是否发生变化") from exc
    result = json.loads(payload.decode("utf-8"))
    if not isinstance(result, dict):
        raise EncryptionUnavailable("环境密钥内容格式错误")
    return result
