"""Run one regression suite through the public API and return a CI-friendly exit code."""

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


TERMINAL = {"passed", "failed", "cancelled", "interrupted"}


def request_json(
    base_url: str,
    path: str,
    *,
    method: str = "GET",
    api_key: str = "",
    payload: dict[str, Any] | None = None,
) -> Any:
    headers = {"Accept": "application/json"}
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if api_key:
        headers["X-API-Key"] = api_key
    request = Request(base_url.rstrip("/") + path, data=data, headers=headers, method=method)
    try:
        with urlopen(request, timeout=15) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code}: {body}") from exc
    except URLError as exc:
        raise RuntimeError(f"无法连接质量平台: {exc.reason}") from exc


def resolve_suite_id(base_url: str, api_key: str, suite_id: int | None, suite_name: str) -> int:
    if suite_id is not None:
        return suite_id
    suites = request_json(base_url, "/suites?enabled=true", api_key=api_key)
    for suite in suites:
        if suite["name"] == suite_name:
            return int(suite["id"])
    raise RuntimeError(f"找不到启用的回归套件: {suite_name}")


def resolve_environment_id(
    base_url: str,
    api_key: str,
    environment_id: int | None,
    environment_name: str,
) -> int | None:
    if environment_id is not None or not environment_name:
        return environment_id
    environments = request_json(base_url, "/environments", api_key=api_key)
    for environment in environments:
        if environment["name"] == environment_name and environment["enabled"]:
            return int(environment["id"])
    raise RuntimeError(f"找不到启用的测试环境: {environment_name}")


def run_gate(args: argparse.Namespace) -> dict[str, Any]:
    suite_id = resolve_suite_id(args.base_url, args.api_key, args.suite_id, args.suite_name)
    environment_id = resolve_environment_id(
        args.base_url, args.api_key, args.environment_id, args.environment_name
    )
    accepted = request_json(
        args.base_url,
        f"/suites/{suite_id}/runs/async",
        method="POST",
        api_key=args.api_key,
        payload={
            "environment_id": environment_id,
            "variables": {},
            "analyze_by_ai": False,
        },
    )
    run_id = int(accepted["run_id"])
    deadline = time.monotonic() + args.timeout
    while time.monotonic() < deadline:
        run = request_json(args.base_url, f"/runs/{run_id}", api_key=args.api_key)
        if run["status"] in TERMINAL:
            return run
        time.sleep(args.poll_interval)
    raise RuntimeError(f"回归任务 #{run_id} 在 {args.timeout} 秒内未结束")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Execute a regression suite as a CI quality gate")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    selector = parser.add_mutually_exclusive_group()
    selector.add_argument("--suite-id", type=int)
    selector.add_argument("--suite-name", default="核心下单回归")
    environment = parser.add_mutually_exclusive_group()
    environment.add_argument("--environment-id", type=int)
    environment.add_argument("--environment-name", default="内置订单服务")
    parser.add_argument("--api-key", default="")
    parser.add_argument("--timeout", type=float, default=60)
    parser.add_argument("--poll-interval", type=float, default=0.5)
    parser.add_argument("--output", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = run_gate(args)
    except RuntimeError as exc:
        print(f"QUALITY GATE ERROR: {exc}", file=sys.stderr)
        return 2
    summary = {
        "run_id": result["id"],
        "suite_id": result.get("suite_id"),
        "status": result["status"],
        "total": result["total"],
        "passed": result["passed"],
        "failed": result["failed"],
    }
    rendered = json.dumps(summary, ensure_ascii=False, indent=2)
    print(rendered)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    if result["status"] == "passed" and result["failed"] == 0:
        print("QUALITY GATE PASSED")
        return 0
    print("QUALITY GATE FAILED", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
