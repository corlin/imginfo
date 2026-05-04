import os
import uuid
import json
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy.orm import Session
from PIL import Image as PILImage

from ..config import settings
from ..database import get_db
from ..models.image import Image

router = APIRouter()


def validate_image(file: UploadFile) -> None:
    """验证图片文件"""
    # 检查文件扩展名
    ext = file.filename.split(".")[-1].lower() if file.filename else ""
    if ext not in settings.ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件类型: {ext}。允许的类型: {', '.join(settings.ALLOWED_EXTENSIONS)}"
        )


def validate_image_content(file_path: str) -> tuple:
    """验证图片内容（分辨率等）"""
    try:
        with PILImage.open(file_path) as img:
            width, height = img.size
            # 检查分辨率
            if width > settings.MAX_RESOLUTION[0] or height > settings.MAX_RESOLUTION[1]:
                raise HTTPException(
                    status_code=400,
                    detail=f"图片分辨率 {width}x{height} 超过最大限制 {settings.MAX_RESOLUTION[0]}x{settings.MAX_RESOLUTION[1]}"
                )
            if width < settings.MIN_RESOLUTION[0] or height < settings.MIN_RESOLUTION[1]:
                raise HTTPException(
                    status_code=400,
                    detail=f"图片分辨率 {width}x{height} 低于最小限制 {settings.MIN_RESOLUTION[0]}x{settings.MIN_RESOLUTION[1]}"
                )
            return width, height
    except Exception as e:
        if isinstance(e, HTTPException):
            raise
        raise HTTPException(status_code=400, detail=f"无法读取图片: {str(e)}")


def generate_storage_path(original_filename: str) -> tuple:
    """生成基于时间戳的存储路径"""
    now = datetime.now()
    date_dir = now.strftime("%Y%m%d")
    time_dir = now.strftime("%H%M%S")
    ext = original_filename.split(".")[-1].lower()
    new_filename = f"{uuid.uuid4().hex}.{ext}"
    storage_dir = os.path.join(settings.UPLOAD_DIR, date_dir, time_dir)
    os.makedirs(storage_dir, exist_ok=True)
    file_path = os.path.join(storage_dir, new_filename)
    return file_path, new_filename


def update_file_index(image_data: dict) -> None:
    """更新文件索引"""
    index_path = os.path.join(settings.UPLOAD_DIR, settings.INDEX_FILE)
    index = []
    if os.path.exists(index_path):
        with open(index_path, "r") as f:
            index = json.load(f)
    index.append(image_data)
    with open(index_path, "w") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)


@router.post("/upload")
async def upload_image(
    file: UploadFile = File(...),
    description: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """上传单张图片"""
    # 验证文件
    validate_image(file)
    
    # 检查文件大小
    content = await file.read()
    if len(content) > settings.MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"文件大小 {len(content)} 字节超过最大限制 {settings.MAX_FILE_SIZE} 字节"
        )
    
    # 生成存储路径
    file_path, new_filename = generate_storage_path(file.filename or "unknown.jpg")
    
    # 保存文件
    with open(file_path, "wb") as f:
        f.write(content)
    
    # 验证图片内容
    width, height = validate_image_content(file_path)
    
    # 创建数据库记录
    db_image = Image(
        filename=new_filename,
        original_filename=file.filename or "unknown",
        file_path=file_path,
        file_size=len(content),
        file_type=file.filename.split(".")[-1].lower() if file.filename else "unknown",
        width=width,
        height=height,
        description=description,
        index_key=f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{new_filename}",
        storage_path=os.path.dirname(file_path)
    )
    db.add(db_image)
    db.commit()
    db.refresh(db_image)
    
    # 更新文件索引
    update_file_index({
        "id": db_image.id,
        "filename": new_filename,
        "original_filename": file.filename,
        "file_path": file_path,
        "upload_time": str(db_image.upload_time)
    })
    
    return {
        "id": db_image.id,
        "filename": new_filename,
        "original_filename": file.filename,
        "file_size": len(content),
        "width": width,
        "height": height,
        "message": "图片上传成功"
    }


@router.post("/upload/multiple")
async def upload_multiple_images(
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db)
):
    """上传多张图片"""
    results = []
    errors = []
    
    for file in files:
        try:
            # 验证文件
            validate_image(file)
            
            # 检查文件大小
            content = await file.read()
            if len(content) > settings.MAX_FILE_SIZE:
                errors.append({"filename": file.filename, "error": "文件超过大小限制"})
                continue
            
            # 生成存储路径
            file_path, new_filename = generate_storage_path(file.filename or "unknown.jpg")
            
            # 保存文件
            with open(file_path, "wb") as f:
                f.write(content)
            
            # 验证图片内容
            width, height = validate_image_content(file_path)
            
            # 创建数据库记录
            db_image = Image(
                filename=new_filename,
                original_filename=file.filename or "unknown",
                file_path=file_path,
                file_size=len(content),
                file_type=file.filename.split(".")[-1].lower() if file.filename else "unknown",
                width=width,
                height=height,
                index_key=f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{new_filename}",
                storage_path=os.path.dirname(file_path)
            )
            db.add(db_image)
            db.commit()
            db.refresh(db_image)
            
            # 更新文件索引
            update_file_index({
                "id": db_image.id,
                "filename": new_filename,
                "original_filename": file.filename,
                "file_path": file_path,
                "upload_time": str(db_image.upload_time)
            })
            
            results.append({
                "id": db_image.id,
                "filename": new_filename,
                "original_filename": file.filename,
                "file_size": len(content),
                "width": width,
                "height": height
            })
        except Exception as e:
            errors.append({"filename": file.filename, "error": str(e)})
    
    return {
        "success_count": len(results),
        "error_count": len(errors),
        "results": results,
        "errors": errors,
        "message": f"成功上传 {len(results)} 张图片，{len(errors)} 张失败"
    }


@router.get("/images")
async def list_images(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """获取图片列表"""
    images = db.query(Image).offset(skip).limit(limit).all()
    total = db.query(Image).count()
    return {
        "total": total,
        "images": [
            {
                "id": img.id,
                "filename": img.filename,
                "original_filename": img.original_filename,
                "file_size": img.file_size,
                "file_type": img.file_type,
                "width": img.width,
                "height": img.height,
                "upload_time": str(img.upload_time),
                "description": img.description,
                "analysis_id": img.analysis_id
            }
            for img in images
        ]
    }


@router.get("/images/{image_id}")
async def get_image(image_id: int, db: Session = Depends(get_db)):
    """获取单张图片信息"""
    image = db.query(Image).filter(Image.id == image_id).first()
    if not image:
        raise HTTPException(status_code=404, detail="图片不存在")
    return {
        "id": image.id,
        "filename": image.filename,
        "original_filename": image.original_filename,
        "file_path": image.file_path,
        "file_size": image.file_size,
        "file_type": image.file_type,
        "width": image.width,
        "height": image.height,
        "upload_time": str(image.upload_time),
        "description": image.description,
        "analysis_id": image.analysis_id
    }


@router.delete("/images/{image_id}")
async def delete_image(image_id: int, db: Session = Depends(get_db)):
    """删除图片"""
    image = db.query(Image).filter(Image.id == image_id).first()
    if not image:
        raise HTTPException(status_code=404, detail="图片不存在")
    
    # 删除文件
    if os.path.exists(image.file_path):
        os.remove(image.file_path)
    
    # 删除数据库记录
    db.delete(image)
    db.commit()
    
    return {"message": "图片删除成功", "id": image_id}
