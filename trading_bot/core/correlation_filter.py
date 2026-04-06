"""
Correlation Filter
───────────────────
Prevents opening correlated positions simultaneously.
Example: BTC and ETH are highly correlated (~0.85+).
Opening both at once doubles your effective risk exposure.

Logic:
  • Compute rolling pairwise correlations over N candles
  • Before entering a trade, check if any open position
    is correlated > threshold with the candidate symbol
  • If yes, skip entry (or reduce size proportionally)
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class CorrelationFilter:

    def __init__(self, threshold: float = 0.75, lookback: int = 48):
        """
        threshold : pearson correlation above which two assets are
                    considered too correlated to hold simultaneously
        lookback  : number of candles used for the rolling correlation
        """
        self.threshold = threshold
        self.lookback  = lookback
        self._price_history: Dict[str, pd.Series] = {}

    # ── Public API ────────────────────────────────────────────────────────────

    def update(self, symbol: str, close_series: pd.Series) -> None:
        """Update the price history for a symbol."""
        self._price_history[symbol] = close_series.iloc[-self.lookback:]

    def can_open(self, candidate: str,
                 open_positions: List[str]) -> tuple[bool, str]:
        """
        Returns (True, "") if it's safe to open `candidate`.
        Returns (False, reason) if the candidate is too correlated
        with an existing open position.
        """
        if not open_positions:
            return True, ""

        if candidate not in self._price_history:
            return True, ""   # no data yet — allow

        candidate_rets = self._returns(candidate)
        if candidate_rets is None:
            return True, ""

        for sym in open_positions:
            if sym not in self._price_history:
                continue
            existing_rets = self._returns(sym)
            if existing_rets is None:
                continue

            corr = self._pearson(candidate_rets, existing_rets)
            if corr is not None and corr >= self.threshold:
                msg = (f"{candidate} correlated with open {sym} "
                       f"(r={corr:.2f} ≥ {self.threshold})")
                logger.info("Correlation filter blocked: %s", msg)
                return False, msg

        return True, ""

    def correlation_matrix(self) -> Optional[pd.DataFrame]:
        """Return the current pairwise correlation matrix."""
        syms = list(self._price_history.keys())
        if len(syms) < 2:
            return None

        rets = {}
        for sym in syms:
            r = self._returns(sym)
            if r is not None:
                rets[sym] = r

        if len(rets) < 2:
            return None

        df = pd.DataFrame(rets)
        return df.corr()

    # ── Internal ──────────────────────────────────────────────────────────────

    def _returns(self, symbol: str) -> Optional[pd.Series]:
        prices = self._price_history.get(symbol)
        if prices is None or len(prices) < 5:
            return None
        return prices.pct_change().dropna()

    @staticmethod
    def _pearson(a: pd.Series, b: pd.Series) -> Optional[float]:
        n = min(len(a), len(b))
        if n < 5:
            return None
        try:
            return float(np.corrcoef(a.values[-n:], b.values[-n:])[0, 1])
        except Exception:
            return None
