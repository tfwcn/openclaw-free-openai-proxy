"""插件模型列表功能综合测试

本测试文件专门测试插件模型列表功能，包括：
1. 插件管理器加载模型列表
2. 各个插件的模型获取功能
3. 模型过滤和缓存机制
4. 错误处理和边界情况
"""

import pytest
import os
import asyncio
import time
import json
import importlib
from unittest.mock import patch, MagicMock, AsyncMock
import sys

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 设置测试环境变量
os.environ['OPENROUTER_API_KEY'] = 'test_openrouter_key'
os.environ['NVIDIA_API_KEY'] = 'test_nvidia_key'
os.environ['MODELSCOPE_API_KEY'] = 'test_modelscope_key'

from openai_proxy.core.plugin_manager import PluginManager
from openai_proxy.core.base_plugin import BasePlugin
from plugin.openrouter import OpenRouterPlugin, OpenRouterModel
from plugin.nvidia import NVIDIAPlugin, NVIDIAModel
from plugin.modelscope import ModelScopePlugin, ModelScopeModel


class MockTestPlugin(BasePlugin):
    """用于测试的模拟插件类"""
    async def get_models(self, plugin_config=None):
        return ['model1:free', 'model2:free']
    
    async def health_check(self, config=None):
        return {"status": "healthy", "response_time_ms": 10}


class TestPluginManagerModelList:
    """测试插件管理器模型列表功能"""

    async def test_load_single_plugin_models(self):
        """测试加载单个插件的模型列表"""
        plugin_config = {
            'code': 'plugin.openrouter',
            'args': {'category': 'free'}
        }
        
        # 创建 PluginManager 实例
        plugin_manager = PluginManager()
        
        with patch('importlib.import_module') as mock_import:
            mock_module = MagicMock()
            mock_module.OpenRouterPlugin = MockTestPlugin
            mock_import.return_value = mock_module

            models = await plugin_manager.load_plugin_models(plugin_config)
            
            assert len(models) == 2
            assert 'model1:free' in models
            assert 'model2:free' in models

    async def test_load_multiple_plugins_models(self):
        """测试加载多个插件的模型列表"""
        config = {
            'openrouter': {
                'baseUrl': 'https://openrouter.ai/api/v1',
                'apiKey': 'test-key',
                'plugin': {
                    'code': 'plugin.openrouter',
                    'args': {'category': 'free'}
                }
            }
        }
        
        # 创建 PluginManager 实例
        plugin_manager = PluginManager()
        
        with patch('importlib.import_module') as mock_import:
            mock_module = MagicMock()
            mock_module.OpenRouterPlugin = MockTestPlugin
            mock_import.return_value = mock_module

            models = await plugin_manager.load_plugin_models(config['openrouter']['plugin'])
            
            assert len(models) == 2

    async def test_load_plugin_with_env_vars(self):
        """测试插件配置中的环境变量解析"""
        os.environ['OPENROUTER_API_KEY'] = 'test_openrouter_key'
        
        plugin_config = {
            'code': 'plugin.openrouter',
            'args': {'category': 'free'}
        }
        
        # 创建 PluginManager 实例
        plugin_manager = PluginManager()
        
        with patch('importlib.import_module') as mock_import:
            mock_module = MagicMock()
            mock_module.OpenRouterPlugin = MockTestPlugin
            mock_import.return_value = mock_module

            models = await plugin_manager.load_plugin_models(plugin_config)
            
            # 验证环境变量被正确解析
            # 注意：在测试中，我们无法直接验证插件实例的 api_key，
            # 但可以通过 PluginManager.resolve_env_vars 测试解析逻辑
            resolved_api_key = PluginManager.resolve_env_vars('${OPENROUTER_API_KEY}')
            assert resolved_api_key == 'test_openrouter_key'
            
            assert len(models) == 2

    async def test_load_plugin_empty_result(self):
        """测试插件返回空结果"""
        plugin_config = {
            'code': 'plugin.openrouter',
            'args': {}
        }
        
        class MockEmptyPlugin(BasePlugin):
            async def get_models(self, plugin_config=None):
                return []
            async def health_check(self, config=None):
                return {"status": "healthy", "response_time_ms": 10}
        
        # 创建 PluginManager 实例
        plugin_manager = PluginManager()
        
        with patch('importlib.import_module') as mock_import:
            mock_module = MagicMock()
            mock_module.OpenRouterPlugin = MockEmptyPlugin
            mock_import.return_value = mock_module

            models = await plugin_manager.load_plugin_models(plugin_config)
            
            assert models == []


class TestOpenRouterModelList:
    """测试 OpenRouter 插件模型列表功能"""

    @pytest.mark.asyncio
    async def test_get_models_success(self):
        """测试成功获取 OpenRouter 模型列表"""
        plugin = OpenRouterPlugin(api_key="test-key")
        
        # Mock 内部方法 _fetch_models_from_api
        mock_models = [
            OpenRouterModel(model_id='gpt-3.5-turbo', model_name='GPT-3.5 Turbo'),
            OpenRouterModel(model_id='claude-3-haiku', model_name='Claude 3 Haiku')
        ]
        
        with patch.object(plugin, '_fetch_models_from_api', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = mock_models
            
            models = await plugin.get_models({'args': {}})
            assert len(models) == 2
            assert models[0].model_id == 'gpt-3.5-turbo'
            assert models[1].model_id == 'claude-3-haiku'

    @pytest.mark.asyncio
    async def test_get_models_with_filters(self):
        """测试带过滤条件的模型获取"""
        plugin = OpenRouterPlugin(api_key="test-key")
        
        # Mock 内部方法 _fetch_models_from_api
        mock_models = [
            OpenRouterModel(model_id='gpt-3.5-turbo', model_name='GPT-3.5 Turbo')
        ]
        
        with patch.object(plugin, '_fetch_models_from_api', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = mock_models
            
            models = await plugin.get_models({
                'args': {
                    'category': 'programming',
                    'input_modalities': 'text',
                    'output_modalities': 'text'
                }
            })
            assert len(models) == 1
            assert models[0].model_id == 'gpt-3.5-turbo'

    @pytest.mark.asyncio
    async def test_get_models_cache_hit(self):
        """测试缓存命中的情况"""
        plugin = OpenRouterPlugin(api_key="test-key")
        plugin.models_cache = [
            OpenRouterModel(model_id='cached-model', model_name='Cached Model')
        ]
        plugin.last_cache_time = time.time()
        
        models = await plugin.get_models({'args': {}})
        assert len(models) == 1
        assert models[0].model_id == 'cached-model'

    @pytest.mark.asyncio
    async def test_get_models_no_api_key(self):
        """测试没有 API 密钥的情况"""
        os.environ.pop('OPENROUTER_API_KEY', None)
        plugin = OpenRouterPlugin(api_key=None)
        
        models = await plugin.get_models({'args': {}})
        assert models == []


class TestNVIDIAModelList:
    """测试 NVIDIA 插件模型列表功能"""

    @pytest.mark.asyncio
    async def test_get_models_success(self):
        """测试成功获取 NVIDIA 模型列表"""
        plugin = NVIDIAPlugin(api_key="test-key")
        
        mock_models = [
            NVIDIAModel(model_id='nvidia/llama-3.1-8b', model_name='Llama 3.1 8B'),
            NVIDIAModel(model_id='microsoft/phi-3-mini', model_name='Phi-3 Mini')
        ]
        
        with patch.object(plugin, '_fetch_models_from_api', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = mock_models
            
            models = await plugin.get_models()
            assert len(models) == 2
            assert 'nvidia/llama-3.1-8b' in [m.model_id for m in models]
            assert 'microsoft/phi-3-mini' in [m.model_id for m in models]

    @pytest.mark.asyncio
    async def test_get_models_filter_free_models(self):
        """测试 NVIDIA 免费模型过滤"""
        plugin = NVIDIAPlugin(api_key="test-key")
        
        all_models = [
            NVIDIAModel(model_id='nvidia/llama-3.1-8b', model_name='Llama 3.1 8B'),
            NVIDIAModel(model_id='paid/expensive-model', model_name='Expensive Model'),
            NVIDIAModel(model_id='microsoft/phi-3-mini', model_name='Phi-3 Mini')
        ]
        
        with patch.object(plugin, '_fetch_models_from_api', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = all_models
            
            models = await plugin.get_models()
            assert len(models) == 2  # 只返回免费模型
            model_ids = [m.model_id for m in models]
            assert 'nvidia/llama-3.1-8b' in model_ids
            assert 'microsoft/phi-3-mini' in model_ids
            assert 'paid/expensive-model' not in model_ids


class TestModelScopeModelList:
    """测试 ModelScope 插件模型列表功能"""

    @pytest.mark.asyncio
    async def test_get_models_success(self):
        """测试成功获取 ModelScope 模型列表"""
        plugin = ModelScopePlugin(api_key="test-key")
        
        mock_models = [
            ModelScopeModel(model_id='minimax/MiniMax-M2.7', model_name='MiniMax M2.7', support_inference='txt2txt'),
            ModelScopeModel(model_id='zhipu/GLM-5.1', model_name='GLM 5.1', support_inference='txt2txt')
        ]
        
        with patch.object(plugin, '_fetch_models_from_api', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = mock_models
            
            models = await plugin.get_models()
            assert len(models) == 2
            assert 'minimax/MiniMax-M2.7' in [m.model_id for m in models]
            assert 'zhipu/GLM-5.1' in [m.model_id for m in models]

    @pytest.mark.asyncio
    async def test_get_models_filter_free_models(self):
        """测试 ModelScope 免费模型过滤"""
        plugin = ModelScopePlugin(api_key="test-key")
        
        all_models = [
            ModelScopeModel(model_id='minimax/MiniMax-M2.7', model_name='MiniMax M2.7', support_inference='txt2txt'),
            ModelScopeModel(model_id='paid/model', model_name='Paid Model', support_inference=''),
            ModelScopeModel(model_id='zhipu/GLM-5.1', model_name='GLM 5.1', support_inference='txt2txt')
        ]
        
        with patch.object(plugin, '_fetch_models_from_api', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = all_models
            
            models = await plugin.get_models()
            assert len(models) == 2  # 只返回免费模型
            model_ids = [m.model_id for m in models]
            assert 'minimax/MiniMax-M2.7' in model_ids
            assert 'zhipu/GLM-5.1' in model_ids
            assert 'paid/model' not in model_ids


class TestModelListIntegration:
    """测试模型列表集成场景"""

    def test_plugin_manager_with_real_plugins(self):
        """测试插件管理器与真实插件集成"""
        # 测试 OpenRouter 插件
        or_config = {
            'code': 'plugin.openrouter',
            'args': {
                'category': 'free',
                'cache_timeout': 60
            }
        }
        
        # 测试 NVIDIA 插件
        nv_config = {
            'code': 'plugin.nvidia',
            'args': {}
        }
        
        # 测试 ModelScope 插件
        ms_config = {
            'code': 'plugin.modelscope',
            'args': {}
        }
        
        # 验证插件可以正常加载
        configs = [or_config, nv_config, ms_config]
        for config in configs:
            try:
                # 这里不实际调用，只验证模块存在
                import importlib
                module = importlib.import_module(config['code'])
                # 检查模块是否有 get_models 函数或类
                has_get_models = hasattr(module, 'get_models')
                # 对于类-based 插件，检查是否有包含 get_models 方法的类
                if not has_get_models:
                    # 查找可能的插件类
                    for attr_name in dir(module):
                        attr = getattr(module, attr_name)
                        if isinstance(attr, type) and hasattr(attr, 'get_models'):
                            has_get_models = True
                            break
                assert has_get_models, f"{config['code']} 缺少 get_models 函数"
            except ImportError as e:
                pytest.skip(f"插件 {config['code']} 未找到: {e}")

    def test_model_list_format_consistency(self):
        """测试模型列表格式一致性"""
        # 测试所有插件返回的模型格式
        test_configs = [
            {'code': 'plugin.openrouter', 'args': {}},
            {'code': 'plugin.nvidia', 'args': {}},
            {'code': 'plugin.modelscope', 'args': {}}
        ]
        
        for config in test_configs:
            try:
                module = importlib.import_module(config['code'])
                # 检查模块是否有 get_models 函数或类
                has_get_models = hasattr(module, 'get_models')
                # 对于类-based 插件，检查是否有包含 get_models 方法的类
                if not has_get_models:
                    # 查找可能的插件类
                    for attr_name in dir(module):
                        attr = getattr(module, attr_name)
                        if isinstance(attr, type) and hasattr(attr, 'get_models'):
                            has_get_models = True
                            break
                assert has_get_models, f"{config['code']} 缺少 get_models 函数"
            except ImportError:
                pytest.skip(f"插件 {config['code']} 未找到")


class TestModelListErrorHandling:
    """测试模型列表错误处理"""

    def test_plugin_manager_load_nonexistent_plugin(self):
        """测试加载不存在的插件"""
        plugin_config = {
            'code': 'plugin.nonexistent',
            'args': {}
        }
        
        models = PluginManager.load_plugin_models(plugin_config)
        assert models == []

    def test_plugin_manager_load_invalid_plugin(self):
        """测试加载无效插件"""
        plugin_config = {
            'code': 'invalid.module.name',
            'args': {}
        }
        
        models = PluginManager.load_plugin_models(plugin_config)
        assert models == []

    @pytest.mark.asyncio
    async def test_plugin_api_timeout(self):
        """测试插件 API 超时处理"""
        plugin = OpenRouterPlugin(api_key="test-key")
        
        with patch('aiohttp.ClientSession') as mock_session:
            mock_get = AsyncMock()
            mock_get.__aenter__.side_effect = asyncio.TimeoutError()
            
            mock_session.return_value.__aenter__.return_value.get.return_value = mock_get
            
            # 测试超时时的行为
            plugin.models_cache = [OpenRouterModel(model_id='cached-model', model_name='Cached')]
            plugin.last_cache_time = time.time()
            
            models = await plugin.get_models({'args': {}})
            assert len(models) == 1  # 应该返回缓存
            assert models[0].model_id == 'cached-model'

    @pytest.mark.asyncio
    async def test_plugin_api_error_with_cache(self):
        """测试 API 错误但有缓存的情况"""
        plugin = NVIDIAPlugin(api_key="test-key")
        
        with patch.object(plugin, '_fetch_models_from_api', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.side_effect = Exception("API Error")
            
            plugin.models_cache = [NVIDIAModel(model_id='cached-model', model_name='Cached')]
            plugin.last_cache_time = time.time()
            
            models = await plugin.get_models()
            assert len(models) == 1  # 应该返回缓存
            assert models[0].model_id == 'cached-model'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])