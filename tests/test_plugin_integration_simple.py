"""简单的插件集成测试"""

import pytest
from unittest.mock import AsyncMock, patch
import asyncio

from plugin.openrouter import OpenRouterPlugin
from plugin.modelscope import ModelScopePlugin
from plugin.nvidia import NVIDIAPlugin


@pytest.mark.asyncio
async def test_openrouter_plugin_instantiation():
    """测试OpenRouter插件实例化"""
    plugin = OpenRouterPlugin(api_key="test-key", cache_ttl=300)
    assert plugin.api_key == "test-key"
    assert plugin.cache_ttl == 300
    assert plugin.base_url == "https://openrouter.ai/api"


@pytest.mark.asyncio
async def test_modelscope_plugin_instantiation():
    """测试ModelScope插件实例化"""
    plugin = ModelScopePlugin(api_key="test-key", cache_ttl=3600)
    assert plugin.api_key == "test-key"
    assert plugin.cache_ttl == 3600
    assert plugin.base_url == "https://modelscope.cn/api/v1"


@pytest.mark.asyncio
async def test_nvidia_plugin_instantiation():
    """测试NVIDIA插件实例化"""
    plugin = NVIDIAPlugin(api_key="test-key", cache_ttl=3600)
    assert plugin.api_key == "test-key"
    assert plugin.cache_ttl == 3600
    assert plugin.base_url == "https://integrate.api.nvidia.com/v1"


def test_base_plugin_cache_functions():
    """测试基类缓存功能"""
    from openai_proxy.core.base_plugin import BasePlugin
    
    class TestPlugin(BasePlugin):
        async def get_models(self, plugin_config=None):
            return ["model1", "model2"]
        
        async def health_check(self, plugin_config=None):
            return {"status": "healthy"}
    
    plugin = TestPlugin(api_key="test-key", cache_ttl=300)
    
    # 初始状态：无缓存
    assert not plugin.is_cache_valid()
    
    # 添加缓存
    plugin.update_cache(["model1", "model2"])
    assert plugin.is_cache_valid()
    
    # 清除缓存
    plugin.clear_cache()
    assert not plugin.is_cache_valid()


def test_base_plugin_config_parsing():
    """测试基类配置解析"""
    from openai_proxy.core.base_plugin import BasePlugin
    
    class TestPlugin(BasePlugin):
        async def get_models(self, plugin_config=None):
            return ["model1", "model2"]
        
        async def health_check(self, plugin_config=None):
            return {"status": "healthy"}
    
    plugin = TestPlugin()
    
    config = {
        "code": "test.plugin",
        "cache_timeout": 300,
        "custom_field": "custom_value",
        "number_field": 42
    }
    
    parsed = plugin.parse_plugin_config(config)
    
    # code和cache_timeout应该被跳过
    assert "code" not in parsed
    assert "cache_timeout" not in parsed
    assert parsed["custom_field"] == "custom_value"
    assert parsed["number_field"] == 42