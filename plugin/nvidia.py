"""NVIDIA API 平台插件 - 动态获取可用免费模型列表"""

import asyncio
import aiohttp
import logging
import os
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import json
import time

from openai_proxy.core.error_classifier import ErrorClassifier, ErrorType
from openai_proxy.core.base_plugin import BasePlugin
from openai_proxy.core.nvidia_scraper import NVIDIAModelScraper
from openai_proxy.core.model_cache import ModelCacheManager
from openai_proxy.core.scheduled_scraper import ScheduledScraper

logger = logging.getLogger(__name__)


@dataclass
class NVIDIAModel:
    """NVIDIA 模型信息"""
    model_id: str
    model_name: str
    context_window: Optional[int] = None
    capabilities: List[str] = None

    def __post_init__(self):
        if self.capabilities is None:
            self.capabilities = ["text"]


class NVIDIAPlugin(BasePlugin):
    """NVIDIA API 平台插件"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        cache_ttl: int = 3600,
        **kwargs
    ):
        """
        初始化 NVIDIA 插件

        Args:
            api_key: API 密钥，如果为 None 则从环境变量获取
            base_url: API 基础URL，如果为 None 则使用默认值
            cache_ttl: 缓存有效期（秒），默认3600秒（1小时）
            **kwargs: 其他插件特定参数，包括爬虫配置
        """
        # 设置默认值
        if base_url is None:
            base_url = "https://integrate.api.nvidia.com/v1"

        # 调用父类初始化
        super().__init__(
            api_key=api_key or os.getenv("NVIDIA_API_KEY"),
            base_url=base_url,
            cache_ttl=cache_ttl,
            **kwargs
        )

        if not self.api_key:
            logger.warning("NVIDIA API 密钥未配置，插件将无法工作")

        # 解析爬虫配置
        plugin_config = kwargs.get('plugin_config', {})
        scraper_args = plugin_config.get('args', {})

        # 爬虫配置参数
        self.free_model_count = scraper_args.get('free_model_count', 10)
        self.cache_file = scraper_args.get('cache_file', 'data/nvidia_free_models.json')
        self.scraper_timeout = scraper_args.get('scraper_timeout', 60)
        self.headless = scraper_args.get('headless', True)
        self.schedule_cron = scraper_args.get('schedule_cron', '0 2 * * *')
        self.enable_scheduled_task = scraper_args.get('enable_scheduled_task', True)
        self.scrape_url = scraper_args.get('scrape_url', None)  # 可选的自定义爬虫URL

        # 验证和修正配置参数
        self._validate_scraper_config()

        # 初始化缓存管理器
        self.cache_manager = ModelCacheManager(cache_file=self.cache_file)

        # 初始化爬虫和调度器（始终启用）
        self.scraper: Optional[NVIDIAModelScraper] = None
        self.scheduler: Optional[ScheduledScraper] = None

        # 标记是否已完成首次爬虫任务
        self.initial_scrape_completed: bool = False

        self._init_scraper()
        if self.enable_scheduled_task:
            self._init_scheduler()

    def _validate_scraper_config(self) -> None:
        """验证和修正爬虫配置参数"""
        # 验证 free_model_count 范围
        if not isinstance(self.free_model_count, int) or self.free_model_count < 1:
            logger.warning(f"free_model_count 无效 ({self.free_model_count})，使用默认值 10")
            self.free_model_count = 10
        elif self.free_model_count > 100:
            logger.warning(f"free_model_count 过大 ({self.free_model_count})，限制为 100")
            self.free_model_count = 100

        # 验证 timeout 范围
        if not isinstance(self.scraper_timeout, (int, float)) or self.scraper_timeout < 10:
            logger.warning(f"scraper_timeout 无效 ({self.scraper_timeout})，使用默认值 60")
            self.scraper_timeout = 60
        elif self.scraper_timeout > 300:
            logger.warning(f"scraper_timeout 过大 ({self.scraper_timeout})，限制为 300")
            self.scraper_timeout = 300

        logger.debug(
            f"爬虫配置: count={self.free_model_count}, "
            f"timeout={self.scraper_timeout}s, headless={self.headless}"
        )

    def _init_scraper(self) -> None:
        """初始化NVIDIA模型爬虫（始终启用）"""
        try:
            # 验证 scrape_url 是否配置
            if not self.scrape_url:
                raise ValueError("scrape_url 是必填参数，请在 models.yaml 中配置")

            logger.info(f"✓ 使用配置的爬虫URL: {self.scrape_url}")

            self.scraper = NVIDIAModelScraper(
                scrape_url=self.scrape_url,
                free_model_count=self.free_model_count,
                timeout=self.scraper_timeout,
                headless=self.headless
            )
            logger.info(f"✓ NVIDIA网页爬虫已初始化 (free_model_count={self.free_model_count})")
        except Exception as e:
            logger.error(f"初始化爬虫失败: {e}")
            raise

    def _init_scheduler(self) -> None:
        """初始化定时任务调度器"""
        try:
            async def scrape_task():
                """包装爬虫任务"""
                await self._run_scraper_and_cache()

            self.scheduler = ScheduledScraper(
                scrape_func=scrape_task,
                cron_expression=self.schedule_cron,
                run_on_start=True,
                timezone="Asia/Shanghai"
            )
            logger.info(f"✓ 定时调度器已初始化 (cron='{self.schedule_cron}')")
        except Exception as e:
            logger.error(f"初始化调度器失败: {e}")

    async def _run_scraper_and_cache(self) -> None:
        """执行爬虫并缓存结果"""
        if not self.scraper:
            logger.warning("爬虫未初始化")
            return

        try:
            logger.info("开始执行爬虫任务...")
            models = await self.scraper.scrape()

            if models:
                # 保存至缓存
                metadata = {
                    "fetch_time": time.time(),
                    "total_count": len(models),
                    "returned_count": len(models),
                    "source": "api_filter"
                }

                success = self.cache_manager.save(
                    models=models,
                    metadata=metadata,
                    success=True
                )

                if success:
                    logger.info(f"✓ 爬虫任务完成，缓存 {len(models)} 个模型")
                    # 标记首次爬虫已完成
                    if not self.initial_scrape_completed:
                        self.initial_scrape_completed = True
                        logger.info("✓ 首次爬虫任务完成，后续将使用最新数据")
                else:
                    logger.error("✗ 保存缓存失败")
            else:
                logger.warning("爬虫返回空结果")

        except Exception as e:
            error_msg = f"爬虫任务异常: {type(e).__name__}: {e}"
            logger.error(error_msg, exc_info=True)

            # 记录错误
            self.cache_manager.save(
                models=[],
                metadata={"error": error_msg},
                success=False
            )
            raise

    async def health_check(self, config: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        健康检查

        Args:
            config: 插件配置

        Returns:
            健康检查结果，包含API状态和爬虫状态
        """
        # 基础API健康检查
        if not self.api_key:
            return {
                "status": "unhealthy",
                "error": "API 密钥未配置",
                "response_time_ms": 0,
                "scraper": self.get_scraper_status()
            }

        start_time = time.time()
        try:
            async with aiohttp.ClientSession() as session:
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "User-Agent": "openai-proxy-plugin/1.0"
                }

                # 简单的健康检查 - 尝试获取模型列表
                url = f"{self.base_url}/models"
                async with session.get(url, headers=headers, timeout=10) as response:
                    response_time = (time.time() - start_time) * 1000

                    health_status = {
                        "status": "healthy" if response.status == 200 else "unhealthy",
                        "response_time_ms": int(response_time),
                        "last_check": time.time(),
                        "scraper": self.get_scraper_status()
                    }

                    if response.status != 200:
                        error_text = await response.text()
                        health_status["error"] = f"HTTP {response.status}: {error_text}"

                    return health_status

        except asyncio.TimeoutError:
            return {
                "status": "timeout",
                "timeout_ms": 10000,
                "response_time_ms": int((time.time() - start_time) * 1000)
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "response_time_ms": int((time.time() - start_time) * 1000)
            }

    async def get_models(self, plugin_config: Dict[str, Any] = None) -> List[NVIDIAModel]:
        """
        获取 NVIDIA 免费模型列表

        策略：
        1. 如果首次爬虫已完成：从内存缓存返回最新数据
        2. 如果首次爬虫未完成：返回空列表（等待爬虫完成）

        注意：服务启动时会等待首次爬虫完成，因此正常使用时不会遇到空列表情况

        Args:
            plugin_config: 插件配置字典

        Returns:
            模型列表
        """
        plugin_config = plugin_config or {}

        # 验证配置
        warnings = self._validate_request_config(plugin_config)
        for warning in warnings:
            logger.warning(f"NVIDIA 配置警告: {warning}")

        # 检查是否已完成首次爬虫
        if not self.initial_scrape_completed:
            logger.warning("首次爬虫任务尚未完成，返回空模型列表。这不应该发生，请检查启动日志。")
            return []

        # 从内存缓存获取模型（爬虫完成后已更新到内存）
        if self.models_cache and self.is_cache_valid():
            logger.debug(f"从内存缓存返回 {len(self.models_cache)} 个模型")
            return self.models_cache

        # 如果内存缓存不可用，尝试从文件缓存加载（作为降级方案）
        if self.cache_manager.is_valid():
            try:
                cache_data = self.cache_manager.load()
                if cache_data and cache_data.get('models'):
                    cached_models = cache_data['models']
                    logger.info(f"✓ 从文件缓存加载 {len(cached_models)} 个免费模型（降级方案）")

                    # 转换为 NVIDIAModel 对象
                    models = [
                        NVIDIAModel(
                            model_id=m['model_id'],
                            model_name=m.get('model_name', m['model_id']),
                            capabilities=["text"]
                        )
                        for m in cached_models
                    ]

                    # 更新内部缓存
                    self.update_cache(models)
                    return models
            except Exception as e:
                logger.warning(f"从文件缓存加载失败: {e}")

        # 最后的降级方案：返回空列表
        logger.warning("无法获取模型列表，返回空列表")
        return []

    async def parse_error(self, response_data: Any) -> ErrorType:
        """
        解析错误响应

        Args:
            response_data: 响应数据

        Returns:
            错误类型
        """
        try:
            if isinstance(response_data, dict):
                error_info = response_data.get("error", {})
                if isinstance(error_info, dict):
                    error_message = error_info.get("message", "").lower()

                    # 检查配额相关错误
                    if any(keyword in error_message for keyword in ['quota', 'rate limit', '超出配额']):
                        return ErrorType.QUOTA_EXCEEDED

                    # 检查认证相关错误
                    if any(keyword in error_message for keyword in ['authentication', 'unauthorized', '认证失败']):
                        return ErrorType.AUTH_ERROR

            # 使用通用错误分类
            return ErrorClassifier.classify_by_response(500, str(response_data))

        except Exception:
            return ErrorType.UNKNOWN_ERROR

    async def start_scheduler(self, wait_for_initial: bool = True) -> None:
        """
        启动定时任务调度器

        Args:
            wait_for_initial: 是否等待初始爬虫任务完成，默认True
                             这样可以确保服务启动时使用最新的模型数据

        应在服务启动时调用此方法。
        """
        if self.scheduler:
            try:
                await self.scheduler.start(wait_for_initial=wait_for_initial)
                logger.info("✓ NVIDIA爬虫调度器已启动")
            except Exception as e:
                logger.error(f"启动调度器失败: {e}")
        else:
            logger.debug("调度器未初始化（可能未启用爬虫功能）")

    async def stop_scheduler(self) -> None:
        """
        停止定时任务调度器

        应在服务关闭时调用此方法。
        """
        if self.scheduler:
            try:
                await self.scheduler.stop(wait=True, timeout=5)
                logger.info("✓ NVIDIA爬虫调度器已停止")
            except Exception as e:
                logger.error(f"停止调度器失败: {e}")

    def get_scraper_status(self) -> Dict[str, Any]:
        """
        获取爬虫状态信息

        Returns:
            包含爬虫状态的字典
        """
        status = {
            "cache_valid": self.cache_manager.is_valid(),
            "scheduler_running": False
        }

        if self.scheduler:
            scheduler_status = self.scheduler.get_status()
            status.update({
                "scheduler_running": scheduler_status["running"],
                "last_success": scheduler_status["last_success_time"],
                "consecutive_failures": scheduler_status["consecutive_failures"],
                "success_rate": scheduler_status["success_rate"]
            })

        cache_info = self.cache_manager.get_cache_info()
        status["cache_info"] = cache_info

        return status
