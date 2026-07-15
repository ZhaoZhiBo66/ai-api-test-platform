from typing import Any

import requests
from sqlalchemy.orm import Session

from app.ai.openai_client import openai_client
from app.models.interface import ApiInterface
from app.models.result import TestResult, TestRun
from app.models.testcase import TestCase
from app.services.sql_validator import sql_validator
from app.utils.config import get_settings
from app.utils.logger import logger


def run_cases(db: Session, interface_id: int | None, case_ids: list[int], analyze_by_ai: bool = True) -> TestRun:
    query = db.query(TestCase)
    if case_ids:
        query = query.filter(TestCase.id.in_(case_ids))
    elif interface_id:
        query = query.filter(TestCase.interface_id == interface_id)

    cases = query.order_by(TestCase.id.asc()).all()
    run = TestRun(interface_id=interface_id, status="running", total=len(cases))
    db.add(run)
    db.commit()
    db.refresh(run)

    passed = 0
    failed = 0
    failed_summaries: list[str] = []

    for case in cases:
        interface = db.get(ApiInterface, case.interface_id)
        result = _execute_case(interface, case, analyze_by_ai)
        result.run_id = run.id
        db.add(result)

        if result.status == "passed":
            passed += 1
        else:
            failed += 1
            failed_summaries.append(f"{case.case_name}: {result.ai_analysis or result.assertion_message}")

    run.passed = passed
    run.failed = failed
    run.status = "passed" if failed == 0 else "failed"
    run.ai_summary = "\n".join(failed_summaries[:10])
    db.commit()
    db.refresh(run)
    return run


def _execute_case(interface: ApiInterface | None, case: TestCase, analyze_by_ai: bool) -> TestResult:
    if not interface:
        return TestResult(case_id=case.id, case_name=case.case_name, status="failed", assertion_message="接口不存在")

    request_data = case.data or {}
    response_json: dict[str, Any] = {}
    status_code: int | None = None
    assertion_message = ""

    try:
        logger.info("执行接口用例: {} {} {}", interface.method, interface.url, request_data)
        response = _send_request(interface, request_data)
        status_code = response.status_code
        response_json = _parse_response(response)
        assertion_message = _assert_response(status_code, response_json, case)

        sql_ok, sql_message = sql_validator.validate(case.sql_check)
        if not sql_ok:
            assertion_message = f"{assertion_message}; {sql_message}" if assertion_message else sql_message

        status = "passed" if not assertion_message else "failed"
    except Exception as exc:
        logger.exception("接口执行失败")
        status = "failed"
        assertion_message = str(exc)

    ai_analysis = ""
    if analyze_by_ai and status == "failed":
        ai_analysis = openai_client.analyze_result(status_code or 0, response_json, assertion_message)

    logger.info("用例执行结果: case={} status={} code={} msg={}", case.case_name, status, status_code, assertion_message)
    return TestResult(
        case_id=case.id,
        case_name=case.case_name,
        status=status,
        status_code=status_code,
        request_data=request_data,
        response_data=response_json,
        assertion_message=assertion_message,
        ai_analysis=ai_analysis,
    )


def _send_request(interface: ApiInterface, data: dict[str, Any]) -> requests.Response:
    timeout = get_settings().request_timeout
    method = interface.method.upper()
    headers = interface.headers or {}
    if method == "GET":
        return requests.get(interface.url, headers=headers, params=data, timeout=timeout)
    if method == "POST":
        return requests.post(interface.url, headers=headers, json=data, timeout=timeout)
    if method == "PUT":
        return requests.put(interface.url, headers=headers, json=data, timeout=timeout)
    if method == "DELETE":
        return requests.delete(interface.url, headers=headers, json=data, timeout=timeout)
    if method == "PATCH":
        return requests.patch(interface.url, headers=headers, json=data, timeout=timeout)
    raise ValueError(f"不支持的请求方法: {method}")


def _parse_response(response: requests.Response) -> dict[str, Any]:
    try:
        data = response.json()
        return data if isinstance(data, dict) else {"data": data}
    except ValueError:
        return {"text": response.text}


def _assert_response(status_code: int, response_json: dict[str, Any], case: TestCase) -> str:
    errors: list[str] = []
    if status_code != case.expected_status_code:
        errors.append(f"响应码错误，期望 {case.expected_status_code}，实际 {status_code}")

    for key, expected_value in (case.expected_json or {}).items():
        actual_value = response_json.get(key)
        if actual_value != expected_value:
            errors.append(f"字段 {key} 校验失败，期望 {expected_value}，实际 {actual_value}")
    return "; ".join(errors)

