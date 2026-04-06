"""
Market Regime Detector
───────────────────────
Identifies the current market regime before entering any trade:
  • BULL    — strong uptrend  → enable long entries, tighten stops
  • BEAR    — strong downtrend → disable longs, widen stops or sit out
  • SIDEWAYS — ranging market  → use mean-reversion signals (BB/RSI)
  • VOLATILE — high-vol chaos  → reduce position size, skip weak signals

Detection uses a combination of:
  1. ADX (Average Directional Index)  — trend strength
  2. EMA slope                         — direction
  3. ATR ratio                         — volatility regime
  4. 200-period SMA filter             — macro bias
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

import numpy as np
import pandas as pd


class Regime(str, Enum):
    BULL     = "BULL"
    BEAR     = "BEAR"
    SIDEWAYS = "SIDEWAYS"
    VOLATILE = "VOLATILE"
    UNKNOWN  = "UNKNOWN"


@dataclass
class RegimeState:
    regime:    Regime
    adx:       float
    ema_slope: float   # % per candle
    atr_ratio: float   # current ATR / 50-period average ATR
    above_200: bool    # price above 200-SMA
    confidence: float  # 0–1

    def __str__(self) -> str:
        return (f"{self.regime.value} "
                f"(adx={self.adx:.1f} slope={self.ema_slope*100:.3f}% "
                f"atr_ratio={self.atr_ratio:.2f} above200={self.above_200} "
                f"conf={self.confidence:.2f})")

    @property
    def position_size_multiplier(self) -> float:
        """Scale position size based on regime."""
        if self.regime == Regime.BULL:
            return 1.0
        if self.regime == Regime.SIDEWAYS:
            return 0.7
        if self.regime == Regime.BEAR:
            return 0.3   # allow tiny longs only for counter-trend scalps
        if self.regime == Regime.VOLATILE:
            return 0.5
        return 0.5

    @property
    def allows_long(self) -> bool:
        return self.regime in (Regime.BULL, Regime.SIDEWAYS, Regime.VOLATILE)

    @property
    def prefers_mean_reversion(self) -> bool:
        return self.regime == Regime.SIDEWAYS


def _adx(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Compute ADX."""
    high  = df["high"]
    low   = df["low"]
    close = df["close"]

    tr1 = high - low
    tr2 = (high - close.shift()).abs()
    tr3 = (low  - close.shift()).abs()
    tr  = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    dm_plus  = high.diff().clip(lower=0)
    dm_minus = (-low.diff()).clip(lower=0)
    # Zero out when the other direction is stronger
    mask = dm_plus < dm_minus; dm_plus[mask]  = 0
    mask = dm_minus < dm_plus; dm_minus[mask] = 0

    atr  = tr.ewm(span=period,      adjust=False).mean()
    dp   = (dm_plus.ewm(span=period, adjust=False).mean()  / atr.replace(0, np.nan)) * 100
    dm   = (dm_minus.ewm(span=period, adjust=False).mean() / atr.replace(0, np.nan)) * 100
    dx   = ((dp - dm).abs() / (dp + dm).replace(0, np.nan)) * 100
    return dx.ewm(span=period, adjust=False).mean()


def _atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high, low, close = df["high"], df["low"], df["close"]
    tr = pd.concat([high - low,
                    (high - close.shift()).abs(),
                    (low  - close.shift()).abs()], axis=1).max(axis=1)
    return tr.ewm(span=period, adjust=False).mean()


class MarketRegimeDetector:

    ADX_TREND_THRESHOLD   = 25   # ADX > 25 → trending
    ADX_STRONG_THRESHOLD  = 40   # ADX > 40 → strong trend
    ATR_VOLATILE_RATIO    = 1.8  # current ATR > 1.8× average → volatile
    EMA_PERIOD            = 50
    SMA_PERIOD            = 200
    ADX_PERIOD            = 14
    ATR_PERIOD            = 14
    ATR_AVG_PERIOD        = 50

    def __init__(self):
        self._cache: dict[str, RegimeState] = {}

    def detect(self, df: pd.DataFrame, symbol: str = "") -> RegimeState:
        need = max(self.SMA_PERIOD, self.ATR_AVG_PERIOD) + self.ADX_PERIOD + 5
        if len(df) < need:
            state = RegimeState(Regime.UNKNOWN, 0, 0, 1.0, False, 0.0)
            self._cache[symbol] = state
            return state

        close    = df["close"]
        price    = float(close.iloc[-1])

        # ADX
        adx_ser  = _adx(df, self.ADX_PERIOD)
        adx_val  = float(adx_ser.iloc[-1])

        # EMA slope (% change over last 5 candles)
        ema      = close.ewm(span=self.EMA_PERIOD, adjust=False).mean()
        slope    = (float(ema.iloc[-1]) - float(ema.iloc[-6])) / float(ema.iloc[-6])

        # ATR ratio
        atr      = _atr(df, self.ATR_PERIOD)
        atr_avg  = atr.rolling(self.ATR_AVG_PERIOD).mean()
        atr_ratio = float(atr.iloc[-1]) / max(float(atr_avg.iloc[-1]), 1e-9)

        # 200-SMA filter
        sma200   = close.rolling(self.SMA_PERIOD).mean()
        above200 = price > float(sma200.iloc[-1])

        # ── Classify ──────────────────────────────────────────────────────────
        confidence = 0.0

        if atr_ratio >= self.ATR_VOLATILE_RATIO:
            regime = Regime.VOLATILE
            confidence = min((atr_ratio - 1) / 2, 1.0)

        elif adx_val >= self.ADX_TREND_THRESHOLD:
            if slope > 0 and above200:
                regime = Regime.BULL
                confidence = min(adx_val / 100 + (slope * 100), 1.0)
            elif slope < 0:
                regime = Regime.BEAR
                confidence = min(adx_val / 100 + abs(slope * 100), 1.0)
            else:
                regime = Regime.SIDEWAYS
                confidence = 0.5
        else:
            regime = Regime.SIDEWAYS
            confidence = min((self.ADX_TREND_THRESHOLD - adx_val) / self.ADX_TREND_THRESHOLD, 1.0)

        state = RegimeState(
            regime     = regime,
            adx        = adx_val,
            ema_slope  = slope,
            atr_ratio  = atr_ratio,
            above_200  = above200,
            confidence = round(confidence, 3),
        )
        self._cache[symbol] = state
        return state

    def last(self, symbol: str) -> Optional[RegimeState]:
        return self._cache.get(symbol)
