# 插件配置迁移指南

## 概述

本次重构将插件参数从语义化配置改为通用 HTTP 请求配置，提高了配置的透明度和灵活性。

## 主要变化

### 1. 配置结构调整

**旧配置（已废弃）：**
```yaml
plugin:
  code: "plugin.openrouter"
  args:
    category: "free"
    input_modalities: ["text"]
    output_modalities: ["text"]
    cache_timeout: 300
```

**新配置：**
```yaml
plugin:
  code: "plugin.openrouter"
  cache_timeout: 300  # 移至 plugin 级别
  args:
    model_list_url: "https://openrouter.ai/api/v1/models"
    model_list_method: "GET"
    request_params:
      max_price: 0  # 直接使用 API 原生参数
    model_list_headers: {}
```

### 2. cache_timeout 位置变更

- **旧位置**: `plugin.args.cache_timeout`
- **新位置**: `plugin.cache_timeout`（与 `code` 同级）

**原因**: `cache_timeout` 是插件行为配置，不是 API 请求参数。

### 3. 移除语义转换逻辑

所有隐式的参数转换已被移除，配置直接映射到 API 请求：

| 平台 | 旧配置 | 新配置 |
|------|--------|--------|
| OpenRouter | `category: "free"` | `request_params.max_price: 0` |
| ModelScope | 后端过滤 `SupportInference` | 保持不变（在代码中过滤） |
| NVIDIA | 硬编码模式匹配 | `request_params.nim_type: "anim_type_preview"` |

## 各平台迁移示例

### OpenRouter

**迁移前：**
```yaml
openrouter:
  baseUrl: "https://openrouter.ai/api/v1"
  apiKey: "${OPENROUTER_API_KEY}"
  plugin:
    code: "plugin.openrouter"
    args:
      category: "free"
      input_modalities: ["text"]
      output_modalities: ["text"]
      cache_timeout: 300
```

**迁移后：**
```yaml
openrouter:
  baseUrl: "https://openrouter.ai/api/v1"
  apiKey: "${OPENROUTER_API_KEY}"
  plugin:
    code: "plugin.openrouter"
    cache_timeout: 300
    args:
      model_list_url: "https://openrouter.ai/api/v1/models"
      model_list_method: "GET"
      request_params:
        max_price: 0  # 0 = 免费模型
      model_list_headers: {}
```

**说明：**
- `max_price: 0` 表示只获取完全免费的模型
- 也可以使用 `categories: "free"` 参数（参考 OpenRouter API 文档）

### ModelScope

**迁移前：**
```yaml
modelscope:
  baseUrl: "https://dashscope.aliyuncs.com/api/v1"
  apiKey: "${MODELSCOPE_API_KEY}"
  plugin:
    code: "plugin.modelscope"
    args:
      cache_timeout: 300
```

**迁移后：**
```yaml
modelscope:
  baseUrl: "https://dashscope.aliyuncs.com/api/v1"
  apiKey: "${MODELSCOPE_API_KEY}"
  plugin:
    code: "plugin.modelscope"
    cache_timeout: 300
    args:
      model_list_url: "https://modelscope.cn/api/v1/models"
      model_list_method: "GET"
      request_params:
        page: 1
        page_size: 100
        model_type: "text-generation"
      model_list_headers: {}
```

**说明：**
- ModelScope 的免费模型过滤仍在代码中进行（基于 `SupportInference` 字段）
- 配置中的参数用于控制 API 请求（分页、模型类型等）

### NVIDIA

**迁移前：**
```yaml
nvidia:
  baseUrl: "https://integrate.api.nvidia.com/v1"
  apiKey: "${NVIDIA_API_KEY}"
  plugin:
    code: "plugin.nvidia"
    args:
      cache_timeout: 300
```

**迁移后：**
```yaml
nvidia:
  baseUrl: "https://integrate.api.nvidia.com/v1"
  apiKey: "${NVIDIA_API_KEY}"
  plugin:
    code: "plugin.nvidia"
    cache_timeout: 300
    args:
      model_list_url: "https://integrate.api.nvidia.com/v1/models"
      model_list_method: "GET"
      request_params:
        nim_type: "anim_type_preview"  # 免费预览模型
      model_list_headers: {}
```

**说明：**
- `nim_type: "anim_type_preview"` 表示只获取免费预览模型
- `nim_type: "anim_type_full"` 表示获取完整付费模型
- 移除了之前的硬编码模式匹配逻辑

## 配置字段说明

### plugin.args 字段

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `model_list_url` | string | 是 | 模型列表 API 的完整 URL |
| `model_list_method` | string | 否 | HTTP 方法，默认 "GET"，可选 "POST" |
| `request_params` | object | 否 | GET 请求的查询参数（URL 参数） |
| `request_body` | object | 否 | POST/PUT/PATCH 请求的请求体 |
| `model_list_headers` | object | 否 | 额外的 HTTP Headers |

### plugin 级别字段

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `code` | string | 是 | 插件类路径 |
| `cache_timeout` | int | 否 | 缓存有效期（秒），默认 300 |

## 常见问题

### Q1: 为什么移除语义化参数？

**A:** 语义化参数（如 `category: "free"`）需要在代码中进行隐式转换，导致：
- 配置不透明，用户不知道实际发送了什么参数
- 难以维护，API 变化需要修改代码
- 不可扩展，无法适配所有平台的原生参数

新配置直接使用 API 原生参数，更加透明和灵活。

### Q2: 如何知道应该使用哪些参数？

**A:** 查阅对应平台的 API 文档：
- OpenRouter: https://openrouter.ai/docs#models
- ModelScope: https://modelscope.cn/docs
- NVIDIA: https://docs.api.nvidia.com/

配置中的 `request_params` 应该直接使用 API 文档中定义的参数名和值。

### Q3: 支持 POST 请求吗？

**A:** 支持。设置 `model_list_method: "POST"` 并使用 `request_body` 字段：

```yaml
args:
  model_list_url: "https://api.example.com/models"
  model_list_method: "POST"
  request_body:
    filter:
      type: "free"
  model_list_headers:
    Content-Type: "application/json"
```

### Q4: 缓存是如何工作的？

**A:** 
- 每个不同的 `plugin_config` 创建独立的插件实例
- 每个实例有独立的缓存
- 缓存基于完整的响应数据
- `cache_timeout` 控制缓存有效期

### Q5: 如果配置错误会怎样？

**A:** 
- 基类会进行基本验证（如 URL 是否存在）
- 验证失败会输出警告日志，但不会阻止运行
- API 调用失败时会返回空列表或使用缓存

## 下一步

1. 根据你的平台选择对应的迁移示例
2. 更新 `models.yaml` 配置文件
3. 重启服务验证配置
4. 查看日志确认模型列表正确获取

如有问题，请查看日志或参考各平台的 API 文档。
