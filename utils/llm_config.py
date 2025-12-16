"""
LLM配置模块 - 连接硅基流动平台Qwen模型
"""
import os
import json
from typing import Any, Dict
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

# 加载环境变量
load_dotenv()


class SiliconFlowChatOpenAI(ChatOpenAI):
    """
    针对硅基流动平台的 ChatOpenAI 子类

    修复 SiliconFlow API 返回 tool_calls.args 为 JSON 字符串而非字典的问题
    """

    def _create_chat_result(
        self, response: Any, generation_info: Dict[str, Any] | None = None
    ) -> Any:
        """修复双重 JSON 编码的 tool_calls.arguments"""
        # 先将 response 转为 dict（避免直接修改 Pydantic 模型）
        if not isinstance(response, dict):
            response_dict = response.model_dump()
        else:
            response_dict = response

        # 修复 tool_calls.arguments（在 dict 上操作）
        for choice in response_dict.get("choices", []):
            message = choice.get("message", {})
            tool_calls = message.get("tool_calls")
            if tool_calls:
                for tc in tool_calls:
                    func = tc.get("function", {})
                    args = func.get("arguments")
                    if isinstance(args, str):
                        try:
                            parsed = json.loads(args)
                            # 如果解析后仍是字符串，说明是双重编码，再解析一次
                            if isinstance(parsed, str):
                                parsed = json.loads(parsed)
                            # 将结果转回单层 JSON 字符串供 parse_tool_call 使用
                            func["arguments"] = json.dumps(parsed, ensure_ascii=False)
                        except (json.JSONDecodeError, TypeError):
                            pass  # 保持原样，让 LangChain 处理

        # 传入修复后的 dict 给父类
        return super()._create_chat_result(response_dict, generation_info)


def get_llm():
    """
    获取配置好的LLM实例（业务Agent专用）
    硅基流动平台使用OpenAI兼容接口
    """
    api_key = os.getenv("SILICONFLOW_API_KEY")
    base_url = os.getenv("SILICONFLOW_BASE_URL", "https://api.siliconflow.cn/v1")
    model_name = os.getenv("MODEL_NAME", "Qwen/Qwen2.5-32B-Instruct")  # 业务Agent使用32B
    
    if not api_key:
        raise ValueError("未找到SILICONFLOW_API_KEY环境变量，请在.env文件中配置")
    
    llm = SiliconFlowChatOpenAI(
        model=model_name,
        openai_api_key=api_key,
        openai_api_base=base_url,
        temperature=0.7,
        max_tokens=2000,
        streaming=False,
    )

    return llm


def get_streaming_llm():
    """
    获取支持流式输出的LLM实例（业务Agent专用）
    """
    api_key = os.getenv("SILICONFLOW_API_KEY")
    base_url = os.getenv("SILICONFLOW_BASE_URL", "https://api.siliconflow.cn/v1")
    model_name = os.getenv("MODEL_NAME", "Qwen/Qwen2.5-32B-Instruct")  # 业务Agent使用32B

    if not api_key:
        raise ValueError("未找到SILICONFLOW_API_KEY环境变量，请在.env文件中配置")

    llm = SiliconFlowChatOpenAI(
        model=model_name,
        openai_api_key=api_key,
        openai_api_base=base_url,
        temperature=0.7,
        max_tokens=2000,
        streaming=True,
    )

    return llm

