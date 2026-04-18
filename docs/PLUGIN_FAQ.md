# 插件配置常见问题 (FAQ)

## 通用问题

### Q1: 如何配置插件获取模型列表?

**A:** 在 `models.yaml` 中为平台添加 `plugin` 配置段:

```yaml
openrouter:
  baseUrl: "https://openrouter.ai/api/v1"
  apiKey: "${OPENROUTER_API_KEY}"
  plugin:
    code: "plugin.openrouter"
    cache_timeout: 300 # 缓存时间(秒)
    args:
      model_list_method: "GET"
      request_params:
        max_price: 0 # 只获取免费模型
```

### Q2: `cache_timeout` 应该放在哪里?

**A:** `cache_timeout` 必须放在 `plugin` 的顶层,与 `code` 同级,**不能**放在 `args` 中:

```yaml
# ✅ 正确
plugin:
  code: "plugin.openrouter"
  cache_timeout: 300  # ← 这里
  args:
    ...

# ❌ 错误
plugin:
  code: "plugin.openrouter"
  args:
    cache_timeout: 300  # ← 不会被读取
```

### Q3: 如何配置不同的 HTTP 方法?

**A:** 使用 `model_list_method` 字段指定:

```yaml
# GET 请求(默认)
args:
  model_list_method: "GET"
  request_params:
    category: "free"

# POST 请求
args:
  model_list_method: "POST"
  request_body:
    filter:
      type: "chat"
```

### Q4: 如何添加自定义 Headers?

**A:** 使用 `model_list_headers` 字段:

```yaml
args:
  model_list_headers:
    X-Custom-Header: "custom-value"
    X-Another-Header: "another-value"
```

注意: `Authorization` Header 会自动添加,无需手动配置。

---

## OpenRouter 特定问题

### Q5: 如何获取 OpenRouter 的免费模型?

**A:** 配置 `max_price: 0` 参数:

```yaml
plugin:
  code: "plugin.openrouter"
  cache_timeout: 300
  args:
    model_list_method: "GET"
    request_params:
      max_price: 0 # 只获取免费模型
```

### Q6: 可以按类别过滤模型吗?

**A:** 可以,使用 `categories` 参数:

```yaml
args:
  request_params:
    categories: "programming" # 编程类模型
```

支持的类别包括: `programming`, `storytelling`, `roleplay` 等。

### Q7: 旧的 `category: "free"` 配置还能用吗?

**A:** **不能**。新版本已完全废弃旧的语义化参数,必须迁移到新的 `request_params` 结构。

**迁移示例:**

```yaml
# ❌ 旧配置(不再支持)
plugin:
  args:
    category: "free"

# ✅ 新配置
plugin:
  args:
    request_params:
      max_price: 0
```

---

## NVIDIA 特定问题

### Q8: 如何获取 NVIDIA 的免费预览模型?

**A:** 配置 `nim_type: "anim_type_preview"` 参数:

```yaml
nvidia:
  baseUrl: "https://integrate.api.nvidia.com/v1"
  apiKey: "${NVIDIA_API_KEY}"
  plugin:
    code: "plugin.nvidia"
    cache_timeout: 3600
    args:
      model_list_method: "GET"
      request_params:
        nim_type: "anim_type_preview" # 获取预览版(免费)模型
```

### Q9: 为什么我的 NVIDIA 模型列表是空的?

**A:** 可能的原因:

1. **未配置 `nim_type` 参数**: NVIDIA API 需要明确指定模型类型
2. **API Key 无效**: 检查环境变量 `NVIDIA_API_KEY` 是否正确
3. **网络问题**: 确认可以访问 `https://integrate.api.nvidia.com`

**调试步骤:**

```bash
# 启用 DEBUG 日志
export LOG_LEVEL=DEBUG

# 重新启动服务,查看详细的请求和响应信息
python run.py
```

---

## ModelScope 特定问题

### Q10: 如何获取 ModelScope 的免费模型?

**A:** 配置 `SupportInference` 参数:

```yaml
modelscope:
  baseUrl: "https://modelscope.cn/api/v1"
  apiKey: "${MODELSCOPE_API_KEY}"
  plugin:
    code: "plugin.modelscope"
    cache_timeout: 3600
    args:
      model_list_method: "GET"
      request_params:
        SupportInference: "txt2txt" # 文本生成模型
```

支持的推理类型: `txt2txt`(文本生成), `txt2img`(文生图) 等。

---

## 缓存相关问题

### Q11: 如何禁用缓存?

**A:** 设置 `cache_timeout: 0`:

```yaml
plugin:
  code: "plugin.openrouter"
  cache_timeout: 0 # 禁用缓存,每次都从 API 获取
  args: ...
```

### Q12: 不同平台的缓存会相互影响吗?

**A:** **不会**。每个插件配置都会创建独立的实例,缓存完全隔离:

```yaml
# 这两个配置使用不同的缓存
openrouter_free:
  plugin:
    code: "plugin.openrouter"
    cache_timeout: 300
    args:
      request_params:
        max_price: 0 # 免费模型

openrouter_paid:
  plugin:
    code: "plugin.openrouter"
    cache_timeout: 300
    args:
      request_params:
        max_price: 0.01 # 付费模型
```

### Q13: 缓存什么时候会被清除?

**A:** 缓存在以下情况会被清除:

1. **过期**: 超过 `cache_timeout` 指定的时间
2. **服务重启**: 缓存存储在内存中,重启后丢失
3. **手动清除**: 调用插件的 `clear_cache()` 方法

---

## 环境变量相关问题

### Q14: 如何在配置中使用环境变量?

**A:** 使用 `${VAR_NAME}` 语法:

```yaml
openrouter:
  baseUrl: "https://openrouter.ai/api/v1"
  apiKey: "${OPENROUTER_API_KEY}" # 从环境变量读取
```

在 `.env` 文件中定义:

```bash
OPENROUTER_API_KEY=sk-or-your-api-key
```

### Q15: 如果环境变量不存在会怎样?

**A:** 占位符会保留原样,可能导致 API 认证失败:

```yaml
# 如果 OPENROUTER_API_KEY 未定义
apiKey: "${OPENROUTER_API_KEY}" # ← 保持原样,不会替换
```

建议在启动前检查所有必需的环境变量是否已设置。

---

## 故障排查

### Q16: 插件加载失败,日志显示 "Module not found"?

**A:** 检查 `plugin.code` 配置是否正确:

```yaml
# ✅ 正确的模块路径
plugin:
  code: "plugin.openrouter"  # 对应 plugin/openrouter.py

# ❌ 错误的路径
plugin:
  code: "openrouter"  # 缺少 plugin. 前缀
```

### Q17: 模型列表为空,但没有报错?

**A:** 可能的原因:

1. **API 返回空列表**: 检查过滤参数是否过于严格
2. **缓存为空且 API 调用失败**: 启用 DEBUG 日志查看详细错误
3. **响应解析失败**: 检查 API 响应格式是否符合预期

**调试命令:**

```bash
export LOG_LEVEL=DEBUG
python run.py
```

### Q18: 如何验证配置是否正确?

**A:** 启动服务后检查日志:

```bash
# 成功加载插件
INFO - 插件 plugin.openrouter 成功加载 50 个模型

# 配置警告
WARNING - OpenRouter 配置警告: POST 请求未配置 request_body
```

---

## 迁移指南

### Q19: 从旧版本迁移需要注意什么?

**A:** 主要变更:

1. **`cache_timeout` 位置变更**: 从 `args.cache_timeout` 移至 `plugin.cache_timeout`
2. **参数结构变更**: 移除语义化参数,使用原生 HTTP 参数
3. **BREAKING CHANGE**: 旧配置完全不兼容,必须迁移

**完整迁移示例:**

```yaml
# ❌ 旧配置(2.x 版本)
plugin:
  code: "plugin.openrouter"
  args:
    category: "free"
    cache_timeout: 300

# ✅ 新配置(3.x 版本)
plugin:
  code: "plugin.openrouter"
  cache_timeout: 300  # ← 移到顶层
  args:
    model_list_method: "GET"
    request_params:
      max_price: 0  # ← 直接使用 API 参数
```

详见 [MIGRATION_GUIDE.md](./MIGRATION_GUIDE.md)。

---

## NVIDIA 爬虫功能

### Q15: NVIDIA 插件如何获取免费模型列表?

**A:** NVIDIA 插件使用 Playwright 网页爬虫从 build.nvidia.com 自动抓取免费预览模型。爬虫始终启用，无需额外配置：

```yaml
nvidia:
  baseUrl: "https://integrate.api.nvidia.com/v1"
  apiKey: "${NVIDIA_API_KEY}"
  plugin:
    code: "plugin.nvidia"
    cache_timeout: 3600
    args:
      free_model_count: 10 # 获取前10个免费模型
      cache_file: "data/nvidia_free_models.json"
      enable_scheduled_task: true # 启用定时更新
      schedule_cron: "0 2 * * *" # 每天凌晨2点
```

### Q16: 爬虫多久更新一次模型列表?

**A:** 默认策略：

- **服务启动时**：立即执行一次抓取
- **定时任务**：每天凌晨 2:00 自动更新
- **手动触发**：重启服务也会触发更新

可以通过 `schedule_cron` 自定义更新时间，例如：

- `"0 3 * * *"` - 每天凌晨3点
- `"0 */6 * * *"` - 每6小时
- `"0 0 * * 0"` - 每周日凌晨

### Q17: 如果爬虫失败会怎么办?

**A:** 系统采用三层降级策略：

1. **优先使用缓存**：如果之前成功抓取过，使用缓存数据
2. **回退到API**：如果缓存不存在，调用API获取所有模型并智能过滤
3. **返回空列表**：如果都失败，返回空列表并记录错误

错误信息会记录在日志和缓存文件的 `error_log` 字段中。

### Q18: 如何查看爬虫运行状态?

**A:** 有两种方式：

1. **查看日志**：

   ```bash
   # 查看爬虫相关日志
   grep -i "scraper\|crawler\|nvidia" logs/app.log
   ```

2. **健康检查端点**（如果已实现）：
   ```bash
   curl http://localhost:8000/health | jq '.plugins.nvidia.scraper'
   ```

### Q19: 缓存文件在哪里？可以手动编辑吗?

**A:**

- **默认位置**：`data/nvidia_free_models.json`
- **文件格式**：JSON，人类可读
- **可以编辑**：是的，但建议通过配置修改参数而非手动编辑

缓存文件结构：

```json
{
  "models": [
    {
      "model_id": "deepseek-ai/deepseek-v3.2",
      "model_name": "...",
      "rank": 1
    }
  ],
  "metadata": {
    "fetch_time": 1234567890,
    "total_count": 10
  },
  "last_success": "2026-04-18T02:00:00+00:00",
  "error_log": []
}
```

### Q20: 为什么获取的免费模型数量不对?

**A:** 可能的原因：

1. **配置问题**：检查 `free_model_count` 参数（默认10，范围1-100）
2. **API限制**：NVIDIA API可能临时不可用
3. **过滤规则**：内置的免费模型识别规则可能需要更新
4. **缓存过期**：删除缓存文件后重新抓取

调试步骤：

```bash
# 1. 删除缓存
rm data/nvidia_free_models.json

# 2. 重启服务
python run.py

# 3. 查看日志
grep "NVIDIA" logs/app.log | tail -50
```

### Q21: 爬虫会影响服务性能吗?

**A:** 不会，因为：

- **异步执行**：爬虫在后台运行，不阻塞主服务
- **缓存优先**：大部分时间直接从缓存读取，速度极快
- **超时控制**：默认60秒超时，防止长时间等待
- **资源管理**：浏览器实例用完即关闭

---

## 获取帮助

如果以上 FAQ 无法解决您的问题:

1. **查看日志**: 启用 DEBUG 级别日志获取详细信息
2. **检查文档**: 阅读 [插件配置指南](./plugin_configuration.md)
3. **提交 Issue**: 在 GitHub 仓库提交问题,附上配置文件和日志
