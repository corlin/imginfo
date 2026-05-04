from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from pathlib import Path

from .config import settings
from .database import engine, Base
from .models.image import Image
from .models.analysis import Analysis

# 创建数据库表
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description=settings.DESCRIPTION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应该限制为具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 获取基础目录
BASE_DIR = Path(__file__).resolve().parent

# 配置静态文件
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

# 配置模板
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

# 配置上传文件目录
app.mount("/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")

# 导入路由
from .routers import upload, analysis, generate, tasks
from .routers.settings_router import router as settings_router

app.include_router(upload.router, prefix=settings.API_V1_STR, tags=["upload"])
app.include_router(analysis.router, prefix=settings.API_V1_STR, tags=["analysis"])
app.include_router(generate.router, prefix=settings.API_V1_STR, tags=["generate"])
app.include_router(tasks.router, prefix=settings.API_V1_STR, tags=["tasks"])
app.include_router(settings_router, prefix=settings.API_V1_STR, tags=["settings"])

@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    return templates.TemplateResponse(request, "index.html")

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT, reload=settings.DEBUG)
