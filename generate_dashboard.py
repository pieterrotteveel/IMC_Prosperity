"""
Generates round4_dashboard.html — a self-contained interactive trade dashboard.
Run: python3 generate_dashboard.py
Then open: round4_dashboard.html in a browser.
"""

import pandas as pd
import json
import os

# ── Load data ──────────────────────────────────────────────────────────────────

base = os.path.dirname(os.path.abspath(__file__))
dfs = []
for day in [1, 2, 3]:
    path = os.path.join(base, "historical_data", "round_4", f"trades_round_4_day_{day}.csv")
    df = pd.read_csv(path, sep=";")
    df["day"] = day
    dfs.append(df)

df = pd.concat(dfs, ignore_index=True)
df = df.drop(columns=["currency"])
df["price"] = df["price"].round(2)

# Serialize to JSON for embedding
records = df.to_dict(orient="records")
data_json = json.dumps(records)

products = sorted(df["symbol"].unique().tolist())
traders = sorted(set(df["buyer"].unique().tolist() + df["seller"].unique().tolist()))

# Trader colour palette
TRADER_COLORS = {
    "Mark 01": "#4e79a7",
    "Mark 14": "#f28e2b",
    "Mark 22": "#e15759",
    "Mark 38": "#76b7b2",
    "Mark 49": "#59a14f",
    "Mark 55": "#edc948",
    "Mark 67": "#b07aa1",
}
colors_json = json.dumps(TRADER_COLORS)

PRODUCT_GROUPS = {
    "HYDROGEL_PACK": "#2196F3",
    "VELVETFRUIT_EXTRACT": "#4CAF50",
    "VEV_4000": "#9C27B0", "VEV_4500": "#9C27B0",
    "VEV_5000": "#E91E63", "VEV_5100": "#E91E63",
    "VEV_5200": "#FF5722", "VEV_5300": "#FF5722",
    "VEV_5400": "#FF9800", "VEV_5500": "#FF9800",
    "VEV_6000": "#795548", "VEV_6500": "#795548",
}
prod_colors_json = json.dumps(PRODUCT_GROUPS)

# ── HTML template ──────────────────────────────────────────────────────────────

html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<title>Round 4 Trade Dashboard</title>
<script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
<style>
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: "Inter", "Segoe UI", sans-serif; background: #0f1117; color: #e0e0e0; display: flex; height: 100vh; overflow: hidden; }}

  /* ── Sidebar ── */
  #sidebar {{ width: 260px; min-width: 220px; background: #1a1d27; border-right: 1px solid #2a2d3e; display: flex; flex-direction: column; padding: 16px; gap: 16px; overflow-y: auto; }}
  #sidebar h1 {{ font-size: 15px; font-weight: 700; color: #a78bfa; letter-spacing: .04em; }}
  .section-label {{ font-size: 11px; font-weight: 600; color: #6b7280; text-transform: uppercase; letter-spacing: .08em; margin-bottom: 6px; }}
  .filter-group {{ display: flex; flex-direction: column; gap: 4px; }}
  .chip-row {{ display: flex; flex-wrap: wrap; gap: 4px; }}
  .chip {{ padding: 3px 10px; border-radius: 999px; font-size: 11px; cursor: pointer; border: 1px solid transparent; transition: all .15s; user-select: none; }}
  .chip.active {{ border-color: currentColor; opacity: 1; }}
  .chip.inactive {{ opacity: .35; border-color: transparent; }}
  select, input[type=range] {{ width: 100%; background: #252836; border: 1px solid #2a2d3e; border-radius: 6px; color: #e0e0e0; padding: 6px 8px; font-size: 12px; }}
  select {{ cursor: pointer; }}
  .range-labels {{ display: flex; justify-content: space-between; font-size: 10px; color: #6b7280; margin-top: 2px; }}
  .stat-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 6px; }}
  .stat-card {{ background: #252836; border-radius: 8px; padding: 8px 10px; }}
  .stat-card .val {{ font-size: 18px; font-weight: 700; color: #a78bfa; }}
  .stat-card .lbl {{ font-size: 10px; color: #6b7280; margin-top: 2px; }}
  .divider {{ height: 1px; background: #2a2d3e; }}

  /* ── Main ── */
  #main {{ flex: 1; display: flex; flex-direction: column; overflow: hidden; }}
  #tabs {{ display: flex; background: #1a1d27; border-bottom: 1px solid #2a2d3e; padding: 0 16px; gap: 4px; }}
  .tab {{ padding: 10px 16px; font-size: 13px; cursor: pointer; border-bottom: 2px solid transparent; color: #6b7280; transition: all .15s; }}
  .tab.active {{ color: #a78bfa; border-bottom-color: #a78bfa; }}
  #panels {{ flex: 1; overflow: hidden; display: flex; flex-direction: column; }}
  .panel {{ display: none; flex: 1; overflow: hidden; flex-direction: column; }}
  .panel.active {{ display: flex; }}
  .chart-container {{ flex: 1; min-height: 0; }}

  /* ── Table ── */
  #table-panel {{ flex: 1; overflow: auto; padding: 12px; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 12px; }}
  thead th {{ background: #1a1d27; position: sticky; top: 0; padding: 8px 10px; text-align: left; color: #6b7280; font-weight: 600; font-size: 11px; text-transform: uppercase; letter-spacing: .06em; border-bottom: 1px solid #2a2d3e; z-index: 1; }}
  tbody tr {{ border-bottom: 1px solid #1e2132; transition: background .1s; }}
  tbody tr:hover {{ background: #1e2132; }}
  tbody td {{ padding: 6px 10px; }}
  .badge {{ display: inline-block; padding: 2px 7px; border-radius: 999px; font-size: 10px; font-weight: 600; }}
  .badge.buy {{ background: rgba(34,197,94,.15); color: #22c55e; }}
  .badge.sell {{ background: rgba(239,68,68,.15); color: #ef4444; }}
  .trader-dot {{ display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 5px; vertical-align: middle; }}
  #table-info {{ padding: 8px 12px; font-size: 11px; color: #6b7280; background: #1a1d27; border-top: 1px solid #2a2d3e; }}
</style>
</head>
<body>

<div id="sidebar">
  <h1>⚗️ Round 4 Trades</h1>

  <div class="filter-group">
    <div class="section-label">Day</div>
    <div class="chip-row" id="day-chips">
      <span class="chip active" data-day="1" style="background:#2a2d3e;color:#a78bfa">Day 1</span>
      <span class="chip active" data-day="2" style="background:#2a2d3e;color:#a78bfa">Day 2</span>
      <span class="chip active" data-day="3" style="background:#2a2d3e;color:#a78bfa">Day 3</span>
    </div>
  </div>

  <div class="divider"></div>

  <div class="filter-group">
    <div class="section-label">Product</div>
    <select id="product-select">
      <option value="ALL">All products</option>
    </select>
  </div>

  <div class="divider"></div>

  <div class="filter-group">
    <div class="section-label">Trader</div>
    <div class="chip-row" id="trader-chips"></div>
  </div>

  <div class="divider"></div>

  <div class="filter-group">
    <div class="section-label">Side</div>
    <div class="chip-row" id="side-chips">
      <span class="chip active" data-side="buy" style="color:#22c55e;background:rgba(34,197,94,.1)">Buy</span>
      <span class="chip active" data-side="sell" style="color:#ef4444;background:rgba(239,68,68,.1)">Sell</span>
    </div>
  </div>

  <div class="divider"></div>

  <div class="section-label">Summary</div>
  <div class="stat-grid">
    <div class="stat-card"><div class="val" id="stat-trades">—</div><div class="lbl">Trades</div></div>
    <div class="stat-card"><div class="val" id="stat-volume">—</div><div class="lbl">Volume</div></div>
    <div class="stat-card"><div class="val" id="stat-products">—</div><div class="lbl">Products</div></div>
    <div class="stat-card"><div class="val" id="stat-traders">—</div><div class="lbl">Traders</div></div>
  </div>
</div>

<div id="main">
  <div id="tabs">
    <div class="tab active" data-tab="price">Price Timeline</div>
    <div class="tab" data-tab="flow">Trade Flow</div>
    <div class="tab" data-tab="volume">Volume by Trader</div>
    <div class="tab" data-tab="heatmap">Trader × Product</div>
    <div class="tab" data-tab="table">Trade Table</div>
  </div>

  <div id="panels">
    <div class="panel active" id="panel-price">
      <div class="chart-container" id="chart-price"></div>
    </div>
    <div class="panel" id="panel-flow">
      <div class="chart-container" id="chart-flow"></div>
    </div>
    <div class="panel" id="panel-volume">
      <div class="chart-container" id="chart-volume"></div>
    </div>
    <div class="panel" id="panel-heatmap">
      <div class="chart-container" id="chart-heatmap"></div>
    </div>
    <div class="panel" id="panel-table" style="overflow:hidden;flex-direction:column;">
      <div id="table-panel"><table><thead id="thead"></thead><tbody id="tbody"></tbody></table></div>
      <div id="table-info"></div>
    </div>
  </div>
</div>

<script>
const RAW = {data_json};
const TRADER_COLORS = {colors_json};
const PROD_COLORS = {prod_colors_json};

const PRODUCTS = {json.dumps(products)};
const TRADERS = {json.dumps(traders)};

// ── State ────────────────────────────────────────────────────────────────────
const state = {{
  days: new Set([1, 2, 3]),
  product: "ALL",
  traders: new Set(TRADERS),
  sides: new Set(["buy", "sell"]),
  activeTab: "price",
}};

// ── Init UI ───────────────────────────────────────────────────────────────────
(function initUI() {{
  // Product select
  const sel = document.getElementById("product-select");
  PRODUCTS.forEach(p => {{
    const opt = document.createElement("option");
    opt.value = p; opt.textContent = p;
    sel.appendChild(opt);
  }});
  sel.addEventListener("change", e => {{ state.product = e.target.value; refresh(); }});

  // Trader chips
  const tc = document.getElementById("trader-chips");
  TRADERS.forEach(t => {{
    const chip = document.createElement("span");
    chip.className = "chip active";
    chip.dataset.trader = t;
    chip.style.background = hexToRgba(TRADER_COLORS[t] || "#888", 0.15);
    chip.style.color = TRADER_COLORS[t] || "#888";
    chip.textContent = t;
    chip.addEventListener("click", () => {{
      if (state.traders.has(t)) state.traders.delete(t);
      else state.traders.add(t);
      updateChips("trader-chips", "trader", state.traders);
      refresh();
    }});
    tc.appendChild(chip);
  }});

  // Day chips
  document.getElementById("day-chips").querySelectorAll(".chip").forEach(chip => {{
    chip.addEventListener("click", () => {{
      const d = parseInt(chip.dataset.day);
      if (state.days.has(d)) state.days.delete(d);
      else state.days.add(d);
      updateChips("day-chips", "day", state.days, v => parseInt(v));
      refresh();
    }});
  }});

  // Side chips
  document.getElementById("side-chips").querySelectorAll(".chip").forEach(chip => {{
    chip.addEventListener("click", () => {{
      const s = chip.dataset.side;
      if (state.sides.has(s)) state.sides.delete(s);
      else state.sides.add(s);
      updateChips("side-chips", "side", state.sides);
      refresh();
    }});
  }});

  // Tabs
  document.querySelectorAll(".tab").forEach(tab => {{
    tab.addEventListener("click", () => {{
      state.activeTab = tab.dataset.tab;
      document.querySelectorAll(".tab").forEach(t => t.classList.toggle("active", t === tab));
      document.querySelectorAll(".panel").forEach(p => p.classList.remove("active"));
      document.getElementById("panel-" + state.activeTab).classList.add("active");
      renderActiveChart(getFiltered());
    }});
  }});
}})();

function updateChips(containerId, attr, activeSet, parse = v => v) {{
  document.getElementById(containerId).querySelectorAll(".chip").forEach(chip => {{
    const val = parse(chip.dataset[attr]);
    chip.classList.toggle("active", activeSet.has(val));
    chip.classList.toggle("inactive", !activeSet.has(val));
  }});
}}

function hexToRgba(hex, alpha) {{
  const r = parseInt(hex.slice(1,3),16), g = parseInt(hex.slice(3,5),16), b = parseInt(hex.slice(5,7),16);
  return `rgba(${{r}},${{g}},${{b}},${{alpha}})`;
}}

// ── Filter ────────────────────────────────────────────────────────────────────
function getFiltered() {{
  return RAW.filter(r => {{
    if (!state.days.has(r.day)) return false;
    if (state.product !== "ALL" && r.symbol !== state.product) return false;
    const buyerOk = state.traders.has(r.buyer) && state.sides.has("buy");
    const sellerOk = state.traders.has(r.seller) && state.sides.has("sell");
    return buyerOk || sellerOk;
  }});
}}

// Each raw trade row = one transaction. Expand to individual side rows for side-aware charts.
function expandSides(data) {{
  const rows = [];
  data.forEach(r => {{
    if (state.traders.has(r.buyer) && state.sides.has("buy"))
      rows.push({{ ...r, trader: r.buyer, side: "buy" }});
    if (state.traders.has(r.seller) && state.sides.has("sell"))
      rows.push({{ ...r, trader: r.seller, side: "sell" }});
  }});
  return rows;
}}

// ── Refresh ───────────────────────────────────────────────────────────────────
function refresh() {{
  const data = getFiltered();
  updateStats(data);
  renderActiveChart(data);
}}

function updateStats(data) {{
  const vol = data.reduce((s, r) => s + r.quantity, 0);
  const products = new Set(data.map(r => r.symbol));
  const traders = new Set([...data.map(r => r.buyer), ...data.map(r => r.seller)]);
  document.getElementById("stat-trades").textContent = data.length.toLocaleString();
  document.getElementById("stat-volume").textContent = vol.toLocaleString();
  document.getElementById("stat-products").textContent = products.size;
  document.getElementById("stat-traders").textContent = traders.size;
}}

function renderActiveChart(data) {{
  const tab = state.activeTab;
  if (tab === "price")   renderPrice(data);
  else if (tab === "flow")    renderFlow(data);
  else if (tab === "volume")  renderVolume(data);
  else if (tab === "heatmap") renderHeatmap(data);
  else if (tab === "table")   renderTable(data);
}}

// ── Chart helpers ─────────────────────────────────────────────────────────────
const layout = (extra = {{}}) => ({{
  paper_bgcolor: "#0f1117",
  plot_bgcolor: "#0f1117",
  font: {{ color: "#9ca3af", family: "Inter, Segoe UI, sans-serif", size: 11 }},
  xaxis: {{ gridcolor: "#1e2132", linecolor: "#2a2d3e", zerolinecolor: "#2a2d3e" }},
  yaxis: {{ gridcolor: "#1e2132", linecolor: "#2a2d3e", zerolinecolor: "#2a2d3e" }},
  legend: {{ bgcolor: "#1a1d27", bordercolor: "#2a2d3e", borderwidth: 1 }},
  margin: {{ l: 55, r: 16, t: 40, b: 50 }},
  ...extra,
}});

const cfg = {{ responsive: true, displayModeBar: false }};

// ── Price Timeline ─────────────────────────────────────────────────────────────
function renderPrice(data) {{
  if (!data.length) {{ Plotly.purge("chart-price"); return; }}

  // Group by (product, day) — show price as scatter colored by trader
  const product = state.product;
  const isSingle = product !== "ALL";

  // Build traces: one per (symbol, day) if ALL, or one per trader if single product
  const traces = [];

  if (isSingle) {{
    // One trace per trader (as buyer)
    const byTrader = {{}};
    data.forEach(r => {{
      const key = r.buyer;
      (byTrader[key] = byTrader[key] || []).push(r);
    }});
    Object.entries(byTrader).forEach(([trader, rows]) => {{
      rows.sort((a, b) => a.day*1e9 + a.timestamp - b.day*1e9 - b.timestamp);
      traces.push({{
        x: rows.map(r => r.day * 1000000 + r.timestamp),
        y: rows.map(r => r.price),
        mode: "markers",
        type: "scattergl",
        name: trader + " (buy)",
        marker: {{ color: TRADER_COLORS[trader] || "#888", size: 7, opacity: 0.85 }},
        text: rows.map(r => `${{trader}} buys ${{r.quantity}} @ ${{r.price}}<br>Day ${{r.day}} ts=${{r.timestamp}}`),
        hoverinfo: "text",
      }});
    }});
    const bySeller = {{}};
    data.forEach(r => {{
      (bySeller[r.seller] = bySeller[r.seller] || []).push(r);
    }});
    Object.entries(bySeller).forEach(([trader, rows]) => {{
      rows.sort((a, b) => a.day*1e9 + a.timestamp - b.day*1e9 - b.timestamp);
      traces.push({{
        x: rows.map(r => r.day * 1000000 + r.timestamp),
        y: rows.map(r => r.price),
        mode: "markers",
        type: "scattergl",
        name: trader + " (sell)",
        marker: {{ color: TRADER_COLORS[trader] || "#888", size: 7, opacity: 0.85, symbol: "triangle-down" }},
        text: rows.map(r => `${{trader}} sells ${{r.quantity}} @ ${{r.price}}<br>Day ${{r.day}} ts=${{r.timestamp}}`),
        hoverinfo: "text",
      }});
    }});
  }} else {{
    // One trace per product
    const byProd = {{}};
    data.forEach(r => {{
      (byProd[r.symbol] = byProd[r.symbol] || []).push(r);
    }});
    Object.entries(byProd).forEach(([sym, rows]) => {{
      rows.sort((a, b) => a.day*1e9 + a.timestamp - b.day*1e9 - b.timestamp);
      traces.push({{
        x: rows.map(r => r.day * 1000000 + r.timestamp),
        y: rows.map(r => r.price),
        mode: "lines+markers",
        type: "scattergl",
        name: sym,
        line: {{ color: PROD_COLORS[sym] || "#888", width: 1.5 }},
        marker: {{ size: 4 }},
        text: rows.map(r => `${{sym}}<br>${{r.buyer}} buys ${{r.quantity}} @ ${{r.price}}<br>from ${{r.seller}}<br>Day ${{r.day}}`),
        hoverinfo: "text",
      }});
    }});
  }}

  // Day boundary lines
  const shapes = state.days.has(2) ? [
    {{ type:"line", x0:2000000, x1:2000000, y0:0, y1:1, yref:"paper", line:{{color:"#374151",width:1,dash:"dot"}} }},
  ] : [];
  if (state.days.has(3)) shapes.push(
    {{ type:"line", x0:3000000, x1:3000000, y0:0, y1:1, yref:"paper", line:{{color:"#374151",width:1,dash:"dot"}} }}
  );

  const tickvals = [], ticktext = [];
  [1,2,3].forEach(d => {{
    if (state.days.has(d)) {{ tickvals.push(d*1000000 + 500000); ticktext.push("Day "+d); }}
  }});

  Plotly.react("chart-price", traces, {{
    ...layout({{ title: {{ text: isSingle ? product + " — Trade Prices" : "All Products — Trade Prices", font:{{size:13}} }} }}),
    shapes,
    xaxis: {{ ...layout().xaxis, tickvals, ticktext }},
    yaxis: {{ ...layout().yaxis, title: "Price" }},
  }}, cfg);
}}

// ── Trade Flow (buyer→seller sankey) ────────────────────────────────────────
function renderFlow(data) {{
  if (!data.length) {{ Plotly.purge("chart-flow"); return; }}

  // Aggregate by (buyer, seller, symbol)
  const agg = {{}};
  data.forEach(r => {{
    const key = r.buyer + "|" + r.seller;
    if (!agg[key]) agg[key] = {{ buyer: r.buyer, seller: r.seller, volume: 0, trades: 0 }};
    agg[key].volume += r.quantity;
    agg[key].trades += 1;
  }});

  const nodes = [...TRADERS];
  const nodeIdx = Object.fromEntries(nodes.map((t,i) => [t,i]));

  const sources = [], targets = [], values = [], labels = [];
  Object.values(agg).forEach(a => {{
    if (nodeIdx[a.buyer] === undefined || nodeIdx[a.seller] === undefined) return;
    sources.push(nodeIdx[a.buyer]);
    targets.push(nodeIdx[a.seller]);
    values.push(a.volume);
    labels.push(`${{a.buyer}} → ${{a.seller}}: ${{a.volume}} units (${{a.trades}} trades)`);
  }});

  const trace = {{
    type: "sankey",
    orientation: "h",
    node: {{
      pad: 20, thickness: 20,
      label: nodes,
      color: nodes.map(t => TRADER_COLORS[t] || "#888"),
      hovertemplate: "%{{label}}<extra></extra>",
    }},
    link: {{
      source: sources, target: targets, value: values,
      label: labels,
      color: sources.map(i => hexToRgba(TRADER_COLORS[nodes[i]] || "#888", 0.35)),
      hovertemplate: "%{{label}}<extra></extra>",
    }},
  }};

  Plotly.react("chart-flow", [trace], {{
    ...layout({{ title: {{ text: "Trade Flow: Buyer → Seller (by volume)", font:{{size:13}} }} }}),
  }}, cfg);
}}

// ── Volume by Trader ─────────────────────────────────────────────────────────
function renderVolume(data) {{
  if (!data.length) {{ Plotly.purge("chart-volume"); return; }}

  const products = [...new Set(data.map(r => r.symbol))].sort();

  // For each trader: volume bought and sold per product
  const buyVol = {{}}, sellVol = {{}};
  data.forEach(r => {{
    buyVol[r.buyer] = buyVol[r.buyer] || {{}};
    sellVol[r.seller] = sellVol[r.seller] || {{}};
    buyVol[r.buyer][r.symbol] = (buyVol[r.buyer][r.symbol] || 0) + r.quantity;
    sellVol[r.seller][r.symbol] = (sellVol[r.seller][r.symbol] || 0) + r.quantity;
  }});

  const traders = [...new Set(Object.keys(buyVol).concat(Object.keys(sellVol)))].sort();

  // Stacked bar: buy (positive) and sell (negative)
  const traces = [];
  products.forEach(prod => {{
    traces.push({{
      type: "bar",
      name: prod + " (buy)",
      x: traders,
      y: traders.map(t => (buyVol[t] || {{}})[prod] || 0),
      marker: {{ color: PROD_COLORS[prod] || "#888", opacity: 0.9 }},
      text: traders.map(t => `${{prod}}: ${{(buyVol[t]||{{}})[prod]||0}} bought`),
      hoverinfo: "text",
    }});
    traces.push({{
      type: "bar",
      name: prod + " (sell)",
      x: traders,
      y: traders.map(t => -((sellVol[t] || {{}})[prod] || 0)),
      marker: {{ color: PROD_COLORS[prod] || "#888", opacity: 0.45 }},
      text: traders.map(t => `${{prod}}: ${{(sellVol[t]||{{}})[prod]||0}} sold`),
      hoverinfo: "text",
    }});
  }});

  Plotly.react("chart-volume", traces, {{
    ...layout({{ title: {{ text: "Volume by Trader & Product (+ bought / − sold)", font:{{size:13}} }}, barmode:"relative" }}),
    yaxis: {{ ...layout().yaxis, title:"Volume" }},
    xaxis: {{ ...layout().xaxis, title:"Trader" }},
  }}, cfg);
}}

// ── Heatmap: Trader × Product ─────────────────────────────────────────────────
function renderHeatmap(data) {{
  if (!data.length) {{ Plotly.purge("chart-heatmap"); return; }}

  const products = [...new Set(data.map(r => r.symbol))].sort();
  const traders = TRADERS;

  const buyMatrix = traders.map(() => products.map(() => 0));
  const sellMatrix = traders.map(() => products.map(() => 0));

  data.forEach(r => {{
    const ti = traders.indexOf(r.buyer), pi = products.indexOf(r.symbol);
    if (ti >= 0 && pi >= 0) buyMatrix[ti][pi] += r.quantity;
    const ti2 = traders.indexOf(r.seller);
    if (ti2 >= 0 && pi >= 0) sellMatrix[ti2][pi] += r.quantity;
  }});

  const netMatrix = traders.map((t, ti) => products.map((p, pi) => buyMatrix[ti][pi] - sellMatrix[ti][pi]));
  const text = traders.map((t, ti) => products.map((p, pi) => {{
    const b = buyMatrix[ti][pi], s = sellMatrix[ti][pi], n = b - s;
    return `${{t}} / ${{p}}<br>Bought: ${{b}}<br>Sold: ${{s}}<br>Net: ${{n >= 0 ? "+" : ""}}${{n}}`;
  }}));

  Plotly.react("chart-heatmap", [{{
    type: "heatmap",
    z: netMatrix,
    x: products,
    y: traders,
    text: text,
    hoverinfo: "text",
    colorscale: [
      [0, "#ef4444"], [0.5, "#1e2132"], [1, "#22c55e"],
    ],
    zmid: 0,
    colorbar: {{ title: {{ text: "Net Vol<br>(buy−sell)", side: "right" }}, tickfont: {{ color: "#9ca3af" }}, titlefont: {{ color: "#9ca3af" }} }},
  }}], {{
    ...layout({{ title: {{ text: "Net Volume: Trader × Product (green = net buyer, red = net seller)", font:{{size:13}} }} }}),
    xaxis: {{ ...layout().xaxis, tickangle: -35 }},
    yaxis: {{ ...layout().yaxis }},
  }}, cfg);
}}

// ── Trade Table ───────────────────────────────────────────────────────────────
function renderTable(data) {{
  const thead = document.getElementById("thead");
  const tbody = document.getElementById("tbody");
  const info  = document.getElementById("table-info");

  thead.innerHTML = `<tr>
    <th>Day</th><th>Timestamp</th><th>Product</th>
    <th>Buyer</th><th>Seller</th><th>Price</th><th>Qty</th><th>Side</th>
  </tr>`;

  // Sort newest first
  const sorted = [...data].sort((a, b) => (b.day - a.day) || (b.timestamp - a.timestamp));
  const MAX = 2000;
  const display = sorted.slice(0, MAX);

  tbody.innerHTML = display.map(r => {{
    const bc = TRADER_COLORS[r.buyer] || "#888";
    const sc = TRADER_COLORS[r.seller] || "#888";
    const pc = PROD_COLORS[r.symbol] || "#888";
    return `<tr>
      <td>${{r.day}}</td>
      <td style="color:#6b7280;font-variant-numeric:tabular-nums">${{r.timestamp.toLocaleString()}}</td>
      <td><span style="color:${{pc}};font-weight:600">${{r.symbol}}</span></td>
      <td><span class="trader-dot" style="background:${{bc}}"></span>${{r.buyer}}</td>
      <td><span class="trader-dot" style="background:${{sc}}"></span>${{r.seller}}</td>
      <td style="font-variant-numeric:tabular-nums;text-align:right">${{r.price}}</td>
      <td style="text-align:right">${{r.quantity}}</td>
      <td>
        <span class="badge buy">BUY →${{r.buyer.split(" ")[1]}}</span>
        <span class="badge sell">SELL ←${{r.seller.split(" ")[1]}}</span>
      </td>
    </tr>`;
  }}).join("");

  info.textContent = `Showing ${{display.length}} of ${{data.length}} trades (most recent first)${{data.length > MAX ? " — apply filters to narrow down" : ""}}`;
}}

// ── Init ──────────────────────────────────────────────────────────────────────
refresh();
</script>
</body>
</html>
"""

out = os.path.join(base, "round4_dashboard.html")
with open(out, "w") as f:
    f.write(html)

print(f"Dashboard written to: {out}")
print(f"Embedded {len(records)} trades.")
