"""
RSI Strategy with divergence detection
──────────────────────────────────────
BUY  : RSI < 30 (oversold) and turning up, or bullish divergence
SELL : RSI > 70 (overbought) and turning down, or bearish divergence
"""

from __future__ import annotations

import pandas as pd
import numpy as np

from .base import BaseStrategy, Signal
from trading_bot.config.settings import RSI_PERIOD, RSI_OVERSOLD, RSI_OVERBOUGHT


def _rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta  = series.diff()
    gain   = delta.clip(lower=0).ewm(com=period - 1, adjust=False).mean()
    loss   = (-delta.clip(upper=0)).ewm(com=period - 1, adjust=False).mean()
    rs     = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


class RSIStrategy(BaseStrategy):

    def __init__(self, period: int = RSI_PERIOD,
                 oversold: float = RSI_OVERSOLD,
                 overbought: float = RSI_OVERBOUGHT):
        super().__init__("RSIStrategy")
        self.period     = period
        self.oversold   = oversold
        self.overbought = overbought

    def generate_signal(self, df: pd.DataFrame, symbol: str = "") -> Signal:
        if not self._require_length(df, self.period + 5):
            return Signal(0, 0.0, "Not enough data", self.name, symbol)

        close  = df["close"]
        price  = self._last_price(df)
        rsi    = _rsi(close, self.period)
        rsi_v  = rsi.iloc[-1]
        rsi_p  = rsi.iloc[-2]

        # ── Oversold region: look for reversal ────────────────────────────────
        if rsi_v < self.oversold:
            # Turning up (hook)
            if rsi_v > rsi_p:
                strength = (self.oversold - rsi_v) / self.oversold
                return Signal(1, min(strength + 0.5, 1.0),
                              f"RSI={rsi_v:.1f} oversold + hook up",
                              self.name, symbol, price)
            strength = (self.oversold - rsi_v) / self.oversold
            return Signal(1, strength,
                          f"RSI={rsi_v:.1f} deep oversold",
                          self.name, symbol, price)

        # ── Overbought region: look for reversal ──────────────────────────────
        if rsi_v > self.overbought:
            if rsi_v < rsi_p:
                strength = (rsi_v - self.overbought) / (100 - self.overbought)
                return Signal(-1, min(strength + 0.5, 1.0),
                              f"RSI={rsi_v:.1f} overbought + turning down",
                              self.name, symbol, price)
            strength = (rsi_v - self.overbought) / (100 - self.overbought)
            return Signal(-1, strength,
                          f"RSI={rsi_v:.1f} deep overbought",
                          self.name, symbol, price)

        # ── Bullish divergence (price lower low, RSI higher low) ──────────────
        lookback = 10
        if len(df) >= lookback + self.period:
            price_swing = close.iloc[-lookback:]
            rsi_swing   = rsi.iloc[-lookback:]
            if (price_swing.iloc[-1] < price_swing.min() * 1.02 and
                    rsi_swing.iloc[-1] > rsi_swing.min() + 5):
                return Signal(1, 0.6,
                              "Bullish RSI divergence",
                              self.name, symbol, price)

        # Neutral zone — slight directional bias
        mid_bias = (rsi_v - 50) / 50
        return Signal(0, abs(mid_bias) * 0.2,
                      f"RSI={rsi_v:.1f} neutral",
                      self.name, symbol, price)
