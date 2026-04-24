# Prosperity 4 — Competition Context for Claude

> Source: https://imc-prosperity.notion.site/prosperity-4-wiki
> Last scraped: April 14, 2026

---

## 🪐 What is Prosperity 4?

Prosperity 4 is IMC's global online algorithmic trading challenge for university students. It is a simulation game developed by IMC traders, quant researchers, and software engineers. The goal is to earn as many **XIRECs** (the in-game currency) as possible by writing a Python trading algorithm and making manual trades.

- **Duration:** 16 days total — two active 6-day phases with a 4-day intermission.
- **Tutorial Round:** Available immediately after signup until April 14, 2026 (12:00 CEST).
- **Round 1 starts:** April 14, 2026 at 12:00 CEST.
- **Winner:** Team with the most profit at the end of Round 5 wins, announced within 2 weeks.

---

## ⏰ Round Schedule (CEST = UTC+2)

| Round        | Start                              | Close                              | Notes |
|--------------|------------------------------------|------------------------------------|-------|
| Round 1      | Tue 14 Apr 2026 12:00 CEST         | Fri 17 Apr 2026 12:00 CEST         | May have short delay transitioning from Tutorial |
| Round 2      | Fri 17 Apr 2026 12:00 CEST         | Mon 20 Apr 2026 12:00 CEST         | Includes 3h calculation mode for Round 1 scores |
| Intermission | Mon 20 Apr 2026 12:00 CEST         | Fri 24 Apr 2026 12:00 CEST         | Includes 3h calculation mode for Round 2 scores |
| Round 3      | Fri 24 Apr 2026 12:00 CEST         | Sun 26 Apr 2026 12:00 CEST         | |
| Round 4      | Sun 26 Apr 2026 12:00 CEST         | Tue 28 Apr 2026 12:00 CEST         | Includes 3h calculation mode for Round 3 scores |
| Round 5      | Tue 28 Apr 2026 12:00 CEST         | Thu 30 Apr 2026 12:00 CEST         | Includes 3h calculation mode for Round 4 scores |

- ~3 hours between rounds for score calculation. Email + Discord notifications sent when next round opens.
- **Submission deadline:** The last successfully processed ("active") submission before the timer runs out is used.

---

## 🕹️ Game Mechanics Overview

### Rounds
- 5 rounds total. Rounds 1 & 2 last 72 hours each. Rounds 3, 4, 5 last 48 hours each.
- At end of each round: submit Python algorithm + manual trades.
- Algorithms run **10,000 iterations** in the final simulation (1,000 during local testing).
- Algorithms from different teams do NOT interact with each other — only bots.
- Previous rounds remain viewable but cannot be changed after closing.

### Algorithmic Trading
- Submit a Python `.py` file via the dashboard ("Challenge Details" → "Upload Algorithm").
- Drag and drop into the XIREN capsule.
- Only the **active** submission is processed. You can upload as many times as you like.
- Debug logs (including print output) are provided after test runs.

### Manual Trading
- Separate from algorithmic — does NOT affect algo PnL.
- Submit directly in the Manual Challenge Overview window.
- Last submitted trade is processed.
- Manual trading is **inactive** during the Tutorial Round.

### Key Dashboard Elements
- **Mission Control**: submission hub for algo and manual challenges.
- **A.R.I.A. Uplinks**: per-round briefing videos with essential information.
- **Leaderboard**: Overall / Algorithmic / Manual / Country rankings.
- **Crew Honors**: Badges earned for achievements.
- **On-Board Advisor**: Selected during Tutorial Round, locked at Round 1 start. 3 options with different styles but same info.
- **Outpost View**: Shows team PnL and rank, grows as you earn XIRECs.

---

## 💻 Writing an Algorithm in Python

### The Trader Class Structure

Your submission must be a Python file containing a `Trader` class with a `run()` method. For **Round 2 only**, it must also define a `bid()` method (safe to include in all rounds — it's ignored otherwise).

```python
from datamodel import OrderDepth, UserId, TradingState, Order
from typing import List
import string

class Trader:
    def bid(self):
        return 15  # Only used in Round 2

    def run(self, state: TradingState):
        result = {}

        for product in state.order_depths:
            order_depth: OrderDepth = state.order_depths[product]
            orders: List[Order] = []
            acceptable_price = 10  # Calculate this based on your strategy

            if len(order_depth.sell_orders) != 0:
                best_ask, best_ask_amount = list(order_depth.sell_orders.items())[0]
                if int(best_ask) < acceptable_price:
                    orders.append(Order(product, best_ask, -best_ask_amount))

            if len(order_depth.buy_orders) != 0:
                best_bid, best_bid_amount = list(order_depth.buy_orders.items())[0]
                if int(best_bid) > acceptable_price:
                    orders.append(Order(product, best_bid, -best_bid_amount))

            result[product] = orders

        traderData = "SAMPLE"  # Persisted state (max 50,000 chars, use jsonpickle)
        conversions = 1        # Conversion request (0 or None if not needed)
        return result, conversions, traderData
```

### Return Values from `run()`
- `result`: `Dict[str, List[Order]]` — orders per product
- `conversions`: `int` — conversion request count (or 0/None)
- `traderData`: `str` — persisted state string (max 50,000 chars)

### TradingState Class

```python
class TradingState(object):
    traderData: str               # State string from previous iteration
    timestamp: int                # Current simulation timestamp
    listings: Dict[Symbol, Listing]
    order_depths: Dict[Symbol, OrderDepth]   # Bot orders you can trade against
    own_trades: Dict[Symbol, List[Trade]]    # Your trades since last state
    market_trades: Dict[Symbol, List[Trade]] # Other participants' trades
    position: Dict[Product, Position]        # Your current position per product
    observations: Observation                # Market observations (see below)
```

### OrderDepth Class

```python
class OrderDepth:
    buy_orders: Dict[int, int]   # {price: total_quantity} — positive quantities
    sell_orders: Dict[int, int]  # {price: total_quantity} — NEGATIVE quantities!
```

**Example:** `sell_orders = {12: -3, 11: -2}` → 3 units available at 12, 2 at 11.

### Order Class

```python
class Order:
    symbol: str    # Product name
    price: int     # Max buy price OR min sell price
    quantity: int  # Positive = BUY, Negative = SELL
```

### Trade Class

```python
class Trade:
    symbol: str
    price: int
    quantity: int
    buyer: str    # "SUBMISSION" if you bought, else ""
    seller: str   # "SUBMISSION" if you sold, else ""
    timestamp: int
```

### Observation Class

```python
class ConversionObservation:
    bidPrice: float
    askPrice: float
    transportFees: float
    exportTariff: float
    importTariff: float
    sunlight: float
    humidity: float

class Observation:
    plainValueObservations: Dict[Product, int]
    conversionObservations: Dict[Product, ConversionObservation]
```

### Position Limits
- Position limits are **per product**, enforced by the exchange.
- If aggregated buy (sell) orders would exceed the long (short) limit, **ALL orders are rejected**.
- Example: limit=30, position=-5 → max buy quantity = 30-(-5) = 35.

### Persistent State (traderData)
- Lambda is stateless — class/global variables do NOT persist between calls.
- Use `traderData` string to pass state across iterations.
- Serialize with `jsonpickle`: `jsonpickle.encode(my_dict)` / `jsonpickle.decode(state.traderData)`
- **Max 50,000 characters** — content beyond this is truncated.

### Conversions
- To convert positions, return the quantity as `conversions`.
- Requirements: you must hold the position (long or short), request ≤ held quantity.
- Conversion incurs transportation fees + import/export tariffs.
- `conversions = 0` or `None` if not using.

### Technical Constraints
- `run()` must complete within **900ms** (average expected ≤ 100ms).
- Only supported libraries (see below) can be imported.

### Supported Libraries (Python 3.12)
- `pandas`
- `numpy`
- `statistics`
- `math`
- `typing`
- `jsonpickle`
- All standard Python 3.12 libraries

---

## 📦 datamodel.py (Full Reference)

```python
import json
from typing import Dict, List
from json import JSONEncoder
import jsonpickle

Time = int
Symbol = str
Product = str
Position = int
UserId = str
ObservationValue = int

class Listing:
    def __init__(self, symbol, product, denomination): ...

class ConversionObservation:
    def __init__(self, bidPrice, askPrice, transportFees,
                 exportTariff, importTariff, sunlight, humidity): ...

class Observation:
    def __init__(self, plainValueObservations, conversionObservations): ...

class Order:
    def __init__(self, symbol: Symbol, price: int, quantity: int): ...

class OrderDepth:
    buy_orders: Dict[int, int] = {}
    sell_orders: Dict[int, int] = {}

class Trade:
    def __init__(self, symbol, price, quantity,
                 buyer=None, seller=None, timestamp=0): ...

class TradingState(object):
    def __init__(self, traderData, timestamp, listings,
                 order_depths, own_trades, market_trades,
                 position, observations): ...
    def toJSON(self): ...

class ProsperityEncoder(JSONEncoder):
    def default(self, o): return o.__dict__
```

---

## 0️⃣ Tutorial Round — "Simulator Practice"

**Setting:** En route to Intara (a distant, resource-rich planet).

**Objective:** Write your first Python algorithm, upload it to the simulator, get familiar with the GUI.

**Products available:**
| Product    | Position Limit |
|------------|---------------|
| EMERALDS   | 80            |
| TOMATOES   | 80            |

- EMERALDS: stable value (good for market-making practice)
- TOMATOES: fluctuating value
- Manual trading: **inactive** in Tutorial Round
- Unlimited test submissions with near-instant feedback
- 1,000 iterations during testing

---

## 🔒 Round 1 — "Trading groundwork"

**Setting:** You have landed on Intara. Established a Trade Outpost. Goal: earn 200,000 XIRECs net profit before the beginning of trading day 3.

**Duration:** 72 hours (Tue Apr 14 12:00 → Fri Apr 17 12:00 CEST)

### Algorithmic Challenge: "First Intarian Goods"

| Product               | Position Limit | Notes |
|-----------------------|---------------|-------|
| INTARIAN_PEPPER_ROOT  | 80            | Steady value, like EMERALDS |
| ASH_COATED_OSMIUM     | 80            | More volatile; may follow a hidden pattern |

### Manual Challenge: "An Intarian Welcome"

Products: **DRYLAND_FLAX** and **EMBER_MUSHROOM** (auction format)

**Auction rules:**
- You submit **a single limit order** (price + quantity) per product.
- You submit **last** — no other bids/asks arrive after you.
- Exchange selects a clearing price that:
  1. Maximizes total traded volume
  2. Breaks ties by choosing the **higher** price
- All bids ≥ clearing price and asks ≤ clearing price execute at the clearing price.
- Priority: price → time. Since you're last, you're last in line at any price level you join.

**Guaranteed buyback after auction (no continuous trading):**
| Product        | Buyback Price | Fee            |
|----------------|--------------|----------------|
| DRYLAND_FLAX   | 30 per unit  | No fee         |
| EMBER_MUSHROOM | 20 per unit  | 0.10 per unit  |

**Strategy hint:** Since you know the buyback prices, you can calculate your profit per unit at any clearing price. Bid just high enough to clear, but consider that you are last in the queue at the price level you choose.

---

## 🌐 Round 2 — (Intermission before Round 3)

*(Round 2 details not yet added — see Round 1 above for reference structure.)*

---

## 🚀 Round 3 — "Gloves Off"

**Setting:** Planet Solvenar — a prosperous, highly developed planet known for technological innovation, a robust economy, and thriving cultural sectors.

**Duration:** 48 hours (Fri 24 Apr 2026 12:00 → Sun 26 Apr 2026 12:00 CEST)

**Special note:** This round marks the start of **GOAT** (Great Orbital Ascension Trials). **All teams begin from zero PnL and the leaderboard is fully reset.**

---

### Algorithmic Challenge: "Options Require Decisions"

There are 2 asset classes:

| Product                      | Type     | Position Limit | Notes |
|------------------------------|----------|---------------|-------|
| `HYDROGEL_PACK`              | Delta-1  | 200           | Similar to previous rounds |
| `VELVETFRUIT_EXTRACT`        | Delta-1  | 200           | Underlying for the vouchers |
| `VELVETFRUIT_EXTRACT_VOUCHER`| Options  | 300 each      | 10 vouchers with different strike prices |

#### Vouchers (VEV = Velvetfruit Extract Voucher)

The 10 vouchers, labeled by strike price:

`VEV_4000`, `VEV_4500`, `VEV_5000`, `VEV_5100`, `VEV_5200`, `VEV_5300`, `VEV_5400`, `VEV_5500`, `VEV_6000`, `VEV_6500`

- Each voucher gives the **right to buy** Velvetfruit Extract at its strike price.
- All products are traded **independently**, even though voucher prices relate to the underlying.
- **7-day expiry** starting from Round 1 (1 round = 1 day):
  - TTE = 7d in Round 1, 6d in Round 2, **5d in Round 3**, 4d in Round 4, 3d in Round 5

**Historical TTE reference for `VEV_5000` (example):**
- TTE = 8d in historical day 0 (tutorial round)
- TTE = 7d in historical day 1 (Round 1)
- TTE = 6d in historical day 2 (Round 2)

#### Historical Data

CSV format for prices: `day;timestamp;product;bid_price_1;bid_volume_1;...;ask_price_1;ask_volume_1;...;mid_price;profit_and_loss`

CSV format for trades: `timestamp;buyer;seller;symbol;currency;price;quantity`

Available files:
- `prices_round_3_day_0.csv`, `prices_round_3_day_1.csv`, `prices_round_3_day_2.csv`
- `trades_round_3_day_0.csv`, `trades_round_3_day_1.csv`, `trades_round_3_day_2.csv`

---

### Manual Challenge: Ornamental Bio-Pods

The **Celestial Gardeners' Guild** ("Guardeners") offers a rare opportunity to buy **Ornamental Bio-Pods**.

- Submit **two offers** to trade with as many Guardeners as aligns with your strategy.
- Acquired Bio-Pods are **automatically converted to profit** before the next trading round begins.

---

## 📈 Trading Glossary

| Term | Definition |
|------|-----------|
| **Bid / Buy order** | Order to buy. "Best bid" = highest active buy price |
| **Ask / Offer / Sell order** | Order to sell. "Best ask" = lowest active sell price |
| **Limit order** | Buy/sell at specified price or better |
| **Market order** | Buy/sell immediately at best available price |
| **Order book** | Collection of all outstanding buy/sell orders |
| **Price-time priority** | Most attractive price matched first; ties broken by order age |
| **Position** | How much of a product you hold (positive = long, negative = short) |
| **Market making** | Simultaneously quoting buy and sell prices to profit from the spread |
| **Spread** | Difference between best ask and best bid |

**Order matching on Prosperity's exchange:**
- BUY order executes immediately against SELL orders with price ≤ buy price (at the SELL price).
- SELL order executes immediately against BUY orders with price ≥ sell price (at the BUY price).
- Remaining unmatched quantity becomes a resting order visible to bots.
- Bots may trade against resting orders; if none do, the order is **cancelled at end of iteration**.
- No latency advantage for bots — your orders arrive instantaneously.

---

## ☑️ Key Rules

- Sign up deadline: **April 14, 2026 at 12:00 CEST** (when Round 1 starts).
- Team changes allowed until end of **Round 2**.
- Top 25 teams must prove university enrollment + be ≥18 years old.
- Top 10 from a previous Prosperity edition are removed from rankings.
- Top 5 teams + Manual Trading Winner must do a verification call.
- Prize eligibility: EMEA, North America, South America, India, Australia, Hong Kong only.
- **Disqualification grounds:** IMC employment, multiple team membership, exploiting bugs, plagiarism of another team's code.
- Code of conduct applies on Discord — be respectful, no harassment.
- Contact: prosperity@imc.com

---

## ❓ Key FAQ Points

- Manual challenge PnL is **independent** of algorithmic PnL.
- A file is only counted as submitted if it was marked **"active"** in the UI.
- ~3 hours between rounds for score calculation.
- All teams trade independently — no interaction between players' algorithms.
- `traderData` persists your state; class/global variables do NOT.
- On-Board Advisor: 3 options, same info in different styles. Locked at Round 1 start.

---

## 🏗️ Local Testing Setup

To test your algorithm locally using the same data format as the simulation:

```python
from datamodel import Listing, OrderDepth, Trade, TradingState

timestamp = 1000
listings = {
    "PRODUCT1": Listing(symbol="PRODUCT1", product="PRODUCT1", denomination="XIRECS"),
}
order_depths = {
    "PRODUCT1": OrderDepth(
        buy_orders={10: 7, 9: 5},
        sell_orders={11: -4, 12: -8}
    ),
}
own_trades = {"PRODUCT1": []}
market_trades = {"PRODUCT1": []}
position = {"PRODUCT1": 3}
observations = {}
traderData = ""

state = TradingState(traderData, timestamp, listings, order_depths,
                     own_trades, market_trades, position, observations)

# Run your trader
from trader import Trader
trader = Trader()
result, conversions, traderData = trader.run(state)
print(result, conversions, traderData)
```

- Simulation runs **1,000 iterations** during local/upload testing.
- Final scoring uses **10,000 iterations** on the actual competition day data.

---

## 🔗 Useful Links

- Competition platform: https://prosperity.imc.com/
- Wiki: https://imc-prosperity.notion.site/prosperity-4-wiki
- Discord: (join via the platform for community Q&A)
- IMC careers: https://www.imc.com
- Python for Beginners (IMC): https://www.youtube.com/playlist?list=PLrk7E_hqakTRHL02V-hxK2lDdblW12Apq
- Real Python OOP tutorial: https://realpython.com/python3-object-oriented-programming
