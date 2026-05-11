"""回测结果可视化 — 生成 HTML 报告"""

import base64
from io import StringIO
from datetime import datetime
from typing import List, Optional
from vulpes_trader.backtest.engine import BacktestResult
from vulpes_trader.backtest.optimizer import ParamResult


def _chart_html(equity: List[float], dd: List[float]) -> str:
    """内联 equity + drawdown 双图 (svg 极简)"""
    if not equity or len(equity) < 2:
        return "<p style='color:#8b949e'>数据不足</p>"

    eq = equity
    w, h = 700, 200
    pad = 40
    cw, ch = w - pad * 2, h - pad * 2

    def _line(vals, color, dash=""):
        mn, mx = min(vals), max(vals)
        rng = mx - mn or 1
        pts = " ".join(
            f"{pad + i * cw / (len(vals) - 1)},{pad + ch - (v - mn) / rng * ch}"
            for i, v in enumerate(vals)
        )
        return f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="1.5"{dash}/>'

    html = f"""<svg width="{w}" height="{h}" style="background:#0d1117;border-radius:6px">
    <rect width="{w}" height="{h}" fill="#0d1117"/>
    {_line(eq, '#3fb950')}
    <text x="{pad}" y="14" fill="#8b949e" font-size="10">Equity</text>
    <text x="{w - pad}" y="{h - 6}" fill="#484f58" font-size="9" text-anchor="end">bar</text>
    </svg>"""
    return html


def _metric_card(label: str, value: str, color: str = "#c9d1d9") -> str:
    return f"""<div style="background:#161b22;border-radius:6px;padding:10px;text-align:center">
      <div style="font-size:11px;color:#8b949e;margin-bottom:4px">{label}</div>
      <div style="font-size:18px;font-weight:700;color:{color}">{value}</div>
    </div>"""


def result_to_html(result: BacktestResult, title: str = "Backtest Report") -> str:
    """BacktestResult → HTML 报告字符串"""
    t = result.total_trades
    wr = f"{result.win_rate:.1f}%" if t > 0 else "—"
    pnl = f"{result.total_pnl:+.2f}" if t > 0 else "0.00"
    sr = f"{result.sharpe_ratio:.2f}" if t > 0 else "—"
    dd = f"{result.max_drawdown:.2f}%" if t > 0 else "—"

    chart = _chart_html(result.equity_curve, [])

    trade_rows = ""
    for tr in result.trades[-30:]:
        color = "#3fb950" if tr.pnl >= 0 else "#f85149"
        trade_rows += f"""<tr>
          <td style="padding:3px 6px;color:#c9d1d9">{tr.symbol}</td>
          <td style="padding:3px 6px;color:#8b949e;text-transform:uppercase">{tr.side}</td>
          <td style="padding:3px 6px;color:#c9d1d9">{tr.entry_price:.2f}</td>
          <td style="padding:3px 6px;color:#c9d1d9">{tr.exit_price or '—'}</td>
          <td style="padding:3px 6px;color:{color};font-weight:600">{tr.pnl:+.2f}</td>
          <td style="padding:3px 6px;color:#484f58;font-size:10px">{tr.exit_reason}</td>
        </tr>"""

    return f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8">
    <title>{title}</title>
    <style>body{{background:#0d1117;color:#c9d1d9;font-family:system-ui;padding:20px;max-width:800px;margin:auto}}
    h1{{color:#58a6ff;font-size:20px}}table{{width:100%;border-collapse:collapse;font-size:12px}}
    th{{text-align:left;padding:4px 6px;color:#8b949e;border-bottom:1px solid #30363d}}
    td{{border-bottom:1px solid #21262d}}</style></head><body>
    <h1>📊 {title}</h1>
    <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin:16px 0">
      {_metric_card("总交易", str(t))}
      {_metric_card("胜率", wr, "#3fb950" if result.win_rate >= 50 else "#f85149")}
      {_metric_card("夏普", sr, "#58a6ff" if result.sharpe_ratio > 1 else "#8b949e")}
      {_metric_card("最大回撤", dd, "#f0883e")}
    </div>
    <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin:16px 0">
      {_metric_card("总 PnL", pnl, "#3fb950" if result.total_pnl > 0 else "#f85149")}
      {_metric_card("盈利交易", str(result.win_trades), "#3fb950")}
      {_metric_card("亏损交易", str(result.loss_trades), "#f85149")}
      {_metric_card("交易频率", f"{t/max(len(result.equity_curve),1)*100:.1f}%" if t > 0 else "—")}
    </div>
    {chart}
    <h2 style="font-size:14px;color:#8b949e;margin-top:20px">最近交易</h2>
    <table><thead><tr><th>币种</th><th>方向</th><th>入场</th><th>出场</th><th>PnL</th><th>原因</th></tr></thead>
    <tbody>{trade_rows or '<tr><td colspan="6" style="color:#484f58;text-align:center">无交易</td></tr>'}</tbody></table>
    <p style="color:#484f58;font-size:10px;margin-top:20px">{datetime.now().strftime("%Y-%m-%d %H:%M")}</p>
    </body></html>"""


def param_results_to_html(results: List[ParamResult], title: str = "Optimization Results") -> str:
    """参数扫描结果 → HTML 对比表格"""
    rows = ""
    for i, pr in enumerate(results):
        r = pr.result
        bg = "#0d1117" if i % 2 == 0 else "#161b22"
        params_str = " ".join(f"{k}={v}" for k, v in pr.params.items())
        rows += f"""<tr style="background:{bg}">
          <td style="padding:4px 8px;color:#58a6ff">{params_str}</td>
          <td style="padding:4px 8px">{r.total_trades}</td>
          <td style="padding:4px 8px;color:{'#3fb950' if r.total_pnl > 0 else '#f85149'}">{r.total_pnl:+.2f}</td>
          <td style="padding:4px 8px">{r.win_rate:.1f}%</td>
          <td style="padding:4px 8px;color:#58a6ff">{r.sharpe_ratio:.2f}</td>
          <td style="padding:4px 8px;color:#f0883e">{r.max_drawdown:.1f}%</td>
          <td style="padding:4px 8px;color:#c9d1d9">{pr.score:.1f}</td>
        </tr>"""

    return f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8">
    <title>{title}</title>
    <style>body{{background:#0d1117;color:#c9d1d9;font-family:system-ui;padding:20px;max-width:1000px;margin:auto}}
    h1{{color:#58a6ff;font-size:20px}}table{{width:100%;border-collapse:collapse;font-size:12px}}
    th{{text-align:left;padding:5px 8px;color:#8b949e;border-bottom:1px solid #30363d;font-weight:600}}
    td{{border-bottom:1px solid #21262d}}</style></head><body>
    <h1>🔬 {title}</h1>
    <p style="color:#8b949e;font-size:12px;margin-bottom:12px">共 {len(results)} 组最优参数，按综合评分排序</p>
    <table><thead><tr><th>参数</th><th>交易</th><th>PnL</th><th>胜率</th><th>Sharpe</th><th>DD</th><th>Score</th></tr></thead>
    <tbody>{rows}</tbody></table>
    <p style="color:#484f58;font-size:10px;margin-top:20px">{datetime.now().strftime("%Y-%m-%d %H:%M")}</p>
    </body></html>"""
