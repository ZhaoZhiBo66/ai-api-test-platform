from __future__ import annotations

import re
import time
import uuid
from typing import Any
from urllib.parse import urljoin

from app.services.data_path import DataPathError, get_path


class VariableError(ValueError):
    pass


_VARIABLE = re.compile(r"\$\{([A-Za-z_][\w.-]*)\}")


def build_runtime_variables(environment_variables: dict | None, overrides: dict | None) -> dict[str, Any]:
    values: dict[str, Any] = {
        "timestamp": int(time.time()),
        "timestamp_ms": int(time.time() * 1000),
        "uuid": str(uuid.uuid4()),
    }
    values.update(environment_variables or {})
    values.update(overrides or {})
    return values


def render_value(value: Any, variables: dict[str, Any]) -> Any:
    if isinstance(value, dict):
        return {key: render_value(item, variables) for key, item in value.items()}
    if isinstance(value, list):
        return [render_value(item, variables) for item in value]
    if not isinstance(value, str):
        return value

    full_match = _VARIABLE.fullmatch(value)
    if full_match:
        name = full_match.group(1)
        if name not in variables:
            raise VariableError(f"变量未定义: {name}")
        return variables[name]

    def replace(match: re.Match[str]) -> str:
        name = match.group(1)
        if name not in variables:
            raise VariableError(f"变量未定义: {name}")
        return str(variables[name])

    return _VARIABLE.sub(replace, value)


def resolve_url(url: str, base_url: str = "") -> str:
    if url.startswith(("http://", "https://")):
        return url
    if not base_url:
        raise VariableError("接口使用相对路径，但当前环境未配置 base_url")
    return urljoin(base_url.rstrip("/") + "/", url.lstrip("/"))


def extract_variables(
    extractors: list[dict],
    *,
    body: Any,
    headers: dict[str, Any],
    status_code: int,
) -> dict[str, Any]:
    extracted: dict[str, Any] = {}
    normalized_headers = {str(key).lower(): value for key, value in headers.items()}
    for extractor in extractors or []:
        name = str(extractor.get("name", "")).strip()
        if not name:
            raise VariableError("提取器缺少 name")
        source = extractor.get("source", "body")
        required = bool(extractor.get("required", True))
        default = extractor.get("default")
        try:
            if source == "body":
                value = get_path(body, extractor.get("path", "$"))
            elif source == "header":
                header_name = str(extractor.get("path", "")).lower()
                if header_name not in normalized_headers:
                    raise VariableError(f"响应头不存在: {header_name}")
                value = normalized_headers[header_name]
            elif source == "status":
                value = status_code
            else:
                raise VariableError(f"不支持的提取来源: {source}")
        except (DataPathError, VariableError):
            if required:
                raise
            value = default
        extracted[name] = value
    return extracted
