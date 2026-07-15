# AI 智能接口自动化测试平台

基于 `Python 3.11 + FastAPI + Pytest + OpenAI API + MySQL` 的接口自动化测试平台，面向测试开发 / AI 测试工程师简历项目。

项目目标不是写一个临时 Demo，而是完成一条真实测试平台链路：

接口录入 -> AI 生成测试用例 -> 自动执行接口请求 -> 响应断言 -> SQL 数据校验 -> AI 分析失败原因 -> 生成 Allure 报告。

## 技术栈

- 后端框架：FastAPI、uvicorn
- 自动化测试：pytest、requests、allure-pytest
- AI 能力：OpenAI API，默认模型 `gpt-4o`
- 数据库：MySQL、SQLAlchemy、pymysql
- 配置管理：python-dotenv、PyYAML
- 日志：loguru
- 文档：FastAPI Swagger
- 部署：Linux、Docker Compose

## 项目结构

```text
ai-api-test-platform/
├── app/
│   ├── api/                 # FastAPI 路由
│   ├── ai/                  # OpenAI 调用与 Prompt 模板
│   ├── database/            # 数据库连接与初始化
│   ├── models/              # SQLAlchemy ORM 模型
│   ├── schemas/             # Pydantic 入参出参模型
│   ├── services/            # 核心业务服务
│   └── utils/               # 配置、日志工具
├── tests/                   # pytest 测试
├── reports/                 # Allure 结果目录
├── logs/                    # 运行日志
├── config.yaml              # 默认配置
├── .env.example             # 环境变量示例
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── main.py
```

## 安装方式

```bash
cd ai-api-test-platform
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

编辑 `.env`：

```bash
OPENAI_API_KEY=你的 OpenAI Key
DB_HOST=127.0.0.1
DB_PORT=3306
DB_USER=root
DB_PASSWORD=你的数据库密码
DB_NAME=ai_test_platform

# 可选：被测系统的数据库，仅 SQL 数据校验用到，见下文
SUT_DATABASE_URL=mysql+pymysql://root:密码@127.0.0.1:3306/被测系统库名?charset=utf8mb4
```

创建 MySQL 数据库：

```sql
create database ai_test_platform default character set utf8mb4 collate utf8mb4_unicode_ci;
```

初始化表：

```bash
python -m app.database.init_db
```

## 启动方式

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

访问：

- Swagger 文档：http://127.0.0.1:8000/docs
- 健康检查：http://127.0.0.1:8000/health

## 核心接口示例

### 1. 添加接口

`POST /interfaces`

```json
{
  "name": "登录接口",
  "url": "https://example.com/api/login",
  "method": "POST",
  "headers": {
    "Content-Type": "application/json"
  },
  "body": {
    "username": "admin",
    "password": "123456"
  }
}
```

### 2. AI 生成测试用例

`POST /ai/interfaces/1/cases`

```json
{
  "input_data": {
    "username": "admin",
    "password": "123456"
  },
  "expected_status_code": 200
}
```

AI 会生成空值、边界值、超长字符串、特殊字符、非法类型、SQL 注入、XSS 等测试数据，并保存到数据库。

如果没有配置 `OPENAI_API_KEY`，系统会走本地规则兜底生成用例，方便本地演示。

### 3. 自动执行接口测试

`POST /runs`

```json
{
  "interface_id": 1,
  "case_ids": [],
  "analyze_by_ai": true
}
```

执行结果会保存到 `test_runs` 和 `test_results` 表，失败用例会调用 AI 输出风险分析。

### 4. AI 分析接口结果

`POST /ai/analyze-result`

```json
{
  "status_code": 500,
  "response": {
    "code": 500,
    "msg": "Internal Server Error"
  },
  "assertion_message": "响应码错误，期望 200，实际 500"
}
```

返回示例：

```json
{
  "analysis": "服务端异常，建议检查后端日志、数据库连接、接口依赖服务和异常堆栈。"
}
```

### 5. 生成 Allure 测试结果

`POST /reports/allure`

该接口会根据数据库中的测试用例生成 `tests/generated_api_tests.py`，然后执行：

```bash
pytest tests/generated_api_tests.py --alluredir reports/allure-results
```

本机安装 Allure 命令行后可查看报告：

```bash
allure serve reports/allure-results
```

## SQL 数据校验

测试用例支持配置 SQL 校验字段：

```json
{
  "sql_check": {
    "sql": "select username from user where username='admin'",
    "expected": {
      "username": "admin"
    }
  }
}
```

平台会在接口请求后执行 SQL，并校验数据库返回结果是否符合预期。

SQL 校验读的是**被测系统的数据库**（上例中 `user` 表属于被测的登录接口），因此需要在 `.env` 中单独配置 `SUT_DATABASE_URL`。没有配置时，SQL 校验会返回明确的未配置提示，而不会去查平台自己的库——平台库里只有 `api_interfaces`、`test_cases` 等元数据表，校验它们没有意义。

出于安全考虑，`sql_check.sql` 只接受单条 `SELECT` 语句：它来自接口入参且会直接在数据库上执行，其他语句（含多语句、注释开头的语句）会被拒绝。

## 日志

系统使用 `loguru` 记录：

- 接口请求方法、URL、参数
- 响应状态码
- 断言失败信息
- SQL 校验失败信息
- OpenAI 调用兜底提示

日志保存位置：

```text
logs/app.log
```

## Docker 启动

```bash
docker-compose up --build
```

启动后访问：

```text
http://127.0.0.1:8000/docs
```

## 简历写法参考

项目名称：AI 智能接口自动化测试平台

项目描述：

基于 FastAPI、Pytest、OpenAI API 和 MySQL 设计并实现接口自动化测试平台，支持接口管理、AI 自动生成测试用例、自动执行接口请求、响应断言、SQL 数据校验、AI 失败原因分析和 Allure 测试报告生成。

个人职责：

- 设计接口管理、测试用例、测试执行记录、测试结果等数据库模型。
- 封装 OpenAI API，实现边界值、空值、非法类型、SQL 注入、XSS 等测试用例自动生成。
- 基于 requests 实现 GET、POST、PUT、DELETE、PATCH 请求执行和响应断言。
- 基于 SQLAlchemy 实现 MySQL 数据校验能力。
- 基于 loguru 实现接口请求、响应结果、异常信息日志落盘。
- 集成 allure-pytest，支持自动生成接口测试报告。

## 后续可扩展方向

- 增加 Web 页面，支持在线录入接口和查看报告。
- 增加定时任务，定时执行回归测试。
- 增加 Jenkins / GitHub Actions CI 集成。
- 增加 token 登录态管理和环境变量切换。
- 增加接口依赖提取，例如登录接口返回 token 后自动传给后续接口。

