"""
路由器配置 - 独立的LLM配置，不影响Agent业务逻辑
"""
import os
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv

load_dotenv()


class RouterLLMConfig:
    """路由专用的轻量级LLM配置"""

    # 使用14B模型做路由判断（比32B快，成本低，准确度足够）
    ROUTER_MODEL = "Qwen/Qwen2.5-14B-Instruct"  # 专门用于意图分流

    # 独立的API配置
    ROUTER_API_KEY = os.getenv("SILICONFLOW_API_KEY")
    ROUTER_BASE_URL = os.getenv("SILICONFLOW_BASE_URL", "https://api.siliconflow.cn/v1")

    # 路由专用参数（快速响应）
    ROUTER_TEMPERATURE = 0.1  # 低温度，确保稳定性
    ROUTER_MAX_TOKENS = 100   # 只需要返回简短的JSON
    ROUTER_TIMEOUT = 3        # 3秒超时

    @classmethod
    def get_router_llm(cls) -> ChatOpenAI:
        """获取路由专用的LLM实例（独立配置）"""
        return ChatOpenAI(
            model=cls.ROUTER_MODEL,
            openai_api_key=cls.ROUTER_API_KEY,
            openai_api_base=cls.ROUTER_BASE_URL,
            temperature=cls.ROUTER_TEMPERATURE,
            max_tokens=cls.ROUTER_MAX_TOKENS,
            request_timeout=cls.ROUTER_TIMEOUT
        )


# 全局路由LLM实例（单例）
_router_llm = None


def get_router_llm() -> ChatOpenAI:
    """获取路由LLM实例（全局单例，与业务LLM隔离）"""
    global _router_llm
    if _router_llm is None:
        _router_llm = RouterLLMConfig.get_router_llm()
    return _router_llm
