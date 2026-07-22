# AI 智能接口自动化测试平台

基于 `Python 3.12 + FastAPI + Pytest + OpenAI API + MySQL` 的接口自动化测试平台

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
python3.12 -m venv .venv
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
docker compose up --build
```

`app` 会等 MySQL 通过健康检查后再启动，首次构建 MySQL 初始化数据目录需要几十秒。

启动后访问：

```text
http://127.0.0.1:8000/docs
```

注意：容器内不会配置 `SUT_DATABASE_URL`，SQL 数据校验会返回未配置提示。需要时在 `docker-compose.yml` 的 `app.environment` 里指向被测系统的数据库。



