# 接口回归质量门禁平台

基于 `Python 3.12 + FastAPI + SQLAlchemy + OpenAPI + MySQL/SQLite` 的接口回归平台。项目重点不是替代 API 调试工具，而是把真实跨接口业务链沉淀为可重复执行、可查询、可接入 CI 的质量门禁。

核心链路：

```text
OpenAPI/接口录入
  → 测试用例与依赖编排
  → 回归套件
  → 异步执行与确定性断言
  → 历史趋势/Allure结果
  → CI通过或阻断
```

仓库内置一个独立订单服务，提供登录、商品、下单、支付和订单查询接口。首次启动会自动创建对应环境、5 条依赖用例和“核心下单回归”套件，因此无需寻找外部被测系统即可验证完整链路。

## 核心能力

- 回归套件：按业务场景组织跨接口用例，保存失败快速停止和 AI 辅助分析策略。
- 依赖与变量：检测循环依赖，按拓扑顺序执行，通过 JSONPath/响应头提取 Token、订单号等变量。
- 确定性断言：支持状态码、JSONPath、响应头、耗时、正则、类型、JSON Schema 和只读 SQL 校验。
- 契约导入：解析 OpenAPI 3/Swagger 文档并生成基础 Schema 用例。
- 异步执行：任务排队、取消、结果持久化及进程重启后的中断状态修正。
- CI 质量门禁：命令行提交套件、轮询结果，以 `0/1/2` 分别表示通过、测试失败和基础设施错误。
- 安全边界：分角色 API Key、SSRF 防护、敏感字段脱敏、环境密钥加密、SQL 只读限制和审计日志。
- AI 辅助：模型只生成候选用例和失败排查建议；最终通过/失败始终由确定性断言决定。

## 一键本地演示

### 1. 安装

```powershell
python -m venv .venv-codex
.\.venv-codex\Scripts\Activate.ps1
pip install -r requirements-dev.txt
Copy-Item .env.example .env
```

本地默认使用项目根目录的 SQLite，不需要先安装 MySQL。

### 2. 同时启动平台和被测订单服务

```powershell
python scripts/run_demo.py
```

也可以双击 `start.cmd`。

- 回归工作台：http://127.0.0.1:8000/workbench
- 平台 API 文档：http://127.0.0.1:8000/docs
- 被测订单服务：http://127.0.0.1:8010/docs

启动脚本会自动执行 Alembic 迁移和幂等演示数据初始化。

### 3. 执行 CI 风格质量门禁

保持两个服务运行，在另一个终端执行：

```powershell
python scripts/quality_gate.py --suite-name "核心下单回归" --output reports/quality-gate.json
```

通过时退出码为 `0`；任何确定性断言失败时退出码为 `1`；连接失败、超时或配置错误时退出码为 `2`。

### 4. 演示发现缺陷

停止服务后设置受控缺陷开关，再重新启动：

```powershell
$env:DEMO_BUG_MODE="wrong_total"
python scripts/run_demo.py
```

此时订单接口会把 `199.8` 错算为 `200.8`，质量门禁将在“创建订单并校验金额”用例处失败。该开关只存在于内置演示服务，用于稳定复现缺陷发现过程。

## Docker Compose

在 `.env` 中设置以下值：

```dotenv
MYSQL_ROOT_PASSWORD=独立的root密码
DB_USER=ai_test_app
DB_PASSWORD=应用账号密码
DB_NAME=ai_test_platform
PLATFORM_API_KEY=高强度随机密钥
PLATFORM_ENCRYPTION_KEY=另一条高强度随机值
```

启动：

```bash
docker compose up --build
```

Compose 会同时启动 MySQL、平台和内置订单服务，并在平台启动前等待依赖健康检查通过。

## 回归套件 API

创建套件：

```http
POST /suites
Content-Type: application/json

{
  "name": "核心下单回归",
  "description": "登录、下单、支付与查询",
  "case_ids": [1, 2, 3, 4, 5],
  "fail_fast": true,
  "analyze_by_ai": false
}
```

异步执行：

```http
POST /suites/1/runs/async
Content-Type: application/json

{
  "environment_id": 1,
  "variables": {}
}
```

查询最近趋势：

```http
GET /suites/1/trends?limit=20
```

## 环境、依赖和断言

- 环境保存 `base_url`、公共请求头、普通变量和只写加密 secrets。
- URL、请求头和请求体支持 `${token}`、`${timestamp}`、`${uuid}` 等运行时变量。
- `dependencies` 声明前置用例；执行器检测循环依赖并补齐未显式选择的前置用例。
- `extractors` 从响应 JSON、响应头或状态码提取变量。
- `assertions` 支持 `eq/ne/contains/regex/type/gt/gte/lt/lte/json_schema` 等操作符。
- SQL 校验只接受单条 `SELECT`，限制返回行数，可配置表白名单；必须使用被测库只读账号。

## AI 使用边界

AI 不是项目的判定核心：

1. 模型根据接口契约和正常输入生成候选用例。
2. 返回内容必须经过 JSON 解析和 Pydantic 结构校验。
3. 缺少密钥、调用失败或输出非法时切换到本地确定性规则。
4. 测试是否通过仅由断言和 SQL 校验决定。
5. 发给模型的响应和断言信息会先进行敏感字段脱敏和长度限制。

不配置 `OPENAI_API_KEY` 不影响回归套件、质量门禁和报告链路。

## 测试与质量

```powershell
pytest tests -q --cov=app --cov-report=term-missing --cov-fail-under=80
```

当前测试覆盖接口/用例/环境/套件 CRUD、依赖执行、变量传递、断言引擎、OpenAPI 导入、异步任务、报告隔离、SQL 安全、SSRF、鉴权、脱敏、内置订单服务和质量门禁脚本。GitHub Actions 同时验证：

当前本地验证结果为 `171 passed`，应用代码覆盖率 `86.93%`。

- 单元与接口测试及 80% 覆盖率门禁；
- MySQL 上的完整 Alembic 迁移；
- 内置订单服务的端到端回归门禁。

## 目录结构

```text
app/                 平台 API、模型、服务和 Web 工作台
demo_sut/            可独立运行的订单被测服务
migrations/          Alembic 数据库迁移
scripts/
  bootstrap_database.py
  seed_demo.py       幂等初始化演示业务链
  run_demo.py        同时管理两个本地服务
  quality_gate.py    CI 质量门禁客户端
tests/               自动化测试
performance/         JMeter 基线脚本和结果记录模板
```

## 已知边界

- 当前异步执行器是单进程受限线程池，适合单实例演示；多实例需要独立任务队列。
- 套件趋势目前按执行任务聚合，尚未实现版本基线、Flaky 自动识别和通知集成。
- SSRF 应用层校验不能替代生产环境的网络出口控制。
- 本地性能脚本只提供可复现实验入口，未把练习参数包装成生产 SLA。
