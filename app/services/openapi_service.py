from __future__ import annotations

from copy import deepcopy
from typing import Any
from urllib.parse import urljoin

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.interface import ApiInterface
from app.models.testcase import TestCase
from app.schemas.openapi_schema import OpenAPIImportRequest


HTTP_METHODS = {"get", "post", "put", "delete", "patch"}


def _resolve_ref(document: dict[str, Any], value: Any) -> Any:
    if not isinstance(value, dict) or "$ref" not in value:
        return value
    ref = value["$ref"]
    if not ref.startswith("#/" ):
        raise HTTPException(status_code=422, detail=f"暂不支持外部 OpenAPI 引用: {ref}")
    current: Any = document
    for part in ref[2:].split("/"):
        current = current[part.replace("~1", "/").replace("~0", "~")]
    return current


def _schema_example(document: dict[str, Any], schema: dict[str, Any]) -> Any:
    schema = _resolve_ref(document, schema) or {}
    if "example" in schema:
        return deepcopy(schema["example"])
    if "default" in schema:
        return deepcopy(schema["default"])
    if schema.get("enum"):
        return deepcopy(schema["enum"][0])
    schema_type = schema.get("type")
    if schema_type == "object" or "properties" in schema:
        return {
            name: _schema_example(document, child)
            for name, child in schema.get("properties", {}).items()
            if name in schema.get("required", []) or "example" in child or "default" in child
        }
    if schema_type == "array":
        return [_schema_example(document, schema.get("items", {}))]
    if schema_type == "integer":
        return schema.get("minimum", 1)
    if schema_type == "number":
        return schema.get("minimum", 1.0)
    if schema_type == "boolean":
        return True
    return "string"


def _operation_data(document: dict[str, Any], path_item: dict[str, Any], operation: dict[str, Any]) -> tuple[dict, dict]:
    data: dict[str, Any] = {}
    headers: dict[str, Any] = {}
    parameters = [*path_item.get("parameters", []), *operation.get("parameters", [])]
    for raw_parameter in parameters:
        parameter = _resolve_ref(document, raw_parameter)
        name = parameter.get("name")
        if not name:
            continue
        value = parameter.get("example", _schema_example(document, parameter.get("schema", {})))
        if parameter.get("in") == "header":
            headers[name] = value
        elif parameter.get("in") in {"query", "path"}:
            data[name] = value

    content = operation.get("requestBody", {}).get("content", {})
    media = content.get("application/json") or content.get("application/x-www-form-urlencoded") or {}
    if media:
        example = media.get("example")
        body = deepcopy(example) if example is not None else _schema_example(document, media.get("schema", {}))
        if isinstance(body, dict):
            data.update(body)
    return data, headers


def _request_config(path_item: dict[str, Any], operation: dict[str, Any]) -> dict[str, Any]:
    parameters = [*path_item.get("parameters", []), *operation.get("parameters", [])]
    path_parameters = [
        item.get("name")
        for item in parameters
        if isinstance(item, dict) and item.get("in") == "path" and item.get("name")
    ]
    content = operation.get("requestBody", {}).get("content", {})
    body_mode = "form" if "application/x-www-form-urlencoded" in content else "json"
    return {"path_parameters": path_parameters, "body_mode": body_mode}


def _success_status(operation: dict[str, Any]) -> int:
    for value in operation.get("responses", {}):
        if str(value).isdigit() and 200 <= int(value) < 300:
            return int(value)
    return 200


def _request_schema(document: dict[str, Any], operation: dict[str, Any]) -> dict[str, Any]:
    content = operation.get("requestBody", {}).get("content", {})
    media = content.get("application/json") or content.get("application/x-www-form-urlencoded") or {}
    return _resolve_ref(document, media.get("schema", {})) or {}


def _schema_cases(
    document: dict[str, Any],
    interface: ApiInterface,
    operation: dict[str, Any],
    base_data: dict[str, Any],
    negative_status: int,
    request_config: dict[str, Any],
) -> list[TestCase]:
    success_status = _success_status(operation)
    cases = [
        TestCase(
            interface_id=interface.id,
            case_name="OpenAPI基础有效用例",
            data=base_data,
            expected_status_code=success_status,
            request_config=request_config,
        )
    ]
    schema = _request_schema(document, operation)
    properties = schema.get("properties", {})
    for field in schema.get("required", []):
        missing = deepcopy(base_data)
        missing.pop(field, None)
        cases.append(
            TestCase(
                interface_id=interface.id,
                case_name=f"必填字段 {field} 缺失",
                data=missing,
                expected_status_code=negative_status,
                request_config=request_config,
            )
        )
    for field, raw_field_schema in properties.items():
        field_schema = _resolve_ref(document, raw_field_schema) or {}
        if field_schema.get("type") == "string" and "maxLength" in field_schema:
            too_long = deepcopy(base_data)
            too_long[field] = "a" * (int(field_schema["maxLength"]) + 1)
            cases.append(
                TestCase(
                    interface_id=interface.id,
                    case_name=f"字段 {field} 超过最大长度",
                    data=too_long,
                    expected_status_code=negative_status,
                    request_config=request_config,
                )
            )
        wrong_type = deepcopy(base_data)
        wrong_type[field] = {"invalid": True} if field_schema.get("type") != "object" else "invalid-object"
        cases.append(
            TestCase(
                interface_id=interface.id,
                case_name=f"字段 {field} 类型错误",
                data=wrong_type,
                expected_status_code=negative_status,
                request_config=request_config,
            )
        )
    return cases


def import_openapi(db: Session, payload: OpenAPIImportRequest) -> dict[str, Any]:
    document = payload.document
    if "openapi" not in document and "swagger" not in document:
        raise HTTPException(status_code=422, detail="不是有效的 OpenAPI/Swagger 文档")
    paths = document.get("paths")
    if not isinstance(paths, dict) or not paths:
        raise HTTPException(status_code=422, detail="OpenAPI 文档没有 paths")

    server_url = payload.base_url
    if not server_url:
        servers = document.get("servers") or []
        server_url = servers[0].get("url") if servers else None
    if not payload.store_relative_urls and not server_url:
        raise HTTPException(status_code=422, detail="存储绝对地址时必须提供 base_url 或 servers[0].url")

    created = updated = skipped = generated = 0
    interface_ids: list[int] = []
    for path, path_item in paths.items():
        if not isinstance(path_item, dict):
            continue
        for method, operation in path_item.items():
            if method.lower() not in HTTP_METHODS or not isinstance(operation, dict):
                continue
            url = path if payload.store_relative_urls else urljoin(server_url.rstrip("/") + "/", path.lstrip("/"))
            existing = (
                db.query(ApiInterface)
                .filter(ApiInterface.url == url, ApiInterface.method == method.upper())
                .one_or_none()
            )
            data, headers = _operation_data(document, path_item, operation)
            request_config = _request_config(path_item, operation)
            spec = {
                "path": path,
                "operation": operation,
                "server_url": server_url or "",
                "request_config": request_config,
            }
            name = operation.get("summary") or operation.get("operationId") or f"{method.upper()} {path}"
            if existing and not payload.overwrite_existing:
                skipped += 1
                interface_ids.append(existing.id)
                continue
            if existing:
                existing.name = name[:100]
                existing.headers = headers
                existing.body = data
                existing.spec = spec
                interface = existing
                updated += 1
            else:
                interface = ApiInterface(
                    name=name[:100],
                    url=url,
                    method=method.upper(),
                    headers=headers,
                    body=data,
                    spec=spec,
                )
                db.add(interface)
                db.flush()
                created += 1
            interface_ids.append(interface.id)
            if payload.generate_schema_cases:
                new_cases = _schema_cases(
                    document,
                    interface,
                    operation,
                    data,
                    payload.default_negative_status_code,
                    request_config,
                )
                db.add_all(new_cases)
                generated += len(new_cases)
    db.commit()
    return {
        "created_interfaces": created,
        "updated_interfaces": updated,
        "skipped_interfaces": skipped,
        "generated_cases": generated,
        "interface_ids": interface_ids,
    }
