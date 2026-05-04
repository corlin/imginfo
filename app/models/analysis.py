from sqlalchemy import Column, Integer, String, DateTime, Text, JSON
from sqlalchemy.sql import func

from ..database import Base


class Analysis(Base):
    __tablename__ = "analyses"

    id = Column(Integer, primary_key=True, index=True)
    image_id = Column(Integer, index=True, nullable=False)
    model_name = Column(String(100), nullable=False)
    
    # 结构化分析结果
    raw_output = Column(Text)  # 模型原始输出
    structured_result = Column(JSON)  # 结构化JSON结果
    
    # 专利角度的关键内容
    patent_elements = Column(JSON)  # 专利要素提取
    technical_description = Column(Text)  # 技术描述
    key_features = Column(JSON)  # 关键特征
    novelty_analysis = Column(Text)  # 新颖性分析
    
    # 生成相关
    generation_prompt = Column(Text)  # 生成提示词
    generated_image_path = Column(String(500))  # 生成的图片路径
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    def __repr__(self):
        return f"<Analysis(id={self.id}, image_id={self.image_id})>"