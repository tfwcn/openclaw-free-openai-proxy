# ModelScope 爬虫功能

## 简介

ModelScope 插件现已支持通过网页爬虫自动获取热门免费模型列表，无需手动配置模型列表或使用 API。

## 快速开始

### 1. 配置 models.yaml

在 `models.yaml` 文件中添加以下配置：

```yaml
modelscope:
  baseUrl: "https://dashscope.aliyuncs.com/api/v1"
  apiKey: "${MODELSCOPE_API_KEY}"
  plugin:
    code: "plugin.modelscope"
    cache_timeout: 3600 # 缓存过期时间（秒）
    args:
      scrape_url: "https://www.modelscope.cn/models?filter=inference_type&page=1&sort=default&tabKey=task"
      max_models: 50 # 获取的最大模型数量
      scraper_timeout: 60 # 爬虫超时时间（秒）
      headless: true # 无头模式运行浏览器
  models: [] # 不再需要静态配置模型
  timeout: 10
  weight: 1
  enabled: true
```

### 2. 启动服务

正常启动服务即可，插件会自动执行爬虫任务获取模型列表。

## 配置参数说明

| 参数              | 类型   | 默认值 | 说明                        |
| ----------------- | ------ | ------ | --------------------------- |
| `scrape_url`      | string | 必填   | ModelScope 模型列表页面 URL |
| `max_models`      | int    | 50     | 获取的最大模型数量          |
| `scraper_timeout` | int    | 60     | 爬虫超时时间（秒）          |
| `headless`        | bool   | true   | 是否使用无头模式运行浏览器  |
| `cache_timeout`   | int    | 3600   | 缓存过期时间（秒）          |

## 工作原理

1. **首次启动**：服务启动时会自动执行爬虫任务，从 ModelScope 网站抓取热门免费模型
2. **缓存机制**：抓取的模型列表会缓存到内存中，减少频繁请求
3. **自动重试**：如果爬虫失败，会自动重试最多 3 次
4. **降级策略**：如果爬虫失败但有缓存，会使用缓存数据

## 注意事项

- 首次启动时可能需要较长时间（取决于网络状况）
- 需要能够访问 `modelscope.cn` 网站
- 爬虫会启动 Chromium 浏览器，占用一定系统资源
- 建议在生产环境中启用 `headless: true` 以节省资源

## 故障排查

### 爬虫失败

如果爬虫失败，检查以下几点：

1. 网络连接是否正常
2. `scrape_url` 是否正确
3. 是否有足够的系统资源（内存、CPU）
4. 查看日志中的详细错误信息

### 获取不到模型

可能的原因：

1. ModelScope 网站结构发生变化
2. 网络连接问题
3. 被反爬虫机制拦截

解决方法：

1. 检查日志中的错误信息
2. 尝试手动访问 `scrape_url` 确认页面可访问
3. 调整 `scraper_timeout` 参数

## 与旧版本的兼容性

本次更新是**破坏性变更**（Breaking Change）：

- 移除了静态模型列表配置
- 移除了 API 获取方式
- 必须配置 `scrape_url` 才能正常工作

如果你仍需要使用静态模型列表，可以在 `models` 字段中手动配置，但建议使用爬虫方式以获取最新的模型列表。

## 示例代码

```python
from plugin.modelscope import ModelScopePlugin

# 创建插件实例
plugin = ModelScopePlugin(
    api_key="your-api-key",
    scrape_url="https://www.modelscope.cn/models?filter=inference_type&page=1&sort=default&tabKey=task",
    max_models=50,
    scraper_timeout=60,
    headless=True
)

# 获取模型列表
models = await plugin.get_models()

# 打印模型
for model in models:
    print(f"{model.model_id} - {model.model_name}")
```

## 更多信息

- [实现文档](MODELSCOPE_SCRAPER_IMPLEMENTATION.md)
- [NVIDIA 爬虫实现](docs/NVIDIA_SCRAPER_README.md)
- [OpenRouter 爬虫实现](docs/OPENROUTER_SCRAPER_README.md)
