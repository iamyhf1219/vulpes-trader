"""交易复盘引擎 — 对每笔交易进行诊断和分析"""

import logging
from typing import Optional, Dict, List
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

logger = logging.getLogger("vulpes.evolution.review")


class ReviewGrade(Enum):
    A = "A"
    B = "B"
    C = "C"
    D = "D"
    F = "F"


class WinLossCategory(Enum):
    CORRECT_DIRECTION = "correct_direction"
    WRONG_DIRECTION = "wrong_direction"
    BAD_ENTRY = "bad_entry"
    STOP_OUT = "stop_out"
    MISSED_OPPORTUNITY = "missed_opportunity"
    EARLY_EXIT = "early_exit"
    LATE_EXIT = "late_exit"


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
    reviewed_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class TradeReviewer:
    """交易复盘引擎"""

    def __init__(self):
        self._reviews: List[ReviewResult] = []
        self._consecutive_losses = 0

    def review(self, trade: dict, signal_snapshot: Optional[dict] = None) -> ReviewResult:
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

        if is_win:
            category = WinLossCategory.CORRECT_DIRECTION
            grade = ReviewGrade.A if pnl_pct > 10 else ReviewGrade.B
            self._consecutive_losses = 0
            if exit_reason == "take_profit":
                lessons.append("take profit strategy effective")
            elif "trailing" in exit_reason:
                lessons.append("trailing stop protected profit")
        else:
            category = WinLossCategory.WRONG_DIRECTION
            self._consecutive_losses += 1
            if exit_reason == "stop_loss":
                if pnl_pct > -5:
                    root_causes.append("stop loss hit by short-term volatility")
                    suggestions.append("consider wider stop loss or additional confirmation")
                else:
                    root_causes.append("wrong direction")
                    suggestions.append("check signal quality for false breakout")
            elif "trailing" in exit_reason:
                root_causes.append("trailing stop triggered by retracement")
                suggestions.append("trailing stop distance too tight?")
            else:
                root_causes.append(f"exit reason: {exit_reason}")

            if pnl_pct < -10:
                grade = ReviewGrade.F if self._consecutive_losses >= 3 else ReviewGrade.D
            elif pnl_pct < -5:
                grade = ReviewGrade.D
            else:
                grade = ReviewGrade.C
            lessons.append("loss trade — lesson recorded")

        if signal_snapshot:
            for source, sig_info in signal_snapshot.items():
                conf = sig_info.get("confidence", 0)
                if is_win and conf > 0.7:
                    lessons.append(f"{source} signal effective (conf={conf})")
                    suggestions.append(f"consider increasing {source} weight")
                elif not is_win and conf < 0.6:
                    root_causes.append(f"{source} signal confidence low ({conf})")

        adjustments = {}
        if not is_win and exit_reason == "stop_loss":
            adjustments["stop_loss_fixed_pct"] = 0.06

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
        logger.info("review %s: %s (%.2f) -> %s", symbol, grade.value, pnl, category.value)
        return review

    def get_recent_reviews(self, n: int = 10) -> List[ReviewResult]:
        return self._reviews[-n:]

    def get_win_rate(self) -> float:
        if not self._reviews:
            return 0.0
        wins = sum(1 for r in self._reviews if r.pnl > 0)
        return wins / len(self._reviews)
