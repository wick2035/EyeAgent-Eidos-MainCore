"""
Search1API 客户端
用于医学文献和网页搜索

API文档: https://docs.search1api.com
"""
import os
import asyncio
import aiohttp
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """搜索结果"""
    title: str
    url: str
    snippet: str
    source: str  # "general", "pubmed", "scholar"
    content: Optional[str] = None  # 爬取的完整内容（如果crawl_results开启）


class Search1APIError(Exception):
    """Search1API异常"""
    pass


class Search1APIClient:
    """
    Search1API 客户端

    支持三种搜索类型：
    - general: 通用网页搜索（Google）
    - pubmed: PubMed医学文献数据库
    - scholar: Google Scholar学术搜索
    """

    BASE_URL = "https://api.search1api.com/search"
    TIMEOUT = 30  # 秒

    # 搜索类型配置映射
    SEARCH_CONFIG = {
        "general": {
            "search_service": "google",
            "include_sites": None
        },
        "pubmed": {
            "search_service": "google",
            "include_sites": ["pubmed.ncbi.nlm.nih.gov", "ncbi.nlm.nih.gov"]
        },
        "scholar": {
            "search_service": "google",
            "include_sites": ["scholar.google.com", "scholar.google.com.hk"]
        }
    }

    def __init__(self, api_key: Optional[str] = None):
        """
        初始化Search1API客户端

        Args:
            api_key: API密钥，如果不提供则从环境变量SEARCH1API_KEY读取
        """
        self.api_key = api_key or os.getenv("SEARCH1API_KEY")
        if not self.api_key:
            logger.warning("[Search1API] 未配置SEARCH1API_KEY，搜索功能将不可用")

        self.headers = {
            "Authorization": f"Bearer {self.api_key}" if self.api_key else "",
            "Content-Type": "application/json"
        }
        logger.info("[Search1API] 客户端初始化完成")

    def is_available(self) -> bool:
        """检查API是否可用"""
        return bool(self.api_key)

    async def search(
        self,
        query: str,
        search_type: str = "general",
        max_results: int = 10,
        crawl_results: int = 0,
        language: str = "zh-CN",
        time_range: Optional[str] = None
    ) -> List[SearchResult]:
        """
        执行单次搜索

        Args:
            query: 搜索查询
            search_type: 搜索类型 ("general", "pubmed", "scholar")
            max_results: 最大结果数 (1-100)
            crawl_results: 爬取页面数量 (0-10)，每次爬取消耗额外credit
            language: 语言代码
            time_range: 时间范围 ("day", "month", "year")

        Returns:
            搜索结果列表
        """
        if not self.is_available():
            logger.warning("[Search1API] API密钥未配置，跳过搜索")
            return []

        config = self.SEARCH_CONFIG.get(search_type, self.SEARCH_CONFIG["general"])

        payload = {
            "query": query,
            "search_service": config["search_service"],
            "max_results": min(max_results, 100),
            "crawl_results": min(crawl_results, 10),
            "language": language
        }

        # 添加站点过滤
        if config["include_sites"]:
            payload["include_sites"] = config["include_sites"]

        # 添加时间范围过滤
        if time_range and time_range in ("day", "month", "year"):
            payload["time_range"] = time_range

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.BASE_URL,
                    headers=self.headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=self.TIMEOUT)
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"[Search1API] 请求失败: {response.status} - {error_text}")
                        return []

                    data = await response.json()

                    # 检查错误响应
                    if "error" in data:
                        logger.error(f"[Search1API] API错误: {data.get('message', 'Unknown error')}")
                        return []

                    results = []
                    for item in data.get("results", []):
                        results.append(SearchResult(
                            title=item.get("title", ""),
                            url=item.get("link", ""),
                            snippet=item.get("snippet", ""),
                            source=search_type,
                            content=item.get("content")  # 爬取的内容（如果有）
                        ))

                    logger.info(f"[Search1API] {search_type}搜索完成，返回{len(results)}条结果")
                    return results

        except asyncio.TimeoutError:
            logger.error(f"[Search1API] 搜索超时: {search_type}")
            return []
        except aiohttp.ClientError as e:
            logger.error(f"[Search1API] 网络错误: {e}")
            return []
        except Exception as e:
            logger.error(f"[Search1API] 搜索异常: {e}", exc_info=True)
            return []

    async def parallel_search(
        self,
        query: str,
        search_types: List[str],
        max_results_per_type: int = 5,
        crawl_results: int = 0,
        language: str = "zh-CN"
    ) -> Dict[str, List[SearchResult]]:
        """
        并行执行多类型搜索

        Args:
            query: 搜索查询
            search_types: 搜索类型列表 (如 ["general", "pubmed", "scholar"])
            max_results_per_type: 每种类型的最大结果数
            crawl_results: 爬取页面数量
            language: 语言

        Returns:
            按类型分组的搜索结果字典
        """
        if not self.is_available():
            logger.warning("[Search1API] API密钥未配置，跳过搜索")
            return {}

        # 过滤有效的搜索类型
        valid_types = [t for t in search_types if t in self.SEARCH_CONFIG]

        if not valid_types:
            logger.warning("[Search1API] 没有有效的搜索类型")
            return {}

        logger.info(f"[Search1API] 开始并行搜索: query='{query}', types={valid_types}")

        # 并行执行搜索
        tasks = [
            self.search(query, search_type, max_results_per_type, crawl_results, language)
            for search_type in valid_types
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 组织结果
        result_dict = {}
        for search_type, result in zip(valid_types, results):
            if isinstance(result, Exception):
                logger.error(f"[Search1API] {search_type}搜索出错: {result}")
                result_dict[search_type] = []
            else:
                result_dict[search_type] = result

        total_results = sum(len(r) for r in result_dict.values())
        logger.info(f"[Search1API] 并行搜索完成，共{total_results}条结果")

        return result_dict

    def search_sync(
        self,
        query: str,
        search_types: List[str],
        max_results_per_type: int = 5,
        crawl_results: int = 0,
        language: str = "zh-CN"
    ) -> Dict[str, List[SearchResult]]:
        """
        同步版本的并行搜索（用于非异步环境）

        在已有事件循环的环境中使用线程池执行
        """
        try:
            # 尝试获取当前事件循环
            loop = asyncio.get_running_loop()
        except RuntimeError:
            # 没有运行中的事件循环，直接运行
            return asyncio.run(
                self.parallel_search(query, search_types, max_results_per_type, crawl_results, language)
            )

        # 有运行中的事件循环，使用线程池
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(
                asyncio.run,
                self.parallel_search(query, search_types, max_results_per_type, crawl_results, language)
            )
            return future.result(timeout=self.TIMEOUT * len(search_types) + 10)


# 全局单例
_search_client: Optional[Search1APIClient] = None


def get_search1api_client() -> Search1APIClient:
    """获取Search1API客户端单例"""
    global _search_client
    if _search_client is None:
        _search_client = Search1APIClient()
    return _search_client
