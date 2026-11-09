"""Explicit provenance and the two supported candle schemas."""

from dataclasses import asdict, dataclass
from typing import Literal

OHLC = ("open", "high", "low", "close")
PriceSide = Literal["bid", "ask", "mid", "unknown", "bid_ask"]


@dataclass(frozen=True)
class Provenance:
    source: str
    reference: str
    data_kind: Literal["historical", "synthetic"]
    price_side: PriceSide
    symbol: str = "XAUUSD"
    timeframe: str = "M5"

    def __post_init__(self) -> None:
        if not self.source.strip() or not self.reference.strip():
            raise ValueError("Source and reference must be nonempty")
        if self.data_kind not in {"historical", "synthetic"}:
            raise ValueError("Data kind must be historical or synthetic")
        if self.price_side not in {"bid", "ask", "mid", "unknown", "bid_ask"}:
            raise ValueError("Invalid price side")
        if self.symbol != "XAUUSD" or self.timeframe != "M5":
            raise ValueError("Phase 1 supports XAUUSD M5 only")

    def to_dict(self) -> dict:
        return asdict(self)


def price_columns(side: PriceSide) -> list[str]:
    if side == "bid_ask":
        return [f"{quote}_{field}" for quote in ("bid", "ask") for field in OHLC]
    return list(OHLC)
