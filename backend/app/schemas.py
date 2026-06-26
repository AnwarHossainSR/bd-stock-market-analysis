"""Request schemas (responses are plain dicts from the service layer)."""
from __future__ import annotations

from pydantic import BaseModel, Field


class HoldingIn(BaseModel):
    code: str
    quantity: float = Field(ge=0)
    buy_price: float = Field(ge=0)


class PortfolioReplaceIn(BaseModel):
    holdings: list[HoldingIn] = []


class WatchIn(BaseModel):
    code: str
    note: str | None = None
