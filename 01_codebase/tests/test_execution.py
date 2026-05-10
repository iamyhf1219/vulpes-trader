import pytest
from vulpes_trader.execution.order_manager import OrderManager, OrderType, OrderStatus, Order
from vulpes_trader.execution.position_manager import PositionManager
from vulpes_trader.execution.stop_loss import StopLossManager


# ─── Order Manager Tests ───

def test_create_order():
    om = OrderManager()
    order = om.create_order("BTC/USDT", "buy", OrderType.MARKET, 0.1)
    assert order.order_id is not None
    assert order.status == OrderStatus.PENDING
    assert order.quantity == 0.1


def test_get_order():
    om = OrderManager()
    order = om.create_order("BTC/USDT", "buy", OrderType.MARKET, 0.1)
    fetched = om.get_order(order.order_id)
    assert fetched is not None
    assert fetched.order_id == order.order_id


def test_update_order():
    om = OrderManager()
    order = om.create_order("BTC/USDT", "buy", OrderType.MARKET, 0.1)
    om.update_order(order.order_id, OrderStatus.FILLED, filled_qty=0.1, avg_price=50000)
    updated = om.get_order(order.order_id)
    assert updated.status == OrderStatus.FILLED
    assert updated.filled_quantity == 0.1
    assert updated.avg_fill_price == 50000


def test_cancel_order():
    om = OrderManager()
    order = om.create_order("BTC/USDT", "buy", OrderType.MARKET, 0.1)
    assert om.cancel_order(order.order_id) is True
    assert om.get_order(order.order_id).status == OrderStatus.CANCELLED


def test_get_active_orders():
    om = OrderManager()
    om.create_order("BTC/USDT", "buy", OrderType.MARKET, 0.1)
    om.create_order("ETH/USDT", "sell", OrderType.LIMIT, 1.0)
    assert len(om.get_active_orders()) == 2


# ─── Position Manager Tests ───

def test_open_position():
    pm = PositionManager()
    pos = pm.open_position("BTC/USDT", "long", 0.1, 50000, leverage=5)
    assert pos.symbol == "BTC/USDT"
    assert pos.side == "long"
    assert pm.has_position("BTC/USDT")


def test_close_position_long():
    pm = PositionManager()
    pm.open_position("BTC/USDT", "long", 1.0, 50000, leverage=10)
    closed = pm.close_position("BTC/USDT", 51000, "take_profit")
    assert closed is not None
    assert closed.pnl > 0
    assert closed.exit_reason == "take_profit"
    assert not pm.has_position("BTC/USDT")


def test_close_position_short():
    pm = PositionManager()
    pm.open_position("ETH/USDT", "short", 0.5, 3000, leverage=3)
    closed = pm.close_position("ETH/USDT", 2800, "stop_loss")
    assert closed is not None
    assert closed.pnl > 0  # 做空，价格下跌盈利
    assert closed.exit_reason == "stop_loss"


def test_position_count():
    pm = PositionManager()
    assert pm.position_count == 0
    pm.open_position("BTC/USDT", "long", 0.1, 50000)
    assert pm.position_count == 1


# ─── Stop Loss Manager Tests ───

def test_create_stop_loss_long():
    slm = StopLossManager()
    state = slm.create_stop_loss("BTC/USDT", "long", 50000)
    assert state.fixed_sl_price < 50000  # 止损价低于入场价
    assert state.trailing_activation_price > 50000  # 激活价高于入场价


def test_create_stop_loss_short():
    slm = StopLossManager()
    state = slm.create_stop_loss("ETH/USDT", "short", 3000)
    assert state.fixed_sl_price > 3000
    assert state.trailing_activation_price < 3000


def test_trailing_stop_activation():
    slm = StopLossManager()
    slm.create_stop_loss("BTC/USDT", "long", 50000, trailing_activation_pct=0.02)
    # 价格上涨 3%，应激活移动止损
    sl = slm.update_price("BTC/USDT", 51500)
    assert sl is not None
    # 移动止损价 < 当前价（有缓冲距离）
    assert sl < 51500
    assert sl > 50000


def test_check_stop_fixed():
    slm = StopLossManager()
    slm.create_stop_loss("BTC/USDT", "long", 50000, fixed_sl_pct=0.05)
    # 价格跌到止损以下
    reason = slm.check_stop_loss("BTC/USDT", 47000)
    assert reason == "fixed"


def test_trailing_stop_follows_price():
    slm = StopLossManager()
    slm.create_stop_loss("BTC/USDT", "long", 50000, trailing_activation_pct=0.02)
    slm.update_price("BTC/USDT", 51500)  # 激活
    sl1 = slm.update_price("BTC/USDT", 52000)  # 上涨
    sl2 = slm.update_price("BTC/USDT", 53000)  # 继续上涨
    assert sl2 >= sl1  # 移动止损跟随价格上涨


def test_remove_stop():
    slm = StopLossManager()
    slm.create_stop_loss("BTC/USDT", "long", 50000)
    slm.remove("BTC/USDT")
    assert slm.check_stop_loss("BTC/USDT", 40000) is None
