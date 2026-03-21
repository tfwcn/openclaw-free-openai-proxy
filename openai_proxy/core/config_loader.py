import os
import json
import yaml
import logging
from typing import Dict, List, Any
from openai_proxy.models import ModelConfig
from openai_proxy.core.plugin_manager import PluginManager

logger = logging.getLogger(__name__)


class ConfigLoader:
    """配置加载器 - 负责加载和解析配置文件"""

    def __init__(self, config_file: str = "models.yaml"):
        self.config_file = config_file
        self.plugin_manager = PluginManager()

    def load_config(self) -> Dict[str, List[ModelConfig]]:
        """加载模型配置"""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    if self.config_file.endswith('.yaml') or self.config_file.endswith('.yml'):
                        config_data = yaml.safe_load(f)
                    else:
                        config_data = json.load(f)

                # 解析新格式的配置
                models = {}
                for platform_name, platform_config in config_data.items():
                    if not isinstance(platform_config, dict):
                        continue

                    base_url = platform_config.get('baseUrl')
                    # 解析并替换配置中的环境变量占位符
                    config_api_key = platform_config.get('apiKey')
                    if isinstance(config_api_key, str):
                        resolved_api_key = self.plugin_manager.resolve_env_vars(config_api_key)
                    else:
                        resolved_api_key = config_api_key

                    # 优先从环境变量获取API密钥，格式为 {PLATFORM_NAME}_API_KEY
                    env_api_key = os.getenv(f"{platform_name.upper()}_API_KEY")
                    api_key = env_api_key if env_api_key else resolved_api_key

                    # 检查是否有插件配置
                    plugin_config = platform_config.get('plugin')
                    if plugin_config:
                        # 使用插件动态获取模型列表
                        plugin_models_list = self.plugin_manager.load_plugin_models(plugin_config)
                        # 获取静态配置的模型列表（如果有）
                        static_models_list = platform_config.get('models', [])
                        # 合并模型列表：插件模型在前，静态模型在后
                        models_list = plugin_models_list + static_models_list
                    else:
                        # 使用静态配置的模型列表
                        models_list = platform_config.get('models', [])

                    timeout = platform_config.get('timeout', 30)
                    weight = platform_config.get('weight', 1)
                    enabled = platform_config.get('enabled', True)
                    quota_period = platform_config.get('quota_period')  # 支持 quota_period 配置

                    if not base_url or not api_key or not models_list:
                        logger.warning(f"跳过无效的平台配置: {platform_name}")
                        continue

                    models[platform_name] = []
                    for model_name in models_list:
                        model_config = ModelConfig(
                            name=f"{platform_name}-{model_name.replace('/', '-')}",
                            api_key=api_key,
                            base_url=base_url,
                            model=model_name,
                            timeout=timeout,
                            weight=weight,
                            enabled=enabled,
                            quota_period=quota_period
                        )
                        models[platform_name].append(model_config)

                logger.info(f"成功加载配置文件: {self.config_file}")
                logger.info(f"可用模型组: {list(models.keys())}")
                # 添加调试日志显示所有加载的模型
                for platform, platform_models in models.items():
                    logger.debug(f"DEBUG: 平台 {platform} 加载了 {len(platform_models)} 个模型: {[m.name for m in platform_models]}")
                
                return models
                
            except Exception as e:
                logger.error(f"加载配置文件失败: {e}")
                raise  # 直接抛出异常，不再创建默认配置
        else:
            error_msg = f"配置文件不存在: {self.config_file}"
            logger.error(error_msg)
            raise FileNotFoundError(error_msg)
