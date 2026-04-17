"""OpenRouter 插件单元测试 - 新配置结构"""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from plugin.openrouter import OpenRouterPlugin


class TestOpenRouterPluginInit:
    """测试 OpenRouterPlugin 初始化"""

    def test_init_with_defaults(self):
        """测试使用默认值初始化"""
        plugin = OpenRouterPlugin(api_key="test-key")
        
        assert plugin.api_key == "test-key"
        assert plugin.base_url == "https://openrouter.ai/api"
        assert plugin.cache_ttl == 300

    def test_init_with_custom_params(self):
        """测试使用自定义参数初始化"""
        plugin = OpenRouterPlugin(
            api_key="custom-key",
            base_url="https://custom.api.com",
            cache_ttl=600
        )
        
        assert plugin.api_key == "custom-key"
        assert plugin.base_url == "https://custom.api.com"
        assert plugin.cache_ttl == 600

    def test_init_without_api_key_warning(self):
        """测试未提供 API Key 时不抛出异常"""
        import os
        original_key = os.environ.pop('OPENROUTER_API_KEY', None)
        
        # 应该能正常初始化,不抛出异常
        plugin = OpenRouterPlugin()
        assert plugin.api_key is None
        
        # 恢复环境变量
        if original_key:
            os.environ['OPENROUTER_API_KEY'] = original_key


class TestGetModelsNewConfig:
    """测试使用新配置结构的 get_models()"""

    @pytest.mark.asyncio
    async def test_get_models_with_new_config(self):
        """测试使用新配置获取模型列表"""
        plugin = OpenRouterPlugin(api_key="test-key")
        
        plugin_config = {
            "args": {
                "model_list_method": "GET",
                "request_params": {"max_price": 0}
            }
        }
        
        mock_response = {
            'data': {
                'models': [
                    {'slug': 'model1', 'name': 'Model 1'},
                    {'slug': 'model2', 'name': 'Model 2'}
                ]
            }
        }
        
        with patch.object(plugin, '_make_api_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response
            
            result = await plugin.get_models(plugin_config)
            
            assert len(result) == 2
            assert result[0].model_id == 'model1:free'
            assert result[1].model_id == 'model2:free'

    @pytest.mark.asyncio
    async def test_get_models_uses_cache(self):
        """测试缓存命中时不发起请求"""
        plugin = OpenRouterPlugin(api_key="test-key")
        
        # 先填充缓存
        from plugin.openrouter import OpenRouterModel
        cached_models = [OpenRouterModel(model_id='cached:free', model_name='Cached')]
        plugin.update_cache(cached_models)
        
        plugin_config = {"args": {"model_list_method": "GET"}}
        
        with patch.object(plugin, '_make_api_request', new_callable=AsyncMock) as mock_request:
            result = await plugin.get_models(plugin_config)
            
            # 应该使用缓存，不发起请求
            mock_request.assert_not_called()
            assert len(result) == 1
            assert result[0].model_id == 'cached:free'


    @pytest.mark.asyncio
    async def test_get_models_no_api_key_returns_empty(self):
        """测试未配置 API Key 时返回空列表"""
        import os
        # 确保没有 API key
        original_key = os.environ.pop('OPENROUTER_API_KEY', None)
        
        plugin = OpenRouterPlugin()
        
        plugin_config = {"args": {"model_list_method": "GET"}}
        
        result = await plugin.get_models(plugin_config)
        
        assert result == []
        
        # 恢复环境变量
        if original_key:
            os.environ['OPENROUTER_API_KEY'] = original_key


class TestParseResponse:
    """测试响应解析"""

    def test_parse_nested_response(self):
        """测试解析嵌套响应格式"""
        plugin = OpenRouterPlugin(api_key="test-key")
        
        response_data = {
            'data': {
                'models': [
                    {'slug': 'model1', 'name': 'Model 1', 'context_length': 4096},
                    {'slug': 'model2', 'name': 'Model 2'}
                ]
            }
        }
        
        models = plugin._parse_response(response_data)
        
        assert len(models) == 2
        assert models[0].model_id == 'model1:free'
        assert models[0].context_window == 4096
        assert models[1].model_id == 'model2:free'

    def test_parse_flat_list_response(self):
        """测试解析扁平列表响应"""
        plugin = OpenRouterPlugin(api_key="test-key")
        
        response_data = [
            {'slug': 'model1', 'name': 'Model 1'},
            {'slug': 'model2', 'name': 'Model 2'}
        ]
        
        models = plugin._parse_response(response_data)
        
        assert len(models) == 2

    def test_parse_empty_response(self):
        """测试解析空响应"""
        plugin = OpenRouterPlugin(api_key="test-key")
        
        models = plugin._parse_response({})
        
        assert models == []

    def test_parse_model_with_capabilities(self):
        """测试解析带功能信息的模型"""
        plugin = OpenRouterPlugin(api_key="test-key")
        
        response_data = {
            'data': {
                'models': [
                    {
                        'slug': 'model1',
                        'name': 'Model 1',
                        'capabilities': ['text', 'image']
                    }
                ]
            }
        }
        
        models = plugin._parse_response(response_data)
        
        assert len(models) == 1
        assert models[0].capabilities == ['text', 'image']