from sqlalchemy import Column, Integer, String, Float, DateTime, Text, ForeignKey
from sqlalchemy.sql import func

from ..database import Base


class Image(Base):
    __tablename__ = "images"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String(255), nullable=False)
    original_filename = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_size = Column(Integer, nullable=False)  # 字节
    file_type = Column(String(50), nullable=False)
    width = Column(Integer)
    height = Column(Integer)
    upload_time = Column(DateTime(timezone=True), server_default=func.now())
    description = Column(Text)
    
    # 索引字段
    index_key = Column(String(100), index=True)  # 用于快速查找的索引键
    storage_path = Column(String(500))  # 存储路径（基于时间戳的目录结构）
    
    # 关联分析结果
    analysis_id = Column(Integer, ForeignKey("analyses.id"), nullable=True)
    
    def __repr__(self):
        return f"<Image(id={self.id}, filename={self.filename})>"