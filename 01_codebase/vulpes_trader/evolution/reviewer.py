"""交易复盘引擎 — 对每笔交易进行诊断和分析"""

import logging
from typing import Optional, Dict, List
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

logger = logging.getLogger("vulpes.evolution.review")


class ReviewGrade(Enum):
    A = "A"  # 完美交易
    B = "B"  # 良好
    C = "C"  # 及格
    D = "D"  # 有缺陷
    F = "F"  # 失败


class WinLossCategory(Enum):
    CORRECT_DIRECTION = "correct_direction"      # 方向对了
    WRONG_DIRECTION = "wrong_direction"           # 方向错了
    BAD_ENTRY = "bad_entry"                       # 入场不好
    STOP_OUT = "stop_out"                         # 被止损扫掉
    MISSED_OPPORTUNITY = "missed_opportunity"     # 错失机会
    EARLY_EXIT = "early_exit"                     # 过早止盈
    LATE_EXIT = "late_exit"                       # 过晚出场


@dataclass
class ReviewResult:
    trade_id: int
    symbol: str
    grade: ReviewGrade
    category: WinLossCategory
    pnl: float
    root_causes: List[str] = field(default_factory=list)
    lessons: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)
    parameter_adjustments: Dict[str, float] = field(default_factory=dict)
    reviewed_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())


class TradeReviewer:
    """
    交易复盘引擎
    
    每笔交易结束后，自动分析:
    - 方向判断是否正确
    - 入场/出场时机
    - 止损设置合理性
    - 可以改进的地方
    """

    def __init__(self):
        self._reviews: List[ReviewResult] = []
        # 连续亏损跟踪
        self._consecutive_losses = 0

    def review(self, trade: dict, signal_snapshot: Optional[dict] = None) -> ReviewResult:
        """
        对交易进行完整复盘

        Args:
            trade: 交易数据，包含 symbol, side, entry_price, exit_price, pnl, exit_reason 等
            signal_snapshot: 入场时的信号快照

        Returns:
            ReviewResult: 复盘结果
        """
        pnl = trade.get("pnl", 0)
        side = trade.get("side", "long")
        entry_price = trade.get("entry_price", 0)
        exit_price = trade.get("exit_price", 0)
        exit_reason = trade.get("exit_reason", "unknown")
        symbol = trade.get("symbol", "unknown")

        root_causes = []
        lessons = []
        suggestions = []
        pnl_pct = 0

        if entry_price > 0:
            if side == "long":
                pnl_pct = (exit_price - entry_price) / entry_price * 100
            else:
                pnl_pct = (entry_price - exit_price) / entry_price * 100

        is_win = pnl > 0

        # 分类
        if is_win:
            category = WinLossCategory.CORRECT_DIRECTION
            grade = ReviewGrade.A if pnl_pct > 10 else ReviewGrade.B
            self._consecutive_losses = 0

            if exit_reason == "take_profit":
                lessons.append("止盈策略有效")
            elif "trailing" in exit_reason:
                lessons.append("移动止损保护了利润")
        else:
            category = WinLossCategory.WRONG_DIRECTION
            self._consecutive_losses += 1

            # 诊断亏损根因
            if exit_reason == "stop_loss" or exit_reason == "fixed_stop":
                if pnl_pct > -5:
                    root_causes.append("止损被短期波动扫到")
                    suggestions.append("考虑略宽止损，或增加确认条件")
                else:
                    root_causes.append("方向判断错误")
                    suggestions.append("检查信号质量，是否出现假突破")
            elif exit_reason in ("trailing", "trailing_stop"):
                root_causes.append("逆势回调触发移动止损")
                suggestions.append("移动止损距离是否过窄？")
            else:
                root_causes.append(f"退出原因: {exit_reason}")

            # 评分
            if pnl_pct < -10:
                grade = ReviewGrade.F if self._consecutive_losses >= 3 else ReviewGrade.D
            elif pnl_pct < -5:
                grade = ReviewGrade.D
            else:
                grade = ReviewGrade.C

            lessons.append("亏损交易 — 记录教训")

        # 信号源分析
        if signal_snapshot:
            for source, sig_info in signal_snapshot.items():
                dir_info = sig_info.get("direction", "")
                conf = sig_info.get("confidence", 0)
                if is_win:
                    if conf > 0.7:
                        lessons.append(f"{source}信号有效(conf={conf})")
                        suggestions.append(f"可以提升{source}信号权重")
                else:
                    if conf < 0.6:
                        root_causes.append(f"{source}信号置信度偏低({conf})")

        # 参数调整建议
        adjustments = {}
        if not is_win and exit_reason == "stop_loss":
            adjustments["stop_loss_fixed_pct"] = 0.06  # 建议扩大止损

        review = ReviewResult(
            trade_id=trade.get("id", 0),
            symbol=symbol,
            grade=grade,
            category=category,
            pnl=pnl,
            root_causes=root_causes,
            lessons=lessons,
            suggestions=suggestions,
            parameter_adjustments=adjustments,
        )

        self._reviews.append(review)
        logger.info("复盘 %s: %s (%.2f) → %s", symbol, grade.value, pnl, category.value)
        return review

    def get_recent_reviews(self, n: int = 10) -> List[ReviewResult]:
        """获取最近 N 条复盘"""
        return self._reviews[-n:]

    def get_win_rate(self) -> float:
        """计算胜率"""
        if not self._reviews:
            return 0.0
        wins = sum(1 for r in self._reviews if r.pnl > 0)
        return wins / len(self._reviews)
