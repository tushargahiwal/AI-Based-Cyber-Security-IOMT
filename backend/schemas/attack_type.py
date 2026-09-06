from typing import Optional

from pydantic import BaseModel, Field

FAMILY_PATTERN = "^(BENIGN|DDOS|DOS|RECON|MQTT|SPOOFING|MALWARE|UNKNOWN)$"
SEVERITY_PATTERN = "^(info|low|medium|high|critical)$"


class AttackTypeCreateRequest(BaseModel):
    code: str = Field(min_length=2, max_length=40)
    family: str = Field(pattern=FAMILY_PATTERN)
    display_name: Optional[str] = Field(default=None, max_length=100)
    description: Optional[str] = None
    default_severity: Optional[str] = Field(default=None, pattern=SEVERITY_PATTERN)
    mitre_technique: Optional[str] = Field(default=None, max_length=20)
    typical_indicators: Optional[list] = None
    recommended_action: Optional[str] = None


class AttackTypeUpdateRequest(BaseModel):
    family: Optional[str] = Field(default=None, pattern=FAMILY_PATTERN)
    display_name: Optional[str] = Field(default=None, max_length=100)
    description: Optional[str] = None
    default_severity: Optional[str] = Field(default=None, pattern=SEVERITY_PATTERN)
    mitre_technique: Optional[str] = Field(default=None, max_length=20)
    typical_indicators: Optional[list] = None
    recommended_action: Optional[str] = None


class AttackTypeOut(BaseModel):
    id: int
    code: str
    family: str
    display_name: Optional[str] = None
    description: Optional[str] = None
    default_severity: Optional[str] = None
    mitre_technique: Optional[str] = None
    typical_indicators: Optional[list] = None
    recommended_action: Optional[str] = None

    model_config = {"from_attributes": True}
