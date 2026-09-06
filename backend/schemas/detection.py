from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class DetectRequest(BaseModel):
    flow_uid: Optional[str] = Field(default=None, description="auto-generated if omitted")
    device_id: Optional[int] = None
    feature_vector: list[float] = Field(description="raw (unscaled) values, in feature_order.json's exact order")
    feature_set_version: str
    src_ip: str = "0.0.0.0"
    dst_ip: str = "0.0.0.0"
    protocol: str = Field(default="OTHER", pattern="^(TCP|UDP|ICMP|MQTT|HTTP|BLE|OTHER)$")
    capture_source: str = Field(default="simulated", pattern="^(live|pcap|dataset|simulated)$")


class Stage1Out(BaseModel):
    label: str
    probability: float


class Stage2Out(BaseModel):
    attack_family: Optional[str] = None
    confidence: float
    class_probabilities: dict


class Stage3Out(BaseModel):
    reconstruction_error: float
    anomaly_score: float
    is_anomaly: bool


class Stage4Out(BaseModel):
    reading_id: int
    max_zscore: float
    threshold: float
    worst_vital: Optional[str] = None
    injection_suspected: bool


class DetectResponse(BaseModel):
    detection_id: int
    flow_id: int
    flow_uid: str
    final_verdict: str
    severity: str
    final_confidence: float
    stage1: Stage1Out
    stage2: Optional[Stage2Out] = None
    stage3: Optional[Stage3Out] = None
    stage4: Optional[Stage4Out] = None
    alert_id: Optional[int] = None
    alert_uid: Optional[str] = None
    inference_latency_ms: float
    detected_at: datetime


class DetectionOut(BaseModel):
    id: int
    flow_id: int
    device_id: Optional[int] = None
    stage1_label: str
    stage1_probability: Optional[float] = None
    stage2_attack_family: Optional[str] = None
    stage2_confidence: Optional[float] = None
    stage3_anomaly_score: Optional[float] = None
    stage3_is_anomaly: bool = False
    stage4_injection_suspected: bool = False
    stage4_max_zscore: Optional[float] = None
    final_verdict: str
    final_confidence: Optional[float] = None
    severity: str
    inference_latency_ms: Optional[float] = None
    detected_at: datetime


class ExplanationFeatureOut(BaseModel):
    feature: str
    value: float
    scaled_value: float
    contribution: float = Field(description="SHAP value; positive pushes toward malicious")


class ExplanationOut(BaseModel):
    detection_id: int
    method: str
    base_value: Optional[float] = None
    top_features: list[ExplanationFeatureOut]
    narrative: Optional[str] = None
    created_at: Optional[datetime] = None


class DetectionListResponse(BaseModel):
    items: list[DetectionOut]
    total: int
    page: int
    size: int
