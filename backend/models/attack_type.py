from sqlalchemy import JSON, Enum, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class AttackType(Base):
    __tablename__ = "attack_types"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    family: Mapped[str] = mapped_column(
        Enum("BENIGN", "DDOS", "DOS", "RECON", "MQTT", "SPOOFING", "MALWARE", "UNKNOWN", name="attack_family"),
        nullable=False,
    )
    display_name: Mapped[str | None] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(Text)
    default_severity: Mapped[str | None] = mapped_column(
        Enum("info", "low", "medium", "high", "critical", name="attack_default_severity")
    )
    mitre_technique: Mapped[str | None] = mapped_column(String(20))
    typical_indicators: Mapped[list | None] = mapped_column(JSON)
    recommended_action: Mapped[str | None] = mapped_column(Text)
