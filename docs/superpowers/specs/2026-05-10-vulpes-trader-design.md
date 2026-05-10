# Vulpes Trader — 自动化币安永续合约交易机器人 设计文档 (v2.0)

> **代号：** Vulpes（狐，象征敏捷与策略）
> **版本：** v2.0
> **日期：** 2026-05-10
> **状态：** 设计稿（更新版）

---

## 1. 项目概述

### 1.1 目标

构建一个全自动、自我进化的币安永续合约交易机器人，核心基于**币安广场热度 + OI 异动 + 新闻事件驱动**的多维度信号体系，具备**交易复盘与参数自适应**的进化能力。

### 1.2 核心原则

| 原则 | 说明 |
|------|------|
| **零信任安全** | API Key 仅 .env 管理，禁止硬编码，禁止日志打印 |
| **军工级容错** | 断线重连 + 指数退避，断网自动保护 |
| **因果律** | 无未来函数，所有信号基于已闭合 K 线 |
| **模块化** | 每一层职责单一，可独立测试 |
| **审计优先** | 全量操作日志，可回溯每一次开平仓决策 |
| **进化优先** | 每笔交易后自动复盘，持续调参优化 |

### 1.3 技术栈

| 组件 | 技术选型 | 理由 |
|------|---------|------|
| 运行时 | Python 3.13 | 生态成熟，异步原生支持 |
| 交易所接口 | ccxt (Pro) | WebSocket 实时行情，统一 API |
| 异步框架 | asyncio + aiohttp | 高并发事件驱动 |
| 数据处理 | pandas + numpy | 指标计算、切片分析 |
| 技术指标 | ta (Technical Analysis Library) | 标准化的指标计算 |
| NLP/摘要 | 本地轻量模型 (可选) | 新闻事件关键词抽取与代币映射 |
| 存储 | SQLite (持久) + JSON (运行时) | 轻量，零依赖 |
| 日志 | logging (RotatingFileHandler) | 分级别、轮转归档 |
| 配置 | python-dotenv + YAML | Key 安全 + 策略参数分离 |

---

## 2. 系统架构 (v2.0 更新版)

### 2.1 整体架构

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         Vulpes Trader Core                              │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │                        DATA LAYER                               │   │
│  │  ┌──────────────┐  ┌─────────────┐  ┌──────────────┐           │   │
│  │  │ WS 行情引擎   │  │ OI/费率采集 │  │ K线聚合引擎  │           │   │
│  │  └──────┬───────┘  └──────┬──────┘  └──────┬───────┘           │   │
│  │  ┌──────────────┐  ┌─────────────┐  ┌──────────────┐           │   │
│  │  │ 币安广场热度  │  │ 新闻事件捕获  │  │ 代币-事件映射 │           │   │
│  │  └──────────────┘  └─────────────┘  └──────────────┘           │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                                    │                                     │
│  ┌──────────────────────────────────┴─────────────────────────────────┐  │
│  │                     SIGNAL LAYER                                   │  │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐             │  │
│  │  │ 趋势跟踪信号  │  │ 热度信号     │  │ 事件驱动信号  │             │  │
│  │  │ (EMA/MACD/OI)│  │ (广场热度+OI)│  │ (新闻+代币)  │             │  │
│  │  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘             │  │
│  │  ┌────────────────────────┼────────────────┐                      │  │
│  │  │             信号融合引擎 (Composite)      │                      │  │
│  │  │  多信号加权 → 最终方向决策 + 信心指数     │                      │  │
│  │  └───────────────────────────────────────────┘                      │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                    │                                     │
│  ┌──────────────────────────────────┴─────────────────────────────────┐  │
│  │                     RISK LAYER                                     │  │
│  │  • 动态杠杆计算  • 动态仓位规模  • 熔断开关  • 最大回撤控制        │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                    │                                     │
│  ┌──────────────────────────────────┴─────────────────────────────────┐  │
│  │                   EXECUTION LAYER                                  │  │
│  │  • 订单管理  • 仓位管理  • 固定止损 + 移动止损  • 分批止盈         │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                    │                                     │
│  ┌──────────────────────────────────┴─────────────────────────────────┐  │
│  │             POST-TRADE REVIEW & EVOLUTION (全新)                   │  │
│  │  ┌────────────┬────────────┬────────────┬────────────┐            │  │
│  │  │ 交易复盘    │ 参数调优    │ 策略权重    │ 知识沉淀    │            │  │
│  │  └────────────┴────────────┴────────────┴────────────┘            │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                          │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │                 STATE & AUDIT LAYER                               │   │
│  │  SQLite 持久化 · 全量操作日志 · 性能监控 · 复盘记录              │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### 2.2 新增数据流

```
币安广场 ----→ [热度爬虫] ---→ 热点 Ticker 排名 ---→ 热度信号
                                      │
                               新鲜度/提及量趋势

新闻源 ------→ [新闻引擎] ---→ 事件文本分析 → 代币映射 ---→ 事件信号
(Twitter/       │                          │
NewsAPI)        │                    {代币: [利好/利空/中性], 事件类型, 置信度}
          事件去重 + 时间戳
```

---

## 3. 新增组件详细设计

### 3.1 币安广场热度监控 (Binance Square Heat Monitor)

**职责：** 实时爬取币安广场帖子中提及的 Ticker，统计热度排名和趋势

**策略来源：** 
- 灵感来自 @lanaaielsa 的交易策略
- 已验证案例：泵泵超人 @crypto_pumpman 的刀盾 (dogdoing.ai) 整合了 "币安广场热度 + OI 异动监控"
- @zaijin338191 的 "币安广场热度监控" 软件：模拟盘 1000U → 2048U（2天），胜率 40-60%

**实现方式：**

```yaml
square_heat:
  enabled: true
  poll_interval: 30                    # 轮询间隔（秒）
  max_tickers: 30                      # 追踪前 N 个热门 Ticker
  source: "binance_square_api"         # 数据源
  heat_window: 3600                    # 热度统计窗口（秒）
  
  signal_rules:
    # 热度 + OI 共振信号
    heat_oi_bullish:
      conditions:
        - ticker_rank_top_20: true      # 热度排名前 20
        - oi_change: "extreme_or_strong" # OI 异动强烈或极端
        - price_trend_up: true          # 价格趋势向上
      confidence: 0.8
      
    heat_only_bullish:
      conditions:
        - ticker_rank_top_10: true      # 热度排名前 10
        - mention_momentum: "rising"    # 提及量在上升
        - price_positive_1h: true       # 1小时涨幅为正
      confidence: 0.6
      
  monitoring_panel:                     # 看板预览
    columns: ["排名", "Ticker", "提及数", "OI变化", "价格", "24H成交额", "信号源数"]
```

### 3.2 新闻事件捕获与分析 (News Event Engine)

**职责：** 实时捕获加密圈新闻，判断对具体代币的影响方向（利好/利空/中性），输出事件信号

**数据源：**
```
┌─────────────────────────────────────────────┐
│             新闻事件引擎                      │
├─────────────────────────────────────────────┤
│  • Twitter/X (关键 KOL、项目官推)            │
│  • 主流加密新闻 (CoinDesk, CoinTelegraph)    │
│  • 链上数据异动 (Whale Alert, 巨鲸追踪)      │
│  • 项目官方公告 (GitHub, Discord, Medium)    │
│  • 宏观事件 (美联储、CPI、ETF 消息)          │
└─────────────────────────────────────────────┘
```

**事件分类与影响判断：**
```yaml
event_types:
  regulation_positive: {impact: "bullish", decay: "4h"}    # 合规利好
  regulation_negative: {impact: "bearish", decay: "4h"}   # 监管利空
  partnership:         {impact: "bullish", decay: "2h"}    # 合作
  hack_exploit:        {impact: "bearish", decay: "6h"}   # 安全事件
  token_unlock:        {impact: "bearish", decay: "24h"}  # 解锁
  listing:             {impact: "bullish", decay: "1h"}   # 上币
  halving:             {impact: "bullish", decay: "7d"}   # 减半
  macro_cpi:           {impact: "broad", decay: "2h"}     # 宏观
  whale_movement:      {impact: "variable", decay: "1h"}  # 巨鲸
```

**事件→代币映射逻辑（Phase A - 关键词匹配，预留 NLP 接口）：**
```python
def map_event_to_tokens(event_text):
    """
    Phase A: 关键词匹配 + 币安 Ticker 映射
    Phase B+: NLP 语义理解 + 影响力评分
    """
    # 直接 Ticker 提及: "$BTC", "#ETH", "SOL/USDT"
    # 项目名映射: "Ethereum" → ETH, "Solana" → SOL
    # 赛道映射: "DeFi" → UNI/AAVE/CRV, "L2" → ARB/OP
    tokens = extract_tickers(event_text)
    return tokens_with_sentiment(event_text, tokens)
```

### 3.3 信号融合引擎 (Signal Fusion Engine)

**职责：** 将趋势信号、热度信号、事件信号加权融合为最终决策

```yaml
signal_weights:
  trend_signal:     0.30    # 技术面趋势（EMA/MACD/OI）
  heat_signal:      0.35    # 币安广场热度（最高权重）
  event_signal:     0.25    # 新闻事件驱动
  macro_signal:     0.10    # 宏观/市场情绪
  
  # 信号融合规则
  fusion_rules:
    - if: "heat_signal.confidence > 0.8 AND trend_signal.direction == same"
      action: "full_allocate"
      boost: 1.5               # 信号共振 → 加仓
    - if: "heat_signal.confidence > 0.6 AND event_signal.direction == same"
      action: "normal_allocate"
    - if: "heat_signal and trend_signal == opposite"
      action: "reduce_position" # 信号矛盾 → 减小仓位
    - if: "all_signals == neutral"
      action: "no_trade"       # 无明确信号 → 不交易
```

---

## 4. 自我进化系统 — Post-Trade Review & Evolution（全新模块）

这是系统最强的部分——**让机器人学会变聪明**。

### 4.1 复盘流程

```
每笔交易结束
     │
     ▼
┌─────────────────┐
│ Step 1: 数据收集 │ ← 完整交易记录 + 当时所有信号快照
└────────┬────────┘
         ▼
┌─────────────────┐
│ Step 2: 归类分析 │ ← 胜/败/错失机会
└────────┬────────┘
         ▼
┌────────────────────┐
│ Step 3: 根因诊断    │ ← 为什么赚/为什么亏/为什么没拿住
└────────┬───────────┘
         ▼
┌────────────────────┐
│ Step 4: 参数调优    │ ← 调整具体参数/规则
└────────┬───────────┘
         ▼
┌────────────────────┐
│ Step 5: 知识沉淀    │ ← 写入规则库，下次避免同类错误
└────────────────────┘
```

### 4.2 复盘分类体系

每笔交易结束后，自动进入复盘流水线：

```yaml
post_trade_review:
  # ─── 盈利交易分析 ───
  win_analysis:
    - type: "correct_direction"
      check: "入场方向是否正确？"
      learn: "确认此信号模式为有效，加分"
    - type: "perfect_exit"
      check: "出场是否接近最优？"
      learn: "止损/止盈设置是否合理？"
    - type: "could_be_better"
      check: "是否存在收益未最大化？"
      sub_checks:
        - "加仓过早/过晚？"
        - "提前止盈错过后半段？"
        - "移动止损追得太紧/太松？"
  
  # ─── 亏损交易分析 ───  
  loss_analysis:
    - type: "wrong_direction"
      check: "方向判断错误，哪个信号误导了？"
      root_causes:
        - "热度信号出现但 OI 背离"
        - "新闻事件解读错误（假利好）"
        - "趋势指标滞后"
    - type: "bad_entry"
      check: "入场时机不佳，追高了/抄早了？"
    - type: "stop_loss_hit"
      check: "止损被扫，但方向最终正确？"
      learn: "止损宽度是否过窄？"
    - type: "fakeout"
      check: "假突破/假信号"
      learn: "是否需要增加确认条件？"
  
  # ─── 错失机会分析 ───
  missed_opportunity:
    - type: "signal_detected_no_trade"
      check: "信号出现了但没交易，为何？"
      reasons: ["仓位已满", "风控约束", "信号置信度不足"]
      learn: "是否需要放宽条件？"
    - type: "no_signal_at_all"
      check: "大行情出现但系统没有任何信号，为何？"
      learn: "是否需要增加新信号源？"
```

### 4.3 参数自适应调整

```
复盘后，自动调整以下参数：

┌────────────────────────────────────────────────────────┐
│                    参数调整矩阵                          │
├──────────────┬──────────┬──────────┬───────────────────┤
│  复盘结论     │ 调整对象  │ 调整方向  │ 调整幅度          │
├──────────────┼──────────┼──────────┼───────────────────┤
│ 止损过窄被扫  │ SL宽度   │ 扩大     │ +10% (上限200%)  │
│ 止损过宽亏大  │ SL宽度   │ 缩小     │ -10%             │
│ 移动止损追太紧│ TS距离   │ 放宽     │ +20%             │
│ 入场追高      │ 入场时机  │ 加确认   │ 增加一个K线确认   │
│ 热度信号有效   │ 热度权重  │ 上调     │ +0.05 (上限0.50) │
│ 热度信号假    │ 热度权重  │ 下调     │ -0.05            │
│ 事件信号有效   │ 事件权重  │ 上调     │ +0.05 (上限0.40) │
│ 连续亏损3次   │ 策略暂停  │ 暂停     │ 停2小时          │
│ 连续盈利3次   │ 杠杆     │ 微增     │ +0.5x (上限2x)   │
├──────────────┴──────────┴──────────┴───────────────────┤
│ 所有调整记录日志，SQLite 持久化                          │
└────────────────────────────────────────────────────────┘
```

### 4.4 知识库 (Trade Knowledge Base)

```sql
-- 交易记录
CREATE TABLE trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,  side TEXT NOT NULL,
    entry_price REAL NOT NULL,  exit_price REAL,
    quantity REAL NOT NULL,  leverage INTEGER NOT NULL,
    pnl REAL,  pnl_pct REAL,
    entry_time TIMESTAMP NOT NULL,  exit_time TIMESTAMP,
    stop_loss REAL,  take_profit REAL,  exit_reason TEXT,
    strategy TEXT
);

-- 复盘记录（核心）
CREATE TABLE trade_reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trade_id INTEGER REFERENCES trades(id),
    overall_grade TEXT,           -- 'A'/'B'/'C'/'D'/'F'
    win_loss_category TEXT,       -- 'correct_direction'/'wrong_direction'/'bad_entry'/...
    root_cause TEXT,              -- 根因描述
    signal_snapshot TEXT,         -- 入场时的信号快照 (JSON)
    lessons_learned TEXT,         -- 本次学到的教训
    parameter_adjustments TEXT    -- 本次调整的参数 (JSON)
);

-- 参数状态追踪
CREATE TABLE parameter_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TIMESTAMP NOT NULL,
    parameter_name TEXT NOT NULL,
    old_value REAL,  new_value REAL,
    reason TEXT,                  -- 触发调整的复盘 ID
    trade_id INTEGER
);

-- 规则库
CREATE TABLE rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TIMESTAMP NOT NULL,
    rule TEXT NOT NULL,           -- 如 "当 OI 与价格背离时，降低热度信号权重"
    source_trade_id INTEGER,      -- 触发此规则的交易
    active BOOLEAN DEFAULT 1,
    effectiveness_score REAL DEFAULT 0  -- 此规则后续的有效性评分
);
```

### 4.5 进化接口 (预留扩展)

```python
class EvolutionPlugin(ABC):
    """进化模块的抽象接口，后续可扩展为更复杂的实现"""
    
    @abstractmethod
    def review(self, trade_record, signal_snapshot) -> ReviewResult:
        """对单笔交易进行复盘"""
        pass
    
    @abstractmethod
    def adjust_parameters(self, review_result) -> List[ParameterChange]:
        """根据复盘结果调整参数"""
        pass
    
    @abstractmethod
    def learn(self, trade_history: List[TradeRecord]) -> UpdatedModel:
        """从历史交易中学习（Phase B 可用 ML 模型）"""
        pass
```

---

## 5. 完整数据流 (含新增模块)

```
                     ┌─────────────────────┐
                     │   币安 WebSocket     │
                     └──────────┬──────────┘
                                │
          ┌─────────────────────┼─────────────────────┐
          ▼                     ▼                      ▼
   ┌──────────────┐    ┌──────────────┐    ┌─────────────────┐
   │ WS 行情/OHLCV  │    │ OI/资金费率   │    │ 币安广场爬虫     │
   └──────┬───────┘    └──────┬───────┘    └────────┬────────┘
          │                   │                      │
          ▼                   ▼                      ▼
   ┌──────────────┐    ┌──────────────┐    ┌─────────────────┐
   │ 技术指标计算   │    │ OI 异动检测   │    │ 热度排名统计     │
   └──────┬───────┘    └──────┬───────┘    └────────┬────────┘
          │                   │                      │
          └──────────┬────────┘                      │
                     │                               │
                     ▼                               │
              ┌──────────────┐                        │
              │ 趋势信号      │                        │
              └──────┬───────┘                        │
                     │                               │
          ┌──────────┼───────────────────────────────┘
          │          │                      ┌──────────────────┐
          │          │                      │ 新闻事件引擎      │
          │          │                      └────────┬─────────┘
          │          │                               │
          ▼          ▼                               ▼
     ┌─────────────────────────────────────────────────────┐
     │              信号融合引擎 (Signal Fusion)             │
     │    趋势权重 0.30 + 热度权重 0.35 + 事件权重 0.25     │
     └──────────────────────┬──────────────────────────────┘
                            │
                            ▼
                     ┌──────────────┐
                     │   Risk Layer  │
                     └──────┬───────┘
                            │
                            ▼
                     ┌──────────────┐
                     │  Execution   │
                     └──────┬───────┘
                            │
                            ▼
                     ┌──────────────────────┐
                     │ 复盘 & 进化引擎       │
                     │  (Post-Trade Review)  │
                     └──────────────────────┘
```

---

## 6. 模块接口设计 (新增模块)

### 6.1 BinanceSquareMonitor

```python
class BinanceSquareMonitor:
    """
    币安广场热度监控
    """
    async def fetch_hot_topics(self) -> List[HotTopic]:
        """获取当前热门话题"""
        pass
    
    async def get_ticker_rank(self) -> List[TickerHeatRank]:
        """
        返回 Ticker 热度排名：
        [{"ticker": "LAYER", "mentions": 94, "sources": ["广场","帖子","社区"],
          "momentum": "rising", "oi_change": "extreme"}]
        """
        pass
    
    def compute_heat_signal(self, ticker_rank) -> HeatSignal:
        """根据热度排名+OI+价格生成热度信号"""
        pass
```

### 6.2 NewsEventEngine

```python
class NewsEventEngine:
    """
    新闻事件捕获与分析
    """
    async def poll_news_sources(self):
        """轮询多个新闻源"""
        pass
    
    def analyze_event(self, event_text: str, timestamp) -> EventAnalysis:
        """
        分析事件：
        - 提取关键词
        - 映射到代币
        - 判断利好/利空
        - 给出影响时长
        """
        pass
    
    def map_tokens(self, text: str) -> Dict[str, float]:
        """从文本中映射代币及置信度"""
        pass
```

### 6.3 PostTradeReviewEngine

```python
class PostTradeReviewEngine:
    """
    交易复盘与进化系统
    """
    async def review_trade(self, trade: TradeRecord):
        """对已结束的交易进行全面复盘"""
        pass
    
    def classify_result(self, trade, signals) -> ReviewCategory:
        """归类交易结果"""
        pass
    
    def diagnose_root_cause(self, trade, signals) -> List[RootCause]:
        """诊断根因"""
        pass
    
    def adjust_parameters(self, review) -> List[ParameterChange]:
        """调参"""
        pass
    
    def update_knowledge_base(self, review):
        """更新规则库"""
        pass
```

### 6.4 EvolutionInterface (预留扩展接口)

```python
class EvolutionInterface:
    """
    进化系统接口，Phase B 可对接 ML 模型
    
    预留能力：
    - Q-Learning 策略优化
    - 贝叶斯参数调优
    - 模式识别（识别重复出现的市场结构）
    """
    pass
```

---

## 7. 项目目录结构 (更新版)

```
01_codebase/
├── vulpes_trader/
│   ├── __init__.py
│   ├── main.py                    # 入口
│   ├── config.py                  # 配置管理
│   │
│   ├── data/
│   │   ├── __init__.py
│   │   ├── ws_manager.py          # WebSocket 连接管理
│   │   ├── kline_engine.py        # K 线聚合与缓存
│   │   ├── supplementary.py       # OI/资金费率拉取
│   │   ├── cache.py              # 数据缓存
│   │   ├── square_monitor.py     # 【新增】币安广场热度监控
│   │   └── news_engine.py        # 【新增】新闻事件引擎
│   │
│   ├── signal/
│   │   ├── __init__.py
│   │   ├── base.py               # Signal 抽象基类
│   │   ├── trend_follower.py     # 趋势跟踪信号
│   │   ├── oi_analyzer.py        # OI 分析信号
│   │   ├── heat_analyzer.py      # 【新增】热度信号
│   │   ├── event_analyzer.py     # 【新增】事件驱动信号
│   │   └── fusion.py             # 【新增】信号融合引擎
│   │
│   ├── risk/
│   │   ├── __init__.py
│   │   ├── manager.py            # 风控管理器
│   │   └── circuit_breaker.py    # 熔断器
│   │
│   ├── execution/
│   │   ├── __init__.py
│   │   ├── order_manager.py      # 订单管理
│   │   ├── position_manager.py   # 仓位管理
│   │   └── stop_loss.py         # 止损管理
│   │
│   ├── evolution/                # 【新增】自我进化模块
│   │   ├── __init__.py
│   │   ├── reviewer.py           # 交易复盘引擎
│   │   ├── optimizer.py          # 参数调优器
│   │   ├── knowledge_base.py     # 规则库管理
│   │   └── interfaces.py         # 进化接口抽象
│   │
│   ├── audit/
│   │   ├── __init__.py
│   │   ├── db.py                 # SQLite 数据库
│   │   ├── logger.py             # 日志配置
│   │   └── reporter.py           # 报表生成
│   │
│   └── utils/
│       ├── __init__.py
│       ├── retry.py              # 指数退避重试
│       ├── helpers.py            # 工具函数
│       └── token_mapper.py       # 【新增】代币映射工具
│
├── config/
│   ├── strategy.yaml             # 策略参数
│   ├── risk.yaml                 # 风控参数
│   ├── square.yaml               # 【新增】广场热度配置
│   └── news.yaml                 # 【新增】新闻源配置
│
├── .env.example                  # API Key 模板
├── requirements.txt              # 依赖清单
├── logs/                         # 日志目录
└── tests/                        # 单元测试
```

---

## 8. 开发路线图 (更新版)

| 阶段 | 内容 | 工时 |
|------|------|------|
| **Phase 0: 基建** | 项目脚手架、依赖、配置、日志、数据库 | 1 天 |
| **Phase 1: 数据层核心** | WS 行情、K 线引擎、OI/费率采集 | 1-2 天 |
| **Phase 1b: 数据层扩展** | 币安广场热度爬虫 + 新闻事件引擎 | 2 天 |
| **Phase 2: 信号层** | 趋势信号 + OI 分析 + 热度信号 + 事件信号 + 融合引擎 | 2-3 天 |
| **Phase 3: 风控 & 执行** | 风控、熔断、订单、仓位、止损管理 | 2 天 |
| **Phase 4: 复盘 & 进化** | 复盘引擎、参数调优、规则库 | 2-3 天 |
| **Phase 5: 审计 & 稳定** | 完整日志、数据库审计、测试网运行 | 2 天 |
| **Phase 6: 测试网实跑** | 200+ 笔模拟交易、参数调优 | 7-14 天 |

---

## 9. 边界条件与异常处理

### 9.1 数据源异常
- 币安广场不可用 → 降级为纯技术面交易
- 新闻源中断 → 降级，等待恢复后补采
- OI/费率数据延迟 → 延迟信号输出，不生成虚假信号

### 9.2 进化系统安全
- 参数调整有硬边界（上限/下限），防止发散
- 每次调整有回滚能力
- 自动进化历史可审计、可手动覆盖
- 极端市场（黑天鹅）下禁用自动化调参

### 9.3 其他同 v1.0

---

## 10. 核心哲学

> **Vulpes Trader 不是「写死的策略机器人」，而是一个「会自我进化的交易学徒」。**
>
> 它每做一笔交易，都会问自己三个问题：
> 1. 为什么这笔赚了/亏了？
> 2. 下次怎么做得更好？
> 3. 市场在告诉我什么规律？
>
> 代币「狐」——不是靠蛮力高频刷单，而是靠观察、判断、学习，变得越来越聪明。
