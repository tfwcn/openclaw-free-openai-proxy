import os
import re
import logging
from typing import List, Dict, Any
import importlib

logger = logging.getLogger(__name__)


class PluginManager:
    """插件管理器 - 负责加载和执行插件"""

    @staticmethod
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

    @staticmethod
    def load_plugin_models(plugin_config: Dict[str, Any]) -> List[str]:
        """
        加载插件并获取模型列表

        Args:
            plugin_config: 插件配置字典

        Returns:
            模型ID列表
        """
        try:
            plugin_code = plugin_config.get('code')
            if not plugin_code:
                logger.warning("插件配置缺少 code 字段")
                return []

            # 动态导入插件模块
            module = importlib.import_module(plugin_code)

            # 调用插件的 get_models 函数
            if hasattr(module, 'get_models'):
                models = module.get_models(plugin_config)
                if isinstance(models, list):
                    logger.info(f"插件 {plugin_code} 成功加载 {len(models)} 个模型")
                    return models
                else:
                    logger.error(f"插件 {plugin_code} 返回的模型列表格式错误")
                    return []
            else:
                logger.error(f"插件 {plugin_code} 缺少 get_models 函数")
                return []

        except Exception as e:
            logger.error(f"加载插件 {plugin_code} 时发生错误: {e}")
            return []