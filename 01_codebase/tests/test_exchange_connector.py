"""测试交易所连接器 — ExchangeConnector"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

import ccxt

from vulpes_trader.execution.exchange_connector import ExchangeConnector


# ─── Fixtures ────────────────────────────────────────────────

@pytest.fixture
def mock_exchange():
    """创建 mock ccxt 交易所"""
    exchange = MagicMock()
    exchange.load_markets = AsyncMock(return_value={"BTC/USDT:USDT": {}, "ETH/USDT:USDT": {}})
    exchange.close = AsyncMock()

    exchange.create_market_order = AsyncMock(return_value={
        "id": "abc123",
        "symbol": "BTC/USDT:USDT",
        "side": "buy",
        "type": "market",
        "price": None,
        "average": 50010.0,
        "amount": 0.1,
        "filled": 0.1,
        "remaining": 0.0,
        "status": "closed",
        "timestamp": 1700000000000,
        "datetime": "2023-11-14T12:00:00.000Z",
    })

    exchange.create_limit_order = AsyncMock(return_value={
        "id": "limit123",
        "symbol": "BTC/USDT:USDT",
        "side": "buy",
        "type": "limit",
        "price": 49000.0,
        "amount": 0.1,
        "filled": 0.0,
        "remaining": 0.1,
        "status": "open",
        "timestamp": 1700000000000,
    })

    exchange.cancel_order = AsyncMock(return_value={
        "id": "abc123",
        "status": "canceled",
    })

    exchange.fetch_order = AsyncMock(return_value={
        "id": "abc123",
        "symbol": "BTC/USDT:USDT",
        "status": "closed",
        "filled": 0.1,
        "price": 50000.0,
    })

    exchange.fetch_open_orders = AsyncMock(return_value=[])
    exchange.fetch_positions = AsyncMock(return_value=[
        {
            "symbol": "BTC/USDT:USDT",
            "side": "long",
            "contracts": 0.1,
            "entryPrice": 50000.0,
            "markPrice": 51000.0,
            "unrealizedProfit": 10.0,
            "percentage": 2.0,
            "collateral": 500.0,
        }
    ])
    exchange.fetch_balance = AsyncMock(return_value={
        "total": {"USDT": 10000.0},
        "free": {"USDT": 8000.0},
        "used": {"USDT": 2000.0},
    })
    return exchange


@pytest.fixture
def connector(mock_exchange):
    """创建 ExchangeConnector 并注入 mock"""
    conn = ExchangeConnector(config_override={"apiKey": "test", "secret": "test"})
    conn._exchange = mock_exchange
    conn._connected = True
    conn._markets_loaded = True
    return conn


# ─── 初始化测试 ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_connect():
    """测试连接成功"""
    with patch("ccxt.async_support.binanceusdm") as mock_ccxt_class:
        mock_instance = MagicMock()
        mock_instance.load_markets = AsyncMock(return_value={"BTC/USDT:USDT": {}})
        mock_ccxt_class.return_value = mock_instance

        conn = ExchangeConnector(config_override={"apiKey": "test", "secret": "test"})
        await conn.connect()

        assert conn.is_connected is True
        assert conn._exchange is not None
        mock_instance.load_markets.assert_awaited_once()


@pytest.mark.asyncio
async def test_connect_failure():
    """测试连接失败"""
    with patch("ccxt.async_support.binanceusdm") as mock_ccxt_class:
        mock_instance = MagicMock()
        mock_instance.load_markets = AsyncMock(side_effect=ccxt.NetworkError("connection refused"))
        mock_ccxt_class.return_value = mock_instance

        conn = ExchangeConnector(config_override={"apiKey": "test", "secret": "test"})
        with pytest.raises(ccxt.NetworkError):
            await conn.connect()

        assert conn.is_connected is False


@pytest.mark.asyncio
async def test_close():
    """测试断开连接"""
    conn = ExchangeConnector(config_override={"apiKey": "test", "secret": "test"})
    conn._exchange = MagicMock()
    mock_close = AsyncMock()
    conn._exchange.close = mock_close
    conn._connected = True

    await conn.close()

    assert conn.is_connected is False
    assert conn._exchange is None
    mock_close.assert_awaited_once()


# ─── 订单操作测试 ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_market_order(connector, mock_exchange):
    """测试创建市价单成功"""
    result = await connector.create_market_order("BTC/USDT:USDT", "buy", 0.1)
    assert result["id"] == "abc123"
    assert result["status"] == "closed"
    mock_exchange.create_market_order.assert_awaited_once_with(
        "BTC/USDT:USDT", "buy", 0.1, {}
    )


@pytest.mark.asyncio
async def test_create_limit_order(connector, mock_exchange):
    """测试创建限价单"""
    result = await connector.create_limit_order("BTC/USDT:USDT", "buy", 0.1, 49000.0)
    assert result["id"] == "limit123"
    assert result["status"] == "open"
    mock_exchange.create_limit_order.assert_awaited_once_with(
        "BTC/USDT:USDT", "buy", 0.1, 49000.0, {}
    )


@pytest.mark.asyncio
async def test_cancel_order(connector, mock_exchange):
    """测试取消订单"""
    result = await connector.cancel_order("abc123", "BTC/USDT:USDT")
    assert result["status"] == "canceled"
    mock_exchange.cancel_order.assert_awaited_once_with("abc123", "BTC/USDT:USDT", {})


@pytest.mark.asyncio
async def test_fetch_order(connector, mock_exchange):
    """测试查询订单"""
    result = await connector.fetch_order("abc123", "BTC/USDT:USDT")
    assert result["status"] == "closed"
    mock_exchange.fetch_order.assert_awaited_once_with("abc123", "BTC/USDT:USDT", {})


# ─── 持仓与余额测试 ────────────────────────────────────────

@pytest.mark.asyncio
async def test_fetch_positions(connector, mock_exchange):
    """测试获取持仓"""
    positions = await connector.fetch_positions()
    assert len(positions) == 1
    assert positions[0]["symbol"] == "BTC/USDT:USDT"
    assert positions[0]["side"] == "long"
    mock_exchange.fetch_positions.assert_awaited_once_with(None, {})


@pytest.mark.asyncio
async def test_fetch_open_orders(connector, mock_exchange):
    """测试获取未成交订单"""
    orders = await connector.fetch_open_orders()
    assert orders == []
    mock_exchange.fetch_open_orders.assert_awaited_once_with(None, {})


@pytest.mark.asyncio
async def test_fetch_balance(connector, mock_exchange):
    """测试获取余额"""
    balance = await connector.fetch_balance()
    assert balance["total"]["USDT"] == 10000.0
    assert balance["free"]["USDT"] == 8000.0
    mock_exchange.fetch_balance.assert_awaited_once_with({})


# ─── 错误处理与重试测试 ────────────────────────────────────

@pytest.mark.asyncio
async def test_create_order_retry_on_network_error(connector, mock_exchange):
    """测试下单时网络错误的自动重试"""
    mock_exchange.create_market_order = AsyncMock(
        side_effect=[
            ccxt.NetworkError("timeout"),
            {"id": "abc456", "status": "closed", "filled": 0.1},
        ]
    )

    result = await connector.create_market_order("BTC/USDT:USDT", "buy", 0.1)
    assert result["id"] == "abc456"
    assert mock_exchange.create_market_order.await_count == 2


@pytest.mark.asyncio
async def test_create_order_retry_exhausted(connector, mock_exchange):
    """测试重试耗尽后抛出异常"""
    mock_exchange.create_market_order = AsyncMock(
        side_effect=ccxt.NetworkError("persistent timeout")
    )

    with pytest.raises(ccxt.NetworkError):
        await connector.create_market_order("BTC/USDT:USDT", "buy", 0.1)

    # async_retry: 首次尝试 + max_retries(3) 次重试 = 4 次
    assert mock_exchange.create_market_order.await_count >= 3


@pytest.mark.asyncio
async def test_auto_reconnect_on_disconnect(connector, mock_exchange):
    """测试断线后自动重连"""
    # async_retry 重试耗尽后，_call 应触发重连
    mock_exchange.create_market_order = AsyncMock(
        side_effect=ccxt.ExchangeNotAvailable("service unavailable")
    )

    # Mock reconnect
    connector.close = AsyncMock()
    connector.connect = AsyncMock()

    with pytest.raises(ccxt.ExchangeNotAvailable):
        await connector.create_market_order("BTC/USDT:USDT", "buy", 0.1)

    # 重试耗尽后应尝试重连
    connector.close.assert_awaited_once()
    connector.connect.assert_awaited_once()


@pytest.mark.asyncio
async def test_not_connected_error(connector):
    """测试未连接时的错误处理"""
    connector._connected = False
    connector._exchange = None

    with patch.object(connector, "connect", AsyncMock(side_effect=ConnectionError("not connected"))):
        with pytest.raises(ConnectionError):
            await connector.create_market_order("BTC/USDT:USDT", "buy", 0.1)


# ─── OrderManager 实盘集成测试 ────────────────────────────

@pytest.mark.asyncio
async def test_place_market_order_via_ordermanager(connector, mock_exchange):
    """测试通过 OrderManager 下达实盘市价单"""
    from vulpes_trader.execution.order_manager import OrderManager, OrderStatus

    om = OrderManager(exchange=connector)
    order = await om.place_market_order("BTC/USDT:USDT", "buy", 0.1)

    assert order is not None
    assert order.filled_quantity == 0.1
    # price 为 None, 所以用 average
    assert order.avg_fill_price == 50010.0
    assert order.status == OrderStatus.FILLED
    assert order.exchange_order_id == "abc123"


@pytest.mark.asyncio
async def test_place_limit_order_via_ordermanager(connector, mock_exchange):
    """测试通过 OrderManager 下达实盘限价单"""
    from vulpes_trader.execution.order_manager import OrderManager, OrderStatus

    om = OrderManager(exchange=connector)
    order = await om.place_limit_order("BTC/USDT:USDT", "buy", 0.1, 49000.0)

    assert order is not None
    assert order.status == OrderStatus.OPEN
    assert order.price == 49000.0


@pytest.mark.asyncio
async def test_sync_orders_via_ordermanager(connector, mock_exchange):
    """测试通过 OrderManager 同步订单"""
    from vulpes_trader.execution.order_manager import OrderManager, OrderStatus

    om = OrderManager(exchange=connector)

    # 先创建一个本地订单，设置 exchange 订单 ID
    order = om.create_order("BTC/USDT:USDT", "buy", "market", 0.1)
    order.exchange_order_id = "existing123"

    # mock 返回一个匹配的订单
    mock_exchange.fetch_open_orders = AsyncMock(return_value=[
        {
            "id": "existing123",
            "symbol": "BTC/USDT:USDT",
            "status": "closed",
            "filled": 0.1,
            "price": 50100.0,
            "average": 50100.0,
        }
    ])

    updated = await om.sync_orders()
    assert updated == 1
    assert order.status == OrderStatus.FILLED


@pytest.mark.asyncio
async def test_sync_positions_via_ordermanager(connector, mock_exchange):
    """测试通过 OrderManager 同步持仓"""
    from vulpes_trader.execution.order_manager import OrderManager

    om = OrderManager(exchange=connector)
    positions = await om.sync_positions()

    assert len(positions) == 1
    assert positions[0]["symbol"] == "BTC/USDT:USDT"


@pytest.mark.asyncio
async def test_order_manager_without_exchange():
    """测试 OrderManager 无 exchange 时向后兼容"""
    from vulpes_trader.execution.order_manager import OrderManager, OrderType, OrderStatus

    om = OrderManager()  # 不传 exchange
    order = om.create_order("BTC/USDT:USDT", "buy", OrderType.MARKET, 0.1)
    assert order.status == OrderStatus.PENDING

    # 调用 exchange 方法应报错
    with pytest.raises(RuntimeError, match="ExchangeConnector 未注入"):
        await om.place_market_order("BTC/USDT:USDT", "buy", 0.1)

    # 同步 cancel_order 仍可工作
    assert om.cancel_order(order.order_id) is True
    assert order.status == OrderStatus.CANCELLED


@pytest.mark.asyncio
async def test_cancel_remote_order_via_ordermanager(connector, mock_exchange):
    """测试通过 OrderManager 取消远程订单（远程 + 本地）"""
    from vulpes_trader.execution.order_manager import OrderManager, OrderStatus

    om = OrderManager(exchange=connector)
    order = om.create_order("BTC/USDT:USDT", "buy", "limit", 0.1, price=49000)
    order.status = OrderStatus.OPEN
    order.exchange_order_id = "exchange_order_001"

    result = await om.cancel_remote_order(order.order_id)
    assert result is True
    assert order.status == OrderStatus.CANCELLED
    # ExchangeConnector.cancel_order 接收 (order_id, symbol, params) 三个参数
    mock_exchange.cancel_order.assert_awaited_once_with("exchange_order_001", "BTC/USDT:USDT", {})


@pytest.mark.asyncio
async def test_cancel_order_fallback_no_exchange():
    """测试无 exchange 时 cancel_remote_order 只取消本地"""
    from vulpes_trader.execution.order_manager import OrderManager, OrderStatus

    om = OrderManager()  # 无 exchange
    order = om.create_order("BTC/USDT:USDT", "buy", "limit", 0.1, price=49000)
    # 使用同步方法
    assert om.cancel_order(order.order_id) is True
    assert order.status == OrderStatus.CANCELLED
