from sqlalchemy import Column, Integer, String, Float, Text, DateTime
from sqlalchemy.sql import func
from app.database import Base


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String, index=True, nullable=False)
    event_type = Column(
        String, nullable=False
    )  # e.g., "EARNINGS", "PRICE_CHANGE", "VOLUME_SPIKE"
    severity = Column(String, default="Medium")  # Low, Medium, High
    summary = Column(Text, nullable=False)
    market_impact = Column(Text, nullable=True)
    suggested_action = Column(Text, nullable=True)
    confidence_score = Column(Float, nullable=True)
    key_risks = Column(Text, nullable=True)
    sources = Column(Text, nullable=True)
    alert_hash = Column(
        String, unique=True, index=True, nullable=False
    )  # Hash to prevent duplicate notifications
    sent_at = Column(DateTime(timezone=True), server_default=func.now())
