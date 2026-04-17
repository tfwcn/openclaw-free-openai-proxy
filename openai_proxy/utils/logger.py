"""日志工具模块 - 提供安全的日志记录功能"""

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


def sanitize_request_data(request_data: Dict[str, Any], max_messages_len: int = 100) -> Dict[str, Any]:
    """
    脱敏请求数据，移除或截断可能包含敏感信息的字段
    
    Args:
        request_data: 原始请求数据
        max_messages_len: 消息内容最大长度
        
    Returns:
        脱敏后的请求数据
    """
    sanitized = request_data.copy()
    
    # 截断消息内容
    if "messages" in sanitized:
        messages = sanitized["messages"]
        if isinstance(messages, list):
            # 只显示消息数量和角色，不显示具体内容
            sanitized["messages"] = [
                {"role": msg.get("role", "unknown"), "content": "..."} 
                for msg in messages
            ][:10]  # 最多显示10条消息
    
    # 移除可能的敏感字段
    sensitive_fields = ["api_key", "authorization", "token", "secret", "password"]
    for field in sensitive_fields:
        if field in sanitized:
            del sanitized[field]
    
    return sanitized


def log_request_info(model_name: str, is_stream: bool = False, request_data: Dict[str, Any] = None):
    """
    安全地记录请求信息
    
    Args:
        model_name: 模型名称
        is_stream: 是否为流式请求
        request_data: 请求数据（会被脱敏）
    """
    stream_info = "stream" if is_stream else "non-stream"
    logger.info(f"处理请求: 模型={model_name}, 模式={stream_info}")
    
    if request_data and logger.isEnabledFor(logging.DEBUG):
        sanitized = sanitize_request_data(request_data)
        logger.debug(f"请求详情: {sanitized}")


def log_model_call_start(model_name: str, model_id: str, is_stream: bool = False):
    """
    记录模型调用开始
    
    Args:
        model_name: 模型配置名称
        model_id: 实际模型ID
        is_stream: 是否为流式请求
    """
    stream_info = "流式" if is_stream else "非流式"
    logger.info(f"调用模型: {model_name} ({model_id}) - {stream_info}")


def log_model_call_success(model_name: str, is_stream: bool = False):
    """
    记录模型调用成功
    
    Args:
        model_name: 模型配置名称
        is_stream: 是否为流式请求
    """
    stream_info = "流式" if is_stream else "非流式"
    logger.info(f"模型调用成功: {model_name} ({stream_info})")


def log_model_call_failure(model_name: str, error: str, is_stream: bool = False):
    """
    记录模型调用失败
    
    Args:
        model_name: 模型配置名称
        error: 错误信息
        is_stream: 是否为流式请求
    """
    stream_info = "流式" if is_stream else "非流式"
    logger.warning(f"模型调用失败: {model_name} ({stream_info}) - {error}")


def log_platform_status(platform_name: str, available_models: int, total_models: int):
    """
    记录平台状态
    
    Args:
        platform_name: 平台名称
        available_models: 可用模型数量
        total_models: 总模型数量
    """
    logger.debug(f"平台 {platform_name}: {available_models}/{total_models} 个模型可用")


def log_failover_attempt(platform_name: str, attempt: int, total: int, model_name: str):
    """
    记录故障转移尝试
    
    Args:
        platform_name: 平台名称
        attempt: 当前尝试次数
        total: 总尝试次数
        model_name: 模型名称
    """
    logger.debug(f"故障转移: {platform_name} 尝试 {attempt}/{total} - {model_name}")