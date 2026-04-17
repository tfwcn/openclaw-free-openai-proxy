#!/bin/bash
# 快速验证脚本 - 运行所有测试

set -e

echo "========================================"
echo "  OpenAI Proxy 插件测试快速验证"
echo "========================================"
echo ""

# 检查是否安装了 pytest
if ! command -v pytest &> /dev/null; then
    echo "错误：pytest 未安装。请先运行：pip install -r requirements-dev.txt"
    exit 1
fi

# 设置测试环境变量
export TEST_OPENROUTER_API_KEY="test_key_for_validation"

echo "1. 运行单元测试..."
echo "----------------------------------------"
pytest tests/test_plugin_openrouter.py -v --tb=short

echo ""
echo "2. 运行插件管理器测试..."
echo "----------------------------------------"
pytest tests/test_plugin_manager.py -v --tb=short

echo ""
echo "3. 运行配置加载器测试..."
echo "----------------------------------------"
pytest tests/test_config_loader.py -v --tb=short

echo ""
echo "4. 运行集成测试..."
echo "----------------------------------------"
pytest tests/test_plugin_integration.py -v --tb=short

echo ""
echo "========================================"
echo "  所有测试完成!"
echo "========================================"