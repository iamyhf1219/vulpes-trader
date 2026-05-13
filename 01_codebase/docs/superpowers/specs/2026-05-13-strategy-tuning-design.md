# Vulpes Trader — 策略调优 & 多币种适配 设计文档

> 日期: 2026-05-13
> 方案: B (系统化参数优化 + 多币种适配)
> 币种: BTC/USDT:USDT, ETH/USDT:USDT, SOL/USDT:USDT

---

## 1. 概览

### 1.1 目标

在现有 Vulpes Trader 框架基础上，实现：
1. **参数系统化优化** — 网格扫描 EMA/MACD/融合权重/止损参数，确认真实最优值
2. **多币种适配** — 每个币独立参数 Profile，支持按币种波动率和走势特征差异化配置
3. **波动率自适应** — ATR 驱动的动态 EMA 周期 / 动态仓位 / 动态止损
4. **信号质量评分** — 各信号源历史胜率追踪，融合权重自适应调整

### 1.2 范围

- **不涉及**: 新增信号源、新增交易所、机器学习优化、多时间帧信号融合
- **增量改造**: 不破坏现有 170 tests，只加不减

### 1.3 非功能要求

- 回测数据源: 从 ExchangeConnector REST 获取，至少 30 天 5m K 线
- 参数寻优不写回生产配置，输出到 report/ 目录供人工确认后激活
- 所有修改向后兼容，现有 orchestrator 逻辑不变

---

## 2. 多币种参数 Profile 系统

### 2.1 配置结构

在 `config/strategy.yaml` 扩展 per_symbol 配置:

```yaml
strategy:
  name: "trend_following_v1"
  timeframes:
    primary: "5m"
    secondary: "15m"
  indicators:
    ema_fast: [9, 12]
    ema_slow: [26, 50]
    macd: [12, 26, 9]
  per_symbol:
    BTC/USDT:USDT:
      enabled: true
      ema_fast: [9, 12]
      ema_slow: [26, 50]
      macd: [12, 26, 9]
      fusion_weights:
        trend: 0.30
        heat: 0.35
        event: 0.25
        oi: 0.10
      risk:
        stop_loss_fixed_pct: 0.05
        trailing_activation: 0.02
        trailing_distance: 0.015
    ETH/USDT:USDT:
      enabled: true
      ema_fast: [10, 14]
      ema_slow: [22, 44]
      macd: [10, 22, 7]
      fusion_weights:
        trend: 0.35
        heat: 0.30
        event: 0.25
        oi: 0.10
      risk:
        stop_loss_fixed_pct: 0.06
        trailing_activation: 0.025
        trailing_distance: 0.02
    SOL/USDT:USDT:
      enabled: true
      ema_fast: [12, 15]
      ema_slow: [30, 55]
      macd: [8, 20, 6]
      fusion_weights:
        trend: 0.25
        heat: 0.40
        event: 0.25
        oi: 0.10
      risk:
        stop_loss_fixed_pct: 0.08
        trailing_activation: 0.03
        trailing_distance: 0.025
```

### 2.2 配置加载器

新增 `SymbolConfig` 类:

```
SymbolConfig(symbol: str) -> Dict
  - 先查 per_symbol 中是否有该 symbol 的配置
  - 有则返回合并后的配置（per_symbol 覆盖全局默认）
  - 无则返回全局默认
```

**调用方改造:**
- `TrendFollower.__init__` 增加 `symbol` 参数，加载 per-symbol EMA/MACD
- `SignalFusionEngine` 增加 `update_weights(symbol)` 方法，按 symbol 加载融合权重
- `RiskManager` 增加 `load_symbol_config(symbol)` 方法

### 2.3 接口设计

```python
class SymbolConfig:
    """单个币种的参数配置，由 ConfigLoader 管理"""
    
    def __init__(self, symbol: str):
        self.symbol = symbol
        self._load()
    
    @property
    def ema_fast(self) -> List[int]
    @property
    def ema_slow(self) -> List[int]
    @property
    def macd_params(self) -> Tuple[int, int, int]
    @property
    def fusion_weights(self) -> Dict[str, float]
    @property
    def stop_loss_pct(self) -> float
    
    def update_params(self, params: Dict) -> None
    def save(self) -> None
```

---

## 3. 参数网格扫描优化

### 3.1 目标

使用已有 `ParameterSweep` 框架，对每币种独立扫描以下参数空间:

| 参数 | 搜索范围 | 步长 | 说明 |
|------|----------|------|------|
| ema_fast | [5, 9, 12, 15, 20] | — | 快线周期 |
| ema_slow | [20, 26, 30, 40, 50] | — | 慢线周期 |
| macd_fast | [8, 10, 12] | — | MACD 快线 |
| macd_slow | [20, 22, 26] | — | MACD 慢线 |
| macd_signal | [6, 7, 9] | — | MACD 信号线 |
| fusion_trend_weight | [0.20, 0.25, 0.30, 0.35, 0.40] | — | 趋势权重 |
| fusion_heat_weight | [0.25, 0.30, 0.35, 0.40] | — | 热度权重 |
| stop_loss_pct | [0.03, 0.04, 0.05, 0.06, 0.08] | — | 固定止损百分比 |

总分: ~20,000 组合/币种（全扫约 60,000）。

### 3.2 优化策略

**分批策略:**
1. **第一轮（粗扫）:**
   - 固定融合权重和止损，先扫 EMA/MACD 组合
   - 结果: 最佳 EMA/MACD 参数组合
2. **第二轮（精扫）:**
   - 固定 EMA/MACD 为第一轮最优，扫融合权重
3. **第三轮（止损优化）:**
   - 固定前两轮最优参数，扫止损百分比

### 3.3 评分函数

使用已有 `ParamResult.score` 公式，验证其对多币种的通用性:

```
score = max(sharpe, 0) * win_rate * sqrt(trades) / sqrt(max_drawdown)
```

**备选:**
- Calmar Ratio (sharpe / max_drawdown)
- Profit Factor (gross_profit / gross_loss)

评分函数改为可配置，通过参数传入。

### 3.4 MultiSymbolBacktest

新增多币种回测运行器，支持同时跑 N 个币种的回测并输出综合评分:

```
MultiSymbolBacktest.run(symbols: List[str], params: Dict) -> CombinedResult
  - 对每个 symbol 独立跑回测
  - 计算综合评分: average(score) * min(trades_count_ratio)
  - 输出每个币种的独立回测结果 + 综合排名
```

**评分权重:**
- 各币种评分加权平均（等权重或按流动性加权）
- 惩罚项: 某币种交易次数过少 (< 10)

---

## 4. 波动率自适应系统

### 4.1 ATR 计算

新增 `volatility.py` 模块:

```python
class VolatilityAdapter:
    """波动率自适应计算"""
    
    def __init__(self, period: int = 14):
        self.period = period
        
    def compute_atr(self, df: pd.DataFrame) -> float:
        """计算当前 ATR 百分比"""
        
    def adaptive_ema_period(self, base_period: int, atr_pct: float) -> int:
        """
        波动率大 → 缩短 EMA 周期（更快响应）
        波动率小 → 延长 EMA 周期（更平滑）
        公式: adjusted = base * (1 - atr_percentile * 0.5)
        """
        
    def adaptive_position_size(self, base_size: float, atr_pct: float) -> float:
        """
        波动率大 → 减小仓位
        波动率小 → 增大仓位
        公式: adjusted = base * (target_risk / atr_pct)
        """
        
    def adaptive_stop_loss(self, base_sl: float, atr_pct: float) -> float:
        """
        波动率大 → 放宽止损
        波动率小 → 收紧止损
        公式: adjusted = max(base_sl, atr_pct * 1.5)
        """
```

### 4.2 集成点

- **TrendFollower**: `generate()` 前调用 `compute_atr()` → 动态调整 EMA 周期
- **RiskManager**: `compute_position_size()` 和 `compute_leverage()` 接入 ATR
- **StopLossManager**: `create_stop_loss()` 接入 ATR 自适应止损

### 4.3 ATR 数据源

- 从 KlineEngine 获取 5m K 线数据
- 计算 14 周期 ATR（约 70 分钟）
- 同时维护一个 **ATR 百分位排名**（过去 24h 的波动率区间），用于归一化

---

## 5. 信号质量评分 & 自适应权重

### 5.1 信号质量追踪

新增 `signal_tracker.py`:

```python
class SignalQualityTracker:
    """追踪各信号源历史胜率"""
    
    def record_trade(self, symbol: str, signal_sources: Dict, trade_pnl: float):
        """记录一笔交易中各信号源的表现"""
        
    def get_win_rate(self, source: str, window: int = 20) -> float:
        """获取最近 N 笔信号的平均胜率"""
        
    def get_weight_adjustment(self, symbol: str) -> Dict[str, float]:
        """根据历史胜率计算权重调整量"""
        
    def get_report(self, symbol: str) -> Dict:
        """生成信号质量报告"""
```

### 5.2 自适应权重调整

在 TradeReviewer 流程中集成:

```
每笔交易平仓后:
  1. SignalQualityTracker.record_trade(symbol, signal_sources, pnl)
  2. 每 10 笔交易后触发：
     a. 读取各信号源最近 20 笔胜率
     b. 计算权重调整: new_weight = base_weight * (1 + (win_rate - 0.5) * 0.5)
     c. 归一化所有权重总和为 1.0
     d. 写入 SignalFusionEngine.weights
     e. 记录到 audit DB
```

### 5.3 权重调整约束

- 单次调整幅度不超过 ±0.05
- 权重下限 0.05（避免完全关闭某信号源）
- 权重上限 0.50（避免单一信号源主导）
- 数据不足 5 笔交易的信号源不做调整

---

## 6. 计划表 & 依赖

### 6.1 实现顺序

| # | 模块 | 预估工时 | 前置依赖 |
|---|------|----------|----------|
| 1 | SymbolConfig 配置系统 | 2h | — |
| 2 | 多币种 Profile 接入 TrendFollower | 2h | #1 |
| 3 | 多币种 Profile 接入 Fusion/Risk | 2h | #1 |
| 4 | VolatilityAdapter (ATR 自适应) | 3h | — |
| 5 | 自适应接入 TrendFollower/Risk/StopLoss | 2h | #4 |
| 6 | SignalQualityTracker | 3h | #1 |
| 7 | 自适应权重接入 TradeReviewer | 1h | #6 |
| 8 | MultiSymbolBacktest 运行器 | 3h | #1 |
| 9 | 参数网格扫描优化脚本 | 3h | #8 |
| 10 | 运行优化 + 输出报告 | 2h | #9 |
| **合计** | | **~23h** | |

### 6.2 测试计划

- 每个新模块对应新建测试文件或追加到现有 tests
- 核心测试点:
  - SymbolConfig: 加载/覆盖/回退逻辑
  - VolatilityAdapter: ATR 计算 > 自适应参数计算
  - SignalQualityTracker: 记录/查询/权重计算
  - MultiSymbolBacktest: 多币种跑通一致结果

### 6.3 风险点

- Binance testnet OI/热度数据模拟化（已存在 mock），多币种热度的获取可能需要调整
- 高波动时 ATR 自适应可能导致过于频繁的参数切换 → 加平滑/中值滤波
- 网格扫描 60,000 组合 × 30 天数据 = 计算量较大 → 用并行扫描或抽样数据

---

## 7. 交付物

1. **代码改动:**
   - 新增: `vulpes_trader/data/volatility.py`
   - 新增: `vulpes_trader/signal/tracker.py`
   - 新增: `vulpes_trader/config/symbol_config.py`（或扩展 `config.py`）
   - 改造: `signal/trend_follower.py`, `signal/fusion.py`, `risk/manager.py`, `execution/stop_loss.py`
   - 改造: `orchestrator.py` 集成 SignalQualityTracker
   - 改造: `config/strategy.yaml` 完整的 per_symbol 配置

2. **测试:**
   - `tests/test_volatility.py`
   - `tests/test_signal_tracker.py`
   - `tests/test_symbol_config.py`
   - 已有测试不变，170 pass 保持

3. **配置输出:**
   - 优化报告到 `reports/optimization/YYYY-MM-DD-symbol-results.json`
   - 建议新参数通过 `strategy.yaml` 激活（人工审核后）

4. **文档:**
   - 本设计文档
   - 更新 TOOLS.md 记录优化命令和流程

---

## 8. 自审

- [x] 无占位符/TODO
- [x] 各节一致: 配置结构、参数范围、评分公式在 3.1/3.3/2.1 一致
- [x] 范围聚焦: 只做参数优化和多币种，不做新信号源/新交易所
- [x] 无歧义: 参数覆盖逻辑、权重调整约束、分批优化策略均明确
