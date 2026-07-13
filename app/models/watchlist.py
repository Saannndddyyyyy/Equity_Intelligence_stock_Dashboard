from sqlalchemy import Column, Integer, String, Float, Date, Text, DateTime
from sqlalchemy.sql import func
from app.database import Base


class Watchlist(Base):
    __tablename__ = "watchlist"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String, unique=True, index=True, nullable=False)  # e.g., "TCS.NS"
    exchange = Column(String, nullable=False)  # e.g., "NSE" or "BSE"
    company_name = Column(String, nullable=False)
    purchase_price = Column(Float, nullable=True)
    quantity = Column(Integer, default=0)
    average_cost = Column(Float, nullable=True)
    target_price = Column(Float, nullable=True)
    stop_loss = Column(Float, nullable=True)
    purchase_date = Column(Date, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), onupdate=func.now(), server_default=func.now()
    )
