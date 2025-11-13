"""
LLM配置模块 - 连接硅基流动平台Qwen模型
"""
import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

# 加载环境变量
load_dotenv()


def get_llm():
    """
    获取配置好的LLM实例
    硅基流动平台使用OpenAI兼容接口
    """
    api_key = os.getenv("SILICONFLOW_API_KEY")
    base_url = os.getenv("SILICONFLOW_BASE_URL", "https://api.siliconflow.cn/v1")
    model_name = os.getenv("MODEL_NAME", "Qwen/Qwen2.5-7B-Instruct")
    
    if not api_key:
        raise ValueError("未找到SILICONFLOW_API_KEY环境变量，请在.env文件中配置")
    
    llm = ChatOpenAI(
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
    获取支持流式输出的LLM实例
    """
    api_key = os.getenv("SILICONFLOW_API_KEY")
    base_url = os.getenv("SILICONFLOW_BASE_URL", "https://api.siliconflow.cn/v1")
    model_name = os.getenv("MODEL_NAME", "Qwen/Qwen2.5-7B-Instruct")
    
    if not api_key:
        raise ValueError("未找到SILICONFLOW_API_KEY环境变量，请在.env文件中配置")
    
    llm = ChatOpenAI(
        model=model_name,
        openai_api_key=api_key,
        openai_api_base=base_url,
        temperature=0.7,
        max_tokens=2000,
        streaming=True,
    )
    
    return llm

