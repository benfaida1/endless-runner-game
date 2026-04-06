"""
Monte Carlo Risk Simulator
───────────────────────────
Given a sequence of historical trade PnLs, simulate thousands of
alternative orderings to estimate the true distribution of outcomes.

Answers questions like:
  • "What's the 95th-percentile max drawdown I should expect?"
  • "What's the probability of blowing up (losing > 30%) ?"
  • "What's the realistic range for my annual return?"

Usage:
  from trading_bot.backtester.monte_carlo import MonteCarloSimulator
  sim = MonteCarloSimulator(trade_pnls, initial_capital=10_000)
  report = sim.run(n_simulations=5_000)
  print(report.summary())
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class MCReport:
    n_sims:          int
    initial_capital: float
    trade_pnls:      List[float]

    # Distribution of final equity
    final_equity_p5:  float   # 5th percentile (worst case)
    final_equity_p25: float
    final_equity_p50: float   # median
    final_equity_p75: float
    final_equity_p95: float   # best case

    # Distribution of max drawdown
    max_dd_p50:  float
    max_dd_p95:  float        # 95th percentile worst drawdown

    # Distribution of CAGR
    cagr_p5:   float
    cagr_p50:  float
    cagr_p95:  float

    # Risk metrics
    prob_loss:     float   # P(final equity < initial)
    prob_ruin:     float   # P(drawdown > 30%)
    expected_return: float # mean final equity

    def summary(self) -> str:
        ic = self.initial_capital
        lines = [
            "─" * 56,
            "  MONTE CARLO SIMULATION REPORT",
            f"  {self.n_sims:,} simulations × {len(self.trade_pnls)} trades",
            "─" * 56,
            f"  Final Equity Distribution (from ${ic:,.0f})",
            f"    5th  pct (worst)  : ${self.final_equity_p5:>10,.2f}",
            f"    25th pct          : ${self.final_equity_p25:>10,.2f}",
            f"    50th pct (median) : ${self.final_equity_p50:>10,.2f}",
            f"    75th pct          : ${self.final_equity_p75:>10,.2f}",
            f"    95th pct (best)   : ${self.final_equity_p95:>10,.2f}",
            "",
            f"  Max Drawdown Distribution",
            f"    Median drawdown   : {self.max_dd_p50*100:>10.1f}%",
            f"    95th pct drawdown : {self.max_dd_p95*100:>10.1f}%",
            "",
            f"  CAGR Distribution (annualised)",
            f"    5th  pct          : {self.cagr_p5*100:>+10.1f}%",
            f"    Median            : {self.cagr_p50*100:>+10.1f}%",
            f"    95th pct          : {self.cagr_p95*100:>+10.1f}%",
            "",
            f"  Risk Metrics",
            f"    P(loss)           : {self.prob_loss*100:>10.1f}%",
            f"    P(drawdown > 30%) : {self.prob_ruin*100:>10.1f}%",
            f"    Expected equity   : ${self.expected_return:>10,.2f}",
            "─" * 56,
        ]
        return "\n".join(lines)


class MonteCarloSimulator:

    def __init__(
        self,
        trade_pnls:      List[float],
        initial_capital: float = 10_000.0,
        annual_trades:   int   = 100,   # for CAGR annualisation
    ):
        self.pnls            = np.array(trade_pnls, dtype=float)
        self.initial_capital = initial_capital
        self.annual_trades   = annual_trades

    def run(self, n_simulations: int = 5_000, seed: int = 42) -> MCReport:
        rng    = np.random.default_rng(seed)
        n      = len(self.pnls)
        ic     = self.initial_capital

        if n < 3:
            logger.warning("Not enough trades for Monte Carlo (need ≥ 3).")
            return self._empty_report(n_simulations)

        final_equities = np.empty(n_simulations)
        max_drawdowns  = np.empty(n_simulations)

        for i in range(n_simulations):
            # Random permutation of historical trade PnLs
            shuffled = rng.choice(self.pnls, size=n, replace=True)
            equity   = ic + np.cumsum(shuffled)
            equity   = np.concatenate([[ic], equity])

            final_equities[i] = equity[-1]

            # Max drawdown of this path
            peak   = np.maximum.accumulate(equity)
            dd     = (peak - equity) / np.where(peak > 0, peak, 1)
            max_drawdowns[i] = dd.max()

        # CAGR: annualise using number of trades per year
        years     = n / self.annual_trades
        cagr_vals = np.where(
            final_equities > 0,
            (final_equities / ic) ** (1 / max(years, 0.01)) - 1,
            -1.0,
        )

        return MCReport(
            n_sims           = n_simulations,
            initial_capital  = ic,
            trade_pnls       = list(self.pnls),
            final_equity_p5  = float(np.percentile(final_equities, 5)),
            final_equity_p25 = float(np.percentile(final_equities, 25)),
            final_equity_p50 = float(np.percentile(final_equities, 50)),
            final_equity_p75 = float(np.percentile(final_equities, 75)),
            final_equity_p95 = float(np.percentile(final_equities, 95)),
            max_dd_p50       = float(np.percentile(max_drawdowns, 50)),
            max_dd_p95       = float(np.percentile(max_drawdowns, 95)),
            cagr_p5          = float(np.percentile(cagr_vals, 5)),
            cagr_p50         = float(np.percentile(cagr_vals, 50)),
            cagr_p95         = float(np.percentile(cagr_vals, 95)),
            prob_loss        = float((final_equities < ic).mean()),
            prob_ruin        = float((max_drawdowns > 0.30).mean()),
            expected_return  = float(final_equities.mean()),
        )

    def _empty_report(self, n: int) -> MCReport:
        ic = self.initial_capital
        return MCReport(
            n_sims=n, initial_capital=ic, trade_pnls=list(self.pnls),
            final_equity_p5=ic, final_equity_p25=ic, final_equity_p50=ic,
            final_equity_p75=ic, final_equity_p95=ic,
            max_dd_p50=0, max_dd_p95=0,
            cagr_p5=0, cagr_p50=0, cagr_p95=0,
            prob_loss=0, prob_ruin=0, expected_return=ic,
        )
