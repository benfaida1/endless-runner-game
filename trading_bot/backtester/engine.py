"""
Backtesting Engine
──────────────────
Walk-forward simulation over historical OHLCV data.
Applies the same strategy + risk management used in live trading.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional

import pandas as pd
import numpy as np

from trading_bot.strategies.base import BaseStrategy
from trading_bot.strategies.multi_factor import MultiFactor
from trading_bot.core.portfolio import Portfolio, Trade
from trading_bot.core.risk_manager import RiskManager
from trading_bot.config import settings

logger = logging.getLogger(__name__)


class BacktestResult:
    def __init__(self, portfolio: Portfolio, equity_curve: List[float],
                 trades: List[Trade], initial_capital: float):
        self.portfolio       = portfolio
        self.equity_curve    = equity_curve
        self.trades          = trades
        self.initial_capital = initial_capital
        self.final_equity    = equity_curve[-1] if equity_curve else initial_capital

    @property
    def stats(self) -> dict:
        s = self.portfolio.stats()
        s["final_equity"]    = self.final_equity
        s["initial_capital"] = self.initial_capital
        return s

    def summary(self) -> str:
        s = self.stats
        win_rate = s.get("win_rate", 0) * 100
        ret      = (self.final_equity / self.initial_capital - 1) * 100
        lines = [
            "─" * 52,
            "  BACKTEST RESULTS",
            "─" * 52,
            f"  Initial capital : ${self.initial_capital:>12,.2f}",
            f"  Final equity    : ${self.final_equity:>12,.2f}",
            f"  Total return    : {ret:>+11.2f}%",
            f"  Total trades    : {s.get('total_trades', 0):>12}",
            f"  Win rate        : {win_rate:>11.1f}%",
            f"  Profit factor   : {s.get('profit_factor', 0):>12.2f}",
            f"  Sharpe ratio    : {s.get('sharpe_ratio', 0):>12.2f}",
            f"  Max drawdown    : {s.get('max_drawdown', 0)*100:>11.1f}%",
            f"  Best trade      : ${s.get('best_trade', 0):>+11.2f}",
            f"  Worst trade     : ${s.get('worst_trade', 0):>+11.2f}",
            "─" * 52,
        ]
        return "\n".join(lines)


class Backtester:

    def __init__(
        self,
        strategy:  Optional[BaseStrategy] = None,
        capital:   float = settings.INITIAL_CAPITAL,
        stop_loss_pct:    float = settings.STOP_LOSS_PCT,
        take_profit_pct:  float = settings.TAKE_PROFIT_PCT,
        trailing_stop_pct: float = settings.TRAILING_STOP_PCT,
        max_open_trades:  int   = settings.MAX_OPEN_TRADES,
        commission_pct:   float = 0.001,   # 0.1 % per trade
    ):
        self.strategy          = strategy or MultiFactor()
        self.capital           = capital
        self.stop_loss_pct     = stop_loss_pct
        self.take_profit_pct   = take_profit_pct
        self.trailing_stop_pct = trailing_stop_pct
        self.max_open_trades   = max_open_trades
        self.commission_pct    = commission_pct

    def run(self, data: Dict[str, pd.DataFrame],
            warmup: int = 50) -> BacktestResult:
        """
        Parameters
        ----------
        data   : {symbol → OHLCV DataFrame}
        warmup : number of candles to skip at the start (indicator warm-up)
        """
        portfolio  = Portfolio(self.capital)
        risk_mgr   = RiskManager(
            initial_capital    = self.capital,
            stop_loss_pct      = self.stop_loss_pct,
            take_profit_pct    = self.take_profit_pct,
            trailing_stop_pct  = self.trailing_stop_pct,
            max_open_trades    = self.max_open_trades,
        )

        # Align all symbols to common timestamps
        common_idx = None
        for sym, df in data.items():
            common_idx = df.index if common_idx is None else common_idx.intersection(df.index)

        if common_idx is None or len(common_idx) == 0:
            raise ValueError("No common timestamps across symbols.")

        equity_curve = [self.capital]

        for i, ts in enumerate(common_idx[warmup:], start=warmup):
            prices = {sym: float(data[sym].loc[ts, "close"]) for sym in data}

            # ── Exit checks ───────────────────────────────────────────────────
            for sym in list(risk_mgr.open_symbols):
                price = prices.get(sym, 0.0)
                risk_mgr.update_trailing_stop(sym, price)
                should_exit, reason = risk_mgr.should_exit(sym, price)
                if should_exit:
                    trade = portfolio.close_position(sym, price, reason)
                    risk_mgr.close_trade(sym)
                    if trade:
                        # Apply commission
                        commission = trade.quantity * price * self.commission_pct
                        portfolio.cash -= commission

            # ── Entry signals ─────────────────────────────────────────────────
            equity = portfolio.total_equity(prices)
            if risk_mgr.check_halt(equity):
                logger.warning("Backtester: max drawdown hit at candle %d", i)
                break

            for sym in data:
                if sym in risk_mgr.open_symbols:
                    continue
                slice_df = data[sym].iloc[:i + 1]
                signal   = self.strategy.generate_signal(slice_df, sym)

                if signal.is_buy:
                    price = prices[sym]
                    order = risk_mgr.size_order(
                        sym, price, equity, signal.strength, "buy", signal.reason
                    )
                    if order:
                        ok = portfolio.open_position(
                            sym, "long", order.quantity, price,
                            order.stop_loss, order.take_profit,
                        )
                        if ok:
                            commission = order.quantity * price * self.commission_pct
                            portfolio.cash -= commission

            equity_curve.append(portfolio.total_equity(prices))

        # Close remaining positions at last price
        for sym in list(risk_mgr.open_symbols):
            price = float(data[sym]["close"].iloc[-1])
            portfolio.close_position(sym, price, "End of backtest")
            risk_mgr.close_trade(sym)

        portfolio.equity_curve = equity_curve
        logger.info("Backtest complete. Trades: %d", len(portfolio.trade_log))
        return BacktestResult(portfolio, equity_curve, portfolio.trade_log, self.capital)
