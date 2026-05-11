"""知识库 — 从交易复盘和用户输入中持续学习进化

知识来源:
1. trade_review — 系统自动复盘交易记录提取的规则
2. user_input — 用户手动输入的交易知识、庄家手法、市场规律
"""

import logging
from typing import List, Optional, Dict
from dataclasses import dataclass, field
from datetime import datetime, timezone

logger = logging.getLogger("vulpes.evolution.kb")


@dataclass
class Rule:
    id: int
    rule_text: str
    source_type: str = "trade_review"   # "trade_review" | "user_input"
    source_trade_id: Optional[int] = None  # 从哪笔交易提取的
    category: str = "signal"             # "signal" | "risk" | "execution" | "whale" | "market"
    tags: List[str] = field(default_factory=list)  # 标签方便检索
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    active: bool = True
    effectiveness_score: float = 0.0


class KnowledgeBase:
    """
    交易知识库
    
    双通道学习:
    - 内部: 系统复盘自动提取 (add_rule)
    - 外部: 用户手动注入知识 (add_user_knowledge)
    """

    def __init__(self):
        self._rules: List[Rule] = []
        self._next_id = 1
        self._rule_effectiveness: Dict[int, List[bool]] = {}

    def add_rule(
        self,
        rule_text: str,
        source_trade_id: int,
        category: str = "signal",
        tags: Optional[List[str]] = None,
    ) -> Rule:
        """从交易复盘添加规则（内部学习）"""
        rule = Rule(
            id=self._next_id,
            rule_text=rule_text,
            source_type="trade_review",
            source_trade_id=source_trade_id,
            category=category,
            tags=tags or [],
        )
        self._next_id += 1
        self._rules.append(rule)
        logger.info("[KB] 复盘规则 #%d [%s]: %s", rule.id, category, rule_text[:60])
        return rule

    def add_user_knowledge(
        self,
        text: str,
        category: str = "market",
        tags: Optional[List[str]] = None,
    ) -> Rule:
        """添加用户输入的交易知识（外部学习）"""
        rule = Rule(
            id=self._next_id,
            rule_text=text,
            source_type="user_input",
            category=category,
            tags=tags or [],
        )
        self._next_id += 1
        self._rules.append(rule)
        logger.info("[KB] 用户知识 #%d [%s]: %s", rule.id, category, text[:60])
        return rule

    def get_active_rules(self, category: Optional[str] = None) -> List[Rule]:
        rules = [r for r in self._rules if r.active]
        if category:
            rules = [r for r in rules if r.category == category]
        return rules

    def search_by_tags(self, tags: List[str]) -> List[Rule]:
        """按标签检索知识"""
        return [r for r in self._rules if r.active and any(t in r.tags for t in tags)]

    def record_effectiveness(self, rule_id: int, was_helpful: bool):
        """记录规则有效性"""
        if rule_id not in self._rule_effectiveness:
            self._rule_effectiveness[rule_id] = []
        self._rule_effectiveness[rule_id].append(was_helpful)
        rule = self._get_rule(rule_id)
        if rule:
            recent = self._rule_effectiveness[rule_id][-10:]
            if len(recent) >= 5 and sum(recent) / len(recent) < 0.3:
                rule.active = False
                logger.info("[KB] 规则 #%d 已停用 (有效率 %.0f%%)", rule_id, sum(recent)/len(recent)*100)

    def generate_lessons_report(self) -> str:
        """生成学习报告"""
        active = self.get_active_rules()
        if not active:
            return "知识库为空，等待学习..."

        lines = ["=" * 50, "  Vulpes 交易知识库", "=" * 50]

        # 按来源分组
        review_rules = [r for r in active if r.source_type == "trade_review"]
        user_rules = [r for r in active if r.source_type == "user_input"]

        if review_rules:
            lines.append(f"\n[📊 复盘学习] ({len(review_rules)} 条)")
            for r in review_rules:
                lines.append(f"  #{r.id} [{r.category}] {r.rule_text}")
                eff = self._rule_effectiveness.get(r.id, [])
                if eff:
                    lines.append(f"      有效率: {sum(eff)}/{len(eff)} ({sum(eff)/len(eff)*100:.0f}%)")

        if user_rules:
            lines.append(f"\n[🧠 用户知识] ({len(user_rules)} 条)")
            for r in user_rules:
                tags = " ".join(f"#{t}" for t in r.tags) if r.tags else ""
                lines.append(f"  #{r.id} [{r.category}] {r.rule_text} {tags}")

        lines.append(f"\n总计: {len(active)} 条活跃规则")
        return "\n".join(lines)

    def to_dict(self) -> Dict:
        return {
            "total_rules": len(self._rules),
            "active_rules": len([r for r in self._rules if r.active]),
            "rules": [
                {
                    "id": r.id,
                    "text": r.rule_text,
                    "source": r.source_type,
                    "category": r.category,
                    "tags": r.tags,
                    "active": r.active,
                }
                for r in self._rules
            ],
        }

    def _get_rule(self, rule_id: int) -> Optional[Rule]:
        for r in self._rules:
            if r.id == rule_id:
                return r
        return None
