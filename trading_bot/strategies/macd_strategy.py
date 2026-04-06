"""
MACD Strategy
─────────────
BUY  : MACD line crosses above signal line (histogram turns positive)
SELL : MACD line crosses below signal line (histogram turns negative)
"""

from __future__ import annotations

import pandas as pd
import numpy as np

from .base import BaseStrategy, Signal
from trading_bot.config.settings import MACD_FAST, MACD_SLOW, MACD_SIGNAL


class MACDStrategy(BaseStrategy):

    def __init__(self, fast: int = MACD_FAST, slow: int = MACD_SLOW,
                 signal: int = MACD_SIGNAL):
        super().__init__("MACDStrategy")
        self.fast   = fast
        self.slow   = slow
        self.signal = signal

    def generate_signal(self, df: pd.DataFrame, symbol: str = "") -> Signal:
        if not self._require_length(df, self.slow + self.signal + 2):
            return Signal(0, 0.0, "Not enough data", self.name, symbol)

        close     = df["close"]
        price     = self._last_price(df)

        ema_fast  = close.ewm(span=self.fast,   adjust=False).mean()
        ema_slow  = close.ewm(span=self.slow,   adjust=False).mean()
        macd_line = ema_fast - ema_slow
        sig_line  = macd_line.ewm(span=self.signal, adjust=False).mean()
        histogram = macd_line - sig_line

        hist_now  = histogram.iloc[-1]
        hist_prev = histogram.iloc[-2]
        macd_now  = macd_line.iloc[-1]

        # Signal line crossovers
        bull_cross = hist_prev <= 0 < hist_now
        bear_cross = hist_prev >= 0 > hist_now

        # Strength: absolute histogram magnitude normalised by price
        strength = min(abs(hist_now) / price * 1_000, 1.0)

        if bull_cross:
            return Signal(1, strength,
                          f"MACD bullish crossover (hist={hist_now:.4f})",
                          self.name, symbol, price)
        if bear_cross:
            return Signal(-1, strength,
                          f"MACD bearish crossover (hist={hist_now:.4f})",
                          self.name, symbol, price)

        # Zero-line crossovers (weaker signal)
        if macd_line.iloc[-2] <= 0 < macd_now:
            return Signal(1, strength * 0.6,
                          "MACD crossed above zero",
                          self.name, symbol, price)
        if macd_line.iloc[-2] >= 0 > macd_now:
            return Signal(-1, strength * 0.6,
                          "MACD crossed below zero",
                          self.name, symbol, price)

        # Trend continuation
        if hist_now > 0:
            return Signal(1, strength * 0.3, "MACD histogram positive",
                          self.name, symbol, price)
        if hist_now < 0:
            return Signal(-1, strength * 0.3, "MACD histogram negative",
                          self.name, symbol, price)

        return Signal(0, 0.0, "No MACD signal", self.name, symbol, price)
