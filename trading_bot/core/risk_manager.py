"""
Risk Manager
────────────
Enforces:
  • Position sizing (Kelly criterion / fixed fractional)
  • Stop-loss / take-profit / trailing stop computation
  • Max drawdown circuit breaker
  • Maximum concurrent open trades
  • Per-trade risk limit
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, Optional

from trading_bot.config import settings

logger = logging.getLogger(__name__)


@dataclass
class TradeOrder:
    symbol:       str
    side:         str       # "buy" | "sell"
    quantity:     float
    entry_price:  float
    stop_loss:    float
    take_profit:  float
    trailing_pct: float
    risk_amount:  float
    reason:       str = ""


class RiskManager:

    def __init__(
        self,
        initial_capital:   float = settings.INITIAL_CAPITAL,
        max_position_pct:  float = settings.MAX_POSITION_PCT,
        stop_loss_pct:     float = settings.STOP_LOSS_PCT,
        take_profit_pct:   float = settings.TAKE_PROFIT_PCT,
        trailing_stop_pct: float = settings.TRAILING_STOP_PCT,
        max_drawdown_pct:  float = settings.MAX_DRAWDOWN_PCT,
        risk_per_trade_pct:float = settings.RISK_PER_TRADE_PCT,
        max_open_trades:   int   = settings.MAX_OPEN_TRADES,
    ):
        self.initial_capital    = initial_capital
        self.peak_capital       = initial_capital
        self.max_position_pct   = max_position_pct
        self.stop_loss_pct      = stop_loss_pct
        self.take_profit_pct    = take_profit_pct
        self.trailing_stop_pct  = trailing_stop_pct
        self.max_drawdown_pct   = max_drawdown_pct
        self.risk_per_trade_pct = risk_per_trade_pct
        self.max_open_trades    = max_open_trades

        self._open_trades: Dict[str, dict] = {}   # symbol → trade info
        self._halted = False

    # ── Public API ────────────────────────────────────────────────────────────

    def check_halt(self, current_capital: float) -> bool:
        """Return True if the bot should halt due to excessive drawdown."""
        if self._halted:
            return True
        self.peak_capital = max(self.peak_capital, current_capital)
        drawdown = (self.peak_capital - current_capital) / self.peak_capital
        if drawdown >= self.max_drawdown_pct:
            logger.critical(
                "MAX DRAWDOWN REACHED (%.1f%%) — bot halted!", drawdown * 100
            )
            self._halted = True
            return True
        return False

    def can_open_trade(self, symbol: str) -> tuple[bool, str]:
        """Check if a new trade can be opened."""
        if self._halted:
            return False, "Bot halted (max drawdown)"
        if symbol in self._open_trades:
            return False, f"Already holding {symbol}"
        if len(self._open_trades) >= self.max_open_trades:
            return False, f"Max open trades ({self.max_open_trades}) reached"
        return True, ""

    def size_order(
        self,
        symbol:          str,
        entry_price:     float,
        capital:         float,
        signal_strength: float = 1.0,
        side:            str   = "buy",
        reason:          str   = "",
    ) -> Optional[TradeOrder]:
        """
        Calculate position size using fixed fractional risk model.
        Risk = capital × risk_per_trade_pct
        Quantity = risk / (entry_price × stop_loss_pct)
        Clamp to max_position_pct of capital.
        """
        ok, msg = self.can_open_trade(symbol)
        if not ok:
            logger.info("Order rejected for %s: %s", symbol, msg)
            return None

        risk_amount = capital * self.risk_per_trade_pct * signal_strength

        if side == "buy":
            stop_price = entry_price * (1 - self.stop_loss_pct)
            tp_price   = entry_price * (1 + self.take_profit_pct)
        else:
            stop_price = entry_price * (1 + self.stop_loss_pct)
            tp_price   = entry_price * (1 - self.take_profit_pct)

        risk_per_unit = abs(entry_price - stop_price)
        if risk_per_unit <= 0:
            return None

        quantity = risk_amount / risk_per_unit

        # Clamp to max position size
        max_qty = (capital * self.max_position_pct) / entry_price
        quantity = min(quantity, max_qty)

        if quantity <= 0:
            return None

        order = TradeOrder(
            symbol       = symbol,
            side         = side,
            quantity     = quantity,
            entry_price  = entry_price,
            stop_loss    = stop_price,
            take_profit  = tp_price,
            trailing_pct = self.trailing_stop_pct,
            risk_amount  = risk_amount,
            reason       = reason,
        )
        self._open_trades[symbol] = {
            "order":        order,
            "highest_price": entry_price,
            "trailing_stop": stop_price,
        }
        logger.info(
            "Sized order: %s %s %.6f @ %.4f | SL=%.4f TP=%.4f",
            side.upper(), symbol, quantity, entry_price, stop_price, tp_price,
        )
        return order

    def update_trailing_stop(self, symbol: str, current_price: float) -> Optional[float]:
        """Update trailing stop and return new stop price (or None if no change)."""
        if symbol not in self._open_trades:
            return None
        trade = self._open_trades[symbol]
        order = trade["order"]

        if order.side == "buy":
            if current_price > trade["highest_price"]:
                trade["highest_price"] = current_price
                new_stop = current_price * (1 - order.trailing_pct)
                if new_stop > trade["trailing_stop"]:
                    trade["trailing_stop"] = new_stop
                    logger.debug("Trailing stop updated for %s: %.4f", symbol, new_stop)
                    return new_stop
        return None

    def should_exit(self, symbol: str, current_price: float) -> tuple[bool, str]:
        """Check if a position should be closed."""
        if symbol not in self._open_trades:
            return False, ""
        trade = self._open_trades[symbol]
        order = trade["order"]

        if order.side == "buy":
            if current_price <= trade["trailing_stop"]:
                return True, f"Trailing stop hit @ {current_price:.4f}"
            if current_price <= order.stop_loss:
                return True, f"Stop-loss hit @ {current_price:.4f}"
            if current_price >= order.take_profit:
                return True, f"Take-profit hit @ {current_price:.4f}"
        else:
            if current_price >= trade["trailing_stop"]:
                return True, f"Trailing stop hit @ {current_price:.4f}"
            if current_price >= order.stop_loss:
                return True, f"Stop-loss hit @ {current_price:.4f}"
            if current_price <= order.take_profit:
                return True, f"Take-profit hit @ {current_price:.4f}"

        return False, ""

    def close_trade(self, symbol: str) -> Optional[dict]:
        return self._open_trades.pop(symbol, None)

    @property
    def open_symbols(self) -> list[str]:
        return list(self._open_trades.keys())

    @property
    def open_count(self) -> int:
        return len(self._open_trades)

    def current_drawdown(self, capital: float) -> float:
        if self.peak_capital == 0:
            return 0.0
        return (self.peak_capital - capital) / self.peak_capital
