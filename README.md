# imgInfo - 专利视觉资料分析与可控生成工作台

imgInfo 是一个面向专利撰写、技术交底整理和附图优化场景的本地 Web 工作台。系统围绕“上传图片 → 视觉分析 → 专利要素结构化 → 编辑计划 → 可控图像生成 → 结果审阅”的闭环设计，帮助把原始截图、产品照片、结构图、流程图等视觉资料转化为更适合专利沟通和申请准备的图像资产。

当前版本重点支持 OpenRouter，可调用 `openai/gpt-5.4-image-2` 等多模态图片模型；同时保留 OpenAI、阿里云 DashScope、自定义 OpenAI 兼容接口等配置入口。系统强调可审阅、可追踪和可控生成：每次生成前会先形成编辑计划，生成结果会记录实际 provider/model，便于判断成本、路径和输出来源。

## 产品定位

imgInfo 不是通用图库或简单文生图页面，而是一个面向专利图像工作流的专业辅助系统：

- **面向专利材料准备**：围绕技术特征、可见事实、组件关系和专利表达建议组织分析结果。
- **面向受控图像编辑**：先生成编辑计划，再执行图生图或文生图，降低模型随意重绘带来的不确定性。
- **面向模型供应商适配**：将 OpenRouter、OpenAI、DashScope 和自定义兼容 API 封装到统一服务层。
- **面向可追踪交付**：上传源图、分析记录、编辑计划、生成结果和调用模型均可回看。
- **面向本地运行**：默认 SQLite + 本地文件存储，方便在个人机器或内网环境中快速部署。

## 系统能力

- **图片上传与管理**
  - 支持 JPG、JPEG、PNG、BMP、GIF、TIFF、WebP。
  - 默认单文件最大 10MB。
  - 默认分辨率范围 100x100 到 8192x8192。
  - 上传文件按日期和时间目录存储，生成图片统一进入 `uploads/generated/`。

- **专利角度图片分析**
  - 使用视觉模型读取图片内容，并结合用户补充上下文进行解释。
  - 输出结构化图片上下文、可见事实、组件列表、技术特征和专利撰写建议。
  - 支持用户补充技术交底、权利要求、说明书片段等上下文。
  - 提供同步分析和异步任务分析接口。

- **编辑计划**
  - **快速计划**：本地规则生成，秒回，不调用模型，不产生额外成本，适合高频预览。
  - **AI计划**：调用当前配置的视觉模型，结合原图、分析结果和用户指令生成更具体的编辑策略。
  - 两种计划都会转成统一的执行约束，包括必须保留、允许修改、禁止修改、风险提示。
  - AI 计划会请求 JSON 结构化输出；若模型返回非 JSON 内容，系统会自动回退到快速计划并保留原始建议摘要。

- **图片生成与编辑**
  - **云端图生图**：参考原图执行修改，适合保持风格但做可见优化。
  - **云端文生图**：基于分析结果重新生成新的专利技术插图。
  - **本地保真增强**：不调用外部模型，只做锐化、对比度和清晰度增强。
  - 生成结果会记录实际 provider 和 model，方便确认是否真的调用了 OpenRouter。

- **运行时设置**
  - 前端设置页可切换 provider、API base、API key、视觉模型、图片模型。
  - 支持连接测试。
  - 设置接口会对 API key 做脱敏展示。

- **响应式工作台界面**
  - 默认入口为“工作台”，按导入、上下文、分析与计划、生成审阅组织闭环流程。
  - “资料库”聚合源图资产、生成版本和分析记录，生成版本采用紧凑列表，点击后进入大图 Review。
  - 移动端提供底部主导航和资料库内部分段切换，避免长列表把页面垂直拉长。

## 架构概览

系统采用轻量分层架构：

- **Web 层**：FastAPI 路由提供上传、分析、生成、设置和任务状态接口；`index.html` 提供单页操作界面。
- **服务层**：`llm_service.py` 统一封装模型调用，`image_edit_plan.py` 管理编辑计划，`image_edit_executor.py` 决定实际执行器。
- **数据层**：SQLAlchemy 模型记录图片、分析结果和生成路径；SQLite 作为默认本地数据库。
- **文件层**：源图和生成图保存在 `uploads/`，通过 FastAPI static mount 暴露预览 URL。
- **任务层**：异步分析和生成通过内存 task store 暴露状态，适合本地交互和短任务流。

## 技术栈

- Python 3.12+
- FastAPI
- SQLAlchemy + SQLite
- Pydantic / pydantic-settings
- httpx
- Pillow
- Jinja2 + 原生 HTML/CSS/JavaScript
- uv
- Uvicorn

## 项目结构

```text
imgInfo/
├── app/
│   ├── main.py                         # FastAPI 应用入口
│   ├── config.py                       # 环境变量和运行配置
│   ├── database.py                     # SQLite/SQLAlchemy 配置
│   ├── models/
│   │   ├── image.py                    # 图片记录
│   │   └── analysis.py                 # 分析与生成记录
│   ├── routers/
│   │   ├── upload.py                   # 上传、图片列表、图片删除
│   │   ├── analysis.py                 # 图片分析
│   │   ├── generate.py                 # 编辑计划、生成、生成历史
│   │   ├── settings_router.py          # 运行时设置
│   │   └── tasks.py                    # 异步任务状态
│   ├── services/
│   │   ├── llm_service.py              # OpenRouter/OpenAI/DashScope 等模型调用
│   │   ├── analysis_parser.py          # 分析结果解析与结构化
│   │   ├── image_edit_executor.py      # 执行器选择与本地增强
│   │   ├── image_edit_plan.py          # 快速计划与 AI 计划合并
│   │   ├── storage_paths.py            # 上传文件 URL 转换
│   │   └── task_store.py               # 内存任务状态
│   └── templates/
│       └── index.html                  # 单页前端
├── tests/                              # 单元测试
├── uploads/                            # 上传和生成图片
├── .env.example                        # 环境变量示例
├── pyproject.toml
├── uv.lock
└── README.md
```

## 快速开始

### 1. 安装依赖

```bash
uv sync
```

### 2. 配置环境变量

```bash
cp .env.example .env
```

推荐 OpenRouter 配置：

```env
API_PROVIDER="openrouter"

OPENROUTER_API_KEY="sk-or-v1-..."
OPENROUTER_API_BASE="https://openrouter.ai/api/v1"
OPENROUTER_VISION_MODEL="openai/gpt-5.4-image-2"
OPENROUTER_IMAGE_MODEL="openai/gpt-5.4-image-2"

IMAGE_SIZE="1024x1024"
IMAGE_QUALITY="standard"
IMAGE_STYLE="natural"
VISION_DETAIL="high"
VISION_MAX_TOKENS=4096
```

不要把真实 `.env` 或 API key 提交到 Git。

### 3. 启动服务

```bash
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
```

访问：

- Web 页面：http://127.0.0.1:8000
- API 文档：http://127.0.0.1:8000/docs
- 健康检查：http://127.0.0.1:8000/health

## 标准工作流

1. **上传源图**：提交截图、流程图、产品照片或结构示意图，系统完成格式、大小和分辨率校验。
2. **补充上下文**：输入技术交底、权利要求片段、说明书段落或图片来源说明，作为模型分析的确定性参考。
3. **执行视觉分析**：模型提取图片类型、可见事实、组件关系、技术特征和专利撰写建议。
4. **输入编辑目标**：描述希望生成的结果，例如“突出数据流向，增加步骤编号，保持白底界面风格”。
5. **选择生成策略**：
   - 保持原图风格优化：适合对已有图片做受控改造。
   - 生成新的技术插图：适合从原始材料重组为专利附图。
6. **选择执行器**：
   - 云端图生图：参考原图并执行计划。
   - 云端文生图：基于分析结果重新生成画面。
   - 本地保真增强：只做清晰度增强，不调用外部模型。
7. **生成编辑计划**：
   - 快速计划用于低成本预览。
   - AI计划用于更细致的模型参与式规划。
8. **确认并执行**：前端会把当前确认的计划带入生成请求，确保预览和执行一致。
9. **审阅生成结果**：检查图片、prompt、provider/model 和生成路径，确认是否满足专利用途。

## 前端界面组织

单页前端围绕三个主入口组织：

- **工作台**：承载当前任务，从图片导入到分析、编辑计划、生成和结果审阅。
- **资料库**：高密度资产视图，左侧为源图紧凑网格，右侧为生成版本列表；分析记录默认折叠，避免首屏被历史记录拉长。
- **设置**：管理 provider、API key、模型、上传限制和默认生成参数。

资料库中的生成版本默认不展示大图，只显示小缩略图、文件名、尺寸、provider/model 和两行生成指令。点击任意生成版本会打开 Review Modal 查看大图和原始文件。

## Provider 说明

### OpenRouter

OpenRouter 是当前推荐配置。系统对 OpenRouter 做了专门适配，图片生成和图生图走 `/chat/completions`：

- 文生图：请求带 `modalities: ["image", "text"]`。
- 图生图：请求同时带文本指令和原图 data URL。
- 返回图片从 `message.images[].image_url.url` 读取，支持 base64 data URL，后端会保存到本地。
- AI 编辑计划：请求带 `response_format: {"type": "json_object"}`，优先要求模型返回结构化 JSON。

如果 OpenRouter 返回 200 但 `message.images[].image_url.url` 为空，系统会判定为“未返回图片”。这通常表示当前模型或上游 provider 没有按图片输出格式返回结果，常见处理方式是切换为 `cloud_text_to_image`、降低任务复杂度，或改用本地保真增强。

默认模型：

```env
OPENROUTER_VISION_MODEL="openai/gpt-5.4-image-2"
OPENROUTER_IMAGE_MODEL="openai/gpt-5.4-image-2"
```

### OpenAI

OpenAI provider 使用：

- Vision：`/chat/completions`
- 图片生成：`/images/generations`

```env
API_PROVIDER="openai"
OPENAI_API_KEY="sk-..."
OPENAI_API_BASE="https://api.openai.com/v1"
OPENAI_VISION_MODEL="gpt-4o"
OPENAI_IMAGE_MODEL="dall-e-3"
```

### 阿里云 DashScope

当 provider 为 `aliyun` 且图片模型包含 `wanx` 时，后端会使用 DashScope 原生异步任务接口：

- 文生图：`/api/v1/services/aigc/text2image/image-synthesis`
- 图生图：`/api/v1/services/aigc/image2image/image-synthesis`
- 任务轮询：`/api/v1/tasks/{task_id}`

### 自定义 OpenAI 兼容接口

可通过 `custom` provider 连接其他兼容服务：

```env
API_PROVIDER="custom"
CUSTOM_API_BASE="https://example.com/v1"
CUSTOM_API_KEY="..."
CUSTOM_VISION_MODEL="..."
CUSTOM_IMAGE_MODEL="..."
```

## API 设计

所有业务接口默认挂载在 `/api/v1`。接口设计按工作流拆分为五类：上传、分析、计划、生成、配置。同步接口适合调试，异步接口适合前端任务轮询。

### 上传图片

```http
POST /api/v1/upload
POST /api/v1/upload/multiple
GET  /api/v1/images
GET  /api/v1/images/{image_id}
DELETE /api/v1/images/{image_id}
```

### 图片分析

同步分析：

```http
POST /api/v1/analyze
Content-Type: application/json

{
  "image_id": 1,
  "model_name": "default",
  "patent_focus": "general",
  "user_context": "这里可以放技术交底或权利要求片段"
}
```

异步分析：

```http
POST /api/v1/analyze/async
GET  /api/v1/tasks/{task_id}
```

查询分析：

```http
GET /api/v1/analysis/{analysis_id}
GET /api/v1/analyses
```

### 编辑计划

编辑计划接口只负责规划，不执行图片生成。它的输出会被拼入最终生成 prompt，也可以通过 `edit_plan_override` 固化为确认后的执行计划。

快速计划：

```http
POST /api/v1/generate/plan
Content-Type: application/json

{
  "analysis_id": 1,
  "prompt": "突出关键步骤，增加编号标注，保持原图白底风格",
  "mode": "preserve_style",
  "executor": "cloud_image_to_image",
  "plan_mode": "local",
  "style": "technical",
  "width": 1024,
  "height": 1024,
  "num_images": 1
}
```

AI计划：

```json
{
  "analysis_id": 1,
  "prompt": "突出关键步骤，增加编号标注，保持原图白底风格",
  "mode": "preserve_style",
  "executor": "cloud_image_to_image",
  "plan_mode": "ai",
  "style": "technical",
  "width": 1024,
  "height": 1024,
  "num_images": 1
}
```

响应会包含：

- `plan_mode`
- `executor`
- `executor_reason`
- `planner_provider`
- `planner_model`
- `edit_plan`
- 最终会发送给生成模型的 `prompt`

AI 计划返回非 JSON 时不会中断工作流。系统会使用快速计划兜底，并在 `risk_flags` 中写入：

- AI 返回了非 JSON 内容。
- 兜底原因。
- AI 原始建议摘要。

### 图片生成

同步生成：

```http
POST /api/v1/generate
```

异步生成：

```http
POST /api/v1/generate/async
GET  /api/v1/tasks/{task_id}
```

请求示例：

```json
{
  "analysis_id": 1,
  "prompt": "突出关键步骤，增加编号标注，保持原图白底风格",
  "mode": "preserve_style",
  "executor": "cloud_image_to_image",
  "plan_mode": "ai",
  "edit_plan_override": {
    "intent": "突出关键步骤",
    "executor": "cloud_image_to_image",
    "executor_reason": "AI计划：用户选择云端图生图服务，将参考原图执行编辑",
    "source_reference": "source.png (1024x768, png)",
    "must_preserve": ["保留白底界面风格"],
    "allowed_edits": ["增加步骤编号", "强化主按钮层级"],
    "must_not_change": ["不得改成3D渲染"],
    "risk_flags": ["生成后需人工确认文字可读性"]
  },
  "style": "technical",
  "width": 1024,
  "height": 1024,
  "num_images": 1
}
```

前端在“确认执行”时会自动把当前预览的计划作为 `edit_plan_override` 带回后端，确保预览和执行一致。这一点对专利场景很重要：用户审阅过的限制条件不会在生成阶段被隐式替换。

前端异步生成会长时间轮询任务状态，并显示已等待时间。图片模型生成可能持续数分钟；如果前端停止等待，可稍后进入“资料库”刷新生成版本。

### 生成记录与配置

```http
GET  /api/v1/generate/history
GET  /api/v1/generate/styles
GET  /api/v1/generate/models

GET  /api/v1/settings/current
GET  /api/v1/settings/providers
POST /api/v1/settings/api
POST /api/v1/settings/test-connection
```

## 生成控制模型

### `mode`

- `preserve_style`：保持原图风格优化。适合对已有图片做可控改造。
- `technical_illustration`：生成新的专利技术插图。允许重组画面。

### `executor`

- `cloud_image_to_image`：云端图生图，使用原图作为参考。
- `cloud_text_to_image`：云端文生图，不使用原图像素，只使用分析结果和指令。
- `local_high_fidelity`：本地保真增强，不调用外部模型。
- `auto`：自动选择。UI/截图/文字密集图可能走本地增强。

默认建议使用 `cloud_image_to_image`，这样既能保留原图语义，又能确认确实调用图片模型。对于文字密集截图，系统仍提供本地保真增强作为稳妥兜底，但它不会产生复杂重绘或新增图形。

## 测试

运行全量测试：

```bash
uv run pytest
```

当前测试覆盖：

- 上传校验
- 存储路径
- 分析解析
- 任务状态
- 设置接口
- LLM 服务下载和 OpenRouter payload
- 编辑计划
- 执行器选择
- 生成路由
- AI 计划 JSON 解析与非 JSON 兜底

## 常见问题

### “快速计划”为什么秒回？

快速计划是本地规则生成，不调用模型，所以秒回是正常的。需要模型参与时请选择 AI计划。

### AI计划为什么有时显示“兜底”？

AI计划会要求模型返回结构化 JSON，但部分模型在复杂图像或长上下文下可能返回自然语言说明。系统不会让整个流程失败，而是回退到快速计划，并把模型原始建议摘要放入风险提示。这样用户仍能继续生成，同时保留可审阅线索。

### 如何确认真的调用了 OpenRouter？

生成结果卡片会显示 `provider · model`。如果配置正确，应显示类似：

```text
openrouter · openai/gpt-5.4-image-2
```

也可以查看 `/api/v1/settings/current`，确认：

- `provider` 为 `openrouter`
- `active_api_base` 为 `https://openrouter.ai/api/v1`
- `active_image_model` 为 `openai/gpt-5.4-image-2`
- `api_key_configured` 为 `true`

### 为什么图生图结果和原图很像？

可能原因：

- 使用了本地保真增强。
- prompt 过于保守，只强调“保持原图”。
- 模型认为用户指令没有要求明显变化。

建议：

- 执行器选择 `cloud_image_to_image`。
- 使用 AI计划。
- 指令写出可见修改动作，例如“增加步骤编号、突出主路径、弱化背景元素、扩大关键部件标注”。

### 为什么 OpenRouter 报“未返回编辑图片”？

这说明 OpenRouter 请求成功返回了 chat completion，但响应中没有系统期望的 `message.images[].image_url.url`。可能原因包括：

- 当前模型支持文字回复，但没有返回图片输出。
- 上游 provider 对图生图编辑支持不稳定。
- 模型返回了文字说明或中间结果，而不是图片。

建议先切换执行器为 `cloud_text_to_image` 或 `local_high_fidelity` 验证流程；若必须使用图生图，需要确认当前 OpenRouter 模型确实支持输入图片并返回图片。

### `.env` 修改后为什么没有生效？

`.env` 在应用启动时读取。修改后需要重启 Uvicorn。

## 生产部署注意事项

- 不要提交真实 `.env` 或 API key。
- 生产环境应限制 CORS allow origins。
- 建议换用 PostgreSQL 或其他生产数据库。
- 上传文件应接入对象存储或持久卷。
- 外部模型调用应增加队列、重试、超时和成本控制。
- 当前异步任务状态存储在内存中，服务重启会丢失任务状态。

## 当前边界

- 系统用于专利材料整理和图片表达辅助，不替代专利代理人的法律判断。
- 视觉模型分析结果需要人工复核，尤其是技术特征、组件关系和新颖性相关描述。
- 图像生成可能改变局部细节，正式材料使用前应逐项核对可见事实。
- 本地任务状态是轻量实现，适合单机使用；多用户生产环境需要持久化队列和权限系统。

## 许可证

MIT License
