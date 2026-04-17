# OpenAI Proxy 测试套件

本测试套件用于测试插件自动获取免费模型列表功能。

## 目录结构

```
tests/
├── __init__.py                 # 测试包初始化
├── conftest.py                 # pytest 配置和 fixtures
├── run_tests.sh                # 快速验证脚本
├── test_plugin_openrouter.py   # OpenRouter 插件单元测试
├── test_plugin_manager.py      # 插件管理器测试
├── test_config_loader.py       # 配置加载器测试
├── test_plugin_integration.py  # 集成测试
└── fixtures/
    ├── mock_responses/         # Mock API 响应数据
    │   ├── openrouter_success.json
    │   ├── openrouter_empty.json
    │   └── openrouter_error.json
    └── test_models.yaml        # 测试配置文件
```

## 安装依赖

```bash
pip install -r requirements-dev.txt
```

## 运行测试

### 运行所有测试

```bash
# 使用快速验证脚本
./tests/run_tests.sh

# 或使用 pytest 直接运行
pytest tests/ -v
```

### 运行特定测试文件

```bash
# OpenRouter 插件测试
pytest tests/test_plugin_openrouter.py -v

# 插件管理器测试
pytest tests/test_plugin_manager.py -v

# 配置加载器测试
pytest tests/test_config_loader.py -v

# 集成测试
pytest tests/test_plugin_integration.py -v
```

### 运行特定测试用例

```bash
# 运行特定测试类
pytest tests/test_plugin_openrouter.py::TestExtractFreeModels -v

# 运行特定测试方法
pytest tests/test_plugin_openrouter.py::TestExtractFreeModels::test_success_response -v
```

### 生成覆盖率报告

```bash
# 文本覆盖率报告
pytest tests/ --cov=openai_proxy --cov=plugin -v

# HTML 覆盖率报告
pytest tests/ --cov=openai_proxy --cov=plugin --cov-report=html

# 查看 HTML 报告
open htmlcov/index.html
```

## 测试用例概览

### OpenRouter 插件测试 (test_plugin_openrouter.py)

| 测试类 | 测试用例 | 描述 |
|-------|---------|------|
| TestExtractFreeModels | test_success_response | 测试正常 API 响应 |
| | test_empty_response | 测试空响应 |
| | test_cache_hit | 测试缓存命中 |
| | test_cache_miss_expired | 测试缓存过期 |
| | test_api_timeout | 测试 API 超时 |
| | test_api_connection_error | 测试连接错误 |
| | test_invalid_json_response | 测试无效 JSON |
| | test_category_filter | 测试类别过滤 |
| | test_input_modalities_filter | 测试输入模态过滤 |
| | test_output_modalities_filter | 测试输出模态过滤 |
| TestGetModels | test_full_config | 测试完整配置 |
| | test_minimal_config | 测试最小配置 |
| | test_category_coder_conversion | 测试 category 转换 |
| | test_list_to_string_conversion | 测试列表转字符串 |
| TestCacheFunctions | test_get_cache_key | 测试缓存键生成 |
| | test_is_cache_valid | 测试缓存有效性 |

### 插件管理器测试 (test_plugin_manager.py)

| 测试类 | 描述 |
|-------|------|
| TestPluginManagerResolveEnvVars | 环境变量解析测试 |
| TestPluginManagerLoadPluginModels | 插件加载测试 |
| TestPluginManagerIntegration | 集成测试 |

### 配置加载器测试 (test_config_loader.py)

| 测试类 | 描述 |
|-------|------|
| TestConfigLoaderLoadRawConfig | 原始配置加载测试 |
| TestConfigLoaderLoadSettings | 设置加载测试 |
| TestConfigLoaderLoadConfig | 模型配置加载测试 |
| TestConfigLoaderIntegration | 集成测试 |

### 集成测试 (test_plugin_integration.py)

| 测试类 | 描述 |
|-------|------|
| TestPluginConfigIntegration | 插件配置集成 |
| TestModelFormatValidation | 模型格式验证 |
| TestErrorPropagation | 错误传播测试 |
| TestEndToEnd | 端到端测试 |

## 环境变量

测试可能需要以下环境变量：

```bash
export TEST_OPENROUTER_API_KEY="your_test_key"
export OPENROUTER_API_KEY="your_key"
```

## 故障排除

### 测试失败

如果测试失败，检查：
1. 依赖是否已安装：`pip install -r requirements-dev.txt`
2. 环境变量是否正确设置
3. 测试文件是否有语法错误

### 覆盖率低

如果覆盖率低，检查：
1. 是否有未测试的代码路径
2. 错误处理是否被测试覆盖
3. 边界条件是否被测试

## CI/CD 集成

在 GitHub Actions 中运行测试：

```yaml
name: Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.9'
      - name: Install dependencies
        run: pip install -r requirements-dev.txt
      - name: Run tests
        run: pytest tests/ -v --cov=openai_proxy --cov=plugin