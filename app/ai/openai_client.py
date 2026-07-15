import json
from typing import Any

from openai import OpenAI

from app.ai.prompt_templates import build_case_generation_prompt, build_result_analysis_prompt
from app.utils.config import get_settings
from app.utils.logger import logger


class OpenAIClient:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.client = OpenAI(api_key=self.settings.openai_api_key) if self.settings.openai_api_key else None

    def generate_cases(self, input_data: dict[str, Any]) -> list[dict[str, Any]]:
        if not self.client:
            logger.warning("OPENAI_API_KEY is missing, using local fallback cases")
            return self._fallback_cases(input_data)

        try:
            prompt = build_case_generation_prompt(input_data)
            response = self.client.chat.completions.create(
                model=self.settings.openai_model,
                temperature=self.settings.openai_temperature,
                messages=[
                    {"role": "system", "content": "你只输出严格 JSON，不输出解释。"},
                    {"role": "user", "content": prompt},
                ],
            )
            content = response.choices[0].message.content or "[]"
            return json.loads(content)
        except Exception:
            logger.exception("OpenAI case generation failed, using local fallback cases")
            return self._fallback_cases(input_data)

    def analyze_result(self, status_code: int, response: dict[str, Any], assertion_message: str = "") -> str:
        if not self.client:
            return self._fallback_analysis(status_code, response, assertion_message)

        try:
            prompt = build_result_analysis_prompt(status_code, response, assertion_message)
            result = self.client.chat.completions.create(
                model=self.settings.openai_model,
                temperature=self.settings.openai_temperature,
                messages=[
                    {"role": "system", "content": "你是测试开发专家，输出简洁中文分析。"},
                    {"role": "user", "content": prompt},
                ],
            )
            return result.choices[0].message.content or ""
        except Exception:
            logger.exception("OpenAI result analysis failed, using local fallback analysis")
            return self._fallback_analysis(status_code, response, assertion_message)

    @staticmethod
    def _fallback_cases(input_data: dict[str, Any]) -> list[dict[str, Any]]:
        cases: list[dict[str, Any]] = []
        for key, value in input_data.items():
            cases.append({"case_name": f"{key}为空", "data": {**input_data, key: ""}, "expected_status_code": 200, "expected_json": {}})
            cases.append({"case_name": f"{key}非法类型", "data": {**input_data, key: 123456}, "expected_status_code": 200, "expected_json": {}})
            if isinstance(value, str):
                cases.append({"case_name": f"{key}超长字符串", "data": {**input_data, key: "a" * 256}, "expected_status_code": 200, "expected_json": {}})
        cases.append({"case_name": "SQL注入", "data": {k: "' OR '1'='1" for k in input_data}, "expected_status_code": 200, "expected_json": {}})
        cases.append({"case_name": "XSS脚本注入", "data": {k: "<script>alert(1)</script>" for k in input_data}, "expected_status_code": 200, "expected_json": {}})
        return cases

    @staticmethod
    def _fallback_analysis(status_code: int, response: dict[str, Any], assertion_message: str) -> str:
        if status_code >= 500:
            return "服务端异常，建议检查后端日志、数据库连接、接口依赖服务和异常堆栈。"
        if status_code in {401, 403}:
            return "鉴权失败，可能是 token 过期、权限不足或认证头缺失。"
        if assertion_message:
            return f"接口响应与预期不一致，建议检查接口契约和测试数据。断言信息: {assertion_message}"
        return "未发现明显风险，建议结合业务字段继续校验。"


openai_client = OpenAIClient()
