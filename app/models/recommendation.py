from sqlalchemy import Column, Integer, String, Float, Text, DateTime, JSON
from sqlalchemy.sql import func
from app.database import Base


class AIRecommendation(Base):
    __tablename__ = "ai_recommendations"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String, index=True, nullable=False)
    recommendation = Column(
        String, nullable=False
    )  # Strong Buy, Buy, Accumulate, Hold, Reduce, Sell, Strong Sell
    executive_summary = Column(Text, nullable=False)
    why_it_matters = Column(Text, nullable=False)
    historical_context = Column(Text, nullable=False)
    valuation_analysis = Column(Text, nullable=False)
    technical_analysis = Column(Text, nullable=False)
    risk_assessment = Column(Text, nullable=False)
    suggested_action = Column(Text, nullable=False)
    expected_holding_period = Column(String, nullable=False)
    exit_strategy = Column(Text, nullable=False)
    confidence_score = Column(Float, nullable=False)
    supporting_evidence = Column(Text, nullable=False)
    sources = Column(JSON, nullable=True)  # Store citation list/metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
