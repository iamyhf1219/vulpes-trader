"""多币种参数配置 — 按 per_symbol 覆写全局默认"""

import logging
from typing import Dict, List, Tuple, Optional
from vulpes_trader.config import config

logger = logging.getLogger("vulpes.config.symbol")


class SymbolConfig:
    """单个币种的参数配置"""

    def __init__(self, symbol: str):
        self.symbol = symbol
        self._per_symbol = config.get("strategy", "per_symbol", default={})
        self._global = config.get("strategy", "indicators", default={})
        self._runtime_overrides: Dict = {}

    def _override(self, key: str, default):
        """per_symbol 覆写全局"""
        sym = self._per_symbol.get(self.symbol, {})
        return sym.get(key, self._global.get(key, default))

    @property
    def ema_fast(self) -> List[int]:
        return self._override("ema_fast", [9, 12])

    @property
    def ema_slow(self) -> List[int]:
        return self._override("ema_slow", [26, 50])

    @property
    def macd_params(self) -> Tuple[int, int, int]:
        macd = self._override("macd", [12, 26, 9])
        return tuple(macd)  # type: ignore

    @property
    def fusion_weights(self) -> Dict[str, float]:
        sym = self._per_symbol.get(self.symbol, {})
        fw = sym.get("fusion_weights", config.get("fusion", "weights", default={
            "trend": 0.30, "heat": 0.35, "event": 0.25, "oi": 0.10,
        }))
        return fw

    @property
    def stop_loss_pct(self) -> float:
        sym = self._per_symbol.get(self.symbol, {})
        risk = sym.get("risk", {})
        return risk.get("stop_loss_fixed_pct", config.get("risk", "stop_loss_fixed_pct", default=0.05))

    @property
    def trailing_activation(self) -> float:
        sym = self._per_symbol.get(self.symbol, {})
        risk = sym.get("risk", {})
        return risk.get("trailing_activation", config.get("risk", "trailing_stop_activation", default=0.02))

    @property
    def trailing_distance(self) -> float:
        sym = self._per_symbol.get(self.symbol, {})
        risk = sym.get("risk", {})
        return risk.get("trailing_distance", config.get("risk", "trailing_stop_distance", default=0.015))

    def update_params(self, params: Dict) -> None:
        """更新运行时参数（优化器用，不写回 yaml）"""
        self._runtime_overrides = params

    def get_param(self, key: str, default=None):
        runtime = getattr(self, "_runtime_overrides", {})
        return runtime.get(key, default)
