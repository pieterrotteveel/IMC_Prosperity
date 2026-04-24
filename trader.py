from datamodel import OrderDepth, TradingState, Order
from typing import List, Dict
import json

# ── Position limits ────────────────────────────────────────────────────────────
POS_LIMITS: Dict[str, int] = {
    "ASH_COATED_OSMIUM": 80,
    "INTARIAN_PEPPER_ROOT": 80,
}

# ── Linear drift parameters for INTARIAN_PEPPER_ROOT ──────────────────────────
DRIFT_SLOPE = 0.1          # XIREC per tick (1 tick = 100 timestamp units)
DRIFT_EMA_WINDOW = 200     # slow EMA to estimate daily start price


# ══════════════════════════════════════════════════════════════════════════════
# Base class
# ══════════════════════════════════════════════════════════════════════════════
class ProductTrader:
    """Shared utilities for all product strategies."""

    def __init__(self, symbol: str, state: TradingState, new_trader_data: dict):
        self.name = symbol
        self.state = state
        self.new_trader_data = new_trader_data

        self.position_limit = POS_LIMITS[symbol]
        self.initial_position = state.position.get(symbol, 0)

        # Normalise order book (sell_orders have negative quantities in the API)
        od: OrderDepth = state.order_depths.get(symbol, OrderDepth())
        self.mkt_buy_orders  = {p: abs(v) for p, v in sorted(od.buy_orders.items(),  reverse=True)}
        self.mkt_sell_orders = {p: abs(v) for p, v in sorted(od.sell_orders.items())}

        # Wall Mid = average of the deepest bid and deepest ask (most stable)
        self.bid_wall = min(self.mkt_buy_orders,  default=None)
        self.ask_wall = max(self.mkt_sell_orders, default=None)
        self.wall_mid = (self.bid_wall + self.ask_wall) / 2 if self.bid_wall and self.ask_wall else None
        self.best_bid = max(self.mkt_buy_orders,  default=None)
        self.best_ask = min(self.mkt_sell_orders, default=None)

        # Running capacity — decremented as orders are queued
        self.max_buy  = self.position_limit - self.initial_position
        self.max_sell = self.position_limit + self.initial_position

        self.orders: List[Order] = []
        self.last_data: dict = self._load_state()

    def _load_state(self) -> dict:
        try:
            return json.loads(self.state.traderData).get(self.name, {})
        except Exception:
            return {}

    def bid(self, price: float, volume: float):
        """Queue a BUY order, auto-clipped to remaining capacity."""
        v = min(abs(int(volume)), self.max_buy)
        if v > 0:
            self.orders.append(Order(self.name, int(price), v))
            self.max_buy -= v

    def ask(self, price: float, volume: float):
        """Queue a SELL order, auto-clipped to remaining capacity."""
        v = min(abs(int(volume)), self.max_sell)
        if v > 0:
            self.orders.append(Order(self.name, int(price), -v))
            self.max_sell -= v

    def ema(self, key: str, window: int, value: float) -> float:
        """Exponential moving average — reads from last_data, writes to new_trader_data."""
        alpha = 2 / (window + 1)
        old = self.last_data.get(key, value)   # first call: initialise to current value
        result = alpha * value + (1 - alpha) * old
        self.new_trader_data.setdefault(self.name, {})[key] = result
        return result

    def get_orders(self) -> dict:
        return {}


# ══════════════════════════════════════════════════════════════════════════════
# Strategy 1: Stable product — ASH_COATED_OSMIUM
# ══════════════════════════════════════════════════════════════════════════════
class StableProductTrader(ProductTrader):
    """
    Market making around a fixed fair value of 10,000 XIREC.

    Historical data (3 days, 30,000 rows):
      - Mean ~10,000, std ~5 (excluding missing rows)
      - Strong negative lag-1 autocorrelation (−0.495) → mean reverting
    """

    FAIR_VALUE = 10_000
    SKEW_THRESHOLD = 40  # if |position| exceeds this, post a flatten order at fair value

    def get_orders(self) -> dict:
        fv = self.FAIR_VALUE

        # ── PHASE 1: TAKING ─────────────────────────────────────────────────
        # Buy underpriced sell orders; sell overpriced buy orders immediately.
        for sp, sv in list(self.mkt_sell_orders.items()):
            if sp < fv:
                self.bid(sp, sv)
            elif sp == fv and self.initial_position < 0:
                self.bid(sp, min(sv, abs(self.initial_position)))  # flatten short at fair

        for bp, bv in list(self.mkt_buy_orders.items()):
            if bp > fv:
                self.ask(bp, bv)
            elif bp == fv and self.initial_position > 0:
                self.ask(bp, min(bv, self.initial_position))  # flatten long at fair

        # ── INVENTORY SKEW CONTROL ───────────────────────────────────────────
        # If position is too skewed, post a limit order at fair value to work
        # it down. We give up the spread on the excess to stay balanced.
        if self.initial_position > self.SKEW_THRESHOLD:
            excess = self.initial_position - self.SKEW_THRESHOLD
            self.ask(fv, excess)
        elif self.initial_position < -self.SKEW_THRESHOLD:
            excess = abs(self.initial_position) - self.SKEW_THRESHOLD
            self.bid(fv, excess)

        # ── PHASE 2: MAKING ─────────────────────────────────────────────────
        # Post passive quotes. Start from wall, then overbid / undercut the
        # best existing resting order to get time priority.
        if self.bid_wall is None or self.ask_wall is None:
            return {self.name: self.orders}

        bid_price = self.bid_wall + 1
        ask_price = self.ask_wall - 1

        # Overbid: beat the highest resting bid still below fair value
        for bp in self.mkt_buy_orders:
            if bp < fv:
                bv = self.mkt_buy_orders[bp]
                bid_price = max(bid_price, bp + 1 if bv > 1 else bp)
                break

        # Undercut: beat the lowest resting ask still above fair value
        for sp in self.mkt_sell_orders:
            if sp > fv:
                sv = self.mkt_sell_orders[sp]
                ask_price = min(ask_price, sp - 1 if sv > 1 else sp)
                break

        # Sanity: never cross the book
        bid_price = min(bid_price, fv - 1)
        ask_price = max(ask_price, fv + 1)

        self.bid(bid_price, self.max_buy)
        self.ask(ask_price, self.max_sell)

        return {self.name: self.orders}


# ══════════════════════════════════════════════════════════════════════════════
# Strategy 2: Linearly drifting product — INTARIAN_PEPPER_ROOT
# ══════════════════════════════════════════════════════════════════════════════
class LinearDriftTrader(ProductTrader):
    """
    Market making around a linearly drifting fair value.

    Historical fit (3 days, 30,000 rows):
      fair_value(t) = base_price + 0.1 * (timestamp / 100)

    The base_price is estimated via a slow EMA of the de-trended mid price so
    the algo self-calibrates at the start of each trading day without knowing
    the day number in advance.
    """

    def _observed_mid(self) -> float | None:
        """Best estimate of current mid price from the order book."""
        if self.best_bid and self.best_ask:
            return (self.best_bid + self.best_ask) / 2
        if self.wall_mid:
            return self.wall_mid
        return None

    def _fair_value(self) -> float | None:
        """Estimate fair value at the current timestamp."""
        mid = self._observed_mid()
        if mid is None:
            return None

        ts = self.state.timestamp
        tick = ts / 100

        # De-trend the observed mid to get the estimated start-of-day price
        detrended = mid - DRIFT_SLOPE * tick
        base_ema = self.ema("base_ema", DRIFT_EMA_WINDOW, detrended)

        return base_ema + DRIFT_SLOPE * tick

    def get_orders(self) -> dict:
        fv = self._fair_value()
        if fv is None:
            return {self.name: self.orders}

        # Never go short — only sell down to zero (trend is upward)
        self.max_sell = max(0, self.initial_position)

        # ── PHASE 1: TAKING ─────────────────────────────────────────────────
        for sp, sv in list(self.mkt_sell_orders.items()):
            if sp < fv:
                self.bid(sp, sv)

        for bp, bv in list(self.mkt_buy_orders.items()):
            if bp > fv:
                self.ask(bp, bv)
            elif bp == round(fv) and self.initial_position > 0:
                self.ask(bp, min(bv, self.initial_position))

        # ── PHASE 2: MAKING ─────────────────────────────────────────────────
        if self.bid_wall is None or self.ask_wall is None:
            return {self.name: self.orders}

        bid_price = self.bid_wall + 1
        ask_price = self.ask_wall - 1

        for bp in self.mkt_buy_orders:
            if bp < fv:
                bv = self.mkt_buy_orders[bp]
                bid_price = max(bid_price, bp + 1 if bv > 1 else bp)
                break

        for sp in self.mkt_sell_orders:
            if sp > fv:
                sv = self.mkt_sell_orders[sp]
                ask_price = min(ask_price, sp - 1 if sv > 1 else sp)
                break

        # Sanity: never cross the book
        bid_price = min(bid_price, int(fv))
        ask_price = max(ask_price, int(fv) + 1)

        self.bid(bid_price, self.max_buy)
        self.ask(ask_price, self.max_sell)

        return {self.name: self.orders}


# ══════════════════════════════════════════════════════════════════════════════
# Main entry point
# ══════════════════════════════════════════════════════════════════════════════
PRODUCT_TRADERS = {
    "ASH_COATED_OSMIUM":    StableProductTrader,
    "INTARIAN_PEPPER_ROOT": LinearDriftTrader,
}


class Trader:

    def bid(self):
        """Required for Round 2; safe to include in all rounds."""
        return 15

    def run(self, state: TradingState):
        new_trader_data: dict = {}
        result: dict = {}

        for symbol, trader_class in PRODUCT_TRADERS.items():
            if symbol not in state.order_depths:
                continue
            try:
                trader = trader_class(symbol, state, new_trader_data)
                result.update(trader.get_orders())
            except Exception as e:
                print(f"[ERROR] {symbol}: {e}")

        return result, 0, json.dumps(new_trader_data)
