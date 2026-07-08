"""数据库模型定义"""
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text
from app.database import Base


def _utcnow():
    return datetime.now(timezone.utc)


class Device(Base):
    __tablename__ = "devices"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, comment="设备名称")
    platform = Column(String(50), default="ELF 2 / RK3588", comment="硬件平台")
    status = Column(String(20), default="offline", comment="状态(历史兼容，权威在线判定由服务端动态计算)")
    last_seen = Column(DateTime, comment="服务器最后收到设备数据的时间")
    model_name = Column(String(100), default="", comment="模型名称")
    software_version = Column(String(20), default="", comment="软件版本")
    camera_status = Column(String(20), default="unknown", comment="摄像头状态")
    qt_status = Column(String(20), default="unknown", comment="Qt 界面状态")
    # 新增字段
    sent_at = Column(DateTime, nullable=True, comment="设备发送心跳时的设备时钟时间")
    mode = Column(String(20), default="unknown", comment="运行模式: scenic/navigation/idle")
    npu_status = Column(String(20), default="unknown", comment="NPU状态: running/idle/error")
    qa_status = Column(String(20), default="unknown", comment="文字问答状态: available/busy/error/unsupported")
    asr_status = Column(String(20), default="unknown", comment="ASR状态: available/listening/error/unsupported")
    is_demo = Column(Boolean, default=False, comment="是否为演示设备（seed数据）")
    first_seen = Column(DateTime, nullable=True, comment="设备首次注册时间（服务器时间）")


class ScenicSpot(Base):
    __tablename__ = "scenic_spots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    class_name = Column(String(200), nullable=False, unique=True, comment="模型类别名（英文）")
    display_name = Column(String(200), nullable=False, comment="展示名称（中文）")
    domain = Column(String(20), default="scenic", comment="导览类型: scenic/animal/marine/exhibit")
    introduction = Column(Text, default="", comment="导览讲解简介")
    history = Column(Text, default="", comment="历史背景")
    features = Column(Text, default="", comment="建筑特色")
    narration = Column(Text, default="", comment="语音讲解文本")
    image_url = Column(String(500), default="", comment="景点图片URL")
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)


class RecognitionEvent(Base):
    __tablename__ = "recognition_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_id = Column(String(64), nullable=True, unique=True, comment="事件唯一ID（用于幂等去重）")
    device_id = Column(String(50), nullable=False, comment="设备ID")
    timestamp = Column(DateTime, nullable=False, comment="识别时间(设备采集时间)")
    class_name = Column(String(200), nullable=False, comment="模型类别名")
    display_name = Column(String(200), default="", comment="展示名称")
    confidence = Column(Float, default=0.0, comment="置信度")
    fps = Column(Float, default=0.0, comment="FPS")
    inference_ms = Column(Float, default=0.0, comment="推理耗时(ms)")
    postprocess_ms = Column(Float, default=0.0, comment="后处理耗时(ms)")
    narration_triggered = Column(Boolean, default=False, comment="是否触发讲解")
    source = Column(String(20), default="rknn", comment="来源: rknn / manual / demo")
    received_at = Column(DateTime, default=_utcnow, comment="服务器接收时间")


class QARecord(Base):
    __tablename__ = "qa_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    device_id = Column(String(50), nullable=False, comment="设备ID")
    scenic_name = Column(String(200), default="", comment="关联景点名称")
    question = Column(Text, nullable=False, comment="用户问题")
    answer = Column(Text, default="", comment="回复内容")
    provider = Column(String(50), default="local", comment="回复来源")
    created_at = Column(DateTime, default=_utcnow)
