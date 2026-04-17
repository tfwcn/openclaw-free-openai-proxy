"""ModelScope 平台插件 - 动态获取可用模型列表"""

import asyncio
import aiohttp
import logging
import os
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
import json
import time

from openai_proxy.core.error_classifier import ErrorClassifier, ErrorType
from openai_proxy.core.base_plugin import BasePlugin

logger = logging.getLogger(__name__)


@dataclass
class ModelScopeModel:
    """ModelScope 模型信息"""
    model_id: str
    model_name: str
    context_window: Optional[int] = None
    capabilities: List[str] = None
    support_inference: Optional[str] = None  # ModelScope 免费模型标识字段
    
    def __post_init__(self):
        if self.capabilities is None:
            self.capabilities = ["text"]


class ModelScopePlugin(BasePlugin):
    """ModelScope 平台插件"""
    
    def __init__(
        self, 
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        cache_ttl: int = 3600,
        **kwargs
    ):
        """
        初始化 ModelScope 插件
        
        Args:
            api_key: API 密钥，如果为 None 则从环境变量获取
            base_url: API 基础URL，如果为 None 则使用默认值
            cache_ttl: 缓存有效期（秒），默认3600秒（1小时）
            **kwargs: 其他插件特定参数
        """
        # 设置默认值
        if base_url is None:
            base_url = "https://modelscope.cn/api/v1"
            
        # 调用父类初始化
        super().__init__(
            api_key=api_key or os.getenv("MODELSCOPE_API_KEY"),
            base_url=base_url,
            cache_ttl=cache_ttl,
            **kwargs
        )
        
        if not self.api_key:
            logger.warning("ModelScope API 密钥未配置，插件将无法工作")
    
    async def health_check(self, config: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        健康检查
        
        Args:
            config: 插件配置
            
        Returns:
            健康检查结果
        """
        if not self.api_key:
            return {
                "status": "unhealthy",
                "error": "API 密钥未配置",
                "response_time_ms": 0
            }
        
        start_time = time.time()
        try:
            async with aiohttp.ClientSession() as session:
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "User-Agent": "openai-proxy-plugin/1.0"
                }
                
                # 简单的健康检查 - 尝试获取用户信息
                url = f"{self.base_url}/user/info"
                async with session.get(url, headers=headers, timeout=10) as response:
                    response_time = (time.time() - start_time) * 1000
                    
                    if response.status == 200:
                        return {
                            "status": "healthy",
                            "response_time_ms": int(response_time),
                            "last_check": time.time()
                        }
                    else:
                        error_text = await response.text()
                        return {
                            "status": "unhealthy",
                            "error": f"HTTP {response.status}: {error_text}",
                            "response_time_ms": int(response_time)
                        }
                        
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
    
    async def get_models(self, plugin_config: Dict[str, Any] = None) -> List[ModelScopeModel]:
        """
        从 ModelScope API 获取可用模型列表

        Args:
            plugin_config: 插件配置字典

        Returns:
            模型列表
        """
        plugin_config = plugin_config or {}
        
        # 验证配置
        warnings = self._validate_request_config(plugin_config)
        for warning in warnings:
            logger.warning(f"ModelScope 配置警告: {warning}")
        
        # 检查缓存
        if self.is_cache_valid():
            logger.debug(f"使用缓存的 ModelScope 模型列表，共 {len(self.models_cache)} 个模型")
            return self.models_cache
        
        if not self.api_key:
            logger.warning("ModelScope API 密钥未配置，返回空模型列表")
            return []

        start_time = time.time()
        try:
            # 构建请求配置
            request_config = self._build_model_list_request(plugin_config)
            
            # 发起请求
            response_data = await self._make_api_request(
                url=request_config['url'],
                method=request_config['method'],
                headers=request_config['headers'],
                params=request_config['params'],
                json_data=request_config['json_data'],
                timeout=30
            )
            
            # 解析响应（私有方法）
            models = self._parse_response(response_data)
            
            # 更新缓存
            self.update_cache(models)
            
            fetch_time = (time.time() - start_time) * 1000
            logger.info(
                f"从 ModelScope API 获取到 {len(models)} 个模型，"
                f"耗时: {fetch_time:.2f}ms"
            )
            
            return models

        except Exception as e:
            logger.error(f"获取 ModelScope 模型列表失败: {e}")
            # 如果 API 调用失败但有缓存，返回缓存数据
            if self.models_cache:
                logger.warning("使用缓存的模型列表")
                return self.models_cache
            raise
    
    def _parse_response(self, data: Dict[str, Any]) -> List[ModelScopeModel]:
        """
        解析 ModelScope 特有的响应格式
        
        Args:
            data: API 响应数据
            
        Returns:
            模型列表
        """
        models = []
        
        try:
            # 处理不同格式的响应
            if isinstance(data, dict):
                # ModelScope API 可能返回嵌套结构: {"data": {"models": [...]}} 或 {"data": [...]}
                if 'data' in data and isinstance(data['data'], dict) and 'models' in data['data']:
                    model_list = data['data']['models']
                elif 'data' in data and isinstance(data['data'], list):
                    model_list = data['data']
                elif 'models' in data and isinstance(data['models'], list):
                    model_list = data['models']
                else:
                    model_list = []
            elif isinstance(data, list):
                model_list = data
            else:
                logger.error(f"API 返回的数据格式不支持，实际类型: {type(data)}")
                model_list = []
            
            # 解析每个模型
            for model_card in model_list:
                if isinstance(model_card, dict):
                    model_info = self._parse_model_info(model_card)
                    if model_info:
                        # 根据 SupportInference 字段过滤免费模型
                        if model_info.support_inference:
                            models.append(model_info)
            
            logger.debug(f"成功解析 {len(models)} 个免费模型")
            
        except Exception as e:
            logger.error(f"解析 ModelScope 响应时出错: {e}")
        
        return models
    
    def _parse_model_info(self, model_info: Dict[str, Any]) -> Optional[ModelScopeModel]:
        """
        解析模型信息
        
        Args:
            model_info: 原始模型信息
            
        Returns:
            解析后的模型对象
        """
        try:
            model_id = model_info.get("model_id") or model_info.get("modelId")
            if not model_id:
                return None
            
            model_name = model_info.get("model_name") or model_info.get("modelName") or model_id
            
            # 提取上下文窗口信息
            context_window = None
            if "context_window" in model_info:
                context_window = model_info["context_window"]
            elif "max_length" in model_info:
                context_window = model_info["max_length"]
            
            # 提取功能信息
            capabilities = ["text"]  # ModelScope 主要支持文本
            if model_info.get("model_type") == "text-to-image":
                capabilities = ["image"]
            
            # 提取 SupportInference 字段（免费模型标识）
            support_inference = model_info.get("SupportInference")
            
            return ModelScopeModel(
                model_id=model_id,
                model_name=model_name,
                context_window=context_window,
                capabilities=capabilities,
                support_inference=support_inference
            )
            
        except Exception as e:
            logger.debug(f"解析模型信息失败: {e}")
            return None
    

    
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