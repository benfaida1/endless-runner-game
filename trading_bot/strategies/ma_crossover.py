"""
Moving Average Crossover Strategy
──────────────────────────────────
BUY  : fast MA crosses ABOVE slow MA and price is above signal MA
SELL : fast MA crosses BELOW slow MA or price drops below signal MA
"""

from __future__ import annotations

import pandas as pd

from .base import BaseStrategy, Signal
from trading_bot.config.settings import MA_FAST, MA_SLOW, MA_SIGNAL


class MACrossover(BaseStrategy):

    def __init__(self, fast: int = MA_FAST, slow: int = MA_SLOW,
                 signal: int = MA_SIGNAL):
        super().__init__("MACrossover")
        self.fast   = fast
        self.slow   = slow
        self.signal = signal

    def generate_signal(self, df: pd.DataFrame, symbol: str = "") -> Signal:
        if not self._require_length(df, self.slow + 2):
            return Signal(0, 0.0, "Not enough data", self.name, symbol)

        close = df["close"]
        price = self._last_price(df)

        ma_fast   = close.ewm(span=self.fast,   adjust=False).mean()
        ma_slow   = close.ewm(span=self.slow,   adjust=False).mean()
        ma_signal = close.ewm(span=self.signal, adjust=False).mean()

        # Crossover detection (last two candles)
        cross_up   = (ma_fast.iloc[-2] <= ma_slow.iloc[-2] and
                      ma_fast.iloc[-1]  > ma_slow.iloc[-1])
        cross_down = (ma_fast.iloc[-2] >= ma_slow.iloc[-2] and
                      ma_fast.iloc[-1]  < ma_slow.iloc[-1])

        above_signal = price > ma_signal.iloc[-1]
        below_signal = price < ma_signal.iloc[-1]

        # Trend strength: distance between MAs normalised by price
        spread = abs(ma_fast.iloc[-1] - ma_slow.iloc[-1]) / price
        strength = min(spread * 100, 1.0)

        if cross_up and above_signal:
            return Signal(1, strength,
                          f"EMA{self.fast} crossed above EMA{self.slow}, "
                          f"price above EMA{self.signal}",
                          self.name, symbol, price)
        if cross_down or below_signal:
            return Signal(-1, strength,
                          f"EMA{self.fast} crossed below EMA{self.slow}",
                          self.name, symbol, price)

        # Trend-following: already above all MAs → weak hold/buy bias
        if ma_fast.iloc[-1] > ma_slow.iloc[-1] > ma_signal.iloc[-1]:
            return Signal(1, strength * 0.3, "Trend up — holding",
                          self.name, symbol, price)

        return Signal(0, 0.0, "No clear signal", self.name, symbol, price)
