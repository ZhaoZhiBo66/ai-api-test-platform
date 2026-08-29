from __future__ import annotations

import re
from typing import Any


class DataPathError(ValueError):
    pass


_TOKEN = re.compile(
    r"(?:^\$)|(?:\.([A-Za-z_][\w-]*|\*))|(?:\[(\d+|\*|'[^']+'|\"[^\"]+\")\])"
)
_MISSING = object()


def _tokens(path: str) -> list[str | int]:
    if path in {"", "$"}:
        return []
    if not path.startswith("$"):
        raise DataPathError("JSONPath 必须以 $ 开头")

    result: list[str | int] = []
    position = 0
    for match in _TOKEN.finditer(path):
        if match.start() != position:
            raise DataPathError(f"不支持的 JSONPath: {path}")
        position = match.end()
        dot, bracket = match.groups()
        token = dot if dot is not None else bracket
        if token is None:
            continue
        if token.isdigit():
            result.append(int(token))
        elif token.startswith(("'", '"')):
            result.append(token[1:-1])
        else:
            result.append(token)
    if position != len(path):
        raise DataPathError(f"不支持的 JSONPath: {path}")
    return result


def get_path(data: Any, path: str, default: Any = _MISSING) -> Any:
    values = [data]
    used_wildcard = False
    for token in _tokens(path):
        next_values: list[Any] = []
        for current in values:
            if token == "*":
                used_wildcard = True
                if isinstance(current, dict):
                    next_values.extend(current.values())
                elif isinstance(current, list):
                    next_values.extend(current)
                continue
            try:
                if isinstance(token, int) and isinstance(current, list):
                    next_values.append(current[token])
                elif isinstance(token, str) and isinstance(current, dict):
                    next_values.append(current[token])
            except (IndexError, KeyError):
                continue
        values = next_values
        if not values:
            if default is not _MISSING:
                return default
            raise DataPathError(f"路径不存在: {path}")
    if used_wildcard:
        return values
    if not values:
        if default is not _MISSING:
            return default
        raise DataPathError(f"路径不存在: {path}")
    return values[0]
