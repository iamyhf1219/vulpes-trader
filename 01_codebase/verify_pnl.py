"""验证 Dashboard PnL 数据一致性"""
import urllib.request, json

def check(port=8773):
    pos = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{port}/api/positions").read())
    pnl = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{port}/api/pnl_history?range=30d").read())

    pos_total = sum(p["pnl"] for p in pos)
    metrics = pnl["metrics"]

    print("=== 持仓 PnL ===")
    for p in pos:
        print(f"  {p['symbol']:12s} {p['side']:6s} pnl={p['pnl']:>+8.2f}")
    print(f"  {'总计':12s} {'':6s} pnl={pos_total:>+8.2f}")

    print()
    print("=== PnL 面板指标 ===")
    print(f"  总资产: {metrics['total_assets']:.2f}")
    print(f"  今日盈亏: {metrics['daily']:+.2f} ({metrics['daily_pct']:+.2f}%)")
    print(f"  实时PnL: {metrics['realtime']:+.2f}")
    print(f"  曲线点数: {len(pnl['points'])}")

    print()
    match = abs(pos_total - metrics["daily"]) < 1.0
    print(f"{'[OK]' if match else '[FAIL]'} 今日盈亏({metrics['daily']:.2f}) == 持仓总和({pos_total:.2f}): {'一致' if match else '不一致'}")

if __name__ == "__main__":
    import sys
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8773
    check(port)
