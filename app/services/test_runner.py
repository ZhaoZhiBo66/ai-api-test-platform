from time import perf_counter
from types import SimpleNamespace
from typing import Any
from urllib.parse import quote

import requests
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.ai.openai_client import openai_client
from app.models.environment import TestEnvironment as EnvironmentModel
from app.models.interface import ApiInterface
from app.models.result import TestResult as ResultModel
from app.models.result import TestRun as RunModel
from app.models.testcase import TestCase as CaseModel
from app.services.assertion_service import evaluate_assertions
from app.services.environment_service import environment_secrets
from app.services.sql_validator import sql_validator
from app.services.target_validator import validate_target_url
from app.services.variable_service import (
    build_runtime_variables,
    extract_variables,
    render_value,
    resolve_url,
)
from app.utils.config import get_settings
from app.utils.logger import logger
from app.utils.redaction import redact
from app.utils.time_utils import utc_now


def _resolve_dependencies(db: Session, selected: list[CaseModel]) -> list[CaseModel]:
    by_id = {case.id: case for case in selected}
    visiting: set[int] = set()
    visited: set[int] = set()
    ordered: list[CaseModel] = []

    def visit(case: CaseModel) -> None:
        if case.id in visited:
            return
        if case.id in visiting:
            raise HTTPException(status_code=422, detail=f"检测到循环用例依赖，涉及 case_id={case.id}")
        visiting.add(case.id)
        for dependency_id in case.dependencies or []:
            dependency = by_id.get(dependency_id) or db.get(CaseModel, dependency_id)
            if dependency is None:
                raise HTTPException(status_code=404, detail=f"依赖用例不存在: {dependency_id}")
            if not dependency.enabled:
                raise HTTPException(status_code=422, detail=f"依赖用例已禁用: {dependency_id}")
            by_id[dependency.id] = dependency
            visit(dependency)
        visiting.remove(case.id)
        visited.add(case.id)
        ordered.append(case)

    for item in selected:
        visit(item)
    return ordered


def select_cases(db: Session, interface_id: int | None, case_ids: list[int]) -> list[CaseModel]:
    if interface_id is None and not case_ids:
        raise HTTPException(status_code=422, detail="必须指定 interface_id 或 case_ids，禁止隐式执行全部用例")

    query = db.query(CaseModel)
    if case_ids:
        query = query.filter(CaseModel.id.in_(case_ids))
    elif interface_id is not None:
        if db.get(ApiInterface, interface_id) is None:
            raise HTTPException(status_code=404, detail="接口不存在")
        query = query.filter(CaseModel.interface_id == interface_id)

    cases = query.filter(CaseModel.enabled.is_(True)).order_by(CaseModel.id.asc()).all()
    if case_ids:
        found_ids = {case.id for case in cases}
        missing_ids = sorted(set(case_ids) - found_ids)
        if missing_ids:
            raise HTTPException(status_code=404, detail=f"测试用例不存在或已禁用: {missing_ids}")
        if interface_id is not None and any(case.interface_id != interface_id for case in cases):
            raise HTTPException(status_code=422, detail="case_ids 中包含不属于指定接口的用例")
    if not cases:
        raise HTTPException(status_code=404, detail="没有可执行的测试用例")
    return _resolve_dependencies(db, cases)


def run_cases(
    db: Session,
    interface_id: int | None,
    case_ids: list[int],
    analyze_by_ai: bool = True,
    environment_id: int | None = None,
    variables: dict[str, Any] | None = None,
    fail_fast: bool = False,
    existing_run: RunModel | None = None,
    suite_id: int | None = None,
) -> RunModel:
    cases = select_cases(db, interface_id, case_ids)
    environment = None
    if environment_id is not None:
        environment = db.get(EnvironmentModel, environment_id)
        if environment is None:
            raise HTTPException(status_code=404, detail="测试环境不存在")
        if not environment.enabled:
            raise HTTPException(status_code=422, detail="测试环境已禁用")
    environment_values = {
        **(environment.variables if environment else {}),
        **environment_secrets(environment),
    }
    runtime_variables = build_runtime_variables(environment_values, variables)

    run = existing_run or RunModel(
        interface_id=interface_id,
        suite_id=suite_id,
        environment_id=environment_id,
    )
    run.status = "running"
    run.total = len(cases)
    run.variables = redact(runtime_variables)
    run.started_at = utc_now()
    run.finished_at = None
    run.cancel_requested = False
    if existing_run is None:
        db.add(run)
    db.commit()
    db.refresh(run)

    passed = 0
    failed = 0
    failed_summaries: list[str] = []

    for case in cases:
        db.refresh(run)
        if run.cancel_requested:
            run.status = "cancelled"
            break
        interface = db.get(ApiInterface, case.interface_id)
        result = _execute_case(
            interface,
            case,
            analyze_by_ai,
            variables=runtime_variables,
            environment=environment,
        )
        result.run_id = run.id
        db.add(result)
        runtime_variables.update(getattr(result, "_runtime_extracted_variables", result.extracted_variables or {}))

        if result.status == "passed":
            passed += 1
        else:
            failed += 1
            failed_summaries.append(f"{case.case_name}: {result.ai_analysis or result.assertion_message}")
            if fail_fast:
                break

    run.passed = passed
    run.failed = failed
    run.total = passed + failed
    if run.status != "cancelled":
        run.status = "passed" if failed == 0 else "failed"
    run.ai_summary = "\n".join(failed_summaries[:10])
    run.variables = redact(runtime_variables)
    run.finished_at = utc_now()
    db.commit()
    db.refresh(run)
    return run


def _execute_case(
    interface: ApiInterface | None,
    case: CaseModel,
    analyze_by_ai: bool,
    *,
    variables: dict[str, Any] | None = None,
    environment: EnvironmentModel | None = None,
) -> ResultModel:
    if not interface:
        return ResultModel(case_id=case.id, case_name=case.case_name, status="failed", assertion_message="接口不存在")

    runtime_variables = variables if variables is not None else build_runtime_variables({}, {})
    request_data = render_value(case.data or {}, runtime_variables)
    response_json: dict[str, Any] = {}
    response_headers: dict[str, Any] = {}
    status_code: int | None = None
    duration_ms: int | None = None
    assertion_message = ""
    extracted: dict[str, Any] = {}
    attempt = 1

    for attempt in range(1, (case.retry_count or 0) + 2):
        try:
            rendered_url = render_value(interface.url, runtime_variables)
            outbound_data = dict(request_data)
            for parameter in (case.request_config or {}).get("path_parameters", []):
                if parameter not in outbound_data:
                    raise ValueError(f"路径参数未提供: {parameter}")
                rendered_url = rendered_url.replace(
                    "{" + parameter + "}", quote(str(outbound_data.pop(parameter)), safe="")
                )
            url = resolve_url(rendered_url, environment.base_url if environment else "")
            headers = {
                **render_value(environment.headers if environment else {}, runtime_variables),
                **render_value(interface.headers or {}, runtime_variables),
            }
            runtime_interface = SimpleNamespace(
                method=interface.method,
                url=url,
                headers=headers,
                request_config=case.request_config or {},
            )
            logger.info("执行接口用例: {} {} {}", interface.method, url, redact(outbound_data))
            started = perf_counter()
            response = _send_request(runtime_interface, outbound_data)
            duration_ms = round((perf_counter() - started) * 1000)
            status_code = response.status_code
            response_headers = dict(getattr(response, "headers", {}) or {})
            response_json = _parse_response(response)
            assertion_message = _assert_response(
                status_code,
                response_json,
                case,
                response_headers=response_headers,
                duration_ms=duration_ms,
            )

            sql_ok, sql_message = sql_validator.validate(
                render_value(case.sql_check or {}, runtime_variables)
            )
            if not sql_ok:
                assertion_message = f"{assertion_message}; {sql_message}" if assertion_message else sql_message

            if not assertion_message:
                extracted = extract_variables(
                    case.extractors or [],
                    body=response_json,
                    headers=response_headers,
                    status_code=status_code,
                )
            status = "passed" if not assertion_message else "failed"
        except Exception as exc:
            logger.exception("接口执行失败")
            status = "failed"
            assertion_message = str(exc)
        if status == "passed" or attempt > (case.retry_count or 0):
            break
        logger.warning("用例失败，准备重试: case={} attempt={}", case.case_name, attempt + 1)

    ai_analysis = ""
    if analyze_by_ai and status == "failed":
        ai_analysis = openai_client.analyze_result(status_code or 0, response_json, assertion_message)

    logger.info("用例执行结果: case={} status={} code={} msg={}", case.case_name, status, status_code, assertion_message)
    result = ResultModel(
        case_id=case.id,
        case_name=case.case_name,
        status=status,
        status_code=status_code,
        request_data=redact(request_data),
        response_data=redact(response_json),
        response_headers=redact(response_headers),
        duration_ms=duration_ms,
        extracted_variables=redact(extracted),
        attempt=attempt,
        assertion_message=assertion_message,
        ai_analysis=ai_analysis,
    )
    # Keep secrets available only for the current in-memory execution chain.
    # The mapped field is redacted before persistence.
    result._runtime_extracted_variables = extracted
    return result


def _send_request(interface: ApiInterface, data: dict[str, Any]) -> requests.Response:
    timeout = get_settings().request_timeout
    method = interface.method.upper()
    headers = interface.headers or {}
    request_config = getattr(interface, "request_config", {}) or {}
    body_mode = request_config.get("body_mode", "json")
    validate_target_url(interface.url)
    if method == "GET":
        return requests.get(interface.url, headers=headers, params=data, timeout=timeout, allow_redirects=False)
    if method == "POST":
        return _send_body_request(requests.post, interface.url, headers, data, timeout, body_mode)
    if method == "PUT":
        return _send_body_request(requests.put, interface.url, headers, data, timeout, body_mode)
    if method == "DELETE":
        return _send_body_request(requests.delete, interface.url, headers, data, timeout, body_mode)
    if method == "PATCH":
        return _send_body_request(requests.patch, interface.url, headers, data, timeout, body_mode)
    raise ValueError(f"不支持的请求方法: {method}")


def _send_body_request(sender, url: str, headers: dict, data: dict, timeout: int, body_mode: str):
    common = {"headers": headers, "timeout": timeout, "allow_redirects": False}
    if body_mode == "json":
        return sender(url, json=data, **common)
    if body_mode in {"form", "x-www-form-urlencoded"}:
        return sender(url, data=data, **common)
    raise ValueError(f"不支持的 body_mode: {body_mode}")


def _parse_response(response: requests.Response) -> dict[str, Any]:
    try:
        data = response.json()
        return data if isinstance(data, dict) else {"data": data}
    except ValueError:
        return {"text": response.text}


def _assert_response(
    status_code: int,
    response_json: dict[str, Any],
    case: CaseModel,
    *,
    response_headers: dict[str, Any] | None = None,
    duration_ms: int = 0,
) -> str:
    errors: list[str] = []
    if status_code != case.expected_status_code:
        errors.append(f"响应码错误，期望 {case.expected_status_code}，实际 {status_code}")

    for key, expected_value in (case.expected_json or {}).items():
        actual_value = response_json.get(key)
        if actual_value != expected_value:
            errors.append(f"字段 {key} 校验失败，期望 {expected_value}，实际 {actual_value}")
    errors.extend(
        evaluate_assertions(
            case.assertions or [],
            status_code=status_code,
            body=response_json,
            headers=response_headers or {},
            duration_ms=duration_ms,
        )
    )
    return "; ".join(errors)

