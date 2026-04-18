# NVIDIA 免费模型爬虫功能 - 使用指南

## 📋 概述

NVIDIA 插件使用 Playwright 网页爬虫从 build.nvidia.com 自动抓取免费预览模型列表，确保只获取真正的免费模型（`nim_type_preview`）。

**重要：** 必须在配置文件中指定 `scrape_url` 参数，否则爬虫无法初始化。

## ✨ 特性

### 1. 准确的免费模型识别

- 直接从 build.nvidia.com 页面抓取
- 自动过滤出免费预览模型（`nim_type_preview`）
- 按人气排序，默认返回前10个
- 支持自定义数量（1-100个）

### 2. 自动化更新

- 服务启动时自动执行一次抓取
- 每天凌晨2点定时更新（可配置）
- 失败自动重试机制
- 优雅的资源管理

### 3. 可靠的缓存系统

- JSON文件持久化存储
- 原子写入防止数据损坏
- 自动验证数据完整性
- 详细的错误日志记录

### 4. 简单的工作流程

```
服务启动
    ↓
初始化网页爬虫
    ↓
执行首次抓取 → 保存到 data/nvidia_free_models.json
    ↓
后续请求 → 直接从缓存读取（快速响应）
    ↓
定时任务 → 每天凌晨2点更新缓存
```

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
playwright install chromium
```

### 2. 配置 models.yaml

```yaml
nvidia:
  baseUrl: "https://integrate.api.nvidia.com/v1"
  apiKey: "${NVIDIA_API_KEY}"
  plugin:
    code: "plugin.nvidia"
    cache_timeout: 3600 # 缓存过期时间（秒）
    args:
      # 爬虫配置（始终启用网页爬虫模式）
      scrape_url: "https://build.nvidia.com/models?filters=nimType%3Anim_type_preview&orderBy=weightPopular%3ADESC" # 爬虫URL（可选）
      free_model_count: 10 # 获取的免费模型数量
      cache_file: "data/nvidia_free_models.json" # 缓存文件路径
      scraper_timeout: 60 # 超时时间（秒）
      headless: true # 无头模式

      # 定时任务配置
      enable_scheduled_task: true # 启用定时更新
      schedule_cron: "0 2 * * *" # 每天凌晨2点
  timeout: 30
  weight: 5
  enabled: true
```

**配置说明：**

- `scrape_url`: 自定义爬虫URL，如果不配置则使用默认值。可以修改此参数来抓取不同的模型列表页面。
- `free_model_count`: 返回的模型数量，范围 1-100
- `cache_file`: 缓存文件存储路径
- `scraper_timeout`: 爬虫超时时间，范围 10-300 秒

### 3. 启动服务

```bash
python run.py
```

服务启动时会自动执行一次模型抓取，并将结果保存到 `data/nvidia_free_models.json`。

## 📁 新增文件

### 核心模块

- `openai_proxy/core/web_scraper.py` - 通用网页爬虫基类
- `openai_proxy/core/nvidia_scraper.py` - NVIDIA专用爬虫
- `openai_proxy/core/model_cache.py` - 缓存管理器
- `openai_proxy/core/scheduled_scraper.py` - 定时任务调度器

### 配置文件

- `data/` - 缓存文件目录（自动创建）
- `data/nvidia_free_models.json` - 模型缓存文件（运行时生成）

### 修改文件

- `plugin/nvidia.py` - 集成爬虫功能
- `requirements.txt` - 添加 playwright 和 apscheduler
- `Dockerfile` - 添加 Playwright 浏览器安装
- `.gitignore` - 排除缓存文件

## 🔧 配置参数说明

| 参数                    | 类型   | 默认值                         | 说明                        |
| ----------------------- | ------ | ------------------------------ | --------------------------- |
| `scrape_url`            | string | 见下方默认URL                  | 爬虫URL（可选配置）         |
| `free_model_count`      | int    | 10                             | 获取的免费模型数量（1-100） |
| `cache_file`            | string | "data/nvidia_free_models.json" | 缓存文件路径                |
| `scraper_timeout`       | int    | 60                             | 爬虫超时时间（秒，10-300）  |
| `headless`              | bool   | true                           | 是否无头模式运行浏览器      |
| `enable_scheduled_task` | bool   | true                           | 是否启用定时任务            |
| `schedule_cron`         | string | "0 2 \* \* \*"                 | cron表达式，控制更新时间    |

**默认爬虫URL：**

```
https://build.nvidia.com/models?filters=nimType%3Anim_type_preview&orderBy=weightPopular%3ADESC
```

## 📊 监控和调试

### 查看爬虫状态

```bash
# 查看相关日志
grep -i "nvidia\|scraper" logs/app.log | tail -50

# 检查缓存文件
cat data/nvidia_free_models.json | jq '.metadata'

# 查看错误日志
cat data/nvidia_free_models.json | jq '.error_log'
```

### 常见问题

**Q: 为什么没有获取到模型？**
A: 检查以下几点：

1. NVIDIA_API_KEY 是否正确配置
2. 网络连接是否正常（需要访问 build.nvidia.com）
3. 查看日志中的错误信息
4. Playwright 浏览器是否已安装：`playwright install chromium`
5. 尝试删除缓存文件后重启：`rm data/nvidia_free_models.json`

**Q: 首次启动时为什么返回空列表？**
A: 服务启动时会先执行爬虫任务，这需要一些时间（通常 10-30 秒）。请等待首次抓取完成后再使用。可以查看日志确认：

```bash
grep "NVIDIA网页爬虫\|爬虫任务" logs/app.log
```

**Q: 如何手动触发更新？**
A: 重启服务即可，或者删除缓存文件后重启：

```bash
rm data/nvidia_free_models.json
python run.py
```

**Q: 爬虫会影响性能吗？**
A: 不会。爬虫在后台异步执行，不阻塞主服务。大部分时间直接从缓存读取，速度极快（毫秒级响应）。

更多问题请查看 [PLUGIN_FAQ.md](./docs/PLUGIN_FAQ.md) 中的 "NVIDIA 爬虫功能" 章节。

## 🧪 测试

运行测试脚本验证功能：

```bash
python test_nvidia_scraper.py
```

预期输出：

```
=== 测试 1: WebScraper 基类 ===
✓ WebScraper 测试成功

=== 测试 2: ModelCacheManager ===
✓ 缓存保存成功
✓ 缓存验证通过
✓ 缓存加载成功

=== 测试 3: NVIDIAModelScraper ===
✓ 成功获取 5 个免费模型

总计: 3/3 测试通过 🎉
```

## 🔄 升级说明

### 从旧版本升级

1. **备份配置**：备份现有的 `models.yaml`
2. **安装依赖**：`pip install -r requirements.txt`
3. **安装浏览器**：`playwright install chromium`
4. **更新配置**：在 `models.yaml` 中添加爬虫配置
5. **重启服务**：`python run.py`

### 兼容性

- ✅ 完全向后兼容
- ✅ 不影响其他平台配置
- ✅ 可选启用/禁用定时任务

## 📝 技术细节

### 架构设计

```
┌─────────────────┐
│  NVIDIA Plugin  │
└────────┬────────┘
         │
    ┌────▼──────────────┐
    │  Cache Manager    │ ← 优先从缓存读取
    └────┬──────────────┘
         │ 缓存失效或不存在
    ┌────▼──────────────┐
    │ Web Scraper       │ ← Playwright 网页爬虫
    │ (build.nvidia.com)│
    └────┬──────────────┘
         │
    ┌────▼──────────────┐
    │ Scheduled Task    │ ← 定时更新
    └───────────────────┘
```

### 免费模型识别方式

通过访问 `build.nvidia.com/models?filters=nimType%3Anim_type_preview` 页面，直接获取标记为免费预览的模型。这种方式比 API 过滤更准确，因为：

1. **官方标识**：直接使用 NVIDIA 官方的免费模型标识
2. **实时数据**：反映当前实际的免费模型列表
3. **按人气排序**：自动按受欢迎程度排序

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📄 许可证

与原项目保持一致。

---

**更新日期**: 2026-04-18  
**版本**: v1.0.0
