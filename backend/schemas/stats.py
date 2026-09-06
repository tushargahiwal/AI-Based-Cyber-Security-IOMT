from typing import Optional

from pydantic import BaseModel


class OverviewStats(BaseModel):
    total_flows: int
    total_detections: int
    detections_by_verdict: dict
    devices_online: int
    devices_total: int
    active_stage1_model: Optional[str] = None
    active_alerts: int = 0
    critical_alerts: int = 0
