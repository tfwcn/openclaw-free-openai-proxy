#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OpenAI代理服务 - 支持多平台模型自动切换重试
"""

import os
import json
import yaml
import asyncio
import logging
import re
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
import time
from contextlib import asynccontextmanager

import aiohttp
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

# 加载环境变量（支持 .env 文件）
from dotenv import load_dotenv
load_dotenv()

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def resolve_env_vars(value: str) -> str:
    """
    解析并替换字符串中的环境变量占位符 ${VAR_NAME}
    
    Args:
        value: 包含环境变量占位符的字符串
        
    Returns:
        替换后的字符串，如果环境变量不存在则保留原占位符
    """
    if not isinstance(value, str):
        return value
        
    def replace_match(match):
        var_name = match.group(1)
        return os.getenv(var_name, match.group(0))
    
    # 使用正则表达式匹配 ${VAR_NAME} 格式的占位符
    pattern = r'\$\{([^}]+)\}'
    return re.sub(pattern, replace_match, value)


@dataclass
class ModelConfig:
    """模型配置"""
    name: str
    api_key: str
    base_url: str
    model: str
    timeout: int = 30
    weight: int = 1  # 权重，用于负载均衡（可选）
    enabled: bool = True
    quota_period: Optional[str] = None  # 额度刷新周期: "daily", "weekly", "monthly", "hourly"


class QuotaManager:
    """额度管理器 - 跟踪每个模型的配额使用情况"""
    
    def __init__(self):
        # 存储配额使用记录: {model_name: {period_start: usage_count}}
        self.quota_usage = {}
        self.lock = asyncio.Lock()
    
    def _get_period_start(self, period: str) -> datetime:
        """获取当前周期的开始时间"""
        now = datetime.now()
        
        if period == "hourly":
            return now.replace(minute=0, second=0, microsecond=0)
        elif period == "daily":
            return now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif period == "weekly":
            # 周一为每周开始
            days_since_monday = now.weekday()
            return (now - timedelta(days=days_since_monday)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
        elif period == "monthly":
            return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        else:
            # 默认为每日
            return now.replace(hour=0, minute=0, second=0, microsecond=0)
    
    def _is_quota_exceeded(self, model_config: ModelConfig) -> bool:
        """检查配额是否已超出"""
        if not model_config.quota_limit or not model_config.quota_period:
            return False  # 无配额限制
        
        model_name = model_config.name
        period_start = self._get_period_start(model_config.quota_period)
        period_key = period_start.isoformat()
        
        # 获取当前周期的使用量
        current_usage = self.quota_usage.get(model_name, {}).get(period_key, 0)
        
        return current_usage >= model_config.quota_limit
    
    async def can_use_model(self, model_config: ModelConfig) -> bool:
        """检查是否可以使用该模型（配额未超限）"""
        async with self.lock:
            return not self._is_quota_exceeded(model_config)
    
    async def record_usage(self, model_config: ModelConfig, usage_amount: int = 1):
        """记录模型使用量"""
        if not model_config.quota_limit or not model_config.quota_period:
            return  # 无配额限制，无需记录
        
        async with self.lock:
            model_name = model_config.name
            period_start = self._get_period_start(model_config.quota_period)
            period_key = period_start.isoformat()
            
            if model_name not in self.quota_usage:
                self.quota_usage[model_name] = {}
            
            # 清理过期的配额记录（可选优化）
            self._cleanup_expired_records(model_name, period_start)
            
            # 记录使用量
            current_usage = self.quota_usage[model_name].get(period_key, 0)
            self.quota_usage[model_name][period_key] = current_usage + usage_amount
    
    def _cleanup_expired_records(self, model_name: str, current_period_start: datetime):
        """清理过期的配额记录（保留最近几个周期的数据）"""
        if model_name not in self.quota_usage:
            return
        
        # 保留最近7天的记录用于调试
        cutoff_date = datetime.now() - timedelta(days=7)
        keys_to_remove = []
        
        for period_key in self.quota_usage[model_name].keys():
            try:
                period_datetime = datetime.fromisoformat(period_key)
                if period_datetime < cutoff_date:
                    keys_to_remove.append(period_key)
            except ValueError:
                keys_to_remove.append(period_key)
        
        for key in keys_to_remove:
            del self.quota_usage[model_name][key]


class ModelStateManager:
    """模型状态管理器 - 跟踪模型在当前周期内的可用性"""
    
    def __init__(self):
        # 存储模型失效时间: {model_name: expiry_time}
        self.disabled_models = {}
        self.lock = asyncio.Lock()
    
    def _get_period_expiry(self, period: str) -> datetime:
        """获取当前周期的结束时间"""
        now = datetime.now()
        
        if period == "hourly":
            return (now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1))
        elif period == "daily":
            return (now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1))
        elif period == "weekly":
            # 周一为每周开始，周日结束
            days_until_sunday = 6 - now.weekday()
            week_start = (now - timedelta(days=now.weekday())).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            return week_start + timedelta(days=7)
        elif period == "monthly":
            if now.month == 12:
                return datetime(now.year + 1, 1, 1)
            else:
                return datetime(now.year, now.month + 1, 1)
        else:
            # 默认为每日
            return (now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1))
    
    async def disable_model_for_period(self, model_config: ModelConfig):
        """标记模型在当前周期内已用完"""
        if not model_config.quota_period:
            return  # 无周期限制，不标记
        
        async with self.lock:
            expiry_time = self._get_period_expiry(model_config.quota_period)
            self.disabled_models[model_config.name] = expiry_time
    
    async def is_model_available(self, model_config: ModelConfig) -> bool:
        """检查模型是否可用（未被标记为周期内用完）"""
        if not model_config.quota_period:
            return True  # 无周期限制，始终可用
        
        async with self.lock:
            # 清理过期的禁用记录
            now = datetime.now()
            expired_models = []
            for model_name, expiry_time in self.disabled_models.items():
                if now >= expiry_time:
                    expired_models.append(model_name)
            
            for model_name in expired_models:
                del self.disabled_models[model_name]
            
            return model_config.name not in self.disabled_models


class OpenAIProxy:
    """OpenAI代理服务核心类"""
    
    def __init__(self, config_file: str = "models.yaml"):
        self.config_file = config_file
        self.models: Dict[str, List[ModelConfig]] = {}
        self.session: Optional[aiohttp.ClientSession] = None
        self.model_state_manager = ModelStateManager()  # 添加模型状态管理器
        self.load_config()
    
    def load_config(self):
        """加载模型配置"""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    if self.config_file.endswith('.yaml') or self.config_file.endswith('.yml'):
                        config_data = yaml.safe_load(f)
                    else:
                        config_data = json.load(f)
                
                # 解析新格式的配置
                self.models = {}
                for platform_name, platform_config in config_data.items():
                    if not isinstance(platform_config, dict):
                        continue
                    
                    base_url = platform_config.get('baseUrl')
                    # 解析并替换配置中的环境变量占位符
                    config_api_key = platform_config.get('apiKey')
                    if isinstance(config_api_key, str):
                        resolved_api_key = resolve_env_vars(config_api_key)
                    else:
                        resolved_api_key = config_api_key
                    
                    # 优先从环境变量获取API密钥，格式为 {PLATFORM_NAME}_API_KEY
                    env_api_key = os.getenv(f"{platform_name.upper()}_API_KEY")
                    api_key = env_api_key if env_api_key else resolved_api_key
                    models_list = platform_config.get('models', [])
                    timeout = platform_config.get('timeout', 30)
                    weight = platform_config.get('weight', 1)
                    enabled = platform_config.get('enabled', True)
                    
                    if not base_url or not api_key or not models_list:
                        logger.warning(f"跳过无效的平台配置: {platform_name}")
                        continue
                    
                    self.models[platform_name] = []
                    for model_name in models_list:
                        model_config = ModelConfig(
                            name=f"{platform_name}-{model_name.replace('/', '-')}",
                            api_key=api_key,
                            base_url=base_url,
                            model=model_name,
                            timeout=timeout,
                            weight=weight,
                            enabled=enabled
                        )
                        self.models[platform_name].append(model_config)
                
                logger.info(f"成功加载配置文件: {self.config_file}")
                logger.info(f"可用模型组: {list(self.models.keys())}")
            except Exception as e:
                logger.error(f"加载配置文件失败: {e}")
                self._create_default_config()
        else:
            self._create_default_config()
    
    def _create_default_config(self):
        """创建默认配置文件"""
        default_config = {
            "modelscope": {
                "baseUrl": "https://api-inference.modelscope.cn/v1",
                "apiKey": "${MODELSCOPE_API_KEY}",  # 使用环境变量占位符
                "models": ["Qwen/Qwen3.5-397B-A17B", "ZhipuAI/GLM-5"],
                "timeout": 30,
                "weight": 1,
                "enabled": True
            },
            "openai": {
                "baseUrl": "https://api.openai.com/v1", 
                "apiKey": "${OPENAI_API_KEY}",  # 使用环境变量占位符
                "models": ["gpt-4", "gpt-3.5-turbo"],
                "timeout": 30,
                "weight": 1,
                "enabled": False
            }
        }
        
        # 创建YAML配置文件
        with open(self.config_file, 'w', encoding='utf-8') as f:
            yaml.dump(default_config, f, default_flow_style=False, allow_unicode=True, indent=2)
        
        logger.info(f"已创建默认配置文件: {self.config_file}")
        logger.info("请编辑配置文件并设置正确的API密钥和端点")
    
    async def get_session(self) -> aiohttp.ClientSession:
        """获取HTTP会话"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=60),
                headers={"Content-Type": "application/json"}
            )
        return self.session
    
    async def call_model(self, model_config: ModelConfig, request_data: Dict[str, Any]) -> tuple[bool, Any]:
        """
        调用单个模型 - 完全参数透传
        
        Returns:
            tuple[bool, Any]: (是否成功, 响应数据或错误信息)
        """
        session = await self.get_session()
        url = f"{model_config.base_url.rstrip('/')}/chat/completions"
        
        # 准备请求数据 - 完全透传，只替换必要的字段
        request_body = request_data.copy()
        request_body["model"] = model_config.model  # 替换为实际的模型名称
        
        headers = {
            "Authorization": f"Bearer {model_config.api_key}",
            "Content-Type": "application/json"
        }
        
        try:
            logger.info(f"调用模型: {model_config.name} ({model_config.model})")
            
            if request_data.get("stream", False):
                # 流式响应
                response = await session.post(
                    url, 
                    json=request_body, 
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=model_config.timeout)
                )
                return True, response
            else:
                # 普通响应
                async with session.post(
                    url, 
                    json=request_body, 
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=model_config.timeout)
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        return True, result
                    else:
                        error_text = await response.text()
                        logger.warning(f"模型 {model_config.name} 返回错误: {response.status} - {error_text}")
                        return False, f"HTTP {response.status}: {error_text}"
                        
        except asyncio.TimeoutError:
            error_msg = f"模型 {model_config.name} 请求超时"
            logger.warning(error_msg)
            return False, error_msg
        except Exception as e:
            error_msg = f"模型 {model_config.name} 调用异常: {str(e)}"
            logger.warning(error_msg)
            return False, error_msg
    
    async def chat_completion(self, request_data: Dict[str, Any]) -> Any:
        """
        执行聊天完成请求，支持自动重试切换模型 - 完全参数透传
        """
        # 处理可选参数的默认值
        model_group = request_data.get("model")
        messages = request_data.get("messages")
        
        # 验证必要参数
        if not messages:
            raise HTTPException(status_code=400, detail="messages参数是必需的")
        
        # 确定要尝试的模型列表
        all_models_to_try = []
        
        if model_group is None or model_group == "all":
            # 遍历所有平台的所有模型
            for platform_models in self.models.values():
                all_models_to_try.extend(platform_models)
            if not all_models_to_try:
                raise HTTPException(status_code=400, detail="无可用模型配置")
        else:
            # 指定特定平台
            if model_group not in self.models or not self.models[model_group]:
                raise HTTPException(status_code=400, detail=f"模型组 '{model_group}' 未配置或无可用模型")
            all_models_to_try = self.models[model_group]
        
        # 过滤当前周期内可用的模型，并按权重降序排序
        available_models = []
        for model_config in all_models_to_try:
            if await self.model_state_manager.is_model_available(model_config):
                available_models.append(model_config)
        
        # 按权重降序排序（权重高的优先）
        available_models.sort(key=lambda x: x.weight, reverse=True)
        
        if not available_models:
            raise HTTPException(status_code=429, detail="所有模型在当前周期内均已用完")
        
        last_error = None
        
        # 按顺序尝试每个模型
        for i, model_config in enumerate(available_models):
            success, result = await self.call_model(model_config, request_data)
            
            if success:
                logger.info(f"模型 {model_config.name} 调用成功")
                return result
            else:
                last_error = result
                logger.warning(f"模型 {model_config.name} 失败，标记为周期内用完...")
                # 标记该模型在当前周期内已用完
                await self.model_state_manager.disable_model_for_period(model_config)
                
                # 如果是最后一个可用模型，抛出错误
                if i == len(available_models) - 1:
                    logger.error(f"所有可用模型都失败了，最后错误: {last_error}")
                    raise HTTPException(status_code=500, detail=f"所有模型都不可用: {last_error}")
        
        # 理论上不会到达这里
        raise HTTPException(status_code=500, detail="未知错误")
    
    async def close(self):
        """关闭会话"""
        if self.session and not self.session.closed:
            await self.session.close()

# 全局代理实例
proxy = OpenAIProxy()

# 定义 lifespan 事件处理器
@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理器"""
    # 启动事件
    logger.info("OpenAI代理服务启动中...")
    yield
    # 关闭事件
    await proxy.close()
    logger.info("OpenAI代理服务已关闭")

# FastAPI应用 - 使用 lifespan 参数
app = FastAPI(title="OpenAI Proxy Service", version="1.0.0", lifespan=lifespan)

@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    """
    OpenAI兼容的聊天完成接口 - 支持完全参数透传
    """
    try:
        request_data = await request.json()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"无效的JSON请求体: {str(e)}")
    
    # 验证必要参数
    if not request_data.get("messages"):
        raise HTTPException(status_code=400, detail="messages参数是必需的")
    
    if request_data.get("stream", False):
        # 流式响应处理
        async def stream_generator():
            try:
                result = await proxy.chat_completion(request_data)
                if isinstance(result, aiohttp.ClientResponse):
                    async for chunk in result.content.iter_any():
                        yield chunk
                else:
                    # 如果返回的是普通响应但请求是流式的，转换为流式格式
                    yield json.dumps(result).encode() + b"\n"
            except Exception as e:
                error_response = {
                    "error": {
                        "message": str(e),
                        "type": "proxy_error",
                        "param": None,
                        "code": "proxy_error"
                    }
                }
                yield json.dumps(error_response).encode() + b"\n"
        
        return StreamingResponse(stream_generator(), media_type="text/plain")
    else:
        # 普通响应
        result = await proxy.chat_completion(request_data)
        return result

@app.get("/health")
async def health_check():
    """健康检查接口"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

@app.get("/models")
async def list_models():
    """列出所有可用的模型组"""
    return {"models": list(proxy.models.keys())}

if __name__ == "__main__":
    import uvicorn
    logger.info("启动OpenAI代理服务...")
    logger.info("请确保已配置 models.json 文件")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")