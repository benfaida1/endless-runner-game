"""
Trading Engine
──────────────
Orchestrates the full trading loop:
  1. Fetch fresh OHLCV data for each symbol
  2. Run the multi-factor strategy
  3. Apply risk management
  4. Execute orders (paper or live)
  5. Update portfolio state
  6. Check exit conditions on open positions
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import List, Optional

from trading_bot.config import settings
from trading_bot.data.fetcher import DataFetcher
from trading_bot.strategies.multi_factor import MultiFactor
from trading_bot.core.risk_manager import RiskManager
from trading_bot.core.portfolio import Portfolio
from trading_bot.notifications.telegram import TelegramNotifier

logger = logging.getLogger(__name__)


class TradingEngine:

    def __init__(
        self,
        symbols:    List[str]  = None,
        timeframe:  str        = settings.TIMEFRAME,
        paper:      bool       = True,
        capital:    float      = settings.INITIAL_CAPITAL,
        fetcher:    Optional[DataFetcher]  = None,
        strategy:   Optional[MultiFactor]  = None,
        risk_mgr:   Optional[RiskManager]  = None,
        portfolio:  Optional[Portfolio]    = None,
    ):
        self.symbols   = symbols or settings.SYMBOLS
        self.timeframe = timeframe
        self.paper     = paper

        self.fetcher   = fetcher   or DataFetcher(
            settings.EXCHANGE_ID, settings.API_KEY,
            settings.API_SECRET,  settings.TESTNET,
        )
        self.strategy  = strategy  or MultiFactor()
        self.risk_mgr  = risk_mgr  or RiskManager(initial_capital=capital)
        self.portfolio = portfolio or Portfolio(initial_capital=capital)
        self.notifier  = TelegramNotifier()

        self._running  = False
        self.tick_count = 0
        self._daily_tick = 0   # track when to send daily summary

    # ── Main loop ─────────────────────────────────────────────────────────────

    def run(self, interval_seconds: int = 60, max_ticks: int = 0) -> None:
        """
        Live / paper trading loop.
        interval_seconds : sleep between ticks (0 = no sleep, for backtesting)
        max_ticks        : stop after N ticks (0 = run forever)
        """
        self._running = True
        logger.info(
            "Engine started | paper=%s | symbols=%s | tf=%s",
            self.paper, self.symbols, self.timeframe,
        )

        while self._running:
            try:
                self._tick()
            except KeyboardInterrupt:
                logger.info("Interrupted by user — shutting down.")
                self._running = False
                break
            except Exception as exc:
                logger.error("Tick error: %s", exc, exc_info=True)

            self.tick_count += 1
            if max_ticks and self.tick_count >= max_ticks:
                logger.info("Reached max_ticks=%d — stopping.", max_ticks)
                break

            if interval_seconds > 0 and self._running:
                time.sleep(interval_seconds)

    def stop(self) -> None:
        self._running = False

    # ── Single tick ───────────────────────────────────────────────────────────

    def _tick(self) -> None:
        prices = {}
        for symbol in self.symbols:
            try:
                df = self.fetcher.fetch_ohlcv(symbol, self.timeframe,
                                               settings.OHLCV_LIMIT)
                price = float(df["close"].iloc[-1])
                prices[symbol] = price

                # ── Exit check ────────────────────────────────────────────────
                if symbol in self.risk_mgr.open_symbols:
                    self.risk_mgr.update_trailing_stop(symbol, price)
                    should_exit, exit_reason = self.risk_mgr.should_exit(symbol, price)
                    if should_exit:
                        self._close(symbol, price, exit_reason)
                        continue

                # ── Entry check ───────────────────────────────────────────────
                equity = self.portfolio.total_equity(prices)
                if self.risk_mgr.check_halt(equity):
                    logger.critical("Bot halted — max drawdown exceeded.")
                    self.notifier.halt_alert("Max drawdown exceeded", equity)
                    self._running = False
                    return

                if symbol not in self.risk_mgr.open_symbols:
                    signal = self.strategy.generate_signal(df, symbol)
                    logger.debug("[%s] %s", symbol, signal)

                    if signal.is_buy:
                        self.notifier.signal_alert(signal)
                        self._enter(symbol, "buy", price, signal.strength,
                                    signal.reason, equity)
                    elif signal.is_sell:
                        # Spot-only: skip short entries
                        pass

            except Exception as exc:
                logger.warning("Error processing %s: %s", symbol, exc)

        # Equity snapshot
        if prices:
            eq = self.portfolio.total_equity(prices)
            self.portfolio.equity_curve.append(eq)
            logger.info(
                "Tick #%d | Equity=%.2f | Positions=%s",
                self.tick_count, eq, self.risk_mgr.open_symbols,
            )
            # Daily summary every 24 ticks (≈ 24h at 1h interval)
            self._daily_tick += 1
            if self._daily_tick >= 24:
                self._daily_tick = 0
                self.notifier.daily_summary(
                    eq, self.portfolio.initial_capital, self.portfolio.stats()
                )

    # ── Order helpers ─────────────────────────────────────────────────────────

    def _enter(self, symbol: str, side: str, price: float,
               strength: float, reason: str, capital: float) -> None:
        order = self.risk_mgr.size_order(
            symbol, price, capital, strength, side, reason
        )
        if order is None:
            return

        if not self.paper:
            # Live order — would call exchange here
            logger.info("[LIVE] Placing %s order: %s", side.upper(), symbol)
        else:
            logger.info("[PAPER] %s %s qty=%.6f @ %.4f | %s",
                        side.upper(), symbol, order.quantity, price, reason)

        ok = self.portfolio.open_position(
            symbol, "long" if side == "buy" else "short",
            order.quantity, price, order.stop_loss, order.take_profit,
        )
        if ok:
            self.notifier.trade_opened(
                symbol, side, order.quantity, price,
                order.stop_loss, order.take_profit, reason,
            )

    def _close(self, symbol: str, price: float, reason: str) -> None:
        if not self.paper:
            logger.info("[LIVE] Closing %s @ %.4f | %s", symbol, price, reason)

        trade = self.portfolio.close_position(symbol, price, reason)
        self.risk_mgr.close_trade(symbol)

        if trade:
            sign = "+" if trade.pnl >= 0 else ""
            logger.info("[CLOSED] %s %s%.2f USDT (%.1f%%) — %s",
                        symbol, sign, trade.pnl, trade.pnl_pct * 100, reason)
            self.notifier.trade_closed(trade)

    # ── State ─────────────────────────────────────────────────────────────────

    def current_state(self, prices: dict) -> dict:
        return {
            "tick":        self.tick_count,
            "equity":      self.portfolio.total_equity(prices),
            "cash":        self.portfolio.cash,
            "positions":   len(self.portfolio.positions),
            "open":        self.risk_mgr.open_symbols,
            "stats":       self.portfolio.stats(),
            "drawdown":    self.risk_mgr.current_drawdown(
                               self.portfolio.total_equity(prices)),
        }
