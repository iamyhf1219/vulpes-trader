"""信号抽象基类"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, Optional
from enum import Enum


class SignalDirection(Enum):
    LONG = "long"
    SHORT = "short"
    NEUTRAL = "neutral"
    EXIT_LONG = "exit_long"
    EXIT_SHORT = "exit_short"


@dataclass
class Signal:
    """统一信号结构"""
    symbol: str
    direction: SignalDirection
    confidence: float  # 0.0 - 1.0
    source: str        # 'trend' | 'heat' | 'event' | 'oi'
    timestamp: int
    metadata: Dict = field(default_factory=dict)
    
    def is_tradeable(self, min_confidence: float = 0.5) -> bool:
        """判断是否可交易"""
        return self.direction in (SignalDirection.LONG, SignalDirection.SHORT) and self.confidence >= min_confidence


class SignalGenerator(ABC):
    """信号生成器基类"""
    
    @abstractmethod
    async def generate(self, symbol: str) -> Optional[Signal]:
        """生成信号"""
        pass
    
    @abstractmethod
    def name(self) -> str:
        """信号源名称"""
        pass
