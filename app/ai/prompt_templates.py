import json
from typing import Any


def build_case_generation_prompt(input_data: dict[str, Any]) -> str:
    return f"""
你是资深测试开发工程师。请基于下面的接口请求参数生成接口自动化测试用例。

基础参数:
{json.dumps(input_data, ensure_ascii=False, indent=2)}

要求:
1. 覆盖空值、边界值、超长字符串、特殊字符、非法类型、SQL 注入、XSS。
2. 输出必须是 JSON 数组，不要输出 Markdown。
3. 每个元素格式如下:
{{
  "case_name": "用例名称",
  "data": {{}},
  "expected_status_code": 200,
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

