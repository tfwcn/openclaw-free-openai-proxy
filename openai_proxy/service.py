import asyncio
import json
import logging
from datetime import datetime
from contextlib import asynccontextmanager
from typing import Dict, List

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse

from openai_proxy.models import ModelConfig
from openai_proxy.core.config_loader import ConfigLoader
from openai_proxy.core.model_failover_manager import ModelFailoverManager

logger = logging.getLogger(__name__)


class OpenAIProxyService:
    """OpenAI代理服务主类 - 负责FastAPI应用和路由"""

    def __init__(self, config_file: str = "models.yaml"):
        self.config_loader = ConfigLoader(config_file)
        self.models = self.config_loader.load_config()
        self.failover_manager = ModelFailoverManager(self.models)

    async def close(self):
        """关闭服务"""
        await self.failover_manager.close()

    def create_app(self) -> FastAPI:
        """创建FastAPI应用"""
        
        @asynccontextmanager
        async def lifespan(app: FastAPI):
            """应用生命周期管理器"""
            # 启动事件
            logger.info("OpenAI代理服务启动中...")
            yield
            # 关闭事件
            await self.close()
            logger.info("OpenAI代理服务已关闭")

        app = FastAPI(title="OpenAI Proxy Service", version="1.0.0", lifespan=lifespan)

        @app.post("/v1/chat/completions")
        async def chat_completions(request: Request):
            """
            OpenAI兼容的聊天完成接口 - 支持完全参数透传
            """
            logger.debug("DEBUG: 接收到新的聊天完成请求")
            logger.debug(f"DEBUG: 请求客户端IP: {request.client.host if request.client else 'unknown'}")
            logger.debug(f"DEBUG: 请求头: {dict(request.headers)}")

            try:
                request_data = await request.json()
                logger.debug("DEBUG: 请求JSON解析成功")
            except Exception as e:
                logger.error(f"DEBUG: 请求JSON解析失败: {str(e)}")
                raise HTTPException(status_code=400, detail=f"无效的JSON请求体: {str(e)}")

            # 验证必要参数
            if not request_data.get("messages"):
                logger.error("DEBUG: 请求缺少messages参数")
                raise HTTPException(status_code=400, detail="messages参数是必需的")

            logger.debug(f"DEBUG: 请求是否为流式: {request_data.get('stream', False)}")

            if request_data.get("stream", False):
                # 流式响应处理
                async def stream_generator():
                    logger.debug("DEBUG: 开始流式响应生成器")
                    try:
                        result = await self.failover_manager.chat_completion_stream(request_data)
                        if hasattr(result, '__aiter__'):
                            # 处理支持异步迭代的对象（包括StreamResponseWrapper和aiohttp.ClientResponse）
                            logger.debug("DEBUG: 流式响应 - 使用异步迭代器")
                            async for chunk in result:
                                if chunk:
                                    chunk_size = len(chunk)
                                    logger.debug(f"DEBUG: 流式响应 - 转发数据块，大小: {chunk_size}字节")

                                    # 打印响应内容（进行脱敏和截断处理）
                                    try:
                                        chunk_str = chunk.decode('utf-8', errors='replace')
                                        # 截断过长的内容以避免日志过大
                                        if len(chunk_str) > 500:
                                            chunk_preview = chunk_str[:500] + "..."
                                        else:
                                            chunk_preview = chunk_str

                                        # 检查是否包含敏感信息（如API密钥等），如果有则脱敏
                                        if "api_key" in chunk_preview.lower() or "secret" in chunk_preview.lower():
                                            chunk_preview = "[SENSITIVE DATA REDACTED]"

                                        logger.debug(f"DEBUG: 流式响应内容预览: {chunk_preview}")
                                    except Exception as decode_error:
                                        logger.debug(f"DEBUG: 无法解码响应内容为UTF-8: {decode_error}")

                                    yield chunk
                        else:
                            # 如果返回的是普通响应但请求是流式的，转换为流式格式
                            logger.debug("DEBUG: 流式响应 - 转换普通响应为流式")
                            result_str = json.dumps(result)
                            # 打印转换后的响应内容
                            if len(result_str) > 500:
                                result_preview = result_str[:500] + "..."
                            else:
                                result_preview = result_str
                            logger.debug(f"DEBUG: 转换后的流式响应内容: {result_preview}")
                            yield result_str.encode() + b"\n"
                    except Exception as e:
                        logger.error(f"DEBUG: 流式响应生成器异常: {str(e)}", exc_info=True)
                        error_response = {
                            "error": {
                                "message": str(e),
                                "type": "proxy_error",
                                "param": None,
                                "code": "proxy_error"
                            }
                        }
                        error_str = json.dumps(error_response)
                        logger.debug(f"DEBUG: 流式错误响应内容: {error_str}")
                        yield error_str.encode() + b"\n"

                logger.debug("DEBUG: 返回流式响应")
                return StreamingResponse(stream_generator(), media_type="text/plain")
            else:
                # 普通响应
                logger.debug("DEBUG: 处理普通（非流式）响应")
                result = await self.failover_manager.chat_completion_non_stream(request_data)
                logger.debug("DEBUG: 返回普通响应")
                return result

        @app.get("/health")
        async def health_check():
            """健康检查端点"""
            return {"status": "healthy", "timestamp": datetime.now().isoformat()}

        return app