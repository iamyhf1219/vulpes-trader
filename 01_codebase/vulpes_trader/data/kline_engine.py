"""K 线引擎 — 管理 OHLCV 数据缓存和聚合"""

import pandas as pd
from typing import Dict, Optional
from collections import defaultdict
from datetime import datetime
import logging

logger = logging.getLogger("vulpes.kline")


class KlineEngine:
    """多币种、多时间框 K 线缓存管理器"""

    COLUMNS = ["timestamp", "open", "high", "low", "close", "volume"]

    def __init__(self, cache_size: int = 1000):
        self.cache_size = cache_size
        # {symbol: {timeframe: DataFrame}}
        self._cache: Dict[str, Dict[str, pd.DataFrame]] = defaultdict(dict)

    def update(self, symbol: str, timeframe: str, ohlcv: list):
        """
        更新单根 K 线

        Args:
            symbol: 交易对
            timeframe: 时间框 (1m, 5m, 15m, etc.)
            ohlcv: [timestamp, open, high, low, close, volume]
        """
        if timeframe not in self._cache[symbol]:
            self._cache[symbol][timeframe] = pd.DataFrame(columns=self.COLUMNS)

        df = self._cache[symbol][timeframe]
        ts = ohlcv[0]

        # 如果已存在同一 timestamp 的 K 线，更新
        if len(df) > 0 and df.iloc[-1]["timestamp"] == ts:
            df.iloc[-1] = ohlcv
        else:
            # 追加新 K 线
            new_row = pd.DataFrame([ohlcv], columns=self.COLUMNS)
            df = pd.concat([df, new_row], ignore_index=True)
            # 裁剪缓存大小
            if len(df) > self.cache_size:
                df = df.iloc[-self.cache_size:]

        self._cache[symbol][timeframe] = df

    def get_klines(self, symbol: str, timeframe: str) -> Optional[pd.DataFrame]:
        """获取指定币种和周期的 K 线数据"""
        return self._cache.get(symbol, {}).get(timeframe)

    def get_latest(self, symbol: str, timeframe: str) -> Optional[dict]:
        """获取最新一根 K 线"""
        df = self.get_klines(symbol, timeframe)
        if df is not None and len(df) > 0:
            latest = df.iloc[-1].to_dict()
            latest["timestamp"] = datetime.fromtimestamp(
                latest["timestamp"] / 1000
            ).isoformat()
            return latest
        return None

    async def seed(self, exchange, symbols: list, timeframes: list, limit: int = 200):
        """启动时从交易所拉取历史 K 线"""
        for sym in symbols:
            base = sym.split(":")[0]
            for tf in timeframes:
                try:
                    ohlcv = await exchange._exec("fetch_ohlcv", base, tf, limit=limit)
                    if ohlcv:
                        for candle in ohlcv:
                            self.update(sym, tf, candle)
                        logger.info("K线: %s %s %d candles", sym, tf, len(ohlcv))
                except Exception as e:
                    logger.warning("K线加载失败 %s %s: %s", sym, tf, e)

    async def poll(self, exchange, symbols: list, timeframes: list):
        """轮询增量更新"""
        for sym in symbols:
            base = sym.split(":")[0]
            for tf in timeframes:
                try:
                    ohlcv = await exchange._exec("fetch_ohlcv", base, tf, limit=2)
                    if ohlcv:
                        for candle in ohlcv:
                            self.update(sym, tf, candle)
                except Exception:
                    pass

    def clean_old_data(self, max_age_hours: int = 24):
        """清理过期数据（手动触发）"""
        now = datetime.now().timestamp() * 1000
        cutoff = now - (max_age_hours * 3600 * 1000)
        for symbol in self._cache:
            for tf in self._cache[symbol]:
                df = self._cache[symbol][tf]
                self._cache[symbol][tf] = df[df["timestamp"] >= cutoff]
