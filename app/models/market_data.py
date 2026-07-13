from sqlalchemy import Column, Integer, String, Float, BigInteger, DateTime
from sqlalchemy.sql import func
from app.database import Base


class PriceHistory(Base):
    __tablename__ = "price_history"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String, index=True, nullable=False)
    price = Column(Float, nullable=False)
    volume = Column(BigInteger, nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
