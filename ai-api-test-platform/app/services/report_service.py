import subprocess
from pathlib import Path

from sqlalchemy.orm import Session

from app.models.interface import ApiInterface
from app.models.testcase import TestCase
from app.utils.config import get_settings


def generate_pytest_file(db: Session) -> Path:
    settings = get_settings()
    test_file = settings.root_dir / "tests" / "generated_api_tests.py"
    cases = db.query(TestCase).order_by(TestCase.id.asc()).all()

    lines = [
        "import requests",
        "import allure",
        "import pytest",
        "",
        "CASES = [",
    ]
    for case in cases:
        interface = db.get(ApiInterface, case.interface_id)
        if not interface:
            continue
        lines.append(
            repr(
                {
                    "case_name": case.case_name,
                    "url": interface.url,
                    "method": interface.method,
                    "headers": interface.headers or {},
                    "data": case.data or {},
                    "expected_status_code": case.expected_status_code,
                    "expected_json": case.expected_json or {},
                }
            )
            + ","
        )
    lines.extend(
        [
            "]",
            "",
            "@allure.feature('AI接口自动化测试')",
            "@pytest.mark.parametrize('case', CASES, ids=[item['case_name'] for item in CASES])",
            "def test_generated_api_case(case):",
            "    with allure.step(case['case_name']):",
            "        method = case['method'].upper()",
            "        if method == 'GET':",
            "            response = requests.get(case['url'], headers=case['headers'], params=case['data'], timeout=10)",
            "        else:",
            "            response = requests.request(method, case['url'], headers=case['headers'], json=case['data'], timeout=10)",
            "        assert response.status_code == case['expected_status_code']",
            "        try:",
            "            body = response.json()",
            "        except ValueError:",
            "            body = {}",
            "        for key, expected in case['expected_json'].items():",
            "            assert body.get(key) == expected",
        ]
    )
    test_file.write_text("\n".join(lines), encoding="utf-8")
    return test_file


def run_allure(db: Session) -> dict:
    settings = get_settings()
    test_file = generate_pytest_file(db)
    allure_dir = settings.root_dir / "reports" / "allure-results"
    allure_dir.mkdir(parents=True, exist_ok=True)
    command = ["pytest", str(test_file), "--alluredir", str(allure_dir)]
    result = subprocess.run(command, cwd=settings.root_dir, capture_output=True, text=True, check=False)
    return {
        "command": " ".join(command),
        "return_code": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "allure_results": str(allure_dir),
    }
