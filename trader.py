import math
import jsonpickle
from typing import Dict, List, Optional, Tuple
from datamodel import OrderDepth, TradingState, Order

# ─── Constants ───────────────────────────────────────────────────────────────

STRIKES: Dict[str, int] = {
    "VEV_4000": 4000, "VEV_4500": 4500, "VEV_5000": 5000,
    "VEV_5100": 5100, "VEV_5200": 5200, "VEV_5300": 5300,
    "VEV_5400": 5400, "VEV_5500": 5500, "VEV_6000": 6000,
    "VEV_6500": 6500,
}

POSITION_LIMITS: Dict[str, int] = {
    "HYDROGEL_PACK": 200,
    "VELVETFRUIT_EXTRACT": 200,
    **{s: 300 for s in STRIKES},
}

# Edge threshold: buy if market_ask < fair - threshold, sell if market_bid > fair + threshold
OPTION_THRESHOLDS: Dict[str, float] = {
    "VEV_4000": 10, "VEV_4500": 8,  "VEV_5000": 5,
    "VEV_5100": 5,  "VEV_5200": 5,  "VEV_5300": 4,
    "VEV_5400": 3,  "VEV_5500": 3,  "VEV_6000": 1,
    "VEV_6500": 1,
}

VEX_VOL: float = 0.263         # ~26.3% annualized implied vol, calibrated from VEV option prices
RISK_FREE: float = 0.0
TRADING_DAYS: int = 252
TTE_DAYS: int = 4              # Round 4; change to 3 for Round 5

HP_HALF_SPREAD: int = 5        # Quote half-spread for HYDROGEL_PACK (Mark 14 posts ~13, we go inside)
VEX_HALF_SPREAD: int = 2       # Quote half-spread for VELVETFRUIT_EXTRACT (Mark 14 posts ~5)
SIGNAL_TTL: int = 500          # Timestamp units before Mark 38/55 signal decays (~5 iterations)
MAX_QUOTE_SIZE: int = 20       # Max units per passive quote order
OPTION_TAKER_SIZE: int = 5     # Max units per aggressive option order


# ─── Black-Scholes ────────────────────────────────────────────────────────────

def _norm_cdf(x: float) -> float:
    return math.erfc(-x / math.sqrt(2)) / 2.0


def bs_call(S: float, K: float, T: float, sigma: float, r: float = 0.0) -> float:
    if T <= 1e-9 or S <= 0 or sigma <= 0:
        return max(S - K, 0.0)
    sqrt_T = math.sqrt(T)
    d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * sqrt_T)
    d2 = d1 - sigma * sqrt_T
    d1 = max(-10.0, min(10.0, d1))
    d2 = max(-10.0, min(10.0, d2))
    return S * _norm_cdf(d1) - K * math.exp(-r * T) * _norm_cdf(d2)


def bs_delta(S: float, K: float, T: float, sigma: float, r: float = 0.0) -> float:
    if T <= 1e-9 or S <= 0 or sigma <= 0:
        return 1.0 if S > K else 0.0
    sqrt_T = math.sqrt(T)
    d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * sqrt_T)
    return _norm_cdf(max(-10.0, min(10.0, d1)))


# ─── State ────────────────────────────────────────────────────────────────────

class StateStore:
    def __init__(self):
        self.mark38_hp_signal: int = 0     # +1 bullish, -1 bearish, 0 neutral
        self.mark38_hp_ts: int = -9999
        self.mark38_vex_signal: int = 0
        self.mark38_vex_ts: int = -9999
        self.mark55_vex_signal: int = 0
        self.mark55_vex_ts: int = -9999
        self.vex_mid_history: List[float] = []


# ─── Trader ───────────────────────────────────────────────────────────────────

class Trader:

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _load_store(self, traderData: str) -> StateStore:
        if traderData and traderData.strip():
            try:
                return jsonpickle.decode(traderData)
            except Exception:
                pass
        return StateStore()

    def _save_store(self, store: StateStore) -> str:
        store.vex_mid_history = store.vex_mid_history[-10:]
        data = jsonpickle.encode(store)
        if len(data) > 45000:
            store.vex_mid_history = store.vex_mid_history[-3:]
            data = jsonpickle.encode(store)
        return data

    def _get_mid(self, depth: Optional[OrderDepth]) -> Optional[float]:
        if depth is None:
            return None
        if depth.buy_orders and depth.sell_orders:
            best_bid = max(depth.buy_orders)
            best_ask = min(depth.sell_orders)
            return (best_bid + best_ask) / 2.0
        if depth.buy_orders:
            return float(max(depth.buy_orders))
        if depth.sell_orders:
            return float(min(depth.sell_orders))
        return None

    def _best_bid_ask(self, depth: Optional[OrderDepth]) -> Tuple[Optional[int], Optional[int]]:
        if depth is None:
            return None, None
        best_bid = max(depth.buy_orders) if depth.buy_orders else None
        best_ask = min(depth.sell_orders) if depth.sell_orders else None
        return best_bid, best_ask

    def _clamp_orders(self, orders: List[Order], pos: int, limit: int) -> List[Order]:
        net = 0
        safe = []
        for o in orders:
            projected = pos + net + o.quantity
            if -limit <= projected <= limit and o.quantity != 0:
                net += o.quantity
                safe.append(o)
        return safe

    def _quote_size(self, pos: int, limit: int, side: int) -> int:
        """side: +1 = buy side, -1 = sell side"""
        abs_pos = abs(pos)
        if abs_pos < 50:
            return MAX_QUOTE_SIZE
        if abs_pos < 100:
            # Reduce the heavy side
            if (side > 0 and pos > 0) or (side < 0 and pos < 0):
                return MAX_QUOTE_SIZE // 2
            return MAX_QUOTE_SIZE
        # Heavy — only quote if it reduces position
        if (side > 0 and pos < 0) or (side < 0 and pos > 0):
            return MAX_QUOTE_SIZE
        return 0  # don't add to heavy side

    # ── Counterparty scanning ─────────────────────────────────────────────────

    def _scan_counterparties(self, state: TradingState, store: StateStore) -> None:
        ts = state.timestamp

        # Decay stale signals
        if ts - store.mark38_hp_ts > SIGNAL_TTL:
            store.mark38_hp_signal = 0
        if ts - store.mark38_vex_ts > SIGNAL_TTL:
            store.mark38_vex_signal = 0
        if ts - store.mark55_vex_ts > SIGNAL_TTL:
            store.mark55_vex_signal = 0

        hp_buys_38 = hp_sells_38 = vex_buys_38 = vex_sells_38 = 0

        for symbol, trades in state.market_trades.items():
            for trade in trades:
                buyer = trade.buyer
                seller = trade.seller

                # Mark 38 signals (informed directional trader)
                if symbol == "HYDROGEL_PACK":
                    if buyer == "Mark 38":
                        hp_buys_38 += 1
                    elif seller == "Mark 38":
                        hp_sells_38 += 1
                elif symbol in ("VEV_4000", "VEV_4500", "VEV_5000"):
                    if buyer == "Mark 38":
                        vex_buys_38 += 1
                    elif seller == "Mark 38":
                        vex_sells_38 += 1

                # Mark 55 intermediary — buying VEX from Mark 14 signals incoming demand
                if symbol == "VELVETFRUIT_EXTRACT" and buyer == "Mark 55" and seller == "Mark 14":
                    store.mark55_vex_signal = 1
                    store.mark55_vex_ts = ts

        # Resolve HP signal for Mark 38
        if hp_buys_38 > 0 and hp_sells_38 == 0:
            store.mark38_hp_signal = 1
            store.mark38_hp_ts = ts
        elif hp_sells_38 > 0 and hp_buys_38 == 0:
            store.mark38_hp_signal = -1
            store.mark38_hp_ts = ts
        elif hp_buys_38 > 0 and hp_sells_38 > 0:
            store.mark38_hp_signal = 0  # conflict → neutral

        # Resolve VEX/option signal for Mark 38
        if vex_buys_38 > 0 and vex_sells_38 == 0:
            store.mark38_vex_signal = 1
            store.mark38_vex_ts = ts
        elif vex_sells_38 > 0 and vex_buys_38 == 0:
            store.mark38_vex_signal = -1
            store.mark38_vex_ts = ts
        elif vex_buys_38 > 0 and vex_sells_38 > 0:
            store.mark38_vex_signal = 0

    # ── HYDROGEL_PACK ─────────────────────────────────────────────────────────

    def _trade_hp(self, state: TradingState, store: StateStore) -> List[Order]:
        symbol = "HYDROGEL_PACK"
        limit = POSITION_LIMITS[symbol]
        depth = state.order_depths.get(symbol)
        pos = state.position.get(symbol, 0)
        orders: List[Order] = []

        mid = self._get_mid(depth)
        if mid is None:
            return []

        mid_int = round(mid)
        signal = store.mark38_hp_signal

        # Skew quotes based on Mark 38 directional signal
        if signal == 1:    # Mark 38 bought → bullish, lean long
            bid_price = mid_int - 3
            ask_price = mid_int + 7
        elif signal == -1:  # Mark 38 sold → bearish, lean short
            bid_price = mid_int - 7
            ask_price = mid_int + 3
        else:
            bid_price = mid_int - HP_HALF_SPREAD
            ask_price = mid_int + HP_HALF_SPREAD

        buy_qty = self._quote_size(pos, limit, +1)
        sell_qty = self._quote_size(pos, limit, -1)

        # Aggressive mean-reversion when very long/short
        if pos >= 150:
            best_bid = max(depth.buy_orders) if depth and depth.buy_orders else None
            if best_bid:
                orders.append(Order(symbol, best_bid, -min(30, pos + limit)))
            buy_qty = 0
        elif pos <= -150:
            best_ask = min(depth.sell_orders) if depth and depth.sell_orders else None
            if best_ask:
                orders.append(Order(symbol, best_ask, min(30, limit - pos)))
            sell_qty = 0

        if buy_qty > 0:
            orders.append(Order(symbol, bid_price, buy_qty))
        if sell_qty > 0:
            orders.append(Order(symbol, ask_price, -sell_qty))

        return self._clamp_orders(orders, pos, limit)

    # ── VELVETFRUIT_EXTRACT ───────────────────────────────────────────────────

    def _trade_vex(self, state: TradingState, store: StateStore) -> List[Order]:
        symbol = "VELVETFRUIT_EXTRACT"
        limit = POSITION_LIMITS[symbol]
        depth = state.order_depths.get(symbol)
        pos = state.position.get(symbol, 0)
        orders: List[Order] = []

        mid = self._get_mid(depth)
        if mid is None:
            return []

        mid_int = round(mid)

        # Mark 55 buying from Mark 14 → incoming demand, skew asks up
        if store.mark55_vex_signal == 1:
            bid_price = mid_int - 1
            ask_price_1 = mid_int + 2
            ask_price_2 = mid_int + 3
        else:
            bid_price = mid_int - VEX_HALF_SPREAD
            ask_price_1 = mid_int + 1  # aggressive ask (Mark 01/67 will lift)
            ask_price_2 = mid_int + VEX_HALF_SPREAD

        buy_qty = self._quote_size(pos, limit, +1)
        sell_qty = self._quote_size(pos, limit, -1)
        half_sell = max(sell_qty // 2, 1) if sell_qty > 0 else 0

        # Aggressive mean-reversion
        if pos >= 150:
            best_bid = max(depth.buy_orders) if depth and depth.buy_orders else None
            if best_bid:
                orders.append(Order(symbol, best_bid, -min(30, pos + limit)))
            buy_qty = 0
            sell_qty = 0
        elif pos <= -150:
            best_ask = min(depth.sell_orders) if depth and depth.sell_orders else None
            if best_ask:
                orders.append(Order(symbol, best_ask, min(30, limit - pos)))
            buy_qty = 0
            sell_qty = 0

        if buy_qty > 0:
            orders.append(Order(symbol, bid_price, buy_qty))
        if half_sell > 0:
            orders.append(Order(symbol, ask_price_1, -half_sell))
        if sell_qty - half_sell > 0:
            orders.append(Order(symbol, ask_price_2, -(sell_qty - half_sell)))

        return self._clamp_orders(orders, pos, limit)

    # ── VEV Options ───────────────────────────────────────────────────────────

    def _trade_option(
        self,
        state: TradingState,
        store: StateStore,
        symbol: str,
        strike: int,
        vex_mid: float,
    ) -> List[Order]:
        limit = POSITION_LIMITS[symbol]
        depth = state.order_depths.get(symbol)
        pos = state.position.get(symbol, 0)
        orders: List[Order] = []

        T = TTE_DAYS / TRADING_DAYS
        fair = bs_call(vex_mid, strike, T, VEX_VOL, RISK_FREE)
        threshold = OPTION_THRESHOLDS[symbol]

        best_bid, best_ask = self._best_bid_ask(depth)

        room_to_buy = limit - pos
        room_to_sell = limit + pos

        # Far OTM: BS value is essentially 0, sell any positive bid
        if symbol in ("VEV_6000", "VEV_6500"):
            if best_bid is not None and best_bid >= 1 and room_to_sell > 0:
                qty = min(OPTION_TAKER_SIZE, room_to_sell)
                orders.append(Order(symbol, best_bid, -qty))
            return self._clamp_orders(orders, pos, limit)

        # Aggressive taker: lift underpriced ask
        if best_ask is not None and best_ask < fair - threshold and room_to_buy > 0:
            qty = min(OPTION_TAKER_SIZE, room_to_buy)
            orders.append(Order(symbol, best_ask, qty))

        # Aggressive taker: hit overpriced bid
        if best_bid is not None and best_bid > fair + threshold and room_to_sell > 0:
            qty = min(OPTION_TAKER_SIZE, room_to_sell)
            orders.append(Order(symbol, best_bid, -qty))

        # Passive market-making: post inside fair value
        passive_bid = round(fair - threshold / 2)
        passive_ask = round(fair + threshold / 2)

        if passive_bid >= 1 and room_to_buy > OPTION_TAKER_SIZE:
            remaining_buy = min(OPTION_TAKER_SIZE, room_to_buy - OPTION_TAKER_SIZE)
            if remaining_buy > 0:
                orders.append(Order(symbol, passive_bid, remaining_buy))

        if room_to_sell > OPTION_TAKER_SIZE:
            remaining_sell = min(OPTION_TAKER_SIZE, room_to_sell - OPTION_TAKER_SIZE)
            if remaining_sell > 0:
                orders.append(Order(symbol, passive_ask, -remaining_sell))

        # VEV_4000 speculative: Mark 38 buying VEX options → lean long deep ITM
        if symbol == "VEV_4000" and store.mark38_vex_signal == 1 and room_to_buy > 0:
            spec_price = round(fair - threshold / 2)
            if spec_price >= 1:
                qty = min(OPTION_TAKER_SIZE, room_to_buy)
                orders.append(Order(symbol, spec_price, qty))

        return self._clamp_orders(orders, pos, limit)

    # ── Main entry point ──────────────────────────────────────────────────────

    def run(self, state: TradingState):
        result: Dict[str, List[Order]] = {}

        store = self._load_store(state.traderData)

        # Update counterparty signals
        self._scan_counterparties(state, store)

        # VEX mid price (needed for option pricing)
        vex_depth = state.order_depths.get("VELVETFRUIT_EXTRACT")
        vex_mid = self._get_mid(vex_depth)
        if vex_mid is None:
            vex_mid = store.vex_mid_history[-1] if store.vex_mid_history else 5245.0
        store.vex_mid_history.append(vex_mid)

        # HYDROGEL_PACK
        hp_orders = self._trade_hp(state, store)
        if hp_orders:
            result["HYDROGEL_PACK"] = hp_orders

        # VELVETFRUIT_EXTRACT
        vex_orders = self._trade_vex(state, store)
        if vex_orders:
            result["VELVETFRUIT_EXTRACT"] = vex_orders

        # VEV Options
        for symbol, strike in STRIKES.items():
            if symbol not in state.order_depths:
                continue
            option_orders = self._trade_option(state, store, symbol, strike, vex_mid)
            if option_orders:
                result[symbol] = option_orders

        traderData = self._save_store(store)
        return result, 0, traderData
