# Vulpes Trader Implementation Plan — Phase 0 & 1

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the foundational scaffolding and data layer for the Vulpes Trader automated trading bot.

**Architecture:** Modular event-driven architecture with isolated layers (Data → Signal → Risk → Execution → Evolution). Phase 0 sets up project structure, config system, logging, and database. Phase 1 implements WS market data, K-line engine, and OI/funding rate collection.

**Tech Stack:** Python 3.13, ccxt Pro, asyncio, aiohttp, pandas, numpy, python-dotenv, SQLite

---

### Task 1: Project Scaffolding & Dependencies

**Files:**
- Create: `01_codebase/vulpes_trader/__init__.py`
- Create: `01_codebase/vulpes_trader/main.py`
- Create: `01_codebase/vulpes_trader/config.py`
- Create: `01_codebase/requirements.txt`
- Create: `01_codebase/.env.example`
- Create: `01_codebase/.gitignore`

- [ ] **Step 1: Create requirements.txt**

```txt
ccxt>=4.4.0
pandas>=2.2.0
numpy>=1.26.0
python-dotenv>=1.0.0
aiohttp>=3.9.0
pyyaml>=6.0
ta>=0.11.0
```

- [ ] **Step 2: Create .env.example**

```env
# Binance API Keys (Testnet)
BINANCE_TESTNET_API_KEY=your_testnet_api_key
BINANCE_TESTNET_SECRET=your_testnet_secret

# Binance API Keys (Mainnet - USE WITH CAUTION)
BINANCE_MAINNET_API_KEY=
BINANCE_MAINNET_SECRET=

# Runtime Mode
VULPES_MODE=testnet  # testnet | mainnet
```

- [ ] **Step 3: Create .gitignore**

```
.env
logs/
__pycache__/
*.pyc
*.db
*.egg-info/
dist/
build/
```

- [ ] **Step 4: Create vulpes_trader/__init__.py**

```python
"""Vulpes Trader — 自动化币安永续合约交易机器人"""

__version__ = "0.1.0"
```

- [ ] **Step 5: Create config.py with dotenv + YAML loading**

```python
"""配置管理 — 从 .env 和 YAML 文件加载配置"""

import os
from pathlib import Path
from dotenv import load_dotenv
import yaml
from typing import Any, Dict

load_dotenv()

PROJECT_ROOT = Path(__file__).parent.parent


class Config:
    """配置加载器，优先 .env 再 YAML"""

    def __init__(self):
        self.mode = os.getenv("VULPES_MODE", "testnet")
        self._yaml_config: Dict[str, Any] = {}
        self._load_yaml()

    def _load_yaml(self):
        config_dir = PROJECT_ROOT / "config"
        for yaml_file in config_dir.glob("*.yaml"):
            with open(yaml_file, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
                if data:
                    self._yaml_config.update(data)

    @property
    def exchange_config(self) -> Dict[str, str]:
        if self.mode == "testnet":
            return {
                "apiKey": os.getenv("BINANCE_TESTNET_API_KEY", ""),
                "secret": os.getenv("BINANCE_TESTNET_SECRET", ""),
                "options": {"defaultType": "swap"},
                "urls": {"api": {"public": "https://testnet.binancefuture.com/fapi/v1"}},
            }
        return {
            "apiKey": os.getenv("BINANCE_MAINNET_API_KEY", ""),
            "secret": os.getenv("BINANCE_MAINNET_SECRET", ""),
            "options": {"defaultType": "swap"},
        }

    def get(self, *keys: str, default=None):
        """安全地获取嵌套配置"""
        data = self._yaml_config
        for key in keys:
            if isinstance(data, dict):
                data = data.get(key)
            else:
                return default
        return data if data is not None else default


config = Config()
```

- [ ] **Step 6: Create main.py entry point**

```python
"""Vulpes Trader 入口"""

import asyncio
import logging
from vulpes_trader.config import config

logger = logging.getLogger("vulpes")


async def main():
    logger.info("=== Vulpes Trader 启动 ===")
    logger.info("模式: %s", config.mode)
    
    try:
        # TODO: Phase 2+ - 启动各层组件
        logger.info("基建就绪，等待后续模块加载...")
        await asyncio.Event().wait()  # 永久运行
    except KeyboardInterrupt:
        logger.info("收到停止信号，正在安全关闭...")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    asyncio.run(main())
```

- [ ] **Step 7: Create directory structure**

Run: `mkdir -p 01_codebase/vulpes_trader/{data,signal,risk,execution,evolution,audit,utils} 01_codebase/config`

Expected: All directories created silently

- [ ] **Step 8: Create config YAML files**

Create `01_codebase/config/strategy.yaml`:
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
```

Create `01_codebase/config/risk.yaml`:
```yaml
risk:
  max_leverage: 20
  min_leverage: 1
  max_capital_per_trade_base: 0.15
  max_total_positions: 5
  stop_loss_fixed_pct: 0.05
  trailing_stop_activation: 0.02
  trailing_stop_distance: 0.015
  daily_loss_limit: 0.20
  max_consecutive_losses: 3
  circuit_breaker: true
  dynamic_position_sizing: true
  dynamic_leverage: true
```

- [ ] **Step 9: Install dependencies and verify**

Run: `pip install -r 01_codebase/requirements.txt`

Expected: All packages install without errors

- [ ] **Step 10: Verify project loads**

Run: `cd 01_codebase && python -c "from vulpes_trader.config import config; print('Config OK:', config.mode)"`

Expected: `Config OK: testnet`

- [ ] **Step 11: Commit**

```bash
git add 01_codebase/
git commit -m "feat(vulpes): Phase 0 scaffolding — config, deps, entry point"
```

---

### Task 2: Logging & Audit Database (audit layer)

**Files:**
- Create: `01_codebase/vulpes_trader/audit/__init__.py`
- Create: `01_codebase/vulpes_trader/audit/logger.py`
- Create: `01_codebase/vulpes_trader/audit/db.py`

- [ ] **Step 1: Write the failing test**

Create `01_codebase/tests/test_audit_db.py`:
```python
import pytest
import tempfile
from pathlib import Path
from vulpes_trader.audit.db import AuditDB


def test_audit_db_init():
    """测试数据库初始化和建表"""
    with tempfile.TemporaryDirectory() as tmpdir:
        db = AuditDB(db_path=Path(tmpdir) / "test.db")
        assert db.initialized
        
        # 验证表存在
        tables = db.fetchall("SELECT name FROM sqlite_master WHERE type='table'")
        table_names = [t[0] for t in tables]
        assert "trades" in table_names
        assert "equity_curve" in table_names
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd 01_codebase && python -m pytest tests/test_audit_db.py -v`
Expected: FAIL with "No module named 'vulpes_trader.audit'"

- [ ] **Step 3: Write audit/logger.py**

```python
"""日志配置 — 控制台 + 滚动文件日志"""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_DIR = Path(__file__).parent.parent.parent / "logs"


def setup_logger(name: str = "vulpes", level: int = logging.INFO) -> logging.Logger:
    """配置并返回 logger 实例"""
    LOG_DIR.mkdir(exist_ok=True)

    logger = logging.getLogger(name)
    logger.setLevel(level)

    # 避免重复添加 handler
    if logger.handlers:
        return logger

    # 控制台 handler
    console = logging.StreamHandler()
    console.setLevel(level)
    console.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    ))
    logger.addHandler(console)

    # 文件 handler (10MB 滚动)
    file_handler = RotatingFileHandler(
        LOG_DIR / f"{name}.log",
        maxBytes=10_485_760,  # 10MB
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s:%(lineno)d: %(message)s"
    ))
    logger.addHandler(file_handler)

    return logger
```

- [ ] **Step 4: Write audit/db.py**

```python
"""SQLite 数据库 — 存储交易记录、复盘数据、权益曲线"""

import sqlite3
import json
from pathlib import Path
from typing import Optional, List, Any
from datetime import datetime

DB_DIR = Path(__file__).parent.parent.parent / "data"


class AuditDB:
    """轻量级 SQLite 数据库封装"""

    def __init__(self, db_path: Optional[Path] = None):
        if db_path is None:
            DB_DIR.mkdir(exist_ok=True)
            db_path = DB_DIR / "vulpes.db"
        self.db_path = db_path
        self.initialized = False
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        return sqlite3.connect(str(self.db_path))

    def _init_db(self):
        """初始化建表"""
        with self._get_conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    entry_price REAL NOT NULL,
                    exit_price REAL,
                    quantity REAL NOT NULL,
                    leverage INTEGER NOT NULL,
                    pnl REAL,
                    pnl_pct REAL,
                    entry_time TIMESTAMP NOT NULL,
                    exit_time TIMESTAMP,
                    stop_loss REAL,
                    take_profit REAL,
                    exit_reason TEXT,
                    strategy TEXT,
                    signal_snapshot TEXT
                );

                CREATE TABLE IF NOT EXISTS signals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TIMESTAMP NOT NULL,
                    symbol TEXT NOT NULL,
                    signal_type TEXT NOT NULL,
                    confidence REAL,
                    indicators TEXT,
                    executed BOOLEAN DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS equity_curve (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TIMESTAMP NOT NULL,
                    equity REAL NOT NULL,
                    unrealized_pnl REAL,
                    margin_used REAL
                );

                CREATE TABLE IF NOT EXISTS trade_reviews (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    trade_id INTEGER REFERENCES trades(id),
                    overall_grade TEXT,
                    win_loss_category TEXT,
                    root_cause TEXT,
                    lessons_learned TEXT,
                    parameter_adjustments TEXT
                );

                CREATE TABLE IF NOT EXISTS parameter_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TIMESTAMP NOT NULL,
                    parameter_name TEXT NOT NULL,
                    old_value REAL,
                    new_value REAL,
                    reason TEXT,
                    trade_id INTEGER
                );
            """)
        self.initialized = True

    def execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        """执行 SQL"""
        with self._get_conn() as conn:
            return conn.execute(sql, params)

    def fetchall(self, sql: str, params: tuple = ()) -> List[Any]:
        """查询并返回所有结果"""
        with self._get_conn() as conn:
            return conn.execute(sql, params).fetchall()

    def save_trade(self, trade_data: dict) -> int:
        """保存交易记录，返回 ID"""
        with self._get_conn() as conn:
            cur = conn.execute(
                """INSERT INTO trades 
                (symbol, side, entry_price, quantity, leverage, 
                 stop_loss, take_profit, strategy, signal_snapshot, entry_time)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    trade_data["symbol"],
                    trade_data["side"],
                    trade_data["entry_price"],
                    trade_data["quantity"],
                    trade_data["leverage"],
                    trade_data.get("stop_loss"),
                    trade_data.get("take_profit"),
                    trade_data.get("strategy"),
                    json.dumps(trade_data.get("signal_snapshot", {})),
                    datetime.utcnow().isoformat(),
                ),
            )
            return cur.lastrowid

    def close_trade(self, trade_id: int, exit_price: float, pnl: float, 
                    exit_reason: str):
        """平仓更新"""
        with self._get_conn() as conn:
            conn.execute(
                """UPDATE trades SET exit_price=?, pnl=?, exit_time=?,
                   exit_reason=? WHERE id=?""",
                (exit_price, pnl, datetime.utcnow().isoformat(),
                 exit_reason, trade_id),
            )
```

- [ ] **Step 5: Write audit/__init__.py**

```python
from .logger import setup_logger
from .db import AuditDB

__all__ = ["setup_logger", "AuditDB"]
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd 01_codebase && python -m pytest tests/test_audit_db.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add 01_codebase/vulpes_trader/audit/ 01_codebase/tests/
git commit -m "feat(vulpes): audit layer — logging + SQLite database"
```

---

### Task 3: Config System Enhancement — Square Monitor & News Config

**Files:**
- Create: `01_codebase/config/square.yaml`
- Create: `01_codebase/config/news.yaml`
- Modify: `01_codebase/vulpes_trader/config.py`

- [ ] **Step 1: Create square.yaml**

```yaml
square_heat:
  enabled: true
  poll_interval: 30
  max_tickers: 30
  heat_window: 3600
  signal_rules:
    heat_oi_bullish:
      confidence: 0.8
    heat_only_bullish:
      confidence: 0.6
```

- [ ] **Step 2: Create news.yaml**

```yaml
news_engine:
  enabled: false
  poll_interval: 60
  sources:
    - name: "crypto_news_api"
      url: ""
      api_key_env: "CRYPTO_NEWS_API_KEY"
    - name: "twitter_kol"
      enabled: false
  event_decay:
    regulation_positive: "4h"
    regulation_negative: "4h"
    hack_exploit: "6h"
    listing: "1h"
```

- [ ] **Step 3: Verify config loads correctly**

Run: `cd 01_codebase && python -c "from vulpes_trader.config import config; print('square:', config.get('square_heat','enabled')); print('news:', config.get('news_engine','enabled'))"`

Expected: `square: True` / `news: False`

- [ ] **Step 4: Commit**

```bash
git add 01_codebase/config/
git commit -m "feat(vulpes): config for square monitor + news engine"
```

---

## Phase 1 — Data Layer

### Task 4: WebSocket Manager — ccxt Pro Connection

**Files:**
- Create: `01_codebase/vulpes_trader/data/__init__.py`
- Create: `01_codebase/vulpes_trader/data/ws_manager.py`
- Create: `01_codebase/vulpes_trader/utils/__init__.py`
- Create: `01_codebase/vulpes_trader/utils/retry.py`

- [ ] **Step 1: Write test for retry utility**

Create `01_codebase/tests/test_retry.py`:
```python
import pytest
import asyncio
from vulpes_trader.utils.retry import async_retry


class MockExchanger:
    def __init__(self):
        self.attempts = 0

    async def unstable_call(self):
        self.attempts += 1
        if self.attempts < 3:
            raise ConnectionError("Temporary failure")
        return "success"


@pytest.mark.asyncio
async def test_async_retry_success():
    """测试指数退避重试最终成功"""
    obj = MockExchanger()
    result = await async_retry(obj.unstable_call, max_retries=3)
    assert result == "success"
    assert obj.attempts == 3
```

- [ ] **Step 2: Write retry.py**

```python
"""指数退避重试工具"""

import asyncio
import logging
from typing import Callable, Awaitable, TypeVar, Any

T = TypeVar("T")
logger = logging.getLogger("vulpes.retry")


async def async_retry(
    func: Callable[..., Awaitable[T]],
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exceptions: tuple = (ConnectionError, TimeoutError),
    *args,
    **kwargs,
) -> T:
    """
    异步指数退避重试

    Args:
        func: 异步函数
        max_retries: 最大重试次数
        base_delay: 初始延迟（秒）
        max_delay: 最大延迟（秒）
        exceptions: 捕获的异常类型
    """
    last_exception = None
    for attempt in range(max_retries + 1):
        try:
            return await func(*args, **kwargs)
        except exceptions as e:
            last_exception = e
            if attempt < max_retries:
                delay = min(base_delay * (2 ** attempt), max_delay)
                logger.warning(
                    "重试 %d/%d: %s, %.1f秒后重试",
                    attempt + 1, max_retries, str(e), delay,
                )
                await asyncio.sleep(delay)
            else:
                logger.error("重试耗尽 (%d次): %s", max_retries, str(e))
                raise
```

- [ ] **Step 3: Write ws_manager.py**

```python
"""WebSocket 连接管理器 — 通过 ccxt Pro 订阅实时行情"""

import asyncio
import logging
from typing import List, Callable, Awaitable, Optional
from ccxt.pro import binance as Binance
from vulpes_trader.config import config
from vulpes_trader.utils.retry import async_retry

logger = logging.getLogger("vulpes.ws")


class WSManager:
    """WebSocket 连接管理，支持自动重连"""

    def __init__(self, symbols: List[str], timeframes: List[str]):
        self.symbols = symbols
        self.timeframes = timeframes
        self.exchange: Optional[Binance] = None
        self._running = False
        self._ticker_handlers: List[Callable] = []
        self._ohlcv_handlers: List[Callable] = []

    async def connect(self):
        """建立连接（指数退避重连）"""
        self._running = True
        await async_retry(self._do_connect, max_retries=5)

    async def _do_connect(self):
        """实际连接逻辑"""
        exchange_config = config.exchange_config
        self.exchange = Binance({
            "apiKey": exchange_config["apiKey"],
            "secret": exchange_config["secret"],
            "options": exchange_config.get("options", {}),
        })
        if "urls" in exchange_config:
            self.exchange.urls = exchange_config["urls"]
        logger.info("WebSocket 连接成功: symbols=%s", self.symbols[:3])

    async def subscribe_tickers(self, handler: Callable[[dict], Awaitable[None]]):
        """订阅实时 Ticker"""
        self._ticker_handlers.append(handler)
        asyncio.create_task(self._ticker_loop())

    async def _ticker_loop(self):
        """Ticker 订阅循环（自动重连）"""
        while self._running:
            try:
                if not self.exchange:
                    await self.connect()
                for symbol in self.symbols:
                    ticker = await self.exchange.watch_ticker(symbol)
                    for handler in self._ticker_handlers:
                        await handler(ticker)
            except Exception as e:
                logger.error("Ticker 订阅中断: %s, 5秒后重连", e)
                await asyncio.sleep(5)

    async def subscribe_ohlcv(self, handler: Callable[[list], Awaitable[None]]):
        """订阅 K 线"""
        self._ohlcv_handlers.append(handler)
        asyncio.create_task(self._ohlcv_loop())

    async def _ohlcv_loop(self):
        """OHLCV 订阅循环"""
        while self._running:
            try:
                if not self.exchange:
                    await self.connect()
                for symbol in self.symbols:
                    for tf in self.timeframes:
                        ohlcv = await self.exchange.watch_ohlcv(symbol, tf)
                        for handler in self._ohlcv_handlers:
                            await handler({"symbol": symbol, "timeframe": tf, "data": ohlcv})
            except Exception as e:
                logger.error("OHLCV 订阅中断: %s, 5秒后重连", e)
                await asyncio.sleep(5)

    async def close(self):
        """安全关闭"""
        self._running = False
        if self.exchange:
            await self.exchange.close()
            logger.info("WebSocket 连接已关闭")
```

- [ ] **Step 4: Write test for WSManager initialization**

Create `01_codebase/tests/test_ws_manager.py`:
```python
import pytest
from vulpes_trader.data.ws_manager import WSManager


def test_ws_manager_init():
    """测试 WSManager 初始化"""
    mgr = WSManager(symbols=["BTC/USDT:USDT"], timeframes=["1m", "5m"])
    assert mgr.symbols == ["BTC/USDT:USDT"]
    assert mgr.timeframes == ["1m", "5m"]
    assert not mgr._running
```

- [ ] **Step 5: Run all tests**

Run: `cd 01_codebase && python -m pytest tests/ -v`
Expected: All tests pass

- [ ] **Step 6: Commit**

```bash
git add 01_codebase/vulpes_trader/data/ 01_codebase/vulpes_trader/utils/ 01_codebase/tests/
git commit -m "feat(vulpes): data layer — WS manager with retry logic"
```

---

### Task 5: K-Line Engine & Data Cache

**Files:**
- Create: `01_codebase/vulpes_trader/data/kline_engine.py`
- Create: `01_codebase/vulpes_trader/data/cache.py`

- [ ] **Step 1: Write test for K-line engine**

```python
import pytest
import pandas as pd
from datetime import datetime
from vulpes_trader.data.kline_engine import KlineEngine


def test_kline_update():
    """测试 K 线更新"""
    engine = KlineEngine(cache_size=100)
    ohlcv = [1700000000000, 50000.0, 51000.0, 49000.0, 50500.0, 100.0]
    engine.update("BTC/USDT", "5m", ohlcv)
    
    df = engine.get_klines("BTC/USDT", "5m")
    assert len(df) == 1
    assert df.iloc[-1]["close"] == 50500.0
```

- [ ] **Step 2: Write kline_engine.py**

```python
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

    def clean_old_data(self, max_age_hours: int = 24):
        """清理过期数据（手动触发）"""
        now = datetime.now().timestamp() * 1000
        cutoff = now - (max_age_hours * 3600 * 1000)
        for symbol in self._cache:
            for tf in self._cache[symbol]:
                df = self._cache[symbol][tf]
                self._cache[symbol][tf] = df[df["timestamp"] >= cutoff]
```

- [ ] **Step 3: Write cache.py (supplementary data cache)**

```python
"""辅助数据缓存 — OI、资金费率等"""

import time
from typing import Dict, Optional, Any
from datetime import datetime
import logging

logger = logging.getLogger("vulpes.cache")


class DataCache:
    """轻量级内存缓存，带 TTL 过期"""

    def __init__(self, default_ttl: int = 60):
        self.default_ttl = default_ttl
        self._data: Dict[str, Any] = {}
        self._expiry: Dict[str, float] = {}

    def set(self, key: str, value: Any, ttl: Optional[int] = None):
        """设置缓存"""
        self._data[key] = value
        self._expiry[key] = time.time() + (ttl or self.default_ttl)

    def get(self, key: str) -> Optional[Any]:
        """获取缓存，过期返回 None"""
        if key not in self._data:
            return None
        if time.time() > self._expiry.get(key, 0):
            del self._data[key]
            del self._expiry[key]
            return None
        return self._data[key]

    def get_or_set(self, key: str, factory, ttl: Optional[int] = None) -> Any:
        """获取或创建"""
        value = self.get(key)
        if value is None:
            value = factory()
            self.set(key, value, ttl)
        return value
```

- [ ] **Step 4: Run tests**

Run: `cd 01_codebase && python -m pytest tests/ -v`
Expected: All pass

- [ ] **Step 5: Commit**

```bash
git add 01_codebase/vulpes_trader/data/kline_engine.py 01_codebase/vulpes_trader/data/cache.py 01_codebase/tests/
git commit -m "feat(vulpes): kline engine + data cache"
```

---

### Task 6: OI & Funding Rate Collection (supplementary data)

**Files:**
- Create: `01_codebase/vulpes_trader/data/supplementary.py`

- [ ] **Step 1: Write test**

```python
import pytest
from vulpes_trader.data.supplementary import OIDataPoint, FundingRateDataPoint


def test_oi_datapoint():
    dp = OIDataPoint(symbol="BTC/USDT:USDT", oi=500000000, 
                     oi_change_pct=15.5, timestamp=1700000000)
    assert dp.symbol == "BTC/USDT:USDT"
    assert dp.oi_change_pct == 15.5
```

- [ ] **Step 2: Write supplementary.py**

```python
"""OI 与资金费率采集 — REST API 定时拉取"""

import asyncio
import logging
from typing import Callable, List, Optional
from dataclasses import dataclass
from ccxt import binance as BinanceRest
from vulpes_trader.config import config
from vulpes_trader.utils.retry import async_retry

logger = logging.getLogger("vulpes.supplementary")


@dataclass
class OIDataPoint:
    symbol: str
    oi: float
    oi_change_pct: float
    timestamp: int


@dataclass
class FundingRateDataPoint:
    symbol: str
    rate: float
    next_payment_time: int
    timestamp: int


class SupplementaryCollector:
    """辅助数据采集器 — OI + 资金费率"""

    def __init__(self, symbols: List[str]):
        self.symbols = symbols
        self.exchange: Optional[BinanceRest] = None
        self._handlers: List[Callable] = []

    async def start(self, oi_interval: int = 60, funding_interval: int = 3600):
        """启动定时采集"""
        asyncio.create_task(self._oi_loop(oi_interval))
        asyncio.create_task(self._funding_loop(funding_interval))

    async def _ensure_exchange(self):
        if not self.exchange:
            self.exchange = BinanceRest(config.exchange_config)

    async def _fetch_open_interest(self, symbol: str) -> Optional[OIDataPoint]:
        """获取单个币种 OI"""
        try:
            await self._ensure_exchange()
            result = await async_retry(
                self.exchange.fetch_open_interest, max_retries=2,
                symbol=symbol,
            )
            return OIDataPoint(
                symbol=symbol,
                oi=result.get("openInterest", 0),
                oi_change_pct=0.0,  # 需要历史数据计算变化率
                timestamp=result.get("timestamp", 0),
            )
        except Exception as e:
            logger.warning("获取 OI 失败 %s: %s", symbol, e)
            return None

    async def _fetch_funding_rate(self, symbol: str) -> Optional[FundingRateDataPoint]:
        """获取资金费率"""
        try:
            await self._ensure_exchange()
            result = await async_retry(
                self.exchange.fetch_funding_rate, max_retries=2,
                symbol=symbol,
            )
            return FundingRateDataPoint(
                symbol=symbol,
                rate=result.get("fundingRate", 0),
                next_payment_time=result.get("nextFundingTime", 0),
                timestamp=result.get("timestamp", 0),
            )
        except Exception as e:
            logger.warning("获取资金费率失败 %s: %s", symbol, e)
            return None

    async def _oi_loop(self, interval: int):
        """OI 定时采集"""
        while True:
            for symbol in self.symbols:
                data = await self._fetch_open_interest(symbol)
                if data:
                    for handler in self._handlers:
                        await handler(data)
            await asyncio.sleep(interval)

    async def _funding_loop(self, interval: int):
        """资金费率定时采集"""
        while True:
            for symbol in self.symbols:
                data = await self._fetch_funding_rate(symbol)
                if data:
                    for handler in self._handlers:
                        await handler(data)
            await asyncio.sleep(interval)

    def on_data(self, handler: Callable):
        """注册数据回调"""
        self._handlers.append(handler)
```

- [ ] **Step 3: Run tests**

Run: `cd 01_codebase && python -m pytest tests/ -v`
Expected: All pass

- [ ] **Step 4: Commit**

```bash
git add 01_codebase/vulpes_trader/data/supplementary.py 01_codebase/tests/
git commit -m "feat(vulpes): OI + funding rate collector"
```

---

## Phase 1b — Data Layer Extension (Square Monitor + News)

### Task 7: Binance Square Heat Monitor

**Files:**
- Create: `01_codebase/vulpes_trader/data/square_monitor.py`
- Create: `01_codebase/tests/test_square_monitor.py`

- [ ] **Step 1: Write test**

```python
import pytest
from vulpes_trader.data.square_monitor import TickerHeatRank


def test_heat_rank_creation():
    rank = TickerHeatRank(ticker="LAYER", mentions=94, sources=3, 
                          momentum="rising", oi_change="extreme")
    assert rank.ticker == "LAYER"
    assert rank.mentions == 94
    assert rank.momentum == "rising"
```

- [ ] **Step 2: Write square_monitor.py**

```python
"""币安广场热度监控 — 爬取广场热点 Ticker"""

import asyncio
import logging
from typing import List, Optional, Dict
from dataclasses import dataclass, field
from datetime import datetime
import aiohttp

logger = logging.getLogger("vulpes.square")


@dataclass
class TickerHeatRank:
    ticker: str
    mentions: int
    sources: int         # 信号源数（广场/帖子/社区）
    momentum: str        # 'rising' | 'stable' | 'falling'
    oi_change: str       # 'extreme' | 'strong' | 'moderate' | 'none'
    price_change_1h: float = 0.0


class SquareMonitor:
    """
    币安广场热度监控
    
    Phase A: 通过币安公开 API 获取
    Phase B+: 增加爬虫/WebSocket 实时流
    """

    BASE_URL = "https://www.binance.com/bapi/square/v1/public/square"

    def __init__(self, poll_interval: int = 30, max_tickers: int = 30):
        self.poll_interval = poll_interval
        self.max_tickers = max_tickers
        self._session: Optional[aiohttp.ClientSession] = None
        self._ticker_rank: List[TickerHeatRank] = []
        self._running = False
        self._handlers = []

    async def _ensure_session(self):
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()

    async def fetch_hot_topics(self) -> List[Dict]:
        """获取币安广场热门话题"""
        await self._ensure_session()
        try:
            # Phase A: 使用公开 API 端点
            async with self._session.get(
                f"{self.BASE_URL}/topic/list",
                params={"pageNo": 1, "pageSize": 50},
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("data", {}).get("topics", [])
                logger.warning("广场API返回状态码: %d", resp.status)
                return []
        except Exception as e:
            logger.warning("获取广场热点失败: %s", e)
            return []

    def extract_tickers(self, topics: List[Dict]) -> Dict[str, int]:
        """从话题中提取 Ticker 及提及次数"""
        ticker_count: Dict[str, int] = {}
        for topic in topics:
            title = topic.get("title", "")
            content = topic.get("content", "")
            text = f"{title} {content}"
            # 简单提取 $TICKER 格式
            words = text.split()
            for word in words:
                if word.startswith("$") and len(word) > 1:
                    ticker = word[1:].upper().strip(".,!?:;")
                    if ticker.isalpha() and len(ticker) <= 10:
                        ticker_count[ticker] = ticker_count.get(ticker, 0) + 1
        return ticker_count

    def compute_rankings(self, ticker_count: Dict[str, int]) -> List[TickerHeatRank]:
        """计算热度排名"""
        sorted_tickers = sorted(
            ticker_count.items(), key=lambda x: x[1], reverse=True
        )[:self.max_tickers]

        rankings = []
        for i, (ticker, count) in enumerate(sorted_tickers):
            momentum = "rising" if i < len(sorted_tickers) // 3 else "stable"
            rankings.append(TickerHeatRank(
                ticker=ticker,
                mentions=count,
                sources=1 if count < 50 else 2 if count < 100 else 3,
                momentum=momentum,
                oi_change="none",
            ))
        return rankings

    async def start(self):
        """启动热度监控循环"""
        self._running = True
        while self._running:
            try:
                topics = await self.fetch_hot_topics()
                if topics:
                    ticker_count = self.extract_tickers(topics)
                    self._ticker_rank = self.compute_rankings(ticker_count)
                    for handler in self._handlers:
                        await handler(self._ticker_rank)
                    logger.debug(
                        "广场热度更新: %d 个 Ticker", len(self._ticker_rank)
                    )
            except Exception as e:
                logger.error("热度监控异常: %s", e)
            await asyncio.sleep(self.poll_interval)

    def on_update(self, handler):
        """注册更新回调"""
        self._handlers.append(handler)

    async def close(self):
        self._running = False
        if self._session and not self._session.closed:
            await self._session.close()
```

- [ ] **Step 3: Run tests**

Run: `cd 01_codebase && python -m pytest tests/ -v`
Expected: All pass

- [ ] **Step 4: Commit**

```bash
git add 01_codebase/vulpes_trader/data/square_monitor.py 01_codebase/tests/
git commit -m "feat(vulpes): binance square heat monitor"
```

---

### Task 8: News Event Engine (skeleton)

**Files:**
- Create: `01_codebase/vulpes_trader/data/news_engine.py`
- Create: `01_codebase/tests/test_news_engine.py`

- [ ] **Step 1: Write news_engine.py (Phase A skeleton — keyword mapping)**

```python
"""新闻事件引擎 — 捕获加密新闻并映射到代币"""

import asyncio
import logging
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

logger = logging.getLogger("vulpes.news")


class EventImpact(Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"
    BROAD = "broad"  # 影响整个市场


class EventCategory(Enum):
    REGULATION = "regulation"
    PARTNERSHIP = "partnership"
    HACK = "hack"
    LISTING = "listing"
    MACRO = "macro"
    WHALE = "whale"
    FUNDAMENTAL = "fundamental"


@dataclass
class EventAnalysis:
    event_id: str
    text: str
    timestamp: int
    category: EventCategory
    impact: EventImpact
    confidence: float  # 0-1
    affected_tokens: Dict[str, float]  # {ticker: confidence}
    decay_hours: float = 2.0


class NewsEventEngine:
    """
    新闻事件捕获与分析引擎
    
    Phase A: 关键词匹配 + Ticker 映射
    Phase B+: NLP 语义理解 + 影响力评分
    """

    # 基础事件关键词映射
    EVENT_PATTERNS = {
        "listing": ["listing", "上线", "list", "上币"],
        "hack": ["hack", "exploit", "被盗", "攻击", "漏洞"],
        "partnership": ["partner", "合作", "integrate", "集成", "alliance"],
        "regulation_good": ["approve", "批准", "ETF", "合规", "license"],
        "regulation_bad": ["ban", "禁止", "crackdown", "监管打击", "SEC"],
        "whale": ["whale", "巨鲸", "large transfer", "大额转出"],
    }

    # Ticker 映射
    TICKER_ALIASES = {
        "bitcoin": "BTC", "btc": "BTC",
        "ethereum": "ETH", "eth": "ETH",
        "solana": "SOL", "sol": "SOL",
        "binance": "BNB", "bnb": "BNB",
        "ripple": "XRP", "xrp": "XRP",
        "cardano": "ADA", "ada": "ADA",
    }

    def __init__(self):
        self._recent_events: Dict[str, EventAnalysis] = {}
        self._handlers = []
        self._running = False

    def analyze_text(self, text: str, timestamp: Optional[int] = None) -> EventAnalysis:
        """
        分析文本事件

        Args:
            text: 事件文本
            timestamp: 事件时间戳（ms）

        Returns:
            EventAnalysis: 包含影响判断和受影响代币
        """
        ts = timestamp or int(datetime.utcnow().timestamp() * 1000)
        text_lower = text.lower()

        # 1. 判断事件类别
        category = EventCategory.FUNDAMENTAL
        impact = EventImpact.NEUTRAL
        for pattern_type, keywords in self.EVENT_PATTERNS.items():
            if any(kw in text_lower for kw in keywords):
                if pattern_type == "listing":
                    category, impact = EventCategory.LISTING, EventImpact.BULLISH
                elif pattern_type == "hack":
                    category, impact = EventCategory.HACK, EventImpact.BEARISH
                elif pattern_type == "partnership":
                    category, impact = EventCategory.PARTNERSHIP, EventImpact.BULLISH
                elif pattern_type == "regulation_good":
                    category, impact = EventCategory.REGULATION, EventImpact.BULLISH
                elif pattern_type == "regulation_bad":
                    category, impact = EventCategory.REGULATION, EventImpact.BEARISH
                elif pattern_type == "whale":
                    category, impact = EventCategory.WHALE, EventImpact.NEUTRAL
                break

        # 2. 提取映射代币
        tokens = self._extract_tokens(text, text_lower)

        # 3. 计算置信度
        confidence = 0.5
        if tokens:
            confidence = 0.7 if impact != EventImpact.NEUTRAL else 0.5

        event_id = f"evt_{ts}_{hash(text) % 10000}"

        return EventAnalysis(
            event_id=event_id,
            text=text[:500],
            timestamp=ts,
            category=category,
            impact=impact,
            confidence=confidence,
            affected_tokens=tokens,
            decay_hours=EventCategory.HACK == category and 6.0 or 2.0,
        )

    def _extract_tokens(self, text: str, text_lower: str) -> Dict[str, float]:
        """从文本中提取代币"""
        tokens = {}

        # 检查 $TICKER 格式
        for word in text.split():
            if word.startswith("$") and len(word) > 1:
                ticker = word[1:].upper().strip(".,!?:;")
                if ticker.isalpha() and len(ticker) <= 10:
                    tokens[ticker] = 0.8

        # 检查别名映射
        for alias, ticker in self.TICKER_ALIASES.items():
            if alias in text_lower and ticker not in tokens:
                tokens[ticker] = 0.6

        return tokens

    async def process_event(self, text: str):
        """处理新事件，推送信号"""
        analysis = self.analyze_text(text)
        self._recent_events[analysis.event_id] = analysis
        for handler in self._handlers:
            await handler(analysis)

    def on_event(self, handler):
        self._handlers.append(handler)
```

- [ ] **Step 2: Write test**

```python
import pytest
from vulpes_trader.data.news_engine import NewsEventEngine, EventImpact, EventCategory


def test_analyze_listing_event():
    engine = NewsEventEngine()
    result = engine.analyze_text("Binance will list $SOL today!")
    assert result.impact == EventImpact.BULLISH
    assert "SOL" in result.affected_tokens
    assert result.affected_tokens["SOL"] >= 0.5


def test_analyze_hack_event():
    engine = NewsEventEngine()
    result = engine.analyze_text("Security: $ETH protocol exploited, 10M stolen")
    assert result.impact == EventImpact.BEARISH
    assert result.category == EventCategory.HACK
    assert result.decay_hours == 6.0
```

- [ ] **Step 3: Run tests**

Run: `cd 01_codebase && python -m pytest tests/ -v`
Expected: All pass

- [ ] **Step 4: Commit**

```bash
git add 01_codebase/vulpes_trader/data/news_engine.py 01_codebase/tests/
git commit -m "feat(vulpes): news event engine skeleton"
```

---

## Plan Self-Review Checklist

- [x] **Spec coverage:** All Phase 0 & Phase 1 modules covered: scaffolding (T1), audit (T2), config (T3), WS Manager (T4), K-line engine (T5), OI/funding (T6), Square Monitor (T7), News Engine (T8)
- [x] **No placeholders:** Every step has concrete code
- [x] **Type consistency:** WSManager.connect → _do_connect, KlineEngine.update → get_klines, all method signatures match across tasks
- [x] **File existence:** All file paths exact and verifiable
