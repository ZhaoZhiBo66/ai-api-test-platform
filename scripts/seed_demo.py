"""Create an idempotent login-to-payment regression suite for the bundled demo API."""

import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from sqlalchemy.orm import Session

from app.database.db import SessionLocal
from app.models.environment import TestEnvironment
from app.models.interface import ApiInterface
from app.models.suite import TestSuite, TestSuiteCase
from app.models.testcase import TestCase


ENVIRONMENT_NAME = "内置订单服务"
SUITE_NAME = "核心下单回归"


INTERFACES = [
    ("Demo - 登录", "/api/login", "POST", {}),
    ("Demo - 查询商品", "/api/products/{product_id}", "GET", {"Authorization": "Bearer ${access_token}"}),
    ("Demo - 创建订单", "/api/orders", "POST", {"Authorization": "Bearer ${access_token}"}),
    ("Demo - 支付订单", "/api/orders/{order_id}/pay", "POST", {"Authorization": "Bearer ${access_token}"}),
    ("Demo - 查询订单", "/api/orders/{order_id}", "GET", {"Authorization": "Bearer ${access_token}"}),
]


def _upsert_interface(db: Session, name: str, url: str, method: str, headers: dict) -> ApiInterface:
    item = db.query(ApiInterface).filter(ApiInterface.name == name).first()
    if item is None:
        item = ApiInterface(name=name, url=url, method=method, headers=headers, body={}, spec={})
        db.add(item)
        db.flush()
    else:
        item.url = url
        item.method = method
        item.headers = headers
    return item


def _upsert_case(db: Session, interface: ApiInterface, name: str, **values) -> TestCase:
    item = db.query(TestCase).filter(TestCase.case_name == name).first()
    defaults = {
        "interface_id": interface.id,
        "data": {},
        "expected_status_code": 200,
        "expected_json": {"code": 0},
        "sql_check": {},
        "assertions": [],
        "extractors": [],
        "dependencies": [],
        "request_config": {},
        "retry_count": 0,
        "enabled": True,
    }
    defaults.update(values)
    if item is None:
        item = TestCase(case_name=name, **defaults)
        db.add(item)
        db.flush()
    else:
        for key, value in defaults.items():
            setattr(item, key, value)
    return item


def seed(db: Session, demo_url: str) -> tuple[int, int]:
    environment = db.query(TestEnvironment).filter(TestEnvironment.name == ENVIRONMENT_NAME).first()
    if environment is None:
        environment = TestEnvironment(name=ENVIRONMENT_NAME)
        db.add(environment)
    environment.base_url = demo_url.rstrip("/")
    environment.variables = {}
    environment.headers = {}
    environment.enabled = True
    db.flush()

    interfaces = {
        name: _upsert_interface(db, name, url, method, headers)
        for name, url, method, headers in INTERFACES
    }
    login = _upsert_case(
        db,
        interfaces["Demo - 登录"],
        "登录并提取访问令牌",
        data={"username": "demo", "password": "demo123"},
        extractors=[{"name": "access_token", "source": "body", "path": "$.data.access_token"}],
        assertions=[{"source": "body", "path": "$.data.token_type", "operator": "eq", "expected": "bearer"}],
    )
    product = _upsert_case(
        db,
        interfaces["Demo - 查询商品"],
        "查询有库存商品",
        data={"product_id": 1},
        dependencies=[login.id],
        request_config={"path_parameters": ["product_id"]},
        assertions=[{"source": "body", "path": "$.data.stock", "operator": "gte", "expected": 2}],
    )
    order = _upsert_case(
        db,
        interfaces["Demo - 创建订单"],
        "创建订单并校验金额",
        data={"product_id": 1, "quantity": 2},
        expected_status_code=201,
        dependencies=[product.id],
        assertions=[{"source": "body", "path": "$.data.total", "operator": "eq", "expected": 199.8}],
        extractors=[{"name": "order_id", "source": "body", "path": "$.data.id"}],
    )
    payment = _upsert_case(
        db,
        interfaces["Demo - 支付订单"],
        "支付订单",
        data={"order_id": "${order_id}"},
        dependencies=[order.id],
        request_config={"path_parameters": ["order_id"]},
        assertions=[{"source": "body", "path": "$.data.status", "operator": "eq", "expected": "paid"}],
    )
    query = _upsert_case(
        db,
        interfaces["Demo - 查询订单"],
        "查询已支付订单",
        data={"order_id": "${order_id}"},
        dependencies=[payment.id],
        request_config={"path_parameters": ["order_id"]},
        assertions=[{"source": "body", "path": "$.data.status", "operator": "eq", "expected": "paid"}],
    )
    case_ids = [login.id, product.id, order.id, payment.id, query.id]

    suite = db.query(TestSuite).filter(TestSuite.name == SUITE_NAME).first()
    if suite is None:
        suite = TestSuite(name=SUITE_NAME)
        db.add(suite)
        db.flush()
    suite.description = "登录、查商品、创建订单、支付并查询结果的真实依赖链"
    suite.fail_fast = True
    suite.analyze_by_ai = False
    suite.enabled = True
    db.query(TestSuiteCase).filter(TestSuiteCase.suite_id == suite.id).delete()
    db.add_all(
        [
            TestSuiteCase(suite_id=suite.id, case_id=case_id, position=index)
            for index, case_id in enumerate(case_ids, start=1)
        ]
    )
    db.commit()
    return environment.id, suite.id


def main() -> None:
    demo_url = os.getenv("DEMO_SUT_URL", "http://127.0.0.1:8010")
    with SessionLocal() as db:
        environment_id, suite_id = seed(db, demo_url)
    print(f"Demo data ready: environment_id={environment_id}, suite_id={suite_id}, target={demo_url}")


if __name__ == "__main__":
    main()
