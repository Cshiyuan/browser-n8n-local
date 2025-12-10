"""LLM API Key Pool 负载均衡管理

实现多 API Key 轮询负载均衡,支持同一 AI 提供商配置多个 API Key。
使用简单的 Round-Robin 轮询策略,确保 Key 使用分布均匀。
"""

import os
import logging
from typing import List, Dict, Optional

logger = logging.getLogger("browser-use-bridge")


class ProviderKeyPool:
    """单个 AI 提供商的 Key 轮询池

    管理一个 AI 提供商的多个 API Key,通过轮询策略自动分配 Key 使用。
    支持向后兼容单 Key 配置格式。

    Attributes:
        provider: AI 提供商名称(如 'openai', 'anthropic', 'google')
        keys: 加载的 API Keys 列表
        current_index: 当前轮询索引
    """

    def __init__(self, provider: str):
        """初始化 Key Pool

        Args:
            provider: AI 提供商名称
        """
        self.provider = provider
        self.keys = self._load_keys()
        self.current_index = 0  # 轮询指针

    def _load_keys(self) -> List[str]:
        """从环境变量加载 API Keys,支持向后兼容

        优先级:
        1. {PROVIDER}_API_KEYS (新格式,逗号分隔)
        2. {PROVIDER}_API_KEY (旧格式,单 Key)

        Returns:
            API Keys 列表,可能为空
        """
        provider_upper = self.provider.upper()

        # 1. 尝试新格式 PROVIDER_API_KEYS
        keys_str = os.environ.get(f"{provider_upper}_API_KEYS")
        if keys_str:
            # 逗号分隔,去除空格
            keys = [k.strip() for k in keys_str.split(',') if k.strip()]
            if keys:
                logger.info(
                    f"Loaded {len(keys)} API Key(s) for {self.provider} "
                    f"from {provider_upper}_API_KEYS"
                )
                return keys

        # 2. 降级到旧格式 PROVIDER_API_KEY
        single_key = os.environ.get(f"{provider_upper}_API_KEY")
        if single_key:
            logger.info(
                f"Loaded 1 API Key for {self.provider} "
                f"from {provider_upper}_API_KEY (backward compatibility)"
            )
            return [single_key]

        # 都没找到
        logger.debug(f"No API Keys configured for {self.provider}")
        return []

    def next_key(self) -> Optional[str]:
        """获取下一个 Key (轮询)

        使用 Round-Robin 策略自动轮询所有可用 Keys。

        Returns:
            下一个 API Key,如果没有可用 Key 则返回 None
        """
        if not self.keys:
            return None

        key = self.keys[self.current_index]
        self.current_index = (self.current_index + 1) % len(self.keys)
        return key

    def has_keys(self) -> bool:
        """检查是否有可用 Keys

        Returns:
            如果有至少一个 Key 返回 True,否则返回 False
        """
        return len(self.keys) > 0

    def get_key_count(self) -> int:
        """获取可用 Keys 数量

        Returns:
            Keys 数量
        """
        return len(self.keys)


class LLMPoolManager:
    """全局 LLM Key Pool 管理器

    管理所有支持的 AI 提供商的 Key Pool,提供统一的 Key 获取接口。

    Attributes:
        pools: 提供商名称到 ProviderKeyPool 的映射
    """

    def __init__(self):
        """初始化所有支持的提供商的 Key Pool"""
        # 为每个支持的 provider 创建 Key Pool
        self.pools: Dict[str, ProviderKeyPool] = {
            'openai': ProviderKeyPool('openai'),
            'anthropic': ProviderKeyPool('anthropic'),
            'google': ProviderKeyPool('google'),
            'azure': ProviderKeyPool('azure'),
            'bedrock': ProviderKeyPool('bedrock'),
            'ollama': ProviderKeyPool('ollama'),
        }

    def get_api_key(self, provider: str) -> Optional[str]:
        """获取指定 provider 的下一个 API Key (轮询)

        Args:
            provider: AI 提供商名称(不区分大小写)

        Returns:
            轮询的 API Key,如果 provider 不存在或没有 Key 则返回 None
        """
        pool = self.pools.get(provider.lower())
        if pool:
            return pool.next_key()
        return None

    def get_provider_pool(self, provider: str) -> Optional[ProviderKeyPool]:
        """获取指定 provider 的 Key Pool

        Args:
            provider: AI 提供商名称(不区分大小写)

        Returns:
            ProviderKeyPool 实例,如果 provider 不存在则返回 None
        """
        return self.pools.get(provider.lower())


# 全局单例(模块加载时初始化)
_llm_pool_manager = LLMPoolManager()


def get_pooled_api_key(provider: str) -> Optional[str]:
    """对外接口: 获取轮询的 API Key

    这是推荐的外部使用接口,用于从 Key Pool 获取下一个可用的 API Key。

    Args:
        provider: AI 提供商名称(如 'openai', 'anthropic', 'google')

    Returns:
        轮询的 API Key,如果没有可用 Key 则返回 None

    Example:
        >>> api_key = get_pooled_api_key("openai")
        >>> if api_key:
        >>>     llm = ChatOpenAI(model="gpt-4o", api_key=api_key)
    """
    return _llm_pool_manager.get_api_key(provider)
