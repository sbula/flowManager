from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, Literal

class StrategySignal(BaseModel):
    signal: float = Field(..., description="1.0 (Long), -1.0 (Short), 0.0 (Neutral)")
    weight: float = Field(..., ge=0.0, le=1.0, description="Confidence/Weight")
    verdict: Literal["LONG", "SHORT", "NEUTRAL"]
    meta_data: Dict[str, Any] = Field(default_factory=dict)

class Strategy:
    def __init__(self, config: BaseModel):
        self.config = config

    def on_candle(self, candle: Dict[str, Any]) -> StrategySignal:
        raise NotImplementedError("Strategy must implement on_candle")
