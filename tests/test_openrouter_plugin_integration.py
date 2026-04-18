"""
OpenRouter 插件集成测试
"""

import pytest
import asyncio
import logging
import sys
import os

# 添加项目路径到 Python 路径
sys.path.insert(0, '/mnt/local_data/ubuntu_x86/kubernetes/ai-free-api/data/openai-proxy')

from plugin.openrouter import OpenRouterPlugin

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

@pytest.mark.asyncio
async def test_openrouter_plugin_with_scraper():
    """测试 OpenRouter 插件使用爬虫获取模型"""

    print("=" * 60)
    print("OpenRouter 插件爬虫功能集成测试")
    print("=" * 60)

    # 创建插件实例，配置爬虫
    plugin = OpenRouterPlugin(
        api_key=None,  # 不需要 API key，使用爬虫
        scrape_url="https://openrouter.ai/models?fmt=cards&input_modalities=text%2Cimage&max_price=0&order=most-popular&output_modalities=text",
        max_models=10,
        scraper_timeout=60,
        headless=True,
        cache_ttl=300
    )

    print("\n✓ 插件实例创建成功")
    print(f"  - 爬虫URL: {plugin.scrape_url}")
    print(f"  - 最大模型数: {plugin.max_models}")
    print(f"  - 超时时间: {plugin.scraper_timeout}秒")
    print(f"  - 无头模式: {plugin.headless}")

    try:
        print("\n开始获取模型列表...")
        models = await plugin.get_models()

        print(f"\n✓ 成功获取到 {len(models)} 个模型:")
        print("-" * 60)

        for i, model in enumerate(models, 1):
            print(f"{i:2d}. {model.model_id}")
            if model.model_name != model.model_id:
                print(f"     名称: {model.model_name}")

        print("-" * 60)
        print(f"\n✅ 集成测试通过! 共获取 {len(models)} 个免费模型")

        # 验证模型格式
        for model in models:
            assert model.model_id.endswith(':free'), f"模型ID应以 :free 结尾: {model.model_id}"
            assert model.model_id, "模型ID不能为空"
            assert model.model_name, "模型名称不能为空"

        print("✓ 所有模型格式验证通过")

        return models

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        raise

if __name__ == "__main__":
    try:
        asyncio.run(test_openrouter_plugin_with_scraper())
    except KeyboardInterrupt:
        print("\n\n测试被用户中断")
    except Exception as e:
        print(f"\n测试异常退出: {e}")
        sys.exit(1)
