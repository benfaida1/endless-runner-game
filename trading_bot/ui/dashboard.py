"""
Rich Terminal Dashboard
───────────────────────
Displays a live-updating view of:
  • Portfolio equity & PnL
  • Open positions
  • Recent trades
  • Strategy signals
  • Per-symbol candlestick summary
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Optional

from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box

from trading_bot.core.portfolio import Portfolio, Trade
from trading_bot.strategies.base import Signal

console = Console()


# ── Colour helpers ────────────────────────────────────────────────────────────

def _pnl_color(value: float) -> str:
    return "green" if value >= 0 else "red"

def _fmt_pnl(value: float, pct: float = None) -> str:
    sign = "+" if value >= 0 else ""
    color = _pnl_color(value)
    s = f"[{color}]{sign}{value:,.2f}[/{color}]"
    if pct is not None:
        s += f" [dim]({sign}{pct*100:.1f}%)[/dim]"
    return s

def _signal_badge(action: int) -> str:
    if action ==  1: return "[bold green] BUY [/bold green]"
    if action == -1: return "[bold red] SELL [/bold red]"
    return "[dim] HOLD [/dim]"


# ── Sub-panels ────────────────────────────────────────────────────────────────

def build_header(equity: float, initial: float, drawdown: float,
                 tick: int) -> Panel:
    total_pnl = equity - initial
    total_pct = total_pnl / initial if initial else 0
    color     = _pnl_color(total_pnl)
    dd_color  = "red" if drawdown > 0.05 else "yellow" if drawdown > 0.02 else "green"

    text = Text()
    text.append("  TRADING BOT DASHBOARD  ", style="bold white on blue")
    text.append(f"  Equity: ")
    text.append(f"${equity:>12,.2f}", style=f"bold {color}")
    text.append(f"  PnL: ")
    text.append(f"{'+' if total_pnl>=0 else ''}{total_pnl:,.2f} ({total_pct*100:.1f}%)",
                style=f"bold {color}")
    text.append(f"  Drawdown: ")
    text.append(f"{drawdown*100:.1f}%", style=f"bold {dd_color}")
    text.append(f"  Tick: #{tick}")
    return Panel(text, box=box.DOUBLE_EDGE)


def build_positions_table(portfolio: Portfolio,
                          prices: Dict[str, float]) -> Table:
    tbl = Table(title="[bold]Open Positions[/bold]", box=box.SIMPLE_HEAVY,
                show_header=True, header_style="bold cyan")
    tbl.add_column("Symbol",    style="bold white",  no_wrap=True)
    tbl.add_column("Side",      justify="center")
    tbl.add_column("Qty",       justify="right")
    tbl.add_column("Entry",     justify="right")
    tbl.add_column("Current",   justify="right")
    tbl.add_column("Unreal. PnL", justify="right")
    tbl.add_column("SL",        justify="right")
    tbl.add_column("TP",        justify="right")

    if not portfolio.positions:
        tbl.add_row("—", "—", "—", "—", "—", "—", "—", "—")
        return tbl

    for sym, pos in portfolio.positions.items():
        price  = prices.get(sym, pos.entry_price)
        upnl   = pos.unrealised_pnl(price)
        upct   = pos.unrealised_pct(price)
        color  = _pnl_color(upnl)
        side_s = f"[bold green]{pos.side.upper()}[/bold green]" if pos.side == "long" \
                 else f"[bold red]{pos.side.upper()}[/bold red]"
        tbl.add_row(
            sym,
            side_s,
            f"{pos.quantity:.6f}",
            f"${pos.entry_price:,.4f}",
            f"${price:,.4f}",
            f"[{color}]{'+' if upnl>=0 else ''}{upnl:,.2f} ({upct*100:.1f}%)[/{color}]",
            f"[red]${pos.stop_loss:,.4f}[/red]",
            f"[green]${pos.take_profit:,.4f}[/green]",
        )
    return tbl


def build_trades_table(trades: List[Trade], n: int = 10) -> Table:
    tbl = Table(title=f"[bold]Recent Trades (last {n})[/bold]",
                box=box.SIMPLE_HEAVY, header_style="bold cyan")
    tbl.add_column("Symbol",  style="bold white", no_wrap=True)
    tbl.add_column("Side",    justify="center")
    tbl.add_column("PnL",     justify="right")
    tbl.add_column("Return",  justify="right")
    tbl.add_column("Reason",  overflow="fold")

    recent = trades[-n:][::-1]
    if not recent:
        tbl.add_row("—", "—", "—", "—", "—")
        return tbl

    for t in recent:
        color  = _pnl_color(t.pnl)
        side_s = "[green]LONG[/green]" if t.side == "long" else "[red]SHORT[/red]"
        tbl.add_row(
            t.symbol,
            side_s,
            f"[{color}]{'+' if t.pnl>=0 else ''}{t.pnl:,.2f}[/{color}]",
            f"[{color}]{'+' if t.pnl_pct>=0 else ''}{t.pnl_pct*100:.1f}%[/{color}]",
            t.reason[:60],
        )
    return tbl


def build_signals_table(signals: Dict[str, Signal]) -> Table:
    tbl = Table(title="[bold]Latest Signals[/bold]",
                box=box.SIMPLE_HEAVY, header_style="bold cyan")
    tbl.add_column("Symbol",   style="bold white", no_wrap=True)
    tbl.add_column("Signal",   justify="center")
    tbl.add_column("Strength", justify="right")
    tbl.add_column("Reason",   overflow="fold")

    for sym, sig in signals.items():
        tbl.add_row(
            sym,
            _signal_badge(sig.action),
            f"{sig.strength:.2f}",
            sig.reason[:70],
        )
    return tbl


def build_stats_panel(stats: dict) -> Panel:
    lines = []
    win_r = stats.get("win_rate", 0) * 100
    pf    = stats.get("profit_factor", 0)
    sh    = stats.get("sharpe_ratio", 0)
    tr    = stats.get("total_trades", 0)
    ret   = stats.get("total_return", 0) * 100
    mdd   = stats.get("max_drawdown", 0) * 100

    lines.append(f"[cyan]Trades:[/cyan]          {tr}")
    lines.append(f"[cyan]Win rate:[/cyan]         {win_r:.1f}%")
    lines.append(f"[cyan]Profit factor:[/cyan]    {pf:.2f}")
    lines.append(f"[cyan]Sharpe ratio:[/cyan]     {sh:.2f}")
    lines.append(f"[cyan]Total return:[/cyan]  "
                 f"[{'green' if ret>=0 else 'red'}]{'+' if ret>=0 else ''}{ret:.1f}%[/]")
    lines.append(f"[cyan]Max drawdown:[/cyan] "
                 f"[{'red' if mdd>10 else 'yellow'}]{mdd:.1f}%[/]")

    return Panel("\n".join(lines), title="[bold]Performance Stats[/bold]",
                 box=box.ROUNDED)


# ── Main display ──────────────────────────────────────────────────────────────

def render_dashboard(
    portfolio:  Portfolio,
    prices:     Dict[str, float],
    signals:    Dict[str, Signal],
    initial:    float,
    tick:       int,
    drawdown:   float,
) -> None:
    equity = portfolio.total_equity(prices)
    stats  = portfolio.stats()

    console.clear()
    console.print(build_header(equity, initial, drawdown, tick))
    console.print(build_positions_table(portfolio, prices))
    console.print(build_signals_table(signals))
    console.print(build_trades_table(portfolio.trade_log))
    console.print(build_stats_panel(stats))
    console.print(
        f"\n[dim]Last update: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}[/dim]"
    )


def print_backtest_summary(result) -> None:
    """Pretty-print backtest results."""
    from rich.rule import Rule
    stats = result.stats
    console.print(Rule("[bold blue]BACKTEST COMPLETE[/bold blue]"))

    tbl = Table(box=box.ROUNDED, show_header=False, padding=(0, 2))
    tbl.add_column("Metric", style="cyan bold")
    tbl.add_column("Value",  justify="right")

    ret   = (result.final_equity / result.initial_capital - 1) * 100
    color = "green" if ret >= 0 else "red"

    rows = [
        ("Initial Capital", f"${result.initial_capital:>12,.2f}"),
        ("Final Equity",    f"${result.final_equity:>12,.2f}"),
        ("Total Return",    f"[{color}]{'+' if ret>=0 else ''}{ret:.2f}%[/{color}]"),
        ("Total Trades",    str(stats.get("total_trades", 0))),
        ("Win Rate",        f"{stats.get('win_rate', 0)*100:.1f}%"),
        ("Profit Factor",   f"{stats.get('profit_factor', 0):.2f}"),
        ("Sharpe Ratio",    f"{stats.get('sharpe_ratio', 0):.2f}"),
        ("Max Drawdown",    f"[red]{stats.get('max_drawdown', 0)*100:.1f}%[/red]"),
        ("Best Trade",      f"[green]+${stats.get('best_trade', 0):.2f}[/green]"),
        ("Worst Trade",     f"[red]${stats.get('worst_trade', 0):.2f}[/red]"),
    ]
    for k, v in rows:
        tbl.add_row(k, v)

    console.print(tbl)
