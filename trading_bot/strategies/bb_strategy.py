"""
Bollinger Bands Strategy
────────────────────────
BUY  : price touches lower band + %B < 0.05 (squeeze breakout up)
SELL : price touches upper band + %B > 0.95 (squeeze breakout down)
Uses BB width (squeeze indicator) to filter low-volatility entries.
"""

from __future__ import annotations

import pandas as pd
import numpy as np

from .base import BaseStrategy, Signal
from trading_bot.config.settings import BB_PERIOD, BB_STD


class BBStrategy(BaseStrategy):

    def __init__(self, period: int = BB_PERIOD, std_dev: float = BB_STD):
        super().__init__("BBStrategy")
        self.period  = period
        self.std_dev = std_dev

    def generate_signal(self, df: pd.DataFrame, symbol: str = "") -> Signal:
        if not self._require_length(df, self.period + 5):
            return Signal(0, 0.0, "Not enough data", self.name, symbol)

        close  = df["close"]
        price  = self._last_price(df)

        sma    = close.rolling(self.period).mean()
        std    = close.rolling(self.period).std()
        upper  = sma + self.std_dev * std
        lower  = sma - self.std_dev * std
        width  = (upper - lower) / sma          # normalised band width

        pct_b  = (close - lower) / (upper - lower)  # %B indicator
        pct_b_now  = pct_b.iloc[-1]
        pct_b_prev = pct_b.iloc[-2]
        width_now  = width.iloc[-1]

        # Squeeze: when width is in the bottom 20th percentile → potential breakout
        width_pct20 = width.rolling(50).quantile(0.20).iloc[-1]
        in_squeeze  = width_now <= width_pct20 if not np.isnan(width_pct20) else False

        # ── Lower band touch / breakout ───────────────────────────────────────
        if pct_b_now < 0.05:
            strength = (1 - pct_b_now) * (1.5 if in_squeeze else 1.0)
            return Signal(1, min(strength, 1.0),
                          f"%B={pct_b_now:.2f} at lower band"
                          + (" [SQUEEZE]" if in_squeeze else ""),
                          self.name, symbol, price)

        # ── Upper band touch / breakout ───────────────────────────────────────
        if pct_b_now > 0.95:
            strength = pct_b_now * (1.5 if in_squeeze else 1.0)
            return Signal(-1, min(strength, 1.0),
                          f"%B={pct_b_now:.2f} at upper band"
                          + (" [SQUEEZE]" if in_squeeze else ""),
                          self.name, symbol, price)

        # ── %B crossing 0.5 (mid-band) ────────────────────────────────────────
        if pct_b_prev < 0.5 <= pct_b_now:
            return Signal(1, 0.4, "%B crossed above mid-band",
                          self.name, symbol, price)
        if pct_b_prev > 0.5 >= pct_b_now:
            return Signal(-1, 0.4, "%B crossed below mid-band",
                          self.name, symbol, price)

        bias = pct_b_now - 0.5
        return Signal(0, abs(bias) * 0.2, f"%B={pct_b_now:.2f} neutral",
                      self.name, symbol, price)
