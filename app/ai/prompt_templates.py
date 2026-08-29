import json
from typing import Any


def build_case_generation_prompt(
    input_data: dict[str, Any],
    expected_status_code: int | None = 200,
    interface_context: dict[str, Any] | None = None,
) -> str:
    expected_rule = (
        f"每个用例的 expected_status_code 统一填 {expected_status_code}。"
        if expected_status_code is not None
        else "根据接口契约判断 expected_status_code：正常用例使用2xx，非法输入使用契约中对应的4xx；无法判断时使用400。"
    )
    return f"""
你是资深测试开发工程师。请基于下面的接口请求参数生成接口自动化测试用例。

接口上下文:
{json.dumps(interface_context or {}, ensure_ascii=False, indent=2)}

基础参数:
{json.dumps(input_data, ensure_ascii=False, indent=2)}

要求:
1. 结合字段名称、类型、必填项、枚举、长度和业务语义生成用例。
2. 覆盖缺失、null、空白、边界值、超长字符串、特殊字符、非法类型、SQL注入、XSS和字段组合。
3. 不生成重复用例，最多生成30条。
4. {expected_rule}
5. 输出必须是严格JSON对象，不要输出Markdown，格式为 {{"cases": [...]}}。
6. 每个元素格式如下:
{{
  "case_name": "用例名称",
  "data": {{}},
  "expected_status_code": 400,
  "expected_json": {{}}
}}
"""


def build_result_analysis_prompt(status_code: int, response: dict[str, Any], assertion_message: str) -> str:
    return f"""
你是接口自动化测试结果分析专家。请分析下面的接口响应和断言信息。

HTTP 状态码: {status_code}
接口响应:
{json.dumps(response, ensure_ascii=False, indent=2)}
断言信息:
{assertion_message}

请输出:
1. 问题类型
2. 可能原因
3. 建议排查方向
要求用简洁中文输出。
"""

