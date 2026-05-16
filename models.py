from pydantic import BaseModel, Field
from datetime import datetime
from typing import Literal


class TradeBase(BaseModel):
    symbol: str = Field(..., example="AAPL")
    side: Literal["BUY", "SELL"]
    quantity: float = Field(..., gt=0, example=10.0)
    price: float = Field(..., gt=0, example=195.50)


class TradeCreate(TradeBase):
    pass


class Trade(TradeBase):
    id: int
    timestamp: datetime

    class Config:
        from_attributes = True
