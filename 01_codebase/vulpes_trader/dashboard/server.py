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
                return HTMLResponse(index_path.read_text(encoding="utf-8"))
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


def _generate_demo_data() -> DashboardState:
    """生成模拟交易数据用于 UI 展示"""
    from random import uniform, choice, random
    now = datetime.now(timezone.utc).isoformat()

    positions = [
        {"symbol": "BTC/USDT", "side": "long", "quantity": 0.15, "entry_price": 62450.0,
         "current_price": 63820.0, "pnl": 205.5, "pnl_pct": 2.19, "leverage": 5},
        {"symbol": "ETH/USDT", "side": "long", "quantity": 2.5, "entry_price": 3120.0,
         "current_price": 3245.0, "pnl": 312.5, "pnl_pct": 4.01, "leverage": 3},
        {"symbol": "SOL/USDT", "side": "short", "quantity": 8.0, "entry_price": 142.8,
         "current_price": 138.5, "pnl": 34.4, "pnl_pct": 3.01, "leverage": 2},
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

    # PnL 多时间范围数据
    from random import seed, uniform
    seed(42)

    def _walk(length, step=1.0, start=0.0):
        v = start
        pts = []
        for i in range(length):
            v += uniform(-20 * step, 35 * step)
            pts.append({"i": i, "value": round(v, 2)})
        return pts

    pnl_by_range = {
        "1d":   _walk(96, 1.0, 8000.0),       # 96点 (15min)
        "7d":   _walk(168, 3.0, 7500.0),       # 168点 (1h)
        "30d":  _walk(360, 8.0, 6000.0),       # 360点 (2h)
        "180d": _walk(180, 20.0, 3000.0),       # 180天
        "360d": _walk(360, 30.0, 0.0),          # 360天
    }

    state = DashboardState(
        status="running",
        mode="testnet",
        uptime_seconds=86400.0,
        positions=positions,
        signals=signals,
        logs=logs,
        total_pnl=552.4,
        win_rate=66.7,
        trade_count=12,
        circuit_breaker_tripped=False,
        max_leverage=20,
        daily_loss=0.0,
        active_positions_count=3,
        max_positions=5,
        pnl_history=pnl_by_range,  # dict of {range_key: points[]}
        pnl_metrics={
            "total_assets": 108632.40,
            "realtime": 552.40,
            "daily": 128.50,
            "daily_pct": 1.25,
            "monthly": 2145.80,
            "monthly_pct": 8.32,
            "total": 8632.40,
            "total_pct": 86.32,
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
