"""Vulpes Trader Web Dashboard — FastAPI 实时监控面板"""

import asyncio
import json
import logging
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

logger = logging.getLogger("vulpes.dashboard")

# ---------------------------------------------------------------------------
# 数据注入回调 —— 外部将数据 push 进 dashboard
# ---------------------------------------------------------------------------

_DEFAULT_PORT = int(os.getenv("VULPES_DASHBOARD_PORT", "8765"))
_STATIC_DIR = Path(__file__).parent / "static"


@dataclass
class DashboardState:
    """Dashboard 全局快照状态"""
    status: str = "stopped"  # running / stopped / error
    mode: str = "testnet"    # testnet / mainnet
    uptime_seconds: float = 0.0

    positions: List[Dict[str, Any]] = field(default_factory=list)
    signals: List[Dict[str, Any]] = field(default_factory=list)
    logs: List[Dict[str, Any]] = field(default_factory=list)

    total_pnl: float = 0.0
    win_rate: float = 0.0
    trade_count: int = 0

    circuit_breaker_tripped: bool = False
    max_leverage: int = 20
    daily_loss: float = 0.0
    active_positions_count: int = 0
    max_positions: int = 5

    config: Dict[str, Any] = field(default_factory=dict)
    trade_history: List[Dict[str, Any]] = field(default_factory=list)  # 历史成交
    knowledge: List[Dict[str, Any]] = field(default_factory=list)  # 知识库
    pnl_history: List[Dict[str, Any]] = field(default_factory=list)  # PnL 时间序列
    pnl_metrics: Dict[str, float] = field(default_factory=lambda: {
        "realtime": 0.0, "daily": 0.0, "monthly": 0.0, "total": 0.0,
    })

    _max_logs: int = 200


class DashboardServer:
    """
    Web Dashboard 服务器

    使用方式:
        dash = DashboardServer()
        dash.register_callbacks(status_cb=..., positions_cb=...)
        await dash.start()
        ...
        await dash.stop()
    """

    def __init__(self, port: int = _DEFAULT_PORT):
        self.port = port
        self._app: Optional[FastAPI] = None
        self._server: Optional[uvicorn.Server] = None
        self._state = DashboardState()
        self._listeners: Set[WebSocket] = set()

        # 数据回调（外部注册）
        self._status_cb: Optional[Callable[[], Dict[str, Any]]] = None
        self._positions_cb: Optional[Callable[[], List[Dict[str, Any]]]] = None
        self._performance_cb: Optional[Callable[[], Dict[str, Any]]] = None
        self._signals_cb: Optional[Callable[[], List[Dict[str, Any]]]] = None
        self._config_cb: Optional[Callable[[], Dict[str, Any]]] = None

        self._build_app()

    # ------------------------------------------------------------------
    # 数据注入
    # ------------------------------------------------------------------

    def register_callbacks(
        self,
        status: Optional[Callable[[], Dict[str, Any]]] = None,
        positions: Optional[Callable[[], List[Dict[str, Any]]]] = None,
        performance: Optional[Callable[[], Dict[str, Any]]] = None,
        signals: Optional[Callable[[], List[Dict[str, Any]]]] = None,
        config: Optional[Callable[[], Dict[str, Any]]] = None,
    ):
        """注册数据回调函数，dashboard 轮询时调用"""
        if status:
            self._status_cb = status
        if positions:
            self._positions_cb = positions
        if performance:
            self._performance_cb = performance
        if signals:
            self._signals_cb = signals
        if config:
            self._config_cb = config

    def inject_state(self, state: DashboardState):
        """直接注入完整状态快照"""
        self._state = state

    def push_log(self, level: str, message: str, source: str = "system"):
        """推送日志到 dashboard"""
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": level,
            "message": message,
            "source": source,
        }
        self._state.logs.append(entry)
        if len(self._state.logs) > self._state._max_logs:
            self._state.logs = self._state.logs[-self._state._max_logs:]

    # ------------------------------------------------------------------
    # 广播
    # ------------------------------------------------------------------

    async def broadcast(self, event_type: str, data: Any):
        """向所有连接的 WebSocket 客户端广播消息"""
        payload = json.dumps({"type": event_type, "data": data}, default=str)
        dead: List[WebSocket] = []
        for ws in self._listeners:
            try:
                await ws.send_text(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._listeners.discard(ws)

    # ------------------------------------------------------------------
    # 生命周期
    # ------------------------------------------------------------------

    async def start(self):
        """启动 uvicorn 服务器（非阻塞）"""
        if self._server:
            logger.warning("Dashboard 已在运行")
            return

        config = uvicorn.Config(
            self._app,
            host="127.0.0.1",
            port=self.port,
            log_level="warning",
            access_log=False,
        )
        self._server = uvicorn.Server(config)
        # 异步启动，不阻塞主循环
        asyncio.create_task(self._server.serve())
        await asyncio.sleep(0.5)  # 给 uvicorn 一点时间完成绑定
        logger.info("Dashboard 启动完成: http://127.0.0.1:%d", self.port)
        self._state.status = "running"

    async def stop(self):
        """停止服务器"""
        if self._server:
            self._server.should_exit = True
            self._server = None
        self._state.status = "stopped"
        logger.info("Dashboard 已停止")

    # ------------------------------------------------------------------
    # FastAPI 路由构建
    # ------------------------------------------------------------------

    def _collect_status(self) -> Dict[str, Any]:
        if self._status_cb:
            return self._status_cb()
        return {
            "status": self._state.status,
            "mode": self._state.mode,
            "uptime_seconds": self._state.uptime_seconds,
            "active_positions": self._state.active_positions_count,
            "max_positions": self._state.max_positions,
            "circuit_breaker_tripped": self._state.circuit_breaker_tripped,
        }

    def _collect_positions(self) -> List[Dict[str, Any]]:
        if self._positions_cb:
            return self._positions_cb()
        return self._state.positions

    def _collect_performance(self) -> Dict[str, Any]:
        if self._performance_cb:
            return self._performance_cb()
        return {
            "total_pnl": self._state.total_pnl,
            "win_rate": self._state.win_rate,
            "trade_count": self._state.trade_count,
            "daily_loss": self._state.daily_loss,
        }

    def _collect_signals(self) -> List[Dict[str, Any]]:
        if self._signals_cb:
            return self._signals_cb()
        return self._state.signals

    def _collect_config(self) -> Dict[str, Any]:
        if self._config_cb:
            return self._config_cb()
        return self._state.config

    def _collect_history(self) -> List[Dict[str, Any]]:
        if self._state.trade_history:
            return self._state.trade_history
        return []

    def _collect_knowledge(self) -> Dict[str, Any]:
        rules = self._state.knowledge
        return {
            "rules": rules if isinstance(rules, list) else [],
            "total": len(rules) if isinstance(rules, list) else 0,
            "active": sum(1 for r in (rules or []) if r.get("active", True)),
        }

    def _collect_pnl_history(self, range_key: str = "30d") -> Dict[str, Any]:
        raw = self._state.pnl_history
        if isinstance(raw, dict):
            points = raw.get(range_key, raw.get("30d", []))
        elif isinstance(raw, list):
            points = raw
        else:
            points = []
        return {
            "points": points,
            "metrics": self._state.pnl_metrics,
        }

    def _build_app(self):
        """构建 FastAPI 应用"""
        app = FastAPI(title="Vulpes Trader Dashboard")

        # ---- 静态文件 ----
        if _STATIC_DIR.exists():
            app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")

        # ---- REST API ----

        @app.get("/")
        async def index():
            """返回前端页面"""
            index_path = _STATIC_DIR / "index.html"
            if index_path.exists():
                content = index_path.read_text(encoding="utf-8")
                return HTMLResponse(content, headers={"Cache-Control": "no-cache, no-store, must-revalidate"})
            return HTMLResponse("<h1>Vulpes Trader Dashboard</h1><p>Static file not found</p>")

        @app.get("/api/status")
        async def api_status():
            return self._collect_status()

        @app.get("/api/positions")
        async def api_positions():
            return self._collect_positions()

        @app.get("/api/performance")
        async def api_performance():
            return self._collect_performance()

        @app.get("/api/signals")
        async def api_signals():
            return self._collect_signals()

        @app.get("/api/config")
        async def api_config():
            return self._collect_config()

        @app.get("/api/history")
        async def api_history():
            return self._collect_history()

        @app.get("/api/knowledge")
        async def api_knowledge():
            return self._collect_knowledge()

        @app.get("/api/pnl_history")
        async def api_pnl_history(range: str = "30d"):
            return self._collect_pnl_history(range)

        # ---- WebSocket ----

        @app.websocket("/ws")
        async def websocket_endpoint(ws: WebSocket):
            await ws.accept()
            self._listeners.add(ws)
            logger.info("Dashboard WebSocket 客户端已连接 (%d 在线)", len(self._listeners))
            try:
                while True:
                    # 接收客户端消息（心跳保持连接）
                    msg = await ws.receive_text()
                    if msg == "ping":
                        await ws.send_text(json.dumps({"type": "pong"}))
            except WebSocketDisconnect:
                pass
            except Exception:
                pass
            finally:
                self._listeners.discard(ws)
                logger.info("Dashboard WebSocket 客户端已断开 (%d 在线)", len(self._listeners))

        self._app = app


# ---------------------------------------------------------------------------
# 便利函数 —— 在不创建实例时也能快速导入 app（uvicorn CLI 用）
# ---------------------------------------------------------------------------

_dash_instance: Optional[DashboardServer] = None
app: Optional[FastAPI] = None


def _ensure_instance(port: int = _DEFAULT_PORT) -> DashboardServer:
    """确保单例已创建（内部使用）"""
    global _dash_instance, app
    if _dash_instance is None:
        _dash_instance = DashboardServer(port=port)
        app = _dash_instance._app
    return _dash_instance


def create_dashboard(port: int = _DEFAULT_PORT) -> DashboardServer:
    """创建并返回一个 DashboardServer 实例（单例）"""
    return _ensure_instance(port=port)


def start_dashboard(port: int = _DEFAULT_PORT) -> DashboardServer:
    """创建并启动 dashboard（便捷入口）"""
    dash = _ensure_instance(port=port)
    return dash


def _generate_pnl_walk(
    n: int,
    hours_back: float,
    start_val: float = 550.0,
    volatility: float = 120.0,
) -> List[Dict[str, Any]]:
    """生成随机游走 PnL 时间序列。"""
    from random import gauss
    from datetime import timedelta
    now = datetime.now(timezone.utc)
    step = hours_back / max(n - 1, 1)
    pts = []
    v = start_val
    for i in range(n):
        t = now - timedelta(hours=hours_back - i * step)
        v += gauss(0, volatility / max(n, 1) ** 0.5 * 2)
        pts.append({"time": t.isoformat(), "value": round(v, 2)})
    return pts


def _generate_demo_data() -> DashboardState:
    """生成模拟交易数据用于 UI 展示"""
    from random import uniform, choice, random
    from datetime import timedelta
    now = datetime.now(timezone.utc).isoformat()

    # 每条持仓附带开仓逻辑
    positions = [
        {"symbol": "BTC/USDT", "side": "long", "quantity": 0.15, "entry_price": 62450.0,
         "current_price": 63820.0, "pnl": 205.5, "pnl_pct": 2.19, "leverage": 5,
         "entry_reason": {"source":"fusion","confidence":0.78,"detail":"趋势+热度+事件三重共振",
           "breakdown":["趋势跟随: EMA金叉9>26, 置信度0.72","热度分析: 排名第3, OI上升5.2%","事件: 无明显影响"]}},
        {"symbol": "ETH/USDT", "side": "long", "quantity": 2.5, "entry_price": 3120.0,
         "current_price": 3245.0, "pnl": 312.5, "pnl_pct": 4.01, "leverage": 3,
         "entry_reason": {"source":"trend","confidence":0.65,"detail":"EMA金叉+放量突破",
           "breakdown":["趋势跟随: EMA12上穿EMA26, 置信度0.65","成交量: 24h放量35%"]}},
        {"symbol": "SOL/USDT", "side": "short", "quantity": 8.0, "entry_price": 142.8,
         "current_price": 138.5, "pnl": 34.4, "pnl_pct": 3.01, "leverage": 2,
         "entry_reason": {"source":"heat","confidence":0.71,"detail":"热度偏高, OI反转下行",
           "breakdown":["热度: Square排名第1, 超买预警","OI: 未平仓量下降8.3%","资金费率: 0.01% 中性"]}},
    ]

    signals = [
        {"symbol": "BTC/USDT", "direction": "long", "confidence": 0.78, "source": "fusion",
         "timestamp": now, "detail": "趋势跟随(0.72) + 热度(0.65) + 事件(0.50)"},
        {"symbol": "ETH/USDT", "direction": "long", "confidence": 0.65, "source": "trend",
         "timestamp": now, "detail": "EMA金叉, 9>26"},
        {"symbol": "SOL/USDT", "direction": "short", "confidence": 0.71, "source": "heat",
         "timestamp": now, "detail": "热度偏高, OI 下降"},
        {"symbol": "DOGE/USDT", "direction": "neutral", "confidence": 0.30, "source": "event",
         "timestamp": now, "detail": "等待事件确认"},
    ]

    logs = [
        {"timestamp": now, "level": "INFO", "message": "Vulpes Trader 启动 模式: testnet", "source": "system"},
        {"timestamp": now, "level": "INFO", "message": "WsManager 连接成功: 3 个交易对", "source": "ws"},
        {"timestamp": now, "level": "INFO", "message": "信号融合: BTC LONG @ 0.78", "source": "fusion"},
        {"timestamp": now, "level": "WARNING", "message": "SOL 热度偏高, OI 下降 5.2%", "source": "heat"},
        {"timestamp": now, "level": "INFO", "message": "开仓 BTC LONG 0.15 @ 62450 x5", "source": "execution"},
        {"timestamp": now, "level": "INFO", "message": "止损设置: BTC @ 60888 (-2.5%)", "source": "risk"},
    ]

    # 初始 PnL = 持仓 PnL 总和
    init_pnl = sum(p["pnl"] for p in positions)  # 552.4

    # 各时间范围的 PnL 历史数据
    pnl_history = {
        "1d": _generate_pnl_walk(96, 24, start_val=480, volatility=60),
        "7d": _generate_pnl_walk(168, 168, start_val=200, volatility=180),
        "30d": _generate_pnl_walk(360, 720, start_val=-150, volatility=350),
        "180d": _generate_pnl_walk(180, 4320, start_val=-300, volatility=600),
        "360d": _generate_pnl_walk(360, 8640, start_val=-500, volatility=800),
    }

    # 最新 PnL 值
    latest_pnl = pnl_history["1d"][-1]["value"]

    # 模拟历史成交记录
    from datetime import timedelta
    now_utc = datetime.now(timezone.utc)
    d = now_utc.day
    history = [
        {"symbol": "BTC/USDT", "side": "long",  "entry": 58200, "exit": 61050,  "qty": 0.1,  "leverage": 5, "pnl": 142.50, "pnl_pct": 2.45, "reason": "止盈", "entry_reason": "趋势+热度共振, 置信度0.78", "time": (now_utc - timedelta(days=1)).isoformat()},
        {"symbol": "ETH/USDT", "side": "long",  "entry": 3050,  "exit": 3180,   "qty": 3.0,  "leverage": 3, "pnl": 390.00, "pnl_pct": 4.26, "reason": "信号平仓", "entry_reason": "EMA金叉+放量, 置信度0.65", "time": (now_utc - timedelta(days=2)).isoformat()},
        {"symbol": "SOL/USDT", "side": "short", "entry": 148.5,"exit": 140.2,  "qty": 10.0, "leverage": 2, "pnl": 83.00,  "pnl_pct": 5.59, "reason": "止盈", "entry_reason": "热度+OI反转, 置信度0.71", "time": (now_utc - timedelta(days=3)).isoformat()},
        {"symbol": "DOGE/USDT","side": "long",  "entry": 0.082,"exit": 0.079,  "qty": 5000, "leverage": 3, "pnl": -45.00, "pnl_pct": -1.10, "reason": "止损", "entry_reason": "事件驱动, 置信度0.45", "time": (now_utc - timedelta(days=4)).isoformat()},
        {"symbol": "BTC/USDT", "side": "short", "entry": 62500, "exit": 61800,  "qty": 0.08, "leverage": 5, "pnl": 28.00, "pnl_pct": 0.56, "reason": "信号平仓", "entry_reason": "趋势反转信号, 置信度0.62", "time": (now_utc - timedelta(days=5)).isoformat()},
        {"symbol": "ETH/USDT", "side": "long",  "entry": 2980,  "exit": 3020,   "qty": 2.0,  "leverage": 3, "pnl": 80.00, "pnl_pct": 1.34, "reason": "手动平仓", "entry_reason": "支撑位反弹, 置信度0.55", "time": (now_utc - timedelta(days=6)).isoformat()},
        {"symbol": "LINK/USDT","side": "long",  "entry": 14.2,  "exit": 15.8,   "qty": 50.0, "leverage": 2, "pnl": 80.00, "pnl_pct": 2.25, "reason": "止盈", "entry_reason": "热度飙升+消息面利好", "time": (now_utc - timedelta(days=7)).isoformat()},
        {"symbol": "ADA/USDT", "side": "short", "entry": 0.48,  "exit": 0.52,   "qty": 2000, "leverage": 2, "pnl": -80.00, "pnl_pct": -1.67, "reason": "止损", "entry_reason": "趋势破位, 置信度0.60", "time": (now_utc - timedelta(days=8)).isoformat()},
        {"symbol": "BTC/USDT", "side": "long",  "entry": 54800, "exit": 57200,  "qty": 0.12, "leverage": 5, "pnl": 144.00, "pnl_pct": 2.19, "reason": "信号平仓", "entry_reason": "EMA多头排列, 趋势跟随", "time": (now_utc - timedelta(days=10)).isoformat()},
        {"symbol": "ETH/USDT", "side": "short", "entry": 3350,  "exit": 3280,   "qty": 2.5,  "leverage": 3, "pnl": 52.50, "pnl_pct": 0.63, "reason": "止盈", "entry_reason": "MACD顶背离, 置信度0.68", "time": (now_utc - timedelta(days=12)).isoformat()},
        {"symbol": "SOL/USDT", "side": "long",  "entry": 132.0, "exit": 138.5,  "qty": 8.0,  "leverage": 2, "pnl": 52.00, "pnl_pct": 0.98, "reason": "信号平仓", "entry_reason": "支撑位反弹+热度回暖", "time": (now_utc - timedelta(days=15)).isoformat()},
    ]

    win_count = sum(1 for t in history if t["pnl"] > 0)
    win_rate_val = round(win_count / len(history) * 100, 1) if history else 0

    state = DashboardState(
        status="running",
        mode="testnet",
        uptime_seconds=86400.0,
        positions=positions,
        signals=signals,
        logs=logs,
        total_pnl=init_pnl,
        win_rate=win_rate_val,
        trade_count=len(history),
        circuit_breaker_tripped=False,
        max_leverage=20,
        daily_loss=0.0,
        active_positions_count=3,
        max_positions=5,
        trade_history=history,
        knowledge=[
            {"id":1,"text":"BTC减半前3个月通常有30-40%的上涨","source":"user_input","category":"market","tags":["BTC","减半","周期性"],"active":True},
            {"id":2,"text":"庄家拉盘前会在关键支撑位挂大量买单吸筹","source":"user_input","category":"whale","tags":["庄家","支撑位","吸筹"],"active":True},
            {"id":3,"text":"EMA金叉+成交量放大时做多胜率高","source":"trade_review","category":"signal","tags":["EMA","金叉","成交量"],"active":True},
            {"id":4,"text":"连续3笔亏损后应暂停交易","source":"trade_review","category":"risk","tags":["风控","亏损"],"active":True},
            {"id":5,"text":"SOL在$120附近连续3天放量不跌可能是主力吸筹","source":"user_input","category":"whale","tags":["SOL","主力","吸筹"],"active":True},
            {"id":6,"text":"BTC ETF净流入持续3天以上往往是中期上涨信号","source":"user_input","category":"market","tags":["BTC","ETF","资金流向"],"active":True},
        ],
        pnl_history=pnl_history,
        pnl_metrics={
            "total_assets": 100000.0 + latest_pnl,
            "realtime": latest_pnl,
            "daily": latest_pnl,
            "daily_pct": round((latest_pnl / 100000.0) * 100, 2),
            "monthly": latest_pnl,
            "monthly_pct": round((latest_pnl / 100000.0) * 100, 2),
            "total": latest_pnl,
            "total_pct": round((latest_pnl / 100000.0) * 100, 2),
        },
        config={
            "mode": "testnet",
            "max_leverage": 20,
            "symbols": ["BTC/USDT", "ETH/USDT", "SOL/USDT"],
            "primary_timeframe": "5m",
            "strategy": "trend_following_v1",
        },
    )
    return state


async def _demo_loop(dash: DashboardServer):
    """Demo 模式下定时更新模拟价格"""
    from random import uniform
    base_prices = {"BTC/USDT": 63820.0, "ETH/USDT": 3245.0, "SOL/USDT": 138.5}
    while True:
        await asyncio.sleep(3)
        for pos in dash._state.positions:
            sym = pos["symbol"]
            bp = base_prices.get(sym, 100.0)
            change = bp * uniform(-0.002, 0.002)
            bp += change
            base_prices[sym] = bp
            pos["current_price"] = round(bp, 2)
            entry = pos["entry_price"]
            pos["pnl"] = round((bp - entry) * pos["quantity"] * (1 if pos["side"] == "long" else -1), 2)
            pos["pnl_pct"] = round(((bp - entry) / entry) * 100, 2)
        dash._state.total_pnl = sum(p["pnl"] for p in dash._state.positions)
        # 广播到 WebSocket
        await dash.broadcast("positions", dash._state.positions)
        await dash.broadcast("status", {
            "total_pnl": dash._state.total_pnl,
            "active_positions": len(dash._state.positions),
        })


# 模块导入时自动初始化（支持 uvicorn vulpes_trader.dashboard.server:app 启动）
dash = _ensure_instance()
