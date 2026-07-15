import ast
import subprocess
import sys

import pytest

from app.models.interface import ApiInterface
from app.models.testcase import TestCase as CaseModel
from app.services import report_service
from app.utils.config import get_settings


@pytest.fixture
def root(tmp_path, monkeypatch):
    """Redirect the service at a scratch tree.

    generate_pytest_file writes to a fixed path inside the repo, so without
    this a test run would clobber the developer's own generated_api_tests.py.
    """
    (tmp_path / "tests").mkdir()
    monkeypatch.setattr(get_settings(), "root_dir", tmp_path)
    return tmp_path


@pytest.fixture
def interface(db_session) -> ApiInterface:
    item = ApiInterface(
        name="登录",
        url="https://api.example.com/login",
        method="POST",
        headers={"X-Token": "abc"},
        body={},
    )
    db_session.add(item)
    db_session.commit()
    return item


def make_case(db_session, interface, **overrides) -> CaseModel:
    fields = {
        "interface_id": interface.id,
        "case_name": "用例",
        "data": {"username": "admin"},
        "expected_status_code": 200,
        "expected_json": {},
        "sql_check": {},
    }
    fields.update(overrides)
    case = CaseModel(**fields)
    db_session.add(case)
    db_session.commit()
    return case


def parse_cases(source: str) -> list[dict]:
    """Pull the CASES literal back out of the generated module."""
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, ast.Assign) and node.targets[0].id == "CASES":
            return ast.literal_eval(node.value)
    raise AssertionError("no CASES assignment in the generated file")


# --- generate_pytest_file ---------------------------------------------------


def test_writes_to_the_tests_directory(root, db_session, interface):
    make_case(db_session, interface)

    path = report_service.generate_pytest_file(db_session)

    assert path == root / "tests" / "generated_api_tests.py"
    assert path.exists()


def test_generated_file_is_valid_python(root, db_session, interface):
    make_case(db_session, interface, case_name="带'单引号'和\"双引号\"的用例名")

    source = report_service.generate_pytest_file(db_session).read_text(encoding="utf-8")

    compile(source, "generated_api_tests.py", "exec")


def test_case_carries_the_interface_and_the_case_fields(root, db_session, interface):
    make_case(db_session, interface, case_name="登录成功", expected_json={"code": 0})

    cases = parse_cases(report_service.generate_pytest_file(db_session).read_text(encoding="utf-8"))

    assert cases == [
        {
            "case_name": "登录成功",
            "url": "https://api.example.com/login",
            "method": "POST",
            "headers": {"X-Token": "abc"},
            "data": {"username": "admin"},
            "expected_status_code": 200,
            "expected_json": {"code": 0},
        }
    ]


def test_cases_are_written_oldest_first(root, db_session, interface):
    make_case(db_session, interface, case_name="第一个")
    make_case(db_session, interface, case_name="第二个")

    cases = parse_cases(report_service.generate_pytest_file(db_session).read_text(encoding="utf-8"))

    assert [c["case_name"] for c in cases] == ["第一个", "第二个"]


def test_case_with_a_missing_interface_is_skipped(root, db_session, interface):
    make_case(db_session, interface, case_name="留下的")
    make_case(db_session, interface, case_name="丢弃的", interface_id=9999)

    cases = parse_cases(report_service.generate_pytest_file(db_session).read_text(encoding="utf-8"))

    assert [c["case_name"] for c in cases] == ["留下的"]


def test_no_cases_still_produces_a_valid_module(root, db_session):
    source = report_service.generate_pytest_file(db_session).read_text(encoding="utf-8")

    compile(source, "generated_api_tests.py", "exec")
    assert parse_cases(source) == []


def test_non_ascii_case_names_survive_the_round_trip(root, db_session, interface):
    make_case(db_session, interface, case_name="用户名为空 <script>alert(1)</script>")

    cases = parse_cases(report_service.generate_pytest_file(db_session).read_text(encoding="utf-8"))

    assert cases[0]["case_name"] == "用户名为空 <script>alert(1)</script>"


def test_generated_file_is_collectible_by_pytest(root, db_session, interface):
    """The file only matters if pytest can actually load and parametrize it.

    An ASCII case name on purpose: pytest escapes non-ASCII ids to \\uXXXX in
    its terminal output. The round trip for real names is covered above,
    through the CASES literal rather than through pytest's reporting.
    """
    make_case(db_session, interface, case_name="collectible-case")
    path = report_service.generate_pytest_file(db_session)

    result = subprocess.run(
        [sys.executable, "-m", "pytest", str(path), "--collect-only", "-q", "-p", "no:cacheprovider"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "test_generated_api_case[collectible-case]" in result.stdout
    assert "1 test collected" in result.stdout


# --- run_allure -------------------------------------------------------------


def stub_run(monkeypatch, returncode: int = 0, stdout: str = "1 passed", stderr: str = ""):
    seen = {}

    def fake_run(command, cwd=None, capture_output=None, text=None, check=None):
        seen.update(command=command, cwd=cwd, check=check)
        return subprocess.CompletedProcess(command, returncode, stdout, stderr)

    monkeypatch.setattr(report_service.subprocess, "run", fake_run)
    return seen


def test_run_allure_invokes_pytest_on_the_generated_file(root, db_session, interface, monkeypatch):
    make_case(db_session, interface)
    seen = stub_run(monkeypatch)

    report = report_service.run_allure(db_session)

    assert seen["command"] == [
        sys.executable,
        "-m",
        "pytest",
        str(root / "tests" / "generated_api_tests.py"),
        "--alluredir",
        str(root / "reports" / "allure-results"),
    ]
    assert seen["cwd"] == root
    assert report["allure_results"] == str(root / "reports" / "allure-results")


def test_run_allure_creates_the_results_directory(root, db_session, monkeypatch):
    stub_run(monkeypatch)

    report_service.run_allure(db_session)

    assert (root / "reports" / "allure-results").is_dir()


def test_run_allure_reports_a_failing_run_without_raising(root, db_session, monkeypatch):
    stub_run(monkeypatch, returncode=1, stdout="1 failed", stderr="boom")

    report = report_service.run_allure(db_session)

    assert report["return_code"] == 1
    assert report["stdout"] == "1 failed"
    assert report["stderr"] == "boom"


def test_run_allure_does_not_raise_on_a_nonzero_exit(root, db_session, monkeypatch):
    seen = stub_run(monkeypatch, returncode=1)

    report_service.run_allure(db_session)

    # check=False keeps a failing test run a report, not an exception.
    assert seen["check"] is False


def test_report_endpoint_returns_the_run_summary(client, db_session, root, monkeypatch):
    stub_run(monkeypatch)

    response = client.post("/reports/allure")

    assert response.status_code == 200
    assert response.json()["return_code"] == 0
