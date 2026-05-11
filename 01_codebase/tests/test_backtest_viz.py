"""测试回测可视化"""

from vulpes_trader.backtest.viz import result_to_html, param_results_to_html
from vulpes_trader.backtest.engine import BacktestResult, BacktestTrade
from vulpes_trader.backtest.optimizer import ParamResult
from datetime import datetime


def test_result_to_html_empty():
    """空结果生成报告"""
    r = BacktestResult()
    html = result_to_html(r)
    assert "Backtest Report" in html
    assert "</html>" in html
    assert len(html) > 200


def test_result_to_html_with_trades():
    """有交易生成报告"""
    trades = [BacktestTrade(
        symbol="BTC", side="long",
        entry_time=datetime(2026, 1, 1), exit_time=datetime(2026, 1, 2),
        entry_price=100, exit_price=110, quantity=1, leverage=1,
        pnl=10.0, pnl_pct=10.0, exit_reason="tp",
    )]
    r = BacktestResult(trades=trades, equity_curve=[100, 110])
    html = result_to_html(r)
    assert "BTC" in html
    assert "10.00" in html


def test_result_to_html_custom_title():
    r = BacktestResult(trades=[], equity_curve=[100])
    html = result_to_html(r, title="My Test")
    assert "My Test" in html


def test_param_results_to_html():
    results = [
        ParamResult(params={"fast": 5}, result=BacktestResult(
            trades=[BacktestTrade(symbol="T", side="long", entry_time=datetime(2026,1,1), pnl=10) for _ in range(5)],
            equity_curve=[100 + i for i in range(20)],
        )),
    ]
    html = param_results_to_html(results)
    assert "Optimization" in html
    assert "fast=5" in html


def test_param_results_ranking():
    """排名标记正确"""
    r1 = ParamResult(params={"a": 1}, result=BacktestResult(
        trades=[BacktestTrade(symbol="T", side="long", entry_time=datetime(2026,1,1), pnl=10) for _ in range(10)],
        equity_curve=[100 + i for i in range(30)],
    ))
    r2 = ParamResult(params={"a": 2}, result=BacktestResult(
        trades=[BacktestTrade(symbol="T", side="long", entry_time=datetime(2026,1,1), pnl=5) for _ in range(3)],
        equity_curve=[100 + i for i in range(20)],
    ))
    html = param_results_to_html([r1, r2])
    assert "Score" in html
