"""主协调器 — 连接数据、信号、风控、执行、进化各层"""

import asyncio
import logging
from typing import Optional, Dict, List
from datetime import datetime, timezone

from vulpes_trader.config import config
from vulpes_trader.audit.db import AuditDB
from vulpes_trader.audit.logger import setup_logger
from vulpes_trader.data.ws_manager import WSManager
from vulpes_trader.data.kline_engine import KlineEngine
from vulpes_trader.data.cache import DataCache
from vulpes_trader.data.supplementary import SupplementaryCollector
from vulpes_trader.data.square_monitor import SquareMonitor
from vulpes_trader.data.news_engine import NewsEventEngine
from vulpes_trader.signal.trend_follower import TrendFollower
from vulpes_trader.signal.heat_analyzer import HeatAnalyzer
from vulpes_trader.signal.event_analyzer import EventAnalyzer
from vulpes_trader.signal.fusion import SignalFusionEngine
from vulpes_trader.risk.manager import RiskManager
from vulpes_trader.execution.order_manager import OrderManager, OrderType
from vulpes_trader.execution.position_manager import PositionManager
from vulpes_trader.execution.stop_loss import StopLossManager
from vulpes_trader.evolution.reviewer import TradeReviewer
from vulpes_trader.evolution.optimizer import ParameterOptimizer
from vulpes_trader.evolution.knowledge_base import KnowledgeBase

logger = logging.getLogger("vulpes")


class VulpesOrchestrator:
    """
    Vulpes Trader 主协调器
    
    核心循环:
    1. 数据采集（K线/OI/热度/新闻）
    2. 信号生成（趋势/热度/事件）
    3. 信号融合（加权决策）
    4. 风控检查
    5. 执行交易
    6. 止损管理
    7. 交易复盘
    """

    def __init__(self):
        # 基础设施
        self.db = AuditDB()
        self.cache = DataCache()
        self.kline_engine = KlineEngine()
        self.running = False

        # 数据层
        symbols = config.get("data", "symbols", default=["BTC/USDT:USDT", "ETH/USDT:USDT"])
        timeframes = config.get("data", "timeframes", default=["5m", "15m"])
        self.ws_manager = WSManager(symbols=symbols, timeframes=timeframes)
        self.supplementary = SupplementaryCollector(symbols=symbols)
        self.square_monitor = SquareMonitor()
        self.news_engine = NewsEventEngine()

        # 信号层
        self.trend_follower = TrendFollower(self.kline_engine)
        self.heat_analyzer = HeatAnalyzer(square_monitor=self.square_monitor)
        self.event_analyzer = EventAnalyzer(news_engine=self.news_engine)
        self.fusion = SignalFusionEngine()

        # 风控与执行
        self.risk_manager = RiskManager()
        self.order_manager = OrderManager()
        self.position_manager = PositionManager()
        self.stop_loss_manager = StopLossManager()

        # 进化
        self.reviewer = TradeReviewer()
        self.optimizer = ParameterOptimizer()
        self.knowledge_base = KnowledgeBase()

    async def start(self):
        """启动所有模块"""
        logger.info("Vulpes Trader starting...")
        self.running = True

        # 启动 WS 连接
        await self.ws_manager.connect()

        # 注册数据回调
        self.ws_manager.subscribe_ohlcv(self._on_ohlcv)
        self.supplementary.on_data(self._on_supplementary)
        self.square_monitor.on_update(self._on_heat_update)
        self.news_engine.on_event(self._on_news_event)

        # 启动定时采集
        asyncio.create_task(self.supplementary.start())
        asyncio.create_task(self.square_monitor.start())

        # 启动主循环
        asyncio.create_task(self._main_loop())

        logger.info("All modules started")

    async def _on_ohlcv(self, data: dict):
        """处理 K 线数据"""
        symbol = data["symbol"]
        timeframe = data["timeframe"]
        for candle in data["data"]:
            self.kline_engine.update(symbol, timeframe, candle)

    async def _on_supplementary(self, data):
        """处理 OI/费率数据"""
        if hasattr(data, "symbol"):
            self.cache.set(f"oi_{data.symbol}", data, ttl=120)
            self.heat_analyzer.update_oi(data)

    async def _on_heat_update(self, rankings):
        """处理热度更新"""
        self.cache.set("heat_rankings", rankings, ttl=60)

    async def _on_news_event(self, event):
        """处理新闻事件"""
        logger.info("News event: %s (%s)", event.event_id, event.category.value)

    async def _main_loop(self):
        """主交易循环"""
        symbols = config.get("data", "symbols", default=["BTC/USDT:USDT"])
        
        while self.running:
            try:
                for symbol in symbols:
                    await self._process_symbol(symbol)
                await asyncio.sleep(5)  # 每5秒轮询
            except Exception as e:
                logger.error("Main loop error: %s", e)
                await asyncio.sleep(10)

    async def _process_symbol(self, symbol: str):
        """处理单个交易对的完整流水线"""
        
        # 1. 生成各信号源信号
        trend_sig = await self.trend_follower.generate(symbol)
        heat_sig = await self.heat_analyzer.generate(symbol)
        event_sig = await self.event_analyzer.generate(symbol)

        # 2. 融合信号
        signals = [s for s in [trend_sig, heat_sig, event_sig] if s is not None]
        final_signal = self.fusion.fuse(signals)

        if final_signal is None:
            return

        logger.debug("Signal %s: %s (conf=%.2f)", symbol, final_signal.direction.value, final_signal.confidence)
        self.fusion.record_signal(final_signal)

        # 3. 检查现有仓位并更新止损
        position = self.position_manager.get_position(symbol)
        latest_kline = self.kline_engine.get_latest(symbol, "5m")
        current_price = latest_kline["close"] if latest_kline else None

        if position and current_price:
            # 更新止损
            stop_reason = self.stop_loss_manager.check_stop_loss(symbol, current_price)
            if stop_reason:
                logger.info("Stop loss triggered %s: %s", symbol, stop_reason)
                closed = self.position_manager.close_position(symbol, current_price, stop_reason)
                if closed:
                    signal_snapshot = self._build_signal_snapshot(symbol)
                    review = self.reviewer.review({
                        "id": 0, "symbol": symbol, "side": position.side,
                        "entry_price": position.entry_price, "exit_price": current_price,
                        "pnl": closed.pnl, "exit_reason": stop_reason,
                    }, signal_snapshot)
                    self.optimizer.process_review(review)
                self.stop_loss_manager.remove(symbol)
                return

        # 4. 处理退出信号
        if position and not self._is_exit_signal(final_signal, position.side):
            return

        if position and current_price:
            closed = self.position_manager.close_position(symbol, current_price, final_signal.direction.value)
            if closed:
                self.stop_loss_manager.remove(symbol)
                signal_snapshot = self._build_signal_snapshot(symbol)
                self.reviewer.review({
                    "id": 0, "symbol": symbol, "side": position.side,
                    "entry_price": position.entry_price, "exit_price": current_price,
                    "pnl": closed.pnl, "exit_reason": final_signal.direction.value,
                }, signal_snapshot)

        # 5. 检查是否可开新仓
        if not self.risk_manager.can_open_position(symbol):
            return

        if final_signal.is_tradeable() and current_price:
            await self._execute_signal(symbol, final_signal, current_price)

    async def _execute_signal(self, symbol: str, signal, price: float):
        """执行信号 — 开仓"""
        capital = config.get("risk", "max_capital_per_trade_base", default=0.15) * 10000
        atr = 0  # TODO: compute from kline data
        
        # 计算杠杆和仓位
        leverage = self.risk_manager.compute_leverage(atr_pct=2.0, oi_rank=0.5)
        position_size = self.risk_manager.compute_position_size(capital, atr_pct=2.0)
        quantity = position_size / price

        side = "buy" if signal.direction.value == "long" else "sell"

        # 创建订单
        order = self.order_manager.create_order(symbol, side, OrderType.MARKET, quantity)
        self.order_manager.update_order(order.order_id, type("Status", (), {"value": "filled"})(),
                                       filled_qty=quantity, avg_price=price)

        # 开仓
        pos = self.position_manager.open_position(symbol, signal.direction.value, quantity, price, leverage)
        self.risk_manager.open_position(symbol, signal.direction.value, quantity)

        # 设置止损
        sl, act = self.risk_manager.compute_stop_loss(price, signal.direction.value)
        self.stop_loss_manager.create_stop_loss(symbol, signal.direction.value, price)

        # 记录到数据库
        self.db.save_trade({
            "symbol": symbol, "side": signal.direction.value,
            "entry_price": price, "quantity": quantity, "leverage": leverage,
            "stop_loss": sl, "take_profit": 0,
            "strategy": "fusion", "signal_snapshot": signal.metadata if hasattr(signal, 'metadata') else {},
        })

        logger.info("Trade %s %s @%.2f x%d (qty=%.4f)", symbol, signal.direction.value, price, leverage, quantity)

    def _is_exit_signal(self, signal, current_side: str) -> bool:
        """判断是否需要退出"""
        if signal.direction.value == "exit_long" and current_side == "long":
            return True
        if signal.direction.value == "exit_short" and current_side == "short":
            return True
        return False

    def _build_signal_snapshot(self, symbol: str) -> dict:
        """构建当前信号快照"""
        return {
            "fusion": {
                "weight_trend": self.fusion.weights.get("trend", 0),
                "weight_heat": self.fusion.weights.get("heat", 0),
                "weight_event": self.fusion.weights.get("event", 0),
            },
            "params": dict(self.optimizer.params),
        }

    async def stop(self):
        """安全停止"""
        self.running = False
        await self.ws_manager.close()
        await self.square_monitor.close()
        await self.supplementary.close()
        logger.info("Vulpes Trader stopped")
