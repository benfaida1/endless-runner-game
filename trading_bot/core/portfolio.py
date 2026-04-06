"""
Portfolio tracker — keeps track of cash, positions, trades, and PnL.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class Position:
    symbol:      str
    side:        str        # "long" | "short"
    quantity:    float
    entry_price: float
    entry_time:  datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    stop_loss:   float = 0.0
    take_profit: float = 0.0

    def unrealised_pnl(self, current_price: float) -> float:
        if self.side == "long":
            return (current_price - self.entry_price) * self.quantity
        return (self.entry_price - current_price) * self.quantity

    def unrealised_pct(self, current_price: float) -> float:
        if self.entry_price == 0:
            return 0.0
        if self.side == "long":
            return (current_price - self.entry_price) / self.entry_price
        return (self.entry_price - current_price) / self.entry_price


@dataclass
class Trade:
    symbol:      str
    side:        str
    quantity:    float
    entry_price: float
    exit_price:  float
    entry_time:  datetime
    exit_time:   datetime
    pnl:         float
    pnl_pct:     float
    reason:      str = ""

    @property
    def is_win(self) -> bool:
        return self.pnl > 0

    def __str__(self) -> str:
        sign = "+" if self.pnl >= 0 else ""
        return (f"{self.symbol} {self.side.upper()} "
                f"{sign}{self.pnl:.2f} USDT ({sign}{self.pnl_pct*100:.1f}%) "
                f"— {self.reason}")


class Portfolio:

    def __init__(self, initial_capital: float = 10_000.0):
        self.initial_capital = initial_capital
        self.cash            = initial_capital
        self.positions:  Dict[str, Position] = {}
        self.trade_log:  List[Trade]         = []
        self.equity_curve: List[float]       = [initial_capital]

    # ── Open / close ──────────────────────────────────────────────────────────

    def open_position(self, symbol: str, side: str, quantity: float,
                      price: float, stop_loss: float = 0.0,
                      take_profit: float = 0.0) -> bool:
        cost = quantity * price
        if cost > self.cash:
            logger.warning("Insufficient cash (%.2f) for %s cost %.2f",
                           self.cash, symbol, cost)
            return False

        self.cash -= cost
        self.positions[symbol] = Position(
            symbol      = symbol,
            side        = side,
            quantity    = quantity,
            entry_price = price,
            stop_loss   = stop_loss,
            take_profit = take_profit,
        )
        logger.info("Opened %s %s: qty=%.6f @ %.4f | cash left=%.2f",
                    side.upper(), symbol, quantity, price, self.cash)
        return True

    def close_position(self, symbol: str, price: float,
                       reason: str = "") -> Optional[Trade]:
        pos = self.positions.pop(symbol, None)
        if pos is None:
            logger.warning("No open position for %s", symbol)
            return None

        proceeds = pos.quantity * price
        self.cash += proceeds

        pnl = pos.unrealised_pnl(price)
        pnl_pct = pos.unrealised_pct(price)

        trade = Trade(
            symbol      = symbol,
            side        = pos.side,
            quantity    = pos.quantity,
            entry_price = pos.entry_price,
            exit_price  = price,
            entry_time  = pos.entry_time,
            exit_time   = datetime.now(timezone.utc),
            pnl         = pnl,
            pnl_pct     = pnl_pct,
            reason      = reason,
        )
        self.trade_log.append(trade)
        self.equity_curve.append(self.total_equity({symbol: price}))
        logger.info("Closed %s", trade)
        return trade

    # ── Metrics ───────────────────────────────────────────────────────────────

    def total_equity(self, prices: Dict[str, float]) -> float:
        position_value = sum(
            pos.quantity * prices.get(sym, pos.entry_price)
            for sym, pos in self.positions.items()
        )
        return self.cash + position_value

    def unrealised_pnl(self, prices: Dict[str, float]) -> float:
        return sum(
            pos.unrealised_pnl(prices.get(sym, pos.entry_price))
            for sym, pos in self.positions.items()
        )

    def stats(self) -> dict:
        trades = self.trade_log
        if not trades:
            return {"total_trades": 0}

        wins   = [t for t in trades if t.is_win]
        losses = [t for t in trades if not t.is_win]
        pnls   = [t.pnl for t in trades]

        win_rate  = len(wins) / len(trades)
        avg_win   = sum(t.pnl for t in wins)   / max(len(wins),   1)
        avg_loss  = sum(t.pnl for t in losses) / max(len(losses), 1)
        profit_factor = (
            sum(t.pnl for t in wins) / max(abs(sum(t.pnl for t in losses)), 1e-9)
        )
        total_pnl = sum(pnls)
        total_return = total_pnl / self.initial_capital

        # Sharpe ratio (simplified, daily returns proxy)
        import numpy as np
        if len(pnls) > 1:
            arr = np.array(pnls)
            sharpe = (arr.mean() / (arr.std() + 1e-9)) * (252 ** 0.5)
        else:
            sharpe = 0.0

        # Max drawdown from equity curve
        eq = self.equity_curve
        peak = eq[0]
        max_dd = 0.0
        for v in eq:
            peak = max(peak, v)
            dd = (peak - v) / peak
            max_dd = max(max_dd, dd)

        return {
            "total_trades":   len(trades),
            "win_rate":       win_rate,
            "avg_win":        avg_win,
            "avg_loss":       avg_loss,
            "profit_factor":  profit_factor,
            "total_pnl":      total_pnl,
            "total_return":   total_return,
            "sharpe_ratio":   sharpe,
            "max_drawdown":   max_dd,
            "best_trade":     max(pnls),
            "worst_trade":    min(pnls),
        }
