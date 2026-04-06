"""
Abstract base class for all trading strategies.
Every strategy must implement `generate_signal()` which returns
+1 (BUY), -1 (SELL), or 0 (HOLD).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional

import pandas as pd


@dataclass
class Signal:
    action:     int           # +1 BUY | -1 SELL | 0 HOLD
    strength:   float = 0.0  # 0.0 – 1.0 confidence
    reason:     str   = ""
    strategy:   str   = ""
    symbol:     str   = ""
    price:      float = 0.0
    metadata:   dict  = field(default_factory=dict)

    # Convenience aliases
    @property
    def is_buy(self)  -> bool: return self.action ==  1
    @property
    def is_sell(self) -> bool: return self.action == -1
    @property
    def is_hold(self) -> bool: return self.action ==  0

    def __str__(self) -> str:
        label = {1: "BUY", -1: "SELL", 0: "HOLD"}.get(self.action, "?")
        return (f"[{self.strategy}] {label} {self.symbol} @ {self.price:.4f} "
                f"(strength={self.strength:.2f}) — {self.reason}")


class BaseStrategy(ABC):
    """All strategies inherit from this class."""

    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def generate_signal(self, df: pd.DataFrame, symbol: str = "") -> Signal:
        """
        Parameters
        ----------
        df     : OHLCV DataFrame with columns open/high/low/close/volume
        symbol : trading pair (e.g. 'BTC/USDT')

        Returns
        -------
        Signal
        """

    def _last_price(self, df: pd.DataFrame) -> float:
        return float(df["close"].iloc[-1])

    def _require_length(self, df: pd.DataFrame, n: int) -> bool:
        return len(df) >= n
