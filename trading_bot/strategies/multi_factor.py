"""
Multi-Factor Strategy Aggregator
──────────────────────────────────
Combines all strategies using weighted voting.
A trade is only placed when:
  - The aggregated score exceeds a confidence threshold
  - At least N strategies agree on direction
"""

from __future__ import annotations

from typing import Dict, List

import pandas as pd

from .base import BaseStrategy, Signal
from .ma_crossover import MACrossover
from .rsi_strategy import RSIStrategy
from .macd_strategy import MACDStrategy
from .bb_strategy import BBStrategy
from .vwap_strategy import VWAPStrategy
from trading_bot.config.settings import STRATEGY_WEIGHTS

# Include VWAP in the default weight map
_DEFAULT_WEIGHTS = {**STRATEGY_WEIGHTS, "VWAPStrategy": 0.20}
# Re-normalise so weights sum to 1
_total = sum(_DEFAULT_WEIGHTS.values())
_DEFAULT_WEIGHTS = {k: v / _total for k, v in _DEFAULT_WEIGHTS.items()}


class MultiFactor(BaseStrategy):

    BUY_THRESHOLD  = 0.30   # weighted score to trigger BUY
    SELL_THRESHOLD = -0.30  # weighted score to trigger SELL
    MIN_AGREEING   = 2      # at least 2 strategies must agree

    def __init__(self, weights: Dict[str, float] = None):
        super().__init__("MultiFactor")
        self.weights = weights or _DEFAULT_WEIGHTS
        self._strategies: List[BaseStrategy] = [
            MACrossover(),
            RSIStrategy(),
            MACDStrategy(),
            BBStrategy(),
            VWAPStrategy(),
        ]

    def generate_signal(self, df: pd.DataFrame, symbol: str = "") -> Signal:
        signals: List[Signal] = []
        for strat in self._strategies:
            sig = strat.generate_signal(df, symbol)
            signals.append(sig)

        # Weighted vote
        score     = 0.0
        total_w   = 0.0
        buy_count = sell_count = 0

        for sig in signals:
            w = self.weights.get(sig.strategy, 0.25)
            vote = sig.action * sig.strength * w
            score   += vote
            total_w += w
            if sig.action ==  1: buy_count  += 1
            if sig.action == -1: sell_count += 1

        norm_score = score / total_w if total_w else 0.0
        price = float(df["close"].iloc[-1])

        reasons = " | ".join(
            f"{s.strategy}: {'BUY' if s.action==1 else 'SELL' if s.action==-1 else 'HOLD'}"
            f"({s.strength:.2f})"
            for s in signals
        )

        if norm_score >= self.BUY_THRESHOLD and buy_count >= self.MIN_AGREEING:
            return Signal(1, min(norm_score, 1.0),
                          f"Multi-factor BUY score={norm_score:.2f} | {reasons}",
                          self.name, symbol, price,
                          {"sub_signals": signals, "score": norm_score})

        if norm_score <= self.SELL_THRESHOLD and sell_count >= self.MIN_AGREEING:
            return Signal(-1, min(abs(norm_score), 1.0),
                          f"Multi-factor SELL score={norm_score:.2f} | {reasons}",
                          self.name, symbol, price,
                          {"sub_signals": signals, "score": norm_score})

        return Signal(0, abs(norm_score),
                      f"No consensus (score={norm_score:.2f}) | {reasons}",
                      self.name, symbol, price,
                      {"sub_signals": signals, "score": norm_score})
