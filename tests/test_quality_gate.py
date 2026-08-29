from argparse import Namespace

from scripts import quality_gate


def test_gate_resolves_suite_and_waits_for_terminal_result(monkeypatch):
    responses = iter(
        [
            [{"id": 3, "name": "核心下单回归"}],
            [{"id": 4, "name": "内置订单服务", "enabled": True}],
            {"run_id": 9, "status": "queued"},
            {"id": 9, "status": "running"},
            {"id": 9, "status": "passed", "total": 5, "passed": 5, "failed": 0},
        ]
    )
    monkeypatch.setattr(quality_gate, "request_json", lambda *args, **kwargs: next(responses))
    monkeypatch.setattr(quality_gate.time, "sleep", lambda _: None)
    args = Namespace(
        base_url="http://platform", api_key="", suite_id=None, suite_name="核心下单回归",
        environment_id=None, environment_name="内置订单服务", timeout=5, poll_interval=0,
    )

    result = quality_gate.run_gate(args)
    assert result["status"] == "passed"


def test_main_returns_failed_gate_exit_code(monkeypatch):
    monkeypatch.setattr(
        quality_gate,
        "run_gate",
        lambda _: {"id": 2, "suite_id": 1, "status": "failed", "total": 5, "passed": 4, "failed": 1},
    )
    assert quality_gate.main(["--suite-id", "1"]) == 1
