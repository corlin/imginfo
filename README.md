# imgInfo - 专利图片智能分析与生成系统

一个基于Python的全栈应用，用于专利图片的智能分析和生成，支持多图上传、专利角度分析、文生图等功能。

## 功能特性

### 1. 图片上传管理
- 支持多图批量上传
- 文件类型限制：JPG、PNG、GIF、BMP、WebP、TIFF
- 文件大小限制：单文件最大10MB
- 图片尺寸限制：最小100x100，最大8000x8000像素
- 基于时间戳的目录结构存储
- 自动生成唯一文件名，避免冲突

### 2. 专利图片分析
- 基于专利要求书角度分析图片内容
- 识别图片中的技术组件和关系
- 生成结构化的专利要素分析
- 技术方案描述和关键特征提取
- 新颖性分析报告

### 3. 图片生成
- 基于分析结果和用户指令生成新图片
- 支持多种风格：写实、草图、技术图纸、艺术、3D渲染、蓝图
- 可配置生成参数：尺寸、数量、引导系数等
- 生成图片自动保存并索引

### 4. 系统管理
- 图片列表和详情查看
- 分析结果查询和管理
- 生成记录追踪
- 可用风格和模型查询

## 技术栈

### 后端
- **Python 3.12+**
- **FastAPI** - 高性能Web框架
- **SQLAlchemy** - ORM数据库操作
- **SQLite** - 轻量级数据库
- **Pydantic** - 数据验证

### 前端
- **HTML5/CSS3/JavaScript**
- **响应式设计**
- **现代UI界面**

### 工具链
- **uv** - 快速Python包管理
- **Uvicorn** - ASGI服务器
- **Pillow** - 图片处理

## 项目结构

```
imgInfo/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI应用主入口
│   ├── config.py             # 配置管理
│   ├── database.py           # 数据库配置
│   ├── models/               # 数据模型
│   │   ├── __init__.py
│   │   ├── image.py          # 图片模型
│   │   └── analysis.py       # 分析结果模型
│   ├── routers/              # API路由
│   │   ├── __init__.py
│   │   ├── upload.py         # 上传API
│   │   ├── analysis.py       # 分析API
│   │   └── generate.py       # 生成API
│   ├── templates/            # HTML模板
│   │   └── index.html        # 主页面
│   └── static/               # 静态文件
├── uploads/                  # 上传文件存储
│   └── generated/            # 生成图片存储
├── pyproject.toml            # 项目配置
├── uv.lock                   # 依赖锁定文件
└── README.md                 # 项目文档
```

## 安装与运行

### 环境要求
- Python 3.12+
- uv 包管理器

### 安装步骤

1. **克隆项目**
```bash
git clone <repository-url>
cd imgInfo
```

2. **安装依赖**
```bash
uv sync
```

3. **运行应用**
```bash
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

4. **访问应用**
- 主页面：http://localhost:8000
- API文档：http://localhost:8000/docs
- 健康检查：http://localhost:8000/health

## API接口

### 1. 图片上传
```http
POST /api/v1/upload
Content-Type: multipart/form-data

file: <图片文件>
```

**响应示例：**
```json
{
    "id": 1,
    "filename": "abc123.png",
    "original_filename": "test.png",
    "file_size": 1024,
    "width": 800,
    "height": 600,
    "message": "图片上传成功"
}
```

### 2. 图片分析
```http
POST /api/v1/analyze
Content-Type: application/json

{
    "image_id": 1,
    "patent_focus": "apparatus",  // general, apparatus, method, composition
    "model_name": "default"
}
```

**响应示例：**
```json
{
    "id": 1,
    "image_id": 1,
    "structured_result": {...},
    "patent_elements": {...},
    "technical_description": "...",
    "key_features": [...],
    "novelty_analysis": "...",
    "message": "分析完成"
}
```

### 3. 图片生成
```http
POST /api/v1/generate
Content-Type: application/json

{
    "analysis_id": 1,
    "prompt": "生成一个现代化的技术示意图",
    "style": "technical",  // realistic, sketch, technical, artistic, 3d, blueprint
    "width": 512,
    "height": 512,
    "num_images": 1
}
```

**响应示例：**
```json
{
    "id": 1,
    "analysis_id": 1,
    "generated_images": [...],
    "prompt": "...",
    "style": "technical",
    "message": "成功生成 1 张图片"
}
```

### 4. 其他接口
- `GET /api/v1/images` - 获取图片列表
- `GET /api/v1/images/{id}` - 获取图片详情
- `GET /api/v1/analyses` - 获取分析列表
- `GET /api/v1/analysis/{id}` - 获取分析详情
- `GET /api/v1/generate/styles` - 获取可用风格
- `GET /api/v1/generate/models` - 获取可用模型

## 配置说明

### 环境变量
在项目根目录创建 `.env` 文件：

```env
# 应用配置
APP_NAME=imgInfo
APP_VERSION=1.0.0
DEBUG=true
HOST=0.0.0.0
PORT=8000

# 上传配置
UPLOAD_DIR=uploads
MAX_FILE_SIZE=10485760  # 10MB
ALLOWED_EXTENSIONS=["jpg","jpeg","png","gif","bmp","webp","tiff"]
MIN_IMAGE_SIZE=100
MAX_IMAGE_SIZE=8000

# 数据库配置
DATABASE_URL=sqlite:///./imginfo.db

# 模型配置
VISION_MODEL=local
GENERATION_MODEL=stable-diffusion
```

## 使用流程

1. **上传图片** → 系统存储并建立索引
2. **选择图片** → 进行专利角度分析
3. **查看分析** → 理解技术方案和专利要素
4. **输入指令** → 基于分析结果生成新图片
5. **下载使用** → 获取生成的专利示意图

## 开发说明

### 扩展视觉模型
在 `app/routers/analysis.py` 中替换模拟数据，集成真实的视觉模型API：

```python
# 示例：集成OpenAI Vision API
import openai

def analyze_with_vision(image_path: str) -> dict:
    response = openai.ChatCompletion.create(
        model="gpt-4-vision-preview",
        messages=[{
            "role": "user",
            "content": [
                {"type": "text", "text": "分析这张专利图片..."},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base64_image}"}}
            ]
        }]
    )
    return parse_analysis(response.choices[0].message.content)
```

### 扩展文生图模型
在 `app/routers/generate.py` 中集成真实的文生图模型：

```python
# 示例：集成Stable Diffusion API
from diffusers import StableDiffusionPipeline

def generate_image(prompt: str, style: str) -> str:
    pipe = StableDiffusionPipeline.from_pretrained("runwayml/stable-diffusion-v1-5")
    image = pipe(prompt).images[0]
    return save_image(image)
```

## 注意事项

1. **生产环境部署**：
   - 修改CORS配置，限制允许的域名
   - 使用PostgreSQL等生产级数据库
   - 配置HTTPS
   - 设置适当的文件上传限制

2. **模型集成**：
   - 当前使用模拟数据，需替换为真实模型
   - 考虑模型API的调用限制和成本
   - 实现错误处理和重试机制

3. **性能优化**：
   - 对大文件实现异步处理
   - 添加缓存机制
   - 实现图片压缩和缩略图

## 许可证

MIT License

## 联系方式

如有问题或建议，请提交Issue或联系开发团队。