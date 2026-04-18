# OpenRouter 免费模型爬虫

## 概述

OpenRouter 插件现在支持使用网页爬虫从 OpenRouter 网站直接获取免费模型列表，而无需依赖 API 密钥。

## 功能特性

- ✅ 使用 Playwright 浏览器自动化技术
- ✅ 从网页动态提取免费模型
- ✅ 自动过滤和去重
- ✅ 按人气排序
- ✅ 自动添加 `:free` 后缀
- ✅ 支持缓存机制
- ✅ 失败时回退到 API 方式

## 配置示例

在 `models.yaml` 中配置：

```yaml
openrouter:
  baseUrl: "https://openrouter.ai/api/v1"
  apiKey: "${OPENROUTER_API_KEY}" # 可选，作为备用
  plugin:
    code: "plugin.openrouter"
    cache_timeout: 3600 # 缓存过期时间（秒）
    args:
      # 爬虫配置
      scrape_url: "https://openrouter.ai/models?fmt=cards&input_modalities=text%2Cimage&max_price=0&order=most-popular&output_modalities=text"
      max_models: 50 # 最大模型数量
      scraper_timeout: 60 # 爬虫超时时间（秒）
      headless: true # 无头模式运行浏览器
  models: [] # 静态配置的模型（可选）
  timeout: 10
  weight: 1
  enabled: true
```

## 工作原理

1. **优先使用爬虫**：如果配置了 `scrape_url`，插件会首先尝试使用爬虫从网页获取模型
2. **数据提取**：爬虫会分析页面链接，提取模型 ID（格式：`publisher/model-name`）
3. **过滤处理**：
   - 排除非模型路径（如 `/docs`, `/chat`, `/pricing` 等）
   - 去重
   - 按发现顺序排序
   - 截取指定数量的模型
4. **格式化**：为每个模型 ID 添加 `:free` 后缀
5. **缓存**：结果会被缓存，避免频繁爬取
6. **回退机制**：如果爬虫失败且有 API 密钥，会回退到 API 方式

## URL 参数说明

爬虫 URL 包含以下参数：

- `fmt=cards`: 以卡片格式显示
- `input_modalities=text%2Cimage`: 输入模态（文本、图像）
- `max_price=0`: 只显示免费模型
- `order=most-popular`: 按人气排序
- `output_modalities=text`: 输出模态（文本）

你可以根据需要调整这些参数。

## 测试

运行集成测试：

```bash
python tests/test_openrouter_plugin_integration.py
```

运行基本功能测试：

```bash
PYTHONPATH=. python tests/test_openrouter_scraper_simple.py
```

调试页面结构：

```bash
python tests/debug_openrouter_page.py
```

## 注意事项

1. **首次运行较慢**：首次运行时 Playwright 需要加载浏览器，可能需要 10-30 秒
2. **资源消耗**：爬虫会启动 Chromium 浏览器，消耗一定内存
3. **网络依赖**：需要能够访问 openrouter.ai
4. **页面结构变化**：如果 OpenRouter 网站结构发生变化，可能需要更新爬虫代码

## 故障排除

### 爬虫无法获取模型

1. 检查网络连接
2. 确认 URL 是否正确
3. 查看日志中的错误信息
4. 尝试增加 `scraper_timeout` 值

### 获取的模型数量为 0

1. 确认 URL 参数正确（特别是 `max_price=0`）
2. 检查页面是否真的包含免费模型
3. 运行调试脚本查看页面结构

### 性能问题

1. 启用 `headless=true` 减少资源消耗
2. 适当增加 `cache_timeout` 减少爬取频率
3. 减少 `max_models` 数量

## 技术实现

- **基类**: `WebScraper` - 通用网页爬虫框架
- **实现类**: `OpenRouterModelScraper` - OpenRouter 专用爬虫
- **提取策略**:
  1. 尝试从嵌入 JSON 中提取
  2. 尝试从 DOM 元素中提取
  3. 从页面链接中提取（最可靠）

## 未来改进

- [ ] 支持更多提取策略
- [ ] 添加模型详细信息（上下文长度、能力等）
- [ ] 支持自定义过滤规则
- [ ] 添加重试间隔配置
- [ ] 支持代理设置
