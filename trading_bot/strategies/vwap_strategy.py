"""
VWAP + Volume Momentum Strategy
────────────────────────────────
VWAP (Volume-Weighted Average Price) is the institutional benchmark.
Price trading above VWAP with rising volume = strong buy pressure.
Price trading below VWAP with rising volume = strong sell pressure.

Additional filters:
  • Volume spike detector  (current vol > N × average)
  • OBV (On-Balance Volume) trend confirmation
  • Price momentum (rate of change)
"""

from __future__ import annotations

import pandas as pd
import numpy as np

from .base import BaseStrategy, Signal


def _vwap(df: pd.DataFrame, period: int = 20) -> pd.Series:
    """Rolling VWAP over the last `period` candles."""
    tp      = (df["high"] + df["low"] + df["close"]) / 3
    cum_tpv = (tp * df["volume"]).rolling(period).sum()
    cum_vol = df["volume"].rolling(period).sum()
    return cum_tpv / cum_vol.replace(0, np.nan)


def _obv(df: pd.DataFrame) -> pd.Series:
    """On-Balance Volume."""
    direction = np.sign(df["close"].diff()).fillna(0)
    return (direction * df["volume"]).cumsum()


def _roc(series: pd.Series, n: int = 10) -> pd.Series:
    """Rate of Change (momentum)."""
    return (series - series.shift(n)) / series.shift(n)


class VWAPStrategy(BaseStrategy):

    VWAP_PERIOD    = 20
    VOL_AVG_PERIOD = 20
    VOL_SPIKE_MULT = 1.5   # volume must be > 1.5× average
    ROC_PERIOD     = 10
    OBV_SMOOTH     = 5

    def __init__(self):
        super().__init__("VWAPStrategy")

    def generate_signal(self, df: pd.DataFrame, symbol: str = "") -> Signal:
        need = max(self.VWAP_PERIOD, self.VOL_AVG_PERIOD, self.ROC_PERIOD) + 10
        if not self._require_length(df, need):
            return Signal(0, 0.0, "Not enough data", self.name, symbol)

        price     = self._last_price(df)
        vwap      = _vwap(df, self.VWAP_PERIOD)
        vwap_now  = vwap.iloc[-1]

        # Volume analysis
        vol       = df["volume"]
        vol_avg   = vol.rolling(self.VOL_AVG_PERIOD).mean()
        vol_ratio = vol.iloc[-1] / vol_avg.iloc[-1] if vol_avg.iloc[-1] > 0 else 1.0
        vol_spike = vol_ratio >= self.VOL_SPIKE_MULT

        # OBV trend (smoothed slope)
        obv       = _obv(df)
        obv_slope = obv.diff(self.OBV_SMOOTH).iloc[-1]

        # Momentum
        roc_now   = _roc(df["close"], self.ROC_PERIOD).iloc[-1]

        # VWAP deviation (normalised)
        vwap_dev  = (price - vwap_now) / vwap_now if vwap_now > 0 else 0.0

        # ── Bullish: above VWAP + vol spike + OBV rising + positive momentum ──
        bullish_score = 0.0
        reasons = []

        if vwap_dev > 0.002:
            bullish_score += 0.30
            reasons.append(f"above VWAP (+{vwap_dev*100:.2f}%)")
        if vol_spike:
            bullish_score += 0.25
            reasons.append(f"vol spike {vol_ratio:.1f}×")
        if obv_slope > 0:
            bullish_score += 0.25
            reasons.append("OBV rising")
        if roc_now > 0.005:
            bullish_score += 0.20
            reasons.append(f"momentum +{roc_now*100:.1f}%")

        # ── Bearish: below VWAP + vol spike + OBV falling + negative momentum ─
        bearish_score = 0.0
        bear_reasons = []

        if vwap_dev < -0.002:
            bearish_score += 0.30
            bear_reasons.append(f"below VWAP ({vwap_dev*100:.2f}%)")
        if vol_spike:
            bearish_score += 0.25
            bear_reasons.append(f"vol spike {vol_ratio:.1f}×")
        if obv_slope < 0:
            bearish_score += 0.25
            bear_reasons.append("OBV falling")
        if roc_now < -0.005:
            bearish_score += 0.20
            bear_reasons.append(f"momentum {roc_now*100:.1f}%")

        if bullish_score >= 0.55 and bullish_score > bearish_score:
            return Signal(1, min(bullish_score, 1.0),
                          "VWAP BUY: " + " | ".join(reasons),
                          self.name, symbol, price)

        if bearish_score >= 0.55 and bearish_score > bullish_score:
            return Signal(-1, min(bearish_score, 1.0),
                          "VWAP SELL: " + " | ".join(bear_reasons),
                          self.name, symbol, price)

        net = bullish_score - bearish_score
        return Signal(0, abs(net) * 0.3,
                      f"VWAP neutral (dev={vwap_dev*100:.2f}% vol={vol_ratio:.1f}×)",
                      self.name, symbol, price)
