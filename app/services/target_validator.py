import ipaddress
import socket
from urllib.parse import urlsplit

from app.utils.config import get_settings


class UnsafeTargetError(ValueError):
    """Raised when a test target could reach private platform infrastructure."""


_BLOCKED_HOSTS = {"localhost", "localhost.localdomain", "metadata.google.internal"}


def validate_target_url(url: str) -> None:
    """Allow only public HTTP(S) targets and reject private DNS resolutions.

    Checking after DNS resolution prevents a hostname such as an internal
    service name from bypassing literal-IP validation. Redirects are disabled
    by the request callers, so an allowed public URL cannot redirect into a
    private address.
    """
    parsed = urlsplit(url)
    hostname = parsed.hostname
    if parsed.scheme not in {"http", "https"} or not hostname:
        raise UnsafeTargetError("测试目标必须是带主机名的 HTTP(S) URL")
    if parsed.username or parsed.password:
        raise UnsafeTargetError("测试目标 URL 不允许携带用户凭据")
    normalized_host = hostname.rstrip(".").lower()
    settings = get_settings()
    explicitly_allowed = normalized_host in settings.target_host_allowlist
    if normalized_host in _BLOCKED_HOSTS and not explicitly_allowed:
        raise UnsafeTargetError("测试目标不允许指向本机或云元数据服务")

    try:
        addresses = {item[4][0] for item in socket.getaddrinfo(hostname, None, type=socket.SOCK_STREAM)}
    except socket.gaierror as exc:
        raise UnsafeTargetError(f"无法解析测试目标主机: {hostname}") from exc

    if not addresses:
        raise UnsafeTargetError(f"无法解析测试目标主机: {hostname}")

    for address in addresses:
        if (
            not ipaddress.ip_address(address).is_global
            and not settings.allow_private_targets
            and not explicitly_allowed
        ):
            raise UnsafeTargetError("测试目标解析到了非公网地址，已拒绝执行")
