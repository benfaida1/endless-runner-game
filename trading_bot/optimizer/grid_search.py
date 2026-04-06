"""
Strategy Parameter Optimizer
─────────────────────────────
Grid-search over strategy hyper-parameters using the backtester.
Optimises for Sharpe ratio (risk-adjusted returns) rather than raw PnL
to avoid over-fitting to lucky high-variance results.

Usage
─────
  python main.py optimize
  python main.py optimize --metric sharpe    # default
  python main.py optimize --metric return
  python main.py optimize --metric profit_factor
"""

from __future__ import annotations

import itertools
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from trading_bot.backtester.engine import Backtester, BacktestResult
from trading_bot.strategies.multi_factor import MultiFactor
from trading_bot.strategies.ma_crossover import MACrossover
from trading_bot.strategies.rsi_strategy import RSIStrategy
from trading_bot.strategies.macd_strategy import MACDStrategy
from trading_bot.strategies.bb_strategy import BBStrategy
from trading_bot.config import settings

logger = logging.getLogger(__name__)


# ── Parameter grids ──────────────────────────────────────────────────────────

DEFAULT_GRID: Dict[str, List[Any]] = {
    # MA Crossover
    "ma_fast":   [7, 9, 12],
    "ma_slow":   [18, 21, 26],
    "ma_signal": [40, 50, 60],
    # RSI
    "rsi_period":     [10, 14, 21],
    "rsi_oversold":   [25, 30, 35],
    "rsi_overbought": [65, 70, 75],
    # MACD
    "macd_fast":   [8, 12],
    "macd_slow":   [21, 26],
    "macd_signal": [7, 9],
    # Bollinger Bands
    "bb_period": [15, 20, 25],
    "bb_std":    [1.8, 2.0, 2.2],
    # Risk
    "stop_loss_pct":    [0.02, 0.03, 0.04],
    "take_profit_pct":  [0.04, 0.06, 0.08],
}

# Smaller grid for fast testing
FAST_GRID: Dict[str, List[Any]] = {
    "ma_fast":          [7, 9],
    "ma_slow":          [18, 21],
    "ma_signal":        [40, 50],
    "rsi_period":       [10, 14],
    "rsi_oversold":     [25, 30],
    "rsi_overbought":   [70, 75],
    "macd_fast":        [8, 12],
    "macd_slow":        [21, 26],
    "macd_signal":      [7, 9],
    "bb_period":        [15, 20],
    "bb_std":           [1.8, 2.0],
    "stop_loss_pct":    [0.02, 0.03],
    "take_profit_pct":  [0.05, 0.07],
}


@dataclass
class OptimResult:
    params:   Dict[str, Any]
    metric:   float
    stats:    dict
    equity:   float
    field_name: str = "sharpe_ratio"

    def __lt__(self, other: "OptimResult") -> bool:
        return self.metric < other.metric

    def __str__(self) -> str:
        return (f"metric={self.metric:.4f} equity=${self.equity:,.2f} "
                f"trades={self.stats.get('total_trades',0)} "
                f"wr={self.stats.get('win_rate',0)*100:.1f}%")


class GridSearchOptimizer:

    METRIC_KEYS = {
        "sharpe":         "sharpe_ratio",
        "return":         "total_return",
        "profit_factor":  "profit_factor",
        "win_rate":       "win_rate",
    }

    def __init__(
        self,
        data:    Dict[str, pd.DataFrame],
        grid:    Optional[Dict[str, List[Any]]] = None,
        metric:  str   = "sharpe",
        capital: float = settings.INITIAL_CAPITAL,
        warmup:  int   = 50,
        top_n:   int   = 5,
    ):
        self.data    = data
        self.grid    = grid or FAST_GRID
        self.metric  = self.METRIC_KEYS.get(metric, "sharpe_ratio")
        self.capital = capital
        self.warmup  = warmup
        self.top_n   = top_n

    def run(self) -> List[OptimResult]:
        """
        Run grid search. Returns top_n results sorted by metric (descending).
        """
        keys   = list(self.grid.keys())
        values = list(self.grid.values())
        combos = list(itertools.product(*values))
        total  = len(combos)

        logger.info("Grid search: %d combinations × %d symbols",
                    total, len(self.data))

        results: List[OptimResult] = []

        for i, combo in enumerate(combos):
            params = dict(zip(keys, combo))

            # Validate: fast < slow for MAs
            if params.get("ma_fast", 0) >= params.get("ma_slow", 1):
                continue
            if params.get("macd_fast", 0) >= params.get("macd_slow", 1):
                continue
            if params.get("stop_loss_pct", 0) >= params.get("take_profit_pct", 0):
                continue

            try:
                result = self._evaluate(params)
                if result is not None:
                    results.append(result)
            except Exception as exc:
                logger.debug("Combo %d failed: %s", i, exc)

            if (i + 1) % 50 == 0 or (i + 1) == total:
                logger.info("Progress: %d/%d  |  best so far: %.4f",
                            i + 1, total,
                            max((r.metric for r in results), default=0))

        results.sort(reverse=True)
        logger.info("Optimisation complete. Top result: %s", results[0] if results else "none")
        return results[:self.top_n]

    def _evaluate(self, params: Dict[str, Any]) -> Optional[OptimResult]:
        strategy = MultiFactor(
            weights=settings.STRATEGY_WEIGHTS,
        )
        # Patch sub-strategies with grid params
        for strat in strategy._strategies:
            name = type(strat).__name__
            if name == "MACrossover":
                strat.fast   = params.get("ma_fast",   strat.fast)
                strat.slow   = params.get("ma_slow",   strat.slow)
                strat.signal = params.get("ma_signal", strat.signal)
            elif name == "RSIStrategy":
                strat.period     = params.get("rsi_period",     strat.period)
                strat.oversold   = params.get("rsi_oversold",   strat.oversold)
                strat.overbought = params.get("rsi_overbought", strat.overbought)
            elif name == "MACDStrategy":
                strat.fast   = params.get("macd_fast",   strat.fast)
                strat.slow   = params.get("macd_slow",   strat.slow)
                strat.signal = params.get("macd_signal", strat.signal)
            elif name == "BBStrategy":
                strat.period  = params.get("bb_period", strat.period)
                strat.std_dev = params.get("bb_std",    strat.std_dev)

        backtester = Backtester(
            strategy          = strategy,
            capital           = self.capital,
            stop_loss_pct     = params.get("stop_loss_pct",    settings.STOP_LOSS_PCT),
            take_profit_pct   = params.get("take_profit_pct",  settings.TAKE_PROFIT_PCT),
            trailing_stop_pct = settings.TRAILING_STOP_PCT,
            max_open_trades   = settings.MAX_OPEN_TRADES,
        )

        bt: BacktestResult = backtester.run(self.data, warmup=self.warmup)
        stats  = bt.stats
        metric = stats.get(self.metric, 0.0)

        # Penalise results with < 5 trades (insufficient sample)
        if stats.get("total_trades", 0) < 5:
            metric *= 0.5

        return OptimResult(
            params     = params,
            metric     = metric,
            stats      = stats,
            equity     = bt.final_equity,
            field_name = self.metric,
        )
