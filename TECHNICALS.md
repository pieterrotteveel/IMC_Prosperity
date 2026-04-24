# Prosperity Technical Strategies Reference
## Source: Frankfurt Hedgehogs — 2nd Place Globally, IMC Prosperity 3 (12,000+ teams)

This document extracts the **transferable principles, patterns, and code** from the top-2 finishing team. All product-specific names and round details have been removed — this is a playbook of ideas that apply to any Prosperity competition.

---

## 🏗️ Algorithm Architecture

### Core Design Pattern: One Class Per Product Type

Structure your algorithm with a **base class** containing shared utilities, and one **subclass per trading strategy type**. This keeps code modular, debuggable, and easy to extend each round.

```python
class ProductTrader:               # base — shared utilities
class StableProductTrader(ProductTrader):    # market making on fixed-price products
class DriftingProductTrader(ProductTrader):  # market making on slow random walk
class DirectionalTrader(ProductTrader):      # follow informed trader signals
class EtfTrader:                             # basket vs. constituent arbitrage
class OptionTrader:                          # IV scalping + mean reversion
class ConversionTrader(ProductTrader):       # location / conversion arbitrage
```

### ProductTrader Base Class

```python
from datamodel import OrderDepth, TradingState, Order
import json

class ProductTrader:

    def __init__(self, symbol, state, new_trader_data):
        self.name = symbol
        self.state = state
        self.new_trader_data = new_trader_data

        self.position_limit = POS_LIMITS[symbol]
        self.initial_position = state.position.get(symbol, 0)

        # Parse order book (sell_orders have negative quantities in the API — normalize them)
        od = state.order_depths.get(symbol, OrderDepth())
        self.mkt_buy_orders  = {p: abs(v) for p, v in sorted(od.buy_orders.items(),  reverse=True)}
        self.mkt_sell_orders = {p: abs(v) for p, v in sorted(od.sell_orders.items())}

        # Wall Mid = average of the deepest bid and deepest ask (more stable than raw mid)
        self.bid_wall  = min(self.mkt_buy_orders,  default=None)
        self.ask_wall  = max(self.mkt_sell_orders, default=None)
        self.wall_mid  = (self.bid_wall + self.ask_wall) / 2 if self.bid_wall and self.ask_wall else None
        self.best_bid  = max(self.mkt_buy_orders,  default=None)
        self.best_ask  = min(self.mkt_sell_orders, default=None)

        # Remaining position capacity — decremented as orders are created
        self.max_buy  = self.position_limit - self.initial_position
        self.max_sell = self.position_limit + self.initial_position

        self.orders = []
        self.last_data = self._load_state()

    def _load_state(self):
        try:
            return json.loads(self.state.traderData).get(self.name, {})
        except:
            return {}

    def bid(self, price, volume):
        """Place a BUY order, auto-clipped to position limit."""
        v = min(abs(int(volume)), self.max_buy)
        if v > 0:
            self.orders.append(Order(self.name, int(price), v))
            self.max_buy -= v

    def ask(self, price, volume):
        """Place a SELL order, auto-clipped to position limit."""
        v = min(abs(int(volume)), self.max_sell)
        if v > 0:
            self.orders.append(Order(self.name, int(price), -v))
            self.max_sell -= v

    def get_orders(self):
        return {}  # override in subclasses
```

### Main `run()` Dispatcher

```python
class Trader:
    def run(self, state: TradingState):
        new_trader_data = {}
        result = {}
        conversions = 0

        product_traders = {
            'PRODUCT_A': StableProductTrader,
            'PRODUCT_B': DriftingProductTrader,
            'PRODUCT_C': ConversionTrader,
        }

        for symbol, trader_class in product_traders.items():
            if symbol in state.order_depths:
                try:
                    trader = trader_class(symbol, state, new_trader_data)
                    result.update(trader.get_orders())
                except:
                    pass  # never let one broken product crash the whole algo

        return result, conversions, json.dumps(new_trader_data)
```

**Key:** Always wrap each product in `try/except`. A crash in one product's logic should never silence your entire submission.

---

## 💾 State Persistence Patterns

Lambda is stateless — use `traderData` for anything that must persist across iterations.

### EMA — preferred over storing full history
```python
def ema(key, window, value, last_data, new_data):
    old = last_data.get(key, value)  # default to current value on first call
    alpha = 2 / (window + 1)
    result = alpha * value + (1 - alpha) * old
    new_data[key] = result
    return result
```

### Capped rolling history list
```python
def update_history(key, value, max_len, last_data, new_data):
    hist = list(last_data.get(key, []))
    hist.append(value)
    if len(hist) > max_len:
        hist = hist[-max_len:]
    new_data[key] = hist
    return hist
```

**Warning:** `traderData` is capped at **50,000 characters**. Use EMAs instead of raw lists wherever possible.

---

## 📊 Strategy 1: Market Making

**When to use:** Product has a stable or slowly-drifting true price. Takers cross the fair value — profit from the spread between your quote and fair price.

### The simulation order flow (critical insight)
Each timestep:
1. Deep-liquidity maker bots post orders
2. Taker bots occasionally cross
3. **Your orders** are processed
4. More taker bots may arrive

There is no race. You get a full snapshot of the book every iteration. Focus entirely on **edge vs. fill probability** — not on speed.

### Two-Phase Market Making

```python
class StableProductTrader(ProductTrader):

    def get_orders(self):
        if self.wall_mid is None:
            return {}

        ### PHASE 1: TAKING — immediately capture any obvious mispricing
        for sp, sv in self.mkt_sell_orders.items():
            if sp < self.wall_mid:
                self.bid(sp, sv)                                        # priced below fair → buy
            elif sp == self.wall_mid and self.initial_position < 0:
                self.bid(sp, min(sv, abs(self.initial_position)))       # flatten short at fair

        for bp, bv in self.mkt_buy_orders.items():
            if bp > self.wall_mid:
                self.ask(bp, bv)                                        # priced above fair → sell
            elif bp == self.wall_mid and self.initial_position > 0:
                self.ask(bp, min(bv, self.initial_position))            # flatten long at fair

        ### PHASE 2: MAKING — post passive quotes with edge
        bid_price = int(self.bid_wall + 1)   # start from deep wall, improve inward
        ask_price = int(self.ask_wall - 1)

        # Overbid: beat the best existing bid still below wall_mid
        for bp, bv in self.mkt_buy_orders.items():
            if bp < self.wall_mid:
                bid_price = max(bid_price, bp + 1 if bv > 1 else bp)
                break

        # Undercut: beat the best existing ask still above wall_mid
        for sp, sv in self.mkt_sell_orders.items():
            if sp > self.wall_mid:
                ask_price = min(ask_price, sp - 1 if sv > 1 else sp)
                break

        self.bid(bid_price, self.max_buy)
        self.ask(ask_price, self.max_sell)

        return {self.name: self.orders}
```

### Key market-making principles
- **Wall Mid** is your fair price, not the raw mid. Deep-liquidity bot quotes are more stable.
- If inventory is skewed, flatten at fair value (zero edge) to free up risk capacity.
- Overbid/undercut existing liquidity by 1 tick to get time priority at a better price.
- There is no adverse selection from takers in simple products — just optimize edge/fill tradeoff.

---

## 📡 Strategy 2: Informed Trader Detection & Following

**When to use:** A bot consistently trades at extreme prices (daily high/low) in a consistent direction. Follow that bot.

### Detection Logic

In rounds where trader IDs are hidden, infer the informed trader by:
- Tracking the daily running min/max
- Flagging trades of a consistent lot size at extreme prices in the direction of that extreme
- Cross-referencing `market_trades`

When trader IDs become visible, switch to direct ID matching via `trade.buyer` / `trade.seller`.

```python
INFORMED_TRADER_ID = 'SomeKnownBotName'  # revealed later; infer anonymously early
LONG, NEUTRAL, SHORT = 1, 0, -1

def check_for_informed(symbol, state, last_data, new_data):
    """Returns (direction, bought_ts, sold_ts)."""
    bought_ts, sold_ts = last_data.get('informed', [None, None])

    all_trades = state.market_trades.get(symbol, []) + state.own_trades.get(symbol, [])
    for trade in all_trades:
        if trade.buyer == INFORMED_TRADER_ID:
            bought_ts = trade.timestamp
        if trade.seller == INFORMED_TRADER_ID:
            sold_ts = trade.timestamp

    new_data['informed'] = [bought_ts, sold_ts]

    if bought_ts is None and sold_ts is None:
        return NEUTRAL, None, None
    elif sold_ts is not None and (bought_ts is None or sold_ts > bought_ts):
        return SHORT, bought_ts, sold_ts
    elif bought_ts is not None and (sold_ts is None or bought_ts > sold_ts):
        return LONG, bought_ts, sold_ts
    return NEUTRAL, bought_ts, sold_ts
```

### Pure Directional Following (high-conviction)

```python
class DirectionalTrader(ProductTrader):

    def get_orders(self):
        direction, _, _ = check_for_informed(self.name, self.state, self.last_data, self.new_trader_data)

        target = {LONG: self.position_limit, SHORT: -self.position_limit}.get(direction, 0)
        delta = target - self.initial_position

        if delta > 0:
            self.bid(self.ask_wall, delta)   # buy aggressively
        elif delta < 0:
            self.ask(self.bid_wall, -delta)  # sell aggressively

        return {self.name: self.orders}
```

### Informed-Biased Market Making (lower-conviction)

Use the signal to **shift quoting thresholds** rather than going fully directional:

```python
SIGNAL_WINDOW = 500  # how long (in timestamps) a signal stays active

direction, bought_ts, sold_ts = check_for_informed(...)

if bought_ts and bought_ts + SIGNAL_WINDOW >= state.timestamp and self.initial_position < TARGET_LONG:
    self.bid(self.ask_wall, TARGET_LONG - self.initial_position)  # aggressive
else:
    self.bid(self.bid_wall + 1, self.max_buy)   # normal passive quote

if sold_ts and sold_ts + SIGNAL_WINDOW >= state.timestamp and self.initial_position > -TARGET_SHORT:
    self.ask(self.bid_wall, self.initial_position + TARGET_SHORT)
else:
    self.ask(self.ask_wall - 1, self.max_sell)
```

### Cross-Product Informed Signal

If the informed trader trades a correlated product (e.g., a basket constituent), use that signal when trading the basket:

```python
# If informed is long constituent → basket should follow → lower long entry threshold
adj = -INFORMED_ADJ if direction == LONG else (INFORMED_ADJ if direction == SHORT else 0)
effective_long_thr  = BASE_THRESHOLD + adj
effective_short_thr = BASE_THRESHOLD - adj
```

---

## 📦 Strategy 3: ETF / Basket Statistical Arbitrage

**When to use:** A basket product's price mean-reverts around the weighted sum of its constituent prices.

### Key structural insights
- Ask first: "How was the data generated?" Most likely constituent prices are independent, and a mean-reverting noise is added to produce the basket price.
- If true: **trade the basket, not the constituents.** The basket reverts to its synthetic value.
- Hedging with constituents **reduces EV** (extra transaction costs) unless constituents provably respond to the basket.
- Do NOT use z-scores or MA crossovers without theoretical justification.
- There is often a **persistent non-zero premium** (basket > synthetic) — subtract a running mean to debias.

### Spread Calculation with Premium Correction

```python
CONSTITUENT_FACTORS = [6, 3, 1]  # e.g., basket = 6×A + 3×B + 1×C

def calculate_spread(basket_mid, constituent_mids, factors, last_data, new_data):
    synthetic = sum(f * p for f, p in zip(factors, constituent_mids))
    raw_spread = basket_mid - synthetic
    running_premium = ema('basket_premium', window=60000, value=raw_spread, last_data=last_data, new_data=new_data)
    return raw_spread - running_premium   # debias by subtracting running mean
```

### Fixed-Threshold Entry/Exit

```python
THRESHOLD = 80   # tune via grid search — prioritize flat landscape over peak

spread = calculate_spread(...)

if spread > THRESHOLD and self.max_sell > 0:
    self.ask(self.bid_wall, self.max_sell)    # basket overpriced → sell

elif spread < -THRESHOLD and self.max_buy > 0:
    self.bid(self.ask_wall, self.max_buy)     # basket underpriced → buy

# Close when spread reverts to zero
elif spread > 0 and self.initial_position > 0:
    self.ask(self.bid_wall, self.initial_position)

elif spread < 0 and self.initial_position < 0:
    self.bid(self.ask_wall, -self.initial_position)
```

### Parameter Selection Philosophy
Grid search over threshold values. **Pick the flat, stable region** — not the single best point. The best backtest parameter is almost always overfit.

---

## 📈 Strategy 4: Options — IV Scalping with Black-Scholes

**When to use:** Call (or put) options on an underlying. Price them using a fitted volatility smile. Trade deviations between market price and theoretical fair value.

### Step 1: Volatility Smile — Parabola Fit

Fit a parabola to observed IVs vs. moneyness across strikes. Gives a "fair IV" for any strike at any time.

```python
import numpy as np

def get_smile_iv(S, K, TTE, smile_coeffs):
    """smile_coeffs = [a, b, c] for parabola. Fit offline with np.polyfit()."""
    m = np.log(K / S) / TTE**0.5
    return float(np.poly1d(smile_coeffs)(m))
```

Fit coefficients offline: `coeffs = np.polyfit(moneyness_values, iv_values, deg=2)`

### Step 2: Black-Scholes Pricing

```python
from statistics import NormalDist
import math
_N = NormalDist()

def bs_call(S, K, TTE, sigma, r=0):
    """European call: returns (price, delta, vega)."""
    if TTE <= 0 or sigma <= 0:
        return max(S - K, 0), 1.0 if S > K else 0.0, 0.0
    d1 = (math.log(S / K) + (r + 0.5 * sigma**2) * TTE) / (sigma * TTE**0.5)
    d2 = d1 - sigma * TTE**0.5
    price = S * _N.cdf(d1) - K * math.exp(-r * TTE) * _N.cdf(d2)
    delta = _N.cdf(d1)
    vega  = S * _N.pdf(d1) * TTE**0.5
    return price, delta, vega

def get_tte(total_days, current_day, timestamp, days_per_year=365):
    """Adapt this formula to your specific round/day structure."""
    days_elapsed = current_day + timestamp / (10_000 * 100)
    return (total_days - days_elapsed) / days_per_year
```

### Step 3: Track Theoretical Drift with EMA

```python
theo_price, delta, vega = bs_call(S, K, tte, get_smile_iv(S, K, tte, coeffs))
theo_diff = option_market_mid - theo_price

mean_theo_diff = ema(f'{option}_mean_diff', window=20,  value=theo_diff,              ...)
avg_abs_dev    = ema(f'{option}_avg_dev',  window=100, value=abs(theo_diff - mean_theo_diff), ...)
```

### Step 4: IV Scalping Signals

```python
THR_OPEN     = 0.5
THR_CLOSE    = 0.0
MIN_ACTIVITY = 0.7  # only scalp when avg deviation is large enough

deviation = theo_diff - mean_theo_diff

if avg_abs_dev >= MIN_ACTIVITY:

    if deviation >= THR_OPEN and self.max_sell > 0:
        self.ask(self.best_bid, self.max_sell)       # option overpriced → sell

    elif deviation <= -THR_OPEN and self.max_buy > 0:
        self.bid(self.best_ask, self.max_buy)        # option underpriced → buy

    if deviation >= THR_CLOSE and self.initial_position > 0:
        self.ask(self.best_bid, self.initial_position)   # close long

    elif deviation <= -THR_CLOSE and self.initial_position < 0:
        self.bid(self.best_ask, -self.initial_position)  # close short
```

### Step 5: Mean Reversion on Underlying (optional overlay)

If the underlying shows negative return autocorrelation (verify empirically before using):

```python
MR_THR    = 15
MR_WINDOW = 10

ema_price = ema('ema_underlying', MR_WINDOW, underlying_mid, ...)
deviation  = underlying_mid - ema_price

if deviation > MR_THR and self.max_sell > 0:
    self.ask(self.bid_wall + 1, self.max_sell)

elif deviation < -MR_THR and self.max_buy > 0:
    self.bid(self.ask_wall - 1, self.max_buy)
```

---

## 🌍 Strategy 5: Conversion / Location Arbitrage

**When to use:** A product can be converted between a local exchange and an external market at fixed bid/ask prices, with fees. Exploit the gap.

### Fee-Adjusted External Prices

```python
conv_obs = state.observations.conversionObservations[symbol]

ex_bid = conv_obs.bidPrice  - conv_obs.exportTariff - conv_obs.transportFees  # net if you export
ex_ask = conv_obs.askPrice  + conv_obs.importTariff + conv_obs.transportFees  # net cost to import

short_arb = local_sell_price - ex_ask   # profit: sell locally, import externally
long_arb  = ex_bid - local_buy_price    # profit: buy locally, export externally
```

### Hidden Taker Bot Pattern

In some rounds, a hidden taker bot fills sell offers priced around `int(external_bid + 0.5)` with ~60% probability — a significant price improvement over the visible best bid. Look for this in historical data: **fills at prices better than the visible best bid** is the signal.

```python
import math
local_sell_price = math.floor(conv_obs.bidPrice + 0.5)  # triggers hidden taker ~60% of fills
local_buy_price  = math.ceil(conv_obs.askPrice  - 0.5)
```

### Conversion Strategy

```python
CONVERSION_LIMIT = 10  # max units per timestep (check wiki for your product)

def get_orders(self):
    if short_arb > long_arb and short_arb > 0:
        remaining = CONVERSION_LIMIT
        for bp, bv in self.mkt_buy_orders.items():
            if (short_arb - (local_sell_price - bp)) > 0.58 * short_arb:
                v = min(remaining, bv)
                self.ask(bp, v)
                remaining -= v
            else:
                break
        if remaining > 0:
            self.ask(local_sell_price, remaining)   # ← triggers hidden taker

    elif long_arb > short_arb and long_arb > 0:
        remaining = CONVERSION_LIMIT
        for ap, av in self.mkt_sell_orders.items():
            if (long_arb - (ap - local_buy_price)) > 0.58 * long_arb:
                v = min(remaining, av)
                self.bid(ap, v)
                remaining -= v
            else:
                break
        if remaining > 0:
            self.bid(local_buy_price, remaining)

    return {self.name: self.orders}

def get_conversions(self):
    # Always flatten inventory via conversion each timestep
    return max(min(-self.initial_position, CONVERSION_LIMIT), -CONVERSION_LIMIT)
```

---

## 🔑 Meta-Principles

### 1. Wall Mid as Your Fair Price
Use `(deepest_bid + deepest_ask) / 2`. Deep-liquidity bot quotes are posted by informed market makers — thin overbids/undercuts distort the raw mid.

### 2. "Why Should This Work?" First
Before implementing any strategy, identify the structural reason it generates edge. If you can't explain it from first principles, any backtest outperformance is likely noise.

### 3. Robustness Over Performance
When tuning via grid search, pick values in **flat, stable landscape regions** — not the single best peak. Stable = robust. Peaks = overfit.

### 4. Don't Blindly Apply Techniques
- Z-scores only make sense if volatility genuinely varies over time (verify this).
- Moving average crossovers only make sense if you believe in momentum (verify this).
- Hedging a basket with constituents only makes sense if constituents respond to the basket (usually they don't — verify before doing).

### 5. Two-Stage Backtesting
- Bot-interaction-dependent strategies (fill probabilities, passive quoting): validate on the competition website.
- Signal/logic-based strategies: use an offline backtester across full historical data.
- Never optimize purely for the website test score — it runs a single day and overfits to randomness.

### 6. EMA Over Full History
Prefer EMA over storing full arrays in `traderData`. Drastically reduces state size and avoids the 50,000 char limit.

### 7. Early Informed Trader Detection
Look for informed trader behavior from round 1:
- Consistent lot sizes at price extremes
- Directionally consistent (buys at lows, sells at highs, every time)
- Cross-reference `market_trades`

Once identified, their signal can be used for the direct product AND for correlated products.

### 8. Premium Correction for Spreads
Any spread that theoretically should mean-revert to zero often has a persistent non-zero mean. Subtract a running EMA of the raw spread to debias before applying thresholds.

### 9. Dynamic Position Tracking
If you send orders across multiple logic branches, track remaining capacity dynamically — each order reduces `max_buy`/`max_sell`. The base class pattern above does this automatically.

### 10. Risk-Adjusted Strategy Mixing
When running multiple strategies on correlated products, quantify their covariance. When one strategy is uncertain (high variance), reduce its weight. A 50% hedge is often better than 0% or 100% when unsure.

---

## 🛠️ Reusable Utility Functions

```python
import math
import numpy as np
from statistics import NormalDist

_N = NormalDist()

# ── State helpers ─────────────────────────────────────────────────────────────

def ema(key, window, value, last_data, new_data):
    old = last_data.get(key, value)
    alpha = 2 / (window + 1)
    result = alpha * value + (1 - alpha) * old
    new_data[key] = result
    return result

def update_history(key, value, max_len, last_data, new_data):
    hist = list(last_data.get(key, []))
    hist.append(value)
    if len(hist) > max_len:
        hist = hist[-max_len:]
    new_data[key] = hist
    return hist

# ── Order book helpers ────────────────────────────────────────────────────────

def get_wall_mid(buy_orders, sell_orders):
    """Returns (bid_wall, wall_mid, ask_wall) — deepest levels as fair price proxy."""
    try:
        bid_wall = min(buy_orders)
        ask_wall = max(sell_orders)
        return bid_wall, (bid_wall + ask_wall) / 2, ask_wall
    except:
        return None, None, None

def parse_order_depth(state, symbol):
    """Returns (buy_orders, sell_orders) as {price: abs_volume}, sorted."""
    od = state.order_depths.get(symbol, None)
    if od is None:
        return {}, {}
    buys  = {p: abs(v) for p, v in sorted(od.buy_orders.items(),  reverse=True)}
    sells = {p: abs(v) for p, v in sorted(od.sell_orders.items())}
    return buys, sells

# ── Black-Scholes ──────────────────────────────────────────────────────────────

def bs_call(S, K, TTE, sigma, r=0):
    """European call: returns (price, delta, vega)."""
    if TTE <= 0 or sigma <= 0:
        return max(S - K, 0), 1.0 if S > K else 0.0, 0.0
    d1 = (math.log(S / K) + (r + 0.5 * sigma**2) * TTE) / (sigma * TTE**0.5)
    d2 = d1 - sigma * TTE**0.5
    price = S * _N.cdf(d1) - K * math.exp(-r * TTE) * _N.cdf(d2)
    delta = _N.cdf(d1)
    vega  = S * _N.pdf(d1) * TTE**0.5
    return price, delta, vega

def smile_iv(S, K, TTE, coeffs):
    """Get implied vol from a fitted parabolic smile. coeffs = [a, b, c]."""
    m = np.log(K / S) / TTE**0.5
    return float(np.poly1d(coeffs)(m))

# ── Autocorrelation check ─────────────────────────────────────────────────────

def lag1_autocorr(series):
    """Negative result → mean reversion signal. Positive → momentum."""
    if len(series) < 10:
        return 0.0
    returns = [series[i] - series[i-1] for i in range(1, len(series))]
    x, y = returns[:-1], returns[1:]
    mx, my = sum(x)/len(x), sum(y)/len(y)
    num   = sum((xi-mx)*(yi-my) for xi,yi in zip(x,y))
    denom = (sum((xi-mx)**2 for xi in x) * sum((yi-my)**2 for yi in y))**0.5
    return num / denom if denom else 0.0
```

---

## ⚠️ Common Pitfalls

| Pitfall | Why It Matters |
|---------|---------------|
| Optimizing purely for the website test score | Single day → overfits to randomness |
| Using z-scores without checking if volatility varies | Complexity with no theoretical basis |
| Hedging basket with constituents by default | Usually reduces EV — verify first |
| Storing full price history in `traderData` | Hits 50,000 char limit → use EMAs |
| Not wrapping each product in `try/except` | One crash silences your whole submission |
| Missing informed trader behavior early | Potentially huge profit left on the table |
| Panicking from Discord backtest screenshots | Often overfitted or fabricated — trust your own validation |

---

## 📋 Manual Trading Principles

### FX / Multi-step Arbitrage
- Build the full conversion matrix.
- Enumerate all possible N-step chains and pick the maximum-profit path.

### Auction / Field Selection (Game Theory)
- Solve the pure optimization first (best if you're the only player).
- Then model crowding effects: how much does overcrowding collapse the payout?
- Avoid fields where slight overcrowding leads to large payout collapses.
- Prefer fields in the **stable region of the payoff function**.

### Reserve Price / Clearing Price Auctions
- Solve the optimization analytically first.
- Layer in game theory: being below average is often penalized more than being above it → bias toward bidding higher than the pure optimum.
- When uncertain about the population average: lean in the direction that minimizes relative loss.

### News / Event-Based Trading
- Estimate both direction AND magnitude of expected moves.
- Reference analogous events from prior rounds or editions to calibrate magnitude.
- **Size down from optimal** — treat estimates as uncertain, hedge accordingly.
- Never go all-in on any single position regardless of confidence.
