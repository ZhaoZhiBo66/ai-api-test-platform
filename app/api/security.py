import secrets
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import APIKeyHeader

from app.utils.config import get_settings
from app.utils.logger import logger


_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def _configured_keys() -> dict[str, str]:
    settings = get_settings()
    keys = dict(settings.platform_api_keys)
    if settings.platform_api_key:
        keys.setdefault(settings.platform_api_key, "admin")
    return keys


def require_api_key(
    request: Request,
    api_key: Annotated[str | None, Depends(_api_key_header)] = None,
) -> None:
    """Protect state-changing and test-execution endpoints when enabled.

    Local development can explicitly leave authentication disabled. Container
    deployments enable it and must provide a non-empty PLATFORM_API_KEY.
    """
    settings = get_settings()
    if not settings.api_auth_enabled:
        return

    configured = _configured_keys()
    if not configured:
        logger.error("API authentication is enabled but no platform API keys are configured")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="平台鉴权未配置")

    matched_role = None
    if api_key:
        for configured_key, role in configured.items():
            if secrets.compare_digest(api_key, configured_key):
                matched_role = role
                break
    if matched_role not in {"viewer", "operator", "admin"}:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效的 API Key")
    if request.method == "DELETE" and matched_role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="删除操作需要 admin 权限")
    if request.method not in {"GET", "HEAD", "OPTIONS"} and matched_role == "viewer":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="当前 API Key 只有只读权限")
    request.state.actor = f"api-key:***{api_key[-4:]}"
    request.state.role = matched_role


def require_admin(request: Request) -> None:
    if not get_settings().api_auth_enabled:
        return
    if getattr(request.state, "role", None) != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="该操作需要 admin 权限")
