"""Generate all Round 3 analysis notebooks."""
import nbformat as nbf
from pathlib import Path

OUT = Path("notebooks")
OUT.mkdir(exist_ok=True)


def md(src): return nbf.v4.new_markdown_cell(src)
def code(src): return nbf.v4.new_code_cell(src)
def save(cells, name):
    nb = nbf.v4.new_notebook()
    nb.cells = cells
    with open(OUT / name, "w") as f:
        nbf.write(nb, f)
    print(f"  wrote {name}")


# ──────────────────────────────────────────────
# SHARED DATA-LOAD TEMPLATE
# ──────────────────────────────────────────────
SETUP_TEMPLATE = """\
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import numpy as np
from pathlib import Path

DATA_DIR = Path("../historical_data/round_3")
PRODUCT  = "{product}"

days       = [0, 1, 2]
day_colors = {{0: "#4C72B0", 1: "#DD8452", 2: "#55A868"}}
day_labels = {{0: "Day 0",   1: "Day 1",   2: "Day 2"}}

frames = []
for d in days:
    tmp = pd.read_csv(DATA_DIR / f"prices_round_3_day_{{d}}.csv", sep=";")
    frames.append(tmp)

raw = pd.concat(frames, ignore_index=True)
df  = raw[raw["product"] == PRODUCT].copy()

ticks_per_day = int(df[df["day"] == 0]["timestamp"].max() + 100)
df["global_ts"] = (df["day"] - days[0]) * ticks_per_day + df["timestamp"]
df = df.sort_values("global_ts").reset_index(drop=True)
df["spread"] = df["ask_price_1"] - df["bid_price_1"]

print(f"Rows: {{len(df)}}   ticks_per_day: {{ticks_per_day}}")
df[["day","timestamp","mid_price","bid_price_1","ask_price_1","spread"]].head()
"""

# ──────────────────────────────────────────────
# SHARED ANALYSIS SECTIONS (used by NB1 & NB2)
# ──────────────────────────────────────────────
SECTION1 = """\
fig, ax = plt.subplots(figsize=(16, 5))
for d in days:
    sub = df[df["day"] == d]
    ax.plot(sub["global_ts"], sub["mid_price"],
            color=day_colors[d], linewidth=0.8, label=day_labels[d])
ts_max = ticks_per_day
for i in range(1, len(days)):
    ax.axvline(i * ts_max, color="grey", linestyle="--", linewidth=0.7, alpha=0.6)
df["mid_rolling"] = df["mid_price"].rolling(50, center=True).mean()
ax.plot(df["global_ts"], df["mid_rolling"],
        color="red", linewidth=1.2, alpha=0.7, label="50-obs rolling mean")
ax.set_title(f"{PRODUCT} — Mid Price", fontsize=14)
ax.set_xlabel("Global timestamp"); ax.set_ylabel("Price (XIREC)")
ax.legend(); ax.grid(True, alpha=0.3)
plt.tight_layout(); plt.show()
"""

SECTION2 = """\
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(16, 8), sharex=True)
for d in days:
    sub = df[df["day"] == d]
    ax1.plot(sub["global_ts"], sub["bid_price_1"], color=day_colors[d], lw=0.7, alpha=0.8)
    ax1.plot(sub["global_ts"], sub["ask_price_1"], color=day_colors[d], lw=0.7, alpha=0.8, ls="--")
    ax2.plot(sub["global_ts"], sub["spread"],      color=day_colors[d], lw=0.7, label=day_labels[d])
for i in range(1, len(days)):
    for ax in (ax1, ax2):
        ax.axvline(i * ticks_per_day, color="grey", ls="--", lw=0.7, alpha=0.5)
from matplotlib.lines import Line2D
proxy = [Line2D([0],[0],color="k",lw=1,label="Best bid"),
         Line2D([0],[0],color="k",lw=1,ls="--",label="Best ask")] + \
        [Line2D([0],[0],color=day_colors[d],lw=1.5,label=day_labels[d]) for d in days]
ax1.legend(handles=proxy, fontsize=8)
ax1.set_title(f"{PRODUCT} — Best Bid & Ask"); ax1.set_ylabel("Price"); ax1.grid(True, alpha=0.3)
ax2.set_title("Bid-Ask Spread"); ax2.set_ylabel("Spread"); ax2.set_xlabel("Global timestamp")
ax2.legend(); ax2.grid(True, alpha=0.3)
plt.tight_layout(); plt.show()
"""

SECTION3 = """\
fig, axes = plt.subplots(1, 3, figsize=(16, 4))
for ax, d in zip(axes, days):
    sub = df[df["day"] == d]["mid_price"].dropna()
    ax.hist(sub, bins=50, color=day_colors[d], edgecolor="white", lw=0.3)
    ax.axvline(sub.mean(), color="red", ls="--", lw=1.2, label=f"Mean {sub.mean():.1f}")
    ax.set_title(day_labels[d]); ax.set_xlabel("Mid price"); ax.set_ylabel("Count")
    ax.legend(fontsize=8); ax.grid(True, alpha=0.3)
fig.suptitle(f"{PRODUCT} — Mid Price Distribution", fontsize=13, y=1.02)
plt.tight_layout(); plt.show()
df.groupby("day")["mid_price"].agg(["mean","std","min","max"]).round(2)
"""

SECTION4 = """\
df["total_bid_vol"] = df[["bid_volume_1","bid_volume_2","bid_volume_3"]].fillna(0).sum(axis=1)
df["total_ask_vol"] = df[["ask_volume_1","ask_volume_2","ask_volume_3"]].fillna(0).abs().sum(axis=1)

fig, axes = plt.subplots(2, 1, figsize=(16, 7), sharex=True)
for d in days:
    sub = df[df["day"] == d]
    axes[0].fill_between(sub["global_ts"], sub["total_bid_vol"],
                         alpha=0.4, color=day_colors[d], label=day_labels[d])
    axes[1].fill_between(sub["global_ts"], sub["total_ask_vol"],
                         alpha=0.4, color=day_colors[d], label=day_labels[d])
for ax in axes:
    for i in range(1, len(days)):
        ax.axvline(i * ticks_per_day, color="grey", ls="--", lw=0.7, alpha=0.5)
    ax.grid(True, alpha=0.3); ax.legend(fontsize=8)
axes[0].set_title(f"{PRODUCT} — Total Bid Depth (levels 1-3)"); axes[0].set_ylabel("Volume")
axes[1].set_title(f"{PRODUCT} — Total Ask Depth (levels 1-3)")
axes[1].set_ylabel("Volume"); axes[1].set_xlabel("Global timestamp")
plt.tight_layout(); plt.show()
"""

SECTION5 = """\
df["returns"]     = df["mid_price"].diff()
df["rolling_vol"] = df["returns"].rolling(100).std()

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(16, 7), sharex=True)
for d in days:
    sub = df[df["day"] == d]
    ax1.bar(sub["global_ts"], sub["returns"], width=80, color=day_colors[d], alpha=0.5, label=day_labels[d])
    ax2.plot(sub["global_ts"], sub["rolling_vol"], color=day_colors[d], lw=0.8, label=day_labels[d])
for ax in (ax1, ax2):
    for i in range(1, len(days)):
        ax.axvline(i * ticks_per_day, color="grey", ls="--", lw=0.7, alpha=0.5)
    ax.grid(True, alpha=0.3); ax.legend(fontsize=8)
ax1.axhline(0, color="black", lw=0.5)
ax1.set_title(f"{PRODUCT} — Tick-by-Tick Returns"); ax1.set_ylabel("Δ Mid Price")
ax2.set_title("Rolling Volatility (std, window=100)"); ax2.set_ylabel("Std Dev")
ax2.set_xlabel("Global timestamp")
plt.tight_layout(); plt.show()
"""

SECTION6 = """\
WINDOW = 200
df["fair_value"]  = df["mid_price"].rolling(WINDOW, center=True).mean()
df["fv_std"]      = df["mid_price"].rolling(WINDOW, center=True).std()
df["fv_zscore"]   = (df["mid_price"] - df["fair_value"]) / df["fv_std"]

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(16, 8), sharex=True)
for d in days:
    sub = df[df["day"] == d]
    ax1.plot(sub["global_ts"], sub["mid_price"],  color=day_colors[d], lw=0.6, alpha=0.7)
    ax1.plot(sub["global_ts"], sub["fair_value"], color=day_colors[d], lw=1.4, ls="--")
    ax2.plot(sub["global_ts"], sub["fv_zscore"],  color=day_colors[d], lw=0.7, label=day_labels[d])
ax2.axhline( 1.5, color="red",   ls="--", lw=0.8, alpha=0.6, label="+1.5σ (sell)")
ax2.axhline(-1.5, color="green", ls="--", lw=0.8, alpha=0.6, label="-1.5σ (buy)")
ax2.axhline( 0,   color="black", lw=0.5)
for ax in (ax1, ax2):
    for i in range(1, len(days)):
        ax.axvline(i * ticks_per_day, color="grey", ls="--", lw=0.7, alpha=0.5)
    ax.grid(True, alpha=0.3)
ax1.set_title(f"{PRODUCT} — Mid Price vs Rolling Fair Value ({WINDOW}-obs)"); ax1.set_ylabel("Price")
ax2.set_title("Z-Score (deviation from fair value)"); ax2.set_ylabel("Z-score")
ax2.set_xlabel("Global timestamp"); ax2.legend(fontsize=8)
plt.tight_layout(); plt.show()

# Signal stats
overbought = (df["fv_zscore"] > 1.5).sum()
oversold   = (df["fv_zscore"] < -1.5).sum()
print(f"Overbought ticks (z>1.5): {overbought}  ({100*overbought/len(df):.1f}%)")
print(f"Oversold   ticks (z<-1.5): {oversold}  ({100*oversold/len(df):.1f}%)")
"""


def build_base_nb(product):
    """Build the standard price-analysis notebook for a single product."""
    return [
        md(f"# {product} — Round 3 Price Analysis\n\nHistorical data across days **0, 1, 2**."),
        code(SETUP_TEMPLATE.format(product=product)),
        md("## 1 — Mid Price Over Time"),
        code(SECTION1),
        md("## 2 — Bid / Ask Prices & Spread"),
        code(SECTION2),
        md("## 3 — Mid Price Distribution per Day"),
        code(SECTION3),
        md("## 4 — Order Book Depth (Best 3 Levels)"),
        code(SECTION4),
        md("## 5 — Price Returns & Volatility"),
        code(SECTION5),
        md("## 6 — Fair Value Estimation & Mean-Reversion Signal"),
        code(SECTION6),
    ]


# ══════════════════════════════════════════════
# NOTEBOOK 1 — VELVETFRUIT_EXTRACT
# ══════════════════════════════════════════════
print("Building NB1: VELVETFRUIT_EXTRACT…")
save(build_base_nb("VELVETFRUIT_EXTRACT"), "VELVETFRUIT_EXTRACT_ANALYSIS.ipynb")

# ══════════════════════════════════════════════
# NOTEBOOK 2 — HYDROGEL_PACK
# ══════════════════════════════════════════════
print("Building NB2: HYDROGEL_PACK…")
save(build_base_nb("HYDROGEL_PACK"), "HYDROGEL_PACK_ANALYSIS.ipynb")


# ══════════════════════════════════════════════
# NOTEBOOK 3 — VEV OPTIONS ANALYSIS
# ══════════════════════════════════════════════
print("Building NB3: VEV Options…")

OPT_SETUP = """\
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import numpy as np
from pathlib import Path
from scipy.stats import norm
from scipy.optimize import brentq
from mpl_toolkits.mplot3d import Axes3D  # noqa
import warnings

DATA_DIR = Path("../historical_data/round_3")
STRIKES  = [4000, 4500, 5000, 5100, 5200, 5300, 5400, 5500, 6000, 6500]
VEV_COLS = [f"VEV_{k}" for k in STRIKES]
UNDERLYING = "VELVETFRUIT_EXTRACT"
days = [0, 1, 2]
day_colors = {0: "#4C72B0", 1: "#DD8452", 2: "#55A868"}

# ── Load all products ──────────────────────────────────────────────
frames = []
for d in days:
    tmp = pd.read_csv(DATA_DIR / f"prices_round_3_day_{d}.csv", sep=";")
    frames.append(tmp)
raw = pd.concat(frames, ignore_index=True)

ticks_per_day = int(raw[raw["day"] == 0]["timestamp"].max() + 100)
raw["global_ts"] = (raw["day"] - days[0]) * ticks_per_day + raw["timestamp"]

# Pivot to wide: one column per product, indexed by global_ts
wide = raw.pivot_table(index="global_ts", columns="product",
                       values="mid_price", aggfunc="first")
wide = wide.sort_index().reset_index()

# Align day/timestamp info
ts_map = raw.drop_duplicates("global_ts").set_index("global_ts")[["day","timestamp"]]
wide = wide.join(ts_map, on="global_ts")

# Tick index for T estimation (0 = start, total_ticks-1 = end)
total_ticks = len(wide)
wide["tick_idx"] = np.arange(total_ticks)
wide["T"] = (total_ticks - wide["tick_idx"]) / total_ticks  # fraction of time remaining

S = wide[UNDERLYING]
print(f"Total ticks: {total_ticks}  ticks_per_day: {ticks_per_day}")
print(f"Underlying price range: {S.min():.1f} – {S.max():.1f}")
wide[[UNDERLYING] + VEV_COLS].describe().round(2)
"""

OPT_BS_FUNCS = """\
# ── Black-Scholes helper functions ────────────────────────────────────────────

def bs_call(S, K, T, sigma, r=0.0):
    \"\"\"European call price (Black-Scholes, r=0 default).\"\"\"
    if T <= 1e-8 or sigma <= 1e-8:
        return max(float(S) - float(K), 0.0)
    d1 = (np.log(S / K) + 0.5 * sigma**2 * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)
    return S * norm.cdf(d1) - K * norm.cdf(d2)

def bs_delta(S, K, T, sigma, r=0.0):
    \"\"\"Delta = N(d1).\"\"\"
    if T <= 1e-8 or sigma <= 1e-8:
        return 1.0 if S > K else 0.0
    d1 = (np.log(S / K) + 0.5 * sigma**2 * T) / (sigma * np.sqrt(T))
    return float(norm.cdf(d1))

def bs_gamma(S, K, T, sigma, r=0.0):
    \"\"\"Gamma = N'(d1) / (S * sigma * sqrt(T)).\"\"\"
    if T <= 1e-8 or sigma <= 1e-8:
        return 0.0
    d1 = (np.log(S / K) + 0.5 * sigma**2 * T) / (sigma * np.sqrt(T))
    return float(norm.pdf(d1) / (S * sigma * np.sqrt(T)))

def bs_vega(S, K, T, sigma, r=0.0):
    \"\"\"Vega = S * N'(d1) * sqrt(T).\"\"\"
    if T <= 1e-8 or sigma <= 1e-8:
        return 0.0
    d1 = (np.log(S / K) + 0.5 * sigma**2 * T) / (sigma * np.sqrt(T))
    return float(S * norm.pdf(d1) * np.sqrt(T))

def bs_theta(S, K, T, sigma, r=0.0):
    \"\"\"Theta per tick (negative = time decay).\"\"\"
    if T <= 1e-8 or sigma <= 1e-8:
        return 0.0
    d1 = (np.log(S / K) + 0.5 * sigma**2 * T) / (sigma * np.sqrt(T))
    return float(-(S * norm.pdf(d1) * sigma) / (2 * np.sqrt(T)))

def implied_vol(C, S, K, T, tol=1e-7):
    \"\"\"Implied volatility via bisection (brentq). Returns NaN if unsolvable.\"\"\"
    intrinsic = max(float(S) - float(K), 0.0)
    if np.isnan(C) or np.isnan(S) or T <= 1e-8:
        return np.nan
    if C <= intrinsic + tol or C >= S:
        return np.nan
    try:
        return brentq(lambda sig: bs_call(S, K, T, sig) - C,
                      1e-6, 30.0, xtol=tol, maxiter=300)
    except (ValueError, RuntimeError):
        return np.nan

print("Black-Scholes functions defined.")
# Quick sanity check
S_test, K_test, T_test, sig_test = 5250, 5200, 0.5, 0.15
C_test = bs_call(S_test, K_test, T_test, sig_test)
iv_back = implied_vol(C_test, S_test, K_test, T_test)
print(f"BS call({S_test},{K_test},T={T_test},σ={sig_test}) = {C_test:.4f}  → IV roundtrip = {iv_back:.6f}")
"""

OPT_CHAIN_SNAPSHOT = """\
# Snapshots at beginning, middle, end of dataset
snap_indices = [0, total_ticks // 2, total_ticks - 1]
snap_labels  = ["Day 0 start", "Midpoint", "Day 2 end"]
fig, axes = plt.subplots(1, 3, figsize=(18, 5))

for ax, idx, lbl in zip(axes, snap_indices, snap_labels):
    row = wide.iloc[idx]
    S_snap = row[UNDERLYING]
    prices = [row.get(f"VEV_{k}", np.nan) for k in STRIKES]
    intrinsic = [max(S_snap - k, 0) for k in STRIKES]
    time_val  = [max(p - iv, 0) if not np.isnan(p) else np.nan
                 for p, iv in zip(prices, intrinsic)]

    x = np.arange(len(STRIKES))
    ax.bar(x, intrinsic, label="Intrinsic value", color="#4C72B0", alpha=0.7)
    ax.bar(x, time_val, bottom=intrinsic, label="Time value", color="#DD8452", alpha=0.7)
    ax.plot(x, prices, "ko-", ms=4, lw=1.5, label="Market price")
    ax.axvline(x=np.interp(S_snap, STRIKES, x), color="red",
               ls="--", lw=1, label=f"ATM (S={S_snap:.0f})")
    ax.set_xticks(x); ax.set_xticklabels([str(k) for k in STRIKES], rotation=45)
    ax.set_title(lbl); ax.set_xlabel("Strike"); ax.set_ylabel("Price (XIREC)")
    ax.legend(fontsize=7); ax.grid(True, alpha=0.3)

fig.suptitle("Option Chain Snapshot — Intrinsic vs Time Value", fontsize=13)
plt.tight_layout(); plt.show()
"""

OPT_IV_ENGINE = """\
# Compute implied volatility for every tick × strike
print("Computing implied volatilities (this may take ~30s)…")
iv_df = pd.DataFrame(index=wide.index)
iv_df["global_ts"] = wide["global_ts"]
iv_df["day"]       = wide["day"]
iv_df["T"]         = wide["T"]

for K in STRIKES:
    col = f"VEV_{K}"
    if col not in wide.columns:
        iv_df[f"IV_{K}"] = np.nan
        continue
    ivs = []
    for _, row in wide.iterrows():
        C_val = row.get(col, np.nan)
        S_val = row.get(UNDERLYING, np.nan)
        T_val = row["T"]
        ivs.append(implied_vol(C_val, S_val, K, T_val))
    iv_df[f"IV_{K}"] = ivs

iv_cols = [f"IV_{K}" for K in STRIKES]
print("Done.")
iv_df[iv_cols].describe().round(4)
"""

OPT_IV_SMILE = """\
# IV Smile / Skew at multiple snapshots
snap_indices = [500, total_ticks//4, total_ticks//2, 3*total_ticks//4, total_ticks-500]
snap_labels  = ["Early", "Q1", "Mid", "Q3", "Late"]
colors = plt.cm.plasma(np.linspace(0.1, 0.9, len(snap_indices)))

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 5))
for idx, lbl, col in zip(snap_indices, snap_labels, colors):
    row_iv = iv_df.iloc[idx]
    ivs    = [row_iv.get(f"IV_{K}", np.nan) for K in STRIKES]
    ax1.plot(STRIKES, ivs, "o-", color=col, label=lbl, lw=1.5, ms=5)

ax1.set_title("IV Smile (market price implied σ vs strike)")
ax1.set_xlabel("Strike"); ax1.set_ylabel("Implied volatility σ")
ax1.legend(fontsize=8); ax1.grid(True, alpha=0.3)

# Skew: slope of IV across strikes (linear fit)
skews = []
for i in range(len(iv_df)):
    row_iv = iv_df.iloc[i]
    ivs = np.array([row_iv.get(f"IV_{K}", np.nan) for K in STRIKES])
    valid = ~np.isnan(ivs)
    if valid.sum() >= 3:
        coeffs = np.polyfit(np.array(STRIKES)[valid], ivs[valid], 1)
        skews.append(coeffs[0])
    else:
        skews.append(np.nan)
iv_df["skew"] = skews

for d in [0,1,2]:
    sub = iv_df[iv_df["day"] == d]
    ax2.plot(sub["global_ts"], sub["skew"].rolling(50).mean(),
             color=day_colors[d], lw=1.0, label=f"Day {d}")
ax2.axhline(0, color="black", lw=0.5)
ax2.set_title("IV Skew Over Time (slope of IV vs strike, 50-obs rolling)")
ax2.set_xlabel("Global timestamp"); ax2.set_ylabel("Skew slope")
ax2.legend(); ax2.grid(True, alpha=0.3)
plt.tight_layout(); plt.show()
"""

OPT_IV_SURFACE = """\
# IV Surface — strike x time
fig = plt.figure(figsize=(14, 7))
ax3d = fig.add_subplot(111, projection="3d")

X_st = np.array(STRIKES)
Y_ts = iv_df["global_ts"].values[::50]   # downsample for speed
Z = np.array([[iv_df[f"IV_{K}"].values[::50][i] for K in STRIKES]
               for i in range(len(Y_ts))])

Xg, Yg = np.meshgrid(X_st, Y_ts)
mask = ~np.isnan(Z)
Z_plot = np.where(mask, Z, np.nanmedian(Z))

surf = ax3d.plot_surface(Xg, Yg, Z_plot, cmap="viridis", alpha=0.85,
                         linewidth=0, antialiased=True)
fig.colorbar(surf, ax=ax3d, shrink=0.5, label="Implied Vol σ")
ax3d.set_xlabel("Strike"); ax3d.set_ylabel("Global timestamp")
ax3d.set_zlabel("IV σ"); ax3d.set_title("Implied Volatility Surface")
plt.tight_layout(); plt.show()

# Heatmap version (easier to read)
fig2, ax2 = plt.subplots(figsize=(14, 5))
hm_data = iv_df[iv_cols].values[::50].T   # shape (n_strikes, n_times)
im = ax2.imshow(hm_data, aspect="auto", cmap="RdYlGn_r",
                extent=[0, total_ticks, STRIKES[-1], STRIKES[0]])
plt.colorbar(im, ax=ax2, label="Implied Vol σ")
ax2.set_title("IV Heatmap (strike vs time)"); ax2.set_xlabel("Tick"); ax2.set_ylabel("Strike")
plt.tight_layout(); plt.show()
"""

OPT_HIST_VS_IV = """\
# Realised vol of underlying vs ATM implied vol
WINDOW_RV = 200
S_series = wide[UNDERLYING]
rv = S_series.diff().rolling(WINDOW_RV).std()   # realised vol (price units)
rv_norm = rv / S_series                          # normalise to "sigma" units

# ATM IV ≈ VEV_5200 or VEV_5000 (closest to spot)
atm_iv = iv_df["IV_5200"].rolling(50).mean()

fig, ax = plt.subplots(figsize=(16, 5))
ax.plot(wide["global_ts"], rv_norm,  label=f"Realised vol (window={WINDOW_RV})", color="#4C72B0", lw=0.8)
ax.plot(wide["global_ts"], atm_iv,   label="ATM IV (VEV_5200, 50-obs smoothed)", color="#DD8452", lw=1.0)
vol_premium = atm_iv - rv_norm
ax.fill_between(wide["global_ts"], rv_norm, atm_iv,
                where=(atm_iv > rv_norm), alpha=0.2, color="red",   label="Vol premium (IV > RV)")
ax.fill_between(wide["global_ts"], rv_norm, atm_iv,
                where=(atm_iv < rv_norm), alpha=0.2, color="green", label="Vol discount (IV < RV)")
for i in range(1, 3):
    ax.axvline(i * ticks_per_day, color="grey", ls="--", lw=0.7, alpha=0.5)
ax.set_title("Realised Volatility vs ATM Implied Volatility")
ax.set_xlabel("Global timestamp"); ax.set_ylabel("Volatility (σ)")
ax.legend(fontsize=8); ax.grid(True, alpha=0.3)
plt.tight_layout(); plt.show()

print(f"Mean vol premium (IV - RV): {vol_premium.mean():.4f}")
print(f"Vol premium > 0 (IV > RV):  {(vol_premium > 0).mean()*100:.1f}% of ticks")
"""

OPT_INTRINSIC_TIME = """\
# Time value decay across 3 days for each strike
# Compute time value = max(market_price - intrinsic, 0)
fig, axes = plt.subplots(2, 5, figsize=(20, 8), sharex=True)
axes = axes.flatten()
S_arr = wide[UNDERLYING].values

for ax, K in zip(axes, STRIKES):
    col = f"VEV_{K}"
    if col not in wide.columns:
        continue
    C_arr      = wide[col].values
    intrinsic  = np.maximum(S_arr - K, 0)
    time_val   = np.maximum(C_arr - intrinsic, 0)

    ax.fill_between(wide["global_ts"], time_val, alpha=0.6, color="#4C72B0")
    ax.fill_between(wide["global_ts"], intrinsic, alpha=0.5, color="#DD8452")
    ax.set_title(f"K={K}", fontsize=9)
    ax.set_ylabel("Price"); ax.grid(True, alpha=0.3)
    for i in range(1, 3):
        ax.axvline(i * ticks_per_day, color="grey", ls="--", lw=0.7, alpha=0.5)

from matplotlib.patches import Patch
legend_el = [Patch(facecolor="#DD8452", alpha=0.5, label="Intrinsic"),
             Patch(facecolor="#4C72B0", alpha=0.6, label="Time value")]
fig.legend(handles=legend_el, loc="upper right", fontsize=9)
fig.suptitle("Intrinsic vs Time Value Decomposition by Strike", fontsize=13)
plt.tight_layout(); plt.show()
"""

OPT_GREEKS = """\
# Compute BS Greeks for all strikes over time (downsample for speed)
STEP = 50
idx_sub = wide.index[::STEP]
greek_rows = []
for i in idx_sub:
    row = wide.loc[i]
    S_v = row[UNDERLYING]; T_v = row["T"]
    for K in STRIKES:
        iv_val = iv_df.loc[i, f"IV_{K}"]
        if np.isnan(iv_val):
            continue
        greek_rows.append({
            "global_ts": row["global_ts"], "day": row["day"], "K": K,
            "delta": bs_delta(S_v, K, T_v, iv_val),
            "gamma": bs_gamma(S_v, K, T_v, iv_val),
            "vega":  bs_vega (S_v, K, T_v, iv_val),
            "theta": bs_theta(S_v, K, T_v, iv_val),
        })
greeks = pd.DataFrame(greek_rows)

# Plot Greeks vs strike at fixed snapshot
snap_ts = wide["global_ts"].iloc[total_ticks // 2]
snap_g  = greeks[greeks["global_ts"] == greeks["global_ts"].iloc[
                 greeks["global_ts"].searchsorted(snap_ts)]]

fig, axes = plt.subplots(2, 2, figsize=(14, 9))
for ax, gname, ylabel in zip(axes.flatten(),
                              ["delta","gamma","vega","theta"],
                              ["Δ Delta","Γ Gamma","V Vega","Θ Theta"]):
    ax.bar(snap_g["K"].astype(str), snap_g[gname], color="#4C72B0", alpha=0.8)
    ax.set_title(f"{ylabel} vs Strike (midpoint snapshot)")
    ax.set_xlabel("Strike"); ax.set_ylabel(ylabel)
    ax.grid(True, alpha=0.3)
plt.tight_layout(); plt.show()
"""

OPT_GREEKS_HEATMAP = """\
import seaborn as sns

for gname in ["delta", "gamma", "vega", "theta"]:
    pivot = greeks.pivot_table(index="K", columns="global_ts", values=gname, aggfunc="mean")
    fig, ax = plt.subplots(figsize=(16, 4))
    sns.heatmap(pivot, ax=ax, cmap="RdYlGn" if gname == "delta" else "viridis",
                cbar_kws={"label": gname}, xticklabels=False)
    ax.set_title(f"{gname.title()} Heatmap (strike × time)")
    ax.set_ylabel("Strike"); ax.set_xlabel("Time →")
    plt.tight_layout(); plt.show()
"""

OPT_DELTA_HEDGE = """\
# Simulate delta-neutral position: long 1 ATM option, short delta units of underlying
K_HEDGE = 5200
if f"VEV_{K_HEDGE}" in wide.columns:
    hedge_pnl = [0.0]
    prev_opt_price = wide[f"VEV_{K_HEDGE}"].iloc[0]
    prev_und_price = wide[UNDERLYING].iloc[0]
    prev_delta     = bs_delta(prev_und_price, K_HEDGE,
                              wide["T"].iloc[0],
                              iv_df[f"IV_{K_HEDGE}"].iloc[0] or 0.15)
    for i in range(1, len(wide)):
        C_now = wide[f"VEV_{K_HEDGE}"].iloc[i]
        S_now = wide[UNDERLYING].iloc[i]
        if np.isnan(C_now) or np.isnan(S_now):
            hedge_pnl.append(hedge_pnl[-1])
            continue
        opt_pnl = C_now - prev_opt_price
        und_pnl = prev_delta * (prev_und_price - S_now)  # short delta
        hedge_pnl.append(hedge_pnl[-1] + opt_pnl + und_pnl)

        iv_now = iv_df[f"IV_{K_HEDGE}"].iloc[i]
        prev_delta     = bs_delta(S_now, K_HEDGE, wide["T"].iloc[i],
                                  iv_now if not np.isnan(iv_now) else 0.15)
        prev_opt_price = C_now; prev_und_price = S_now

    fig, ax = plt.subplots(figsize=(16, 4))
    ax.plot(wide["global_ts"], hedge_pnl, color="#4C72B0", lw=0.8)
    ax.axhline(0, color="black", lw=0.5)
    for i in range(1, 3):
        ax.axvline(i * ticks_per_day, color="grey", ls="--", lw=0.7, alpha=0.5)
    ax.set_title(f"Delta-Hedged P&L — Long VEV_{K_HEDGE}, Short Delta Units of Underlying")
    ax.set_xlabel("Global timestamp"); ax.set_ylabel("Cumulative P&L (XIREC)")
    ax.grid(True, alpha=0.3)
    plt.tight_layout(); plt.show()
    print(f"Final delta-hedge P&L: {hedge_pnl[-1]:.2f}")
"""

OPT_MEAN_REV = """\
from statsmodels.tsa.stattools import adfuller

def half_life_ar1(series):
    s = series.dropna()
    if len(s) < 20:
        return np.nan
    lag   = s.shift(1).dropna()
    delta = (s - s.shift(1)).dropna()
    n     = min(len(lag), len(delta))
    lag, delta = lag.iloc[-n:].values, delta.iloc[-n:].values
    X = np.column_stack([np.ones(n), lag])
    beta = np.linalg.lstsq(X, delta, rcond=None)[0][1]
    return -np.log(2) / beta if beta < 0 else np.inf

results = []
for K in STRIKES:
    iv_series = iv_df[f"IV_{K}"].dropna()
    if len(iv_series) < 50:
        continue
    adf = adfuller(iv_series, autolag="AIC")
    hl  = half_life_ar1(iv_df[f"IV_{K}"])
    results.append({"Strike": K, "ADF stat": round(adf[0],4),
                    "p-value": round(adf[1],4),
                    "Stationary (p<0.05)": adf[1] < 0.05,
                    "Half-life (ticks)": round(hl,1) if np.isfinite(hl) else "∞"})
print(pd.DataFrame(results).to_string(index=False))

# IV with Bollinger bands
fig, axes = plt.subplots(2, 5, figsize=(20, 8))
ROLL = 300
for ax, K in zip(axes.flatten(), STRIKES):
    s = iv_df[f"IV_{K}"]
    mn = s.rolling(ROLL).mean(); std = s.rolling(ROLL).std()
    ax.plot(iv_df["global_ts"], s,  lw=0.6, color="#4C72B0", label="IV")
    ax.plot(iv_df["global_ts"], mn, lw=1.2, color="orange",  label=f"Mean({ROLL})")
    ax.fill_between(iv_df["global_ts"], mn-1.5*std, mn+1.5*std, alpha=0.2, color="orange")
    ax.set_title(f"K={K}", fontsize=9); ax.grid(True, alpha=0.3)
fig.suptitle("IV Mean-Reversion with Bollinger Bands (±1.5σ)", fontsize=13)
plt.tight_layout(); plt.show()
"""

OPT_IV_SCALPING = """\
# IV Scalping Signal — Z-score based vol entry/exit
ROLL_SIG = 500
fig, axes = plt.subplots(2, 5, figsize=(20, 8))

all_pnl = {}
for ax, K in zip(axes.flatten(), STRIKES):
    s   = iv_df[f"IV_{K}"]
    mn  = s.rolling(ROLL_SIG, min_periods=50).mean()
    std = s.rolling(ROLL_SIG, min_periods=50).std()
    z   = (s - mn) / std.replace(0, np.nan)

    # Signal: +1 = buy vol (z < -1.5), -1 = sell vol (z > +1.5), 0 = flat
    sig = np.where(z < -1.5, 1, np.where(z > 1.5, -1, np.nan))
    sig = pd.Series(sig, index=s.index).ffill().fillna(0)

    # P&L proxy: signal × next tick IV change (vol is "traded" at current IV)
    pnl = (sig.shift(1) * s.diff()).cumsum()
    all_pnl[K] = pnl

    ax.plot(iv_df["global_ts"], z, lw=0.6, color="#4C72B0")
    ax.fill_between(iv_df["global_ts"], z, 1.5,
                    where=(z > 1.5), alpha=0.3, color="red",   label="Sell vol")
    ax.fill_between(iv_df["global_ts"], z, -1.5,
                    where=(z < -1.5), alpha=0.3, color="green", label="Buy vol")
    ax.axhline(0,    color="black", lw=0.5)
    ax.axhline( 1.5, color="red",   ls="--", lw=0.8, alpha=0.7)
    ax.axhline(-1.5, color="green", ls="--", lw=0.8, alpha=0.7)
    ax.set_title(f"K={K}  |  Final PnL={pnl.iloc[-1]:.3f}", fontsize=9)
    ax.grid(True, alpha=0.3)

fig.suptitle(f"IV Scalping Z-Score (window={ROLL_SIG}) — Red=Sell/Green=Buy vol", fontsize=12)
plt.tight_layout(); plt.show()

# Cumulative P&L for all strikes
fig2, ax2 = plt.subplots(figsize=(16, 5))
colors_k = plt.cm.tab10(np.linspace(0, 1, len(STRIKES)))
for (K, pnl), col in zip(all_pnl.items(), colors_k):
    ax2.plot(iv_df["global_ts"], pnl, lw=0.9, color=col, label=f"K={K}")
ax2.axhline(0, color="black", lw=0.5)
ax2.set_title("IV Scalping Cumulative P&L (proxy, per unit vega)")
ax2.set_xlabel("Global timestamp"); ax2.set_ylabel("Cumulative P&L")
ax2.legend(fontsize=7, ncol=5); ax2.grid(True, alpha=0.3)
plt.tight_layout(); plt.show()
"""

OPT_VOL_OF_VOL = """\
# Vol-of-Vol: rolling std of IV per strike
ROLL_VV = 200
fig, ax = plt.subplots(figsize=(16, 5))
colors_k = plt.cm.tab10(np.linspace(0, 1, len(STRIKES)))
for K, col in zip(STRIKES, colors_k):
    vov = iv_df[f"IV_{K}"].rolling(ROLL_VV).std()
    ax.plot(iv_df["global_ts"], vov, lw=0.8, color=col, label=f"K={K}", alpha=0.8)
for i in range(1, 3):
    ax.axvline(i * ticks_per_day, color="grey", ls="--", lw=0.7, alpha=0.5)
ax.set_title(f"Vol-of-Vol (rolling std of IV, window={ROLL_VV})")
ax.set_xlabel("Global timestamp"); ax.set_ylabel("Std(IV)")
ax.legend(fontsize=7, ncol=5); ax.grid(True, alpha=0.3)
plt.tight_layout(); plt.show()

# Summary table
vov_stats = {}
for K in STRIKES:
    vov = iv_df[f"IV_{K}"].rolling(ROLL_VV).std().dropna()
    vov_stats[K] = {"mean_vov": round(vov.mean(),4), "max_vov": round(vov.max(),4)}
print(pd.DataFrame(vov_stats).T.to_string())
"""

OPT_ARB_CHECKS = """\
# Arbitrage checks
violations = []
for i in range(len(wide)):
    row = wide.iloc[i]
    S_v = row.get(UNDERLYING, np.nan)
    if np.isnan(S_v):
        continue
    # (a) Call spread monotonicity: C(K1) > C(K2) for K1 < K2
    prev_price = None
    for K in STRIKES:
        c = row.get(f"VEV_{K}", np.nan)
        if np.isnan(c):
            prev_price = None; continue
        if prev_price is not None and c > prev_price + 0.5:
            violations.append({"type": "spread_monotonicity",
                                "ts": row["global_ts"], "K": K, "detail": f"C({K})={c:.2f} > C(prev)"})
        prev_price = c
    # (b) Lower bound: C >= max(S-K, 0)
    for K in STRIKES:
        c = row.get(f"VEV_{K}", np.nan)
        lb = max(S_v - K, 0)
        if not np.isnan(c) and c < lb - 0.5:
            violations.append({"type": "lower_bound",
                                "ts": row["global_ts"], "K": K,
                                "detail": f"C={c:.2f} < intrinsic={lb:.2f}"})
    # (c) Convexity (butterfly): C(K1) - 2*C(K2) + C(K3) >= 0
    for j in range(1, len(STRIKES)-1):
        K1, K2, K3 = STRIKES[j-1], STRIKES[j], STRIKES[j+1]
        c1 = row.get(f"VEV_{K1}", np.nan)
        c2 = row.get(f"VEV_{K2}", np.nan)
        c3 = row.get(f"VEV_{K3}", np.nan)
        if not any(np.isnan([c1,c2,c3])):
            bf = c1 - 2*c2 + c3
            if bf < -1.0:
                violations.append({"type": "convexity",
                                    "ts": row["global_ts"], "K_mid": K2,
                                    "detail": f"butterfly={bf:.3f}"})

vdf = pd.DataFrame(violations)
if len(vdf):
    print(f"Total violations: {len(vdf)}")
    print(vdf["type"].value_counts().to_string())
    print(vdf.head(10).to_string(index=False))
else:
    print("No arbitrage violations found — option chain is consistent.")
"""

OPT_PRICE_SERIES = """\
# Option price time series: all 10 strikes, color-coded by moneyness
moneyness_colors = plt.cm.RdYlGn(np.linspace(0.1, 0.9, len(STRIKES)))  # red=OTM, green=ITM

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(16, 9), sharex=True)
S_arr = wide[UNDERLYING].values
mid_S = np.nanmedian(S_arr)

for K, col in zip(STRIKES, moneyness_colors):
    vcol = f"VEV_{K}"
    if vcol not in wide.columns:
        continue
    label = f"K={K} ({'ITM' if K < mid_S else 'OTM' if K > mid_S else 'ATM'})"
    ax1.plot(wide["global_ts"], wide[vcol], color=col, lw=0.8, alpha=0.85, label=label)

ax2.plot(wide["global_ts"], wide[UNDERLYING], color="black", lw=0.9, label=UNDERLYING)

for ax in (ax1, ax2):
    for i in range(1, 3):
        ax.axvline(i * ticks_per_day, color="grey", ls="--", lw=0.7, alpha=0.5)
    ax.grid(True, alpha=0.3); ax.legend(fontsize=7, ncol=5)

ax1.set_title("VEV Option Prices Over Time (all strikes)"); ax1.set_ylabel("Option Price")
ax2.set_title(f"{UNDERLYING} Underlying Price"); ax2.set_ylabel("Price")
ax2.set_xlabel("Global timestamp")
plt.tight_layout(); plt.show()
"""

opt_cells = [
    md("# VEV Options — Comprehensive Analysis\n\nRound 3 options chain on **VELVETFRUIT_EXTRACT**.\n"
       "VEV_XXXX are treated as European call options with strike = XXXX.\n\n"
       "> Hint: *La trahison des images* — look beyond face value."),
    code(OPT_SETUP),
    code(OPT_BS_FUNCS),
    md("## 1 — Option Chain Snapshot"),
    code(OPT_CHAIN_SNAPSHOT),
    md("## 2 — Black-Scholes Primer\n\n"
       "**Model:** $C = S \\cdot N(d_1) - K \\cdot N(d_2)$\n\n"
       "where $d_1 = \\frac{\\ln(S/K) + \\frac{1}{2}\\sigma^2 T}{\\sigma\\sqrt{T}}$, "
       "$d_2 = d_1 - \\sigma\\sqrt{T}$\n\n"
       "**Assumptions:** $r = 0$ (no risk-free rate in XIREC economy), "
       "$T$ = fraction of simulation ticks remaining (0→1), "
       "$\\sigma$ = implied volatility in \"per-sim-unit\" space.\n\n"
       "**Implied volatility (IV):** the $\\sigma$ that makes the BS price equal the market price. "
       "IV encodes the market's expectation of future realised vol.\n\n"
       "**Greeks:**\n"
       "- $\\Delta$ (delta): sensitivity to underlying price change\n"
       "- $\\Gamma$ (gamma): rate of change of delta\n"
       "- $V$ (vega): sensitivity to volatility change\n"
       "- $\\Theta$ (theta): time decay per tick"),
    md("## 3 — Implied Volatility Engine"),
    code(OPT_IV_ENGINE),
    md("## 4 — IV Smile & Skew"),
    code(OPT_IV_SMILE),
    md("## 5 — IV Surface (Strike × Time)"),
    code(OPT_IV_SURFACE),
    md("## 6 — Historical Realised Vol vs Implied Vol"),
    code(OPT_HIST_VS_IV),
    md("## 7 — Intrinsic vs Time Value Decomposition"),
    code(OPT_INTRINSIC_TIME),
    md("## 8 — Greeks (Δ, Γ, V, Θ)"),
    code(OPT_GREEKS),
    md("## 9 — Greeks Heatmap (Strike × Time)"),
    code(OPT_GREEKS_HEATMAP),
    md("## 10 — Delta-Hedging P&L Simulation"),
    code(OPT_DELTA_HEDGE),
    md("## 11 — Mean Reversion of IV (ADF + Half-Life)"),
    code(OPT_MEAN_REV),
    md("## 12 — IV Scalping Signal & Backtest"),
    code(OPT_IV_SCALPING),
    md("## 13 — Vol-of-Vol"),
    code(OPT_VOL_OF_VOL),
    md("## 14 — Arbitrage Checks"),
    code(OPT_ARB_CHECKS),
    md("## 15 — Option Price Time Series"),
    code(OPT_PRICE_SERIES),
]
save(opt_cells, "VEV_OPTIONS_ANALYSIS.ipynb")


# ══════════════════════════════════════════════
# NOTEBOOK 4 — CROSS-PRODUCT CORRELATION
# ══════════════════════════════════════════════
print("Building NB4: Cross-Product Correlation…")

CORR_SETUP = """\
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns
from pathlib import Path
from statsmodels.tsa.stattools import coint, adfuller
from statsmodels.regression.linear_model import OLS
from statsmodels.tools.tools import add_constant

DATA_DIR = Path("../historical_data/round_3")
ALL_PRODUCTS = [
    "VELVETFRUIT_EXTRACT", "HYDROGEL_PACK",
    "VEV_4000","VEV_4500","VEV_5000","VEV_5100","VEV_5200",
    "VEV_5300","VEV_5400","VEV_5500","VEV_6000","VEV_6500",
]
STRIKES = [4000,4500,5000,5100,5200,5300,5400,5500,6000,6500]
days = [0, 1, 2]
day_colors = {0:"#4C72B0", 1:"#DD8452", 2:"#55A868"}

frames = []
for d in days:
    tmp = pd.read_csv(DATA_DIR / f"prices_round_3_day_{d}.csv", sep=";")
    frames.append(tmp)
raw = pd.concat(frames, ignore_index=True)

ticks_per_day = int(raw[raw["day"] == 0]["timestamp"].max() + 100)
raw["global_ts"] = (raw["day"] - days[0]) * ticks_per_day + raw["timestamp"]

wide = raw.pivot_table(index="global_ts", columns="product",
                       values="mid_price", aggfunc="first").sort_index().reset_index()
ts_map = raw.drop_duplicates("global_ts").set_index("global_ts")[["day","timestamp"]]
wide   = wide.join(ts_map, on="global_ts")

print(f"Wide shape: {wide.shape}")
print("Products present:", [c for c in ALL_PRODUCTS if c in wide.columns])
wide[ALL_PRODUCTS].describe().round(2)
"""

CORR_MATRIX = """\
price_cols = [c for c in ALL_PRODUCTS if c in wide.columns]
corr = wide[price_cols].corr()

fig, ax = plt.subplots(figsize=(13, 10))
mask = np.zeros_like(corr, dtype=bool)
sns.heatmap(corr, ax=ax, annot=True, fmt=".2f", cmap="RdYlGn",
            vmin=-1, vmax=1, mask=mask,
            annot_kws={"size": 7}, linewidths=0.3)
ax.set_title("Pearson Correlation — All Round 3 Products (mid price levels)", fontsize=13)
plt.xticks(rotation=45, ha="right"); plt.yticks(rotation=0)
plt.tight_layout(); plt.show()

# Returns correlation
ret_corr = wide[price_cols].diff().corr()
fig2, ax2 = plt.subplots(figsize=(13, 10))
sns.heatmap(ret_corr, ax=ax2, annot=True, fmt=".2f", cmap="RdYlGn",
            vmin=-1, vmax=1, annot_kws={"size": 7}, linewidths=0.3)
ax2.set_title("Pearson Correlation — Tick-by-Tick RETURNS", fontsize=13)
plt.xticks(rotation=45, ha="right"); plt.yticks(rotation=0)
plt.tight_layout(); plt.show()
"""

CORR_VEF_HYD = """\
vef = wide["VELVETFRUIT_EXTRACT"].dropna()
hyd = wide["HYDROGEL_PACK"].dropna()
idx = vef.index.intersection(hyd.index)
vef_a, hyd_a = vef[idx], hyd[idx]

fig, axes = plt.subplots(1, 3, figsize=(18, 5))
# Scatter
axes[0].scatter(vef_a, hyd_a, alpha=0.03, s=1, color="#4C72B0")
axes[0].set_xlabel("VELVETFRUIT_EXTRACT"); axes[0].set_ylabel("HYDROGEL_PACK")
axes[0].set_title(f"Scatter  (r={vef_a.corr(hyd_a):.3f})"); axes[0].grid(True, alpha=0.3)

# Time-series overlay (normalised)
ts_x = wide.loc[idx, "global_ts"]
axes[1].plot(ts_x, (vef_a - vef_a.mean()) / vef_a.std(),
             color="#4C72B0", lw=0.6, label="VEF (z-score)")
axes[1].plot(ts_x, (hyd_a - hyd_a.mean()) / hyd_a.std(),
             color="#DD8452", lw=0.6, label="HYD (z-score)")
for i in range(1,3): axes[1].axvline(i*ticks_per_day, color="grey", ls="--", lw=0.7, alpha=0.5)
axes[1].set_title("Normalised Price Overlay"); axes[1].legend(); axes[1].grid(True, alpha=0.3)

# Rolling correlation
roll_corr = vef_a.rolling(500).corr(hyd_a)
axes[2].plot(ts_x, roll_corr, color="#55A868", lw=0.8)
axes[2].axhline(0, color="black", lw=0.5); axes[2].axhline(1, color="grey", ls="--", lw=0.5)
axes[2].set_title("Rolling Correlation (window=500)"); axes[2].set_ylabel("r")
axes[2].grid(True, alpha=0.3)
plt.tight_layout(); plt.show()
"""

CORR_VEF_VEV = """\
vef = wide["VELVETFRUIT_EXTRACT"]
fig, axes = plt.subplots(2, 5, figsize=(20, 8))
for ax, K in zip(axes.flatten(), STRIKES):
    col = f"VEV_{K}"
    if col not in wide.columns:
        continue
    vev = wide[col]
    idx = vef.dropna().index.intersection(vev.dropna().index)
    r   = vef[idx].corr(vev[idx])
    ax.scatter(vef[idx], vev[idx], alpha=0.02, s=1, color="#4C72B0")
    ax.set_title(f"K={K}  r={r:.3f}", fontsize=9)
    ax.set_xlabel("VEF"); ax.set_ylabel(f"VEV_{K}", fontsize=7)
    ax.grid(True, alpha=0.3)
fig.suptitle("VELVETFRUIT_EXTRACT vs Each VEV Option Price", fontsize=13)
plt.tight_layout(); plt.show()

# Rolling correlation per strike vs underlying
fig2, ax2 = plt.subplots(figsize=(16, 5))
colors_k = plt.cm.tab10(np.linspace(0, 1, len(STRIKES)))
for K, col in zip(STRIKES, colors_k):
    vcol = f"VEV_{K}"
    if vcol not in wide.columns: continue
    rc = wide["VELVETFRUIT_EXTRACT"].rolling(500).corr(wide[vcol])
    ax2.plot(wide["global_ts"], rc, lw=0.8, color=col, label=f"K={K}", alpha=0.8)
ax2.axhline(0, color="black", lw=0.5)
ax2.set_title("Rolling Correlation: VELVETFRUIT_EXTRACT vs VEV Strikes (window=500)")
ax2.set_xlabel("Global timestamp"); ax2.set_ylabel("r")
ax2.legend(fontsize=7, ncol=5); ax2.grid(True, alpha=0.3)
plt.tight_layout(); plt.show()
"""

CORR_HYD_VEV = """\
hyd = wide["HYDROGEL_PACK"]
corr_table = {}
for K in STRIKES:
    col = f"VEV_{K}"
    if col not in wide.columns: continue
    idx = hyd.dropna().index.intersection(wide[col].dropna().index)
    corr_table[K] = {"level_r": round(hyd[idx].corr(wide[col][idx]), 4),
                     "return_r": round(hyd[idx].diff().corr(wide[col][idx].diff()), 4)}
print(pd.DataFrame(corr_table).T.to_string())

fig, ax = plt.subplots(figsize=(10, 4))
ks = list(corr_table.keys())
ax.bar(np.array(ks)-50, [corr_table[k]["level_r"]  for k in ks], width=80, label="Level r",  alpha=0.8)
ax.bar(np.array(ks)+50, [corr_table[k]["return_r"] for k in ks], width=80, label="Return r", alpha=0.8)
ax.axhline(0, color="black", lw=0.5)
ax.set_xticks(ks); ax.set_xticklabels([str(k) for k in ks])
ax.set_title("HYDROGEL_PACK vs VEV Options — Correlation by Strike")
ax.set_xlabel("Strike"); ax.set_ylabel("r")
ax.legend(); ax.grid(True, alpha=0.3)
plt.tight_layout(); plt.show()
"""

CORR_COINT = """\
print("Running Engle-Granger cointegration tests…")
results = []
vef_s = wide["VELVETFRUIT_EXTRACT"].dropna()
hyd_s = wide["HYDROGEL_PACK"].dropna()

# VEF vs each VEV
for K in STRIKES:
    col = f"VEV_{K}"
    if col not in wide.columns: continue
    vev_s = wide[col].dropna()
    idx   = vef_s.index.intersection(vev_s.index)
    if len(idx) < 100: continue
    sc, pv, _ = coint(vef_s[idx], vev_s[idx])
    results.append({"Pair": f"VEF vs VEV_{K}", "Coint stat": round(sc,4),
                    "p-value": round(pv,4), "Cointegrated": pv < 0.05})

# VEF vs HYD
idx_vh = vef_s.index.intersection(hyd_s.index)
if len(idx_vh) > 100:
    sc, pv, _ = coint(vef_s[idx_vh], hyd_s[idx_vh])
    results.append({"Pair": "VEF vs HYD", "Coint stat": round(sc,4),
                    "p-value": round(pv,4), "Cointegrated": pv < 0.05})

print(pd.DataFrame(results).to_string(index=False))
"""

CORR_SPREAD_SIGNAL = """\
# Spread trading: C_theoretical - C_market residual
# For a call option: C_theo ≈ max(S-K, 0) (intrinsic lower bound)
# Richer signal: C_market - C_{nearby_strike} should move with delta * ΔS
vef = wide["VELVETFRUIT_EXTRACT"]
fig, axes = plt.subplots(2, 5, figsize=(20, 8))
for ax, K in zip(axes.flatten(), STRIKES):
    col = f"VEV_{K}"
    if col not in wide.columns: continue
    intrinsic = np.maximum(vef - K, 0)
    time_val  = wide[col] - intrinsic
    ax.plot(wide["global_ts"], time_val, lw=0.5, color="#4C72B0", alpha=0.7)
    ax.axhline(0, color="red", lw=0.8, ls="--")
    ax.set_title(f"K={K} — Time Value", fontsize=9); ax.grid(True, alpha=0.3)
    for i in range(1,3): ax.axvline(i*ticks_per_day, color="grey", ls="--", lw=0.7, alpha=0.5)
fig.suptitle("Time Value Over Time (should decay to 0 at expiry)", fontsize=13)
plt.tight_layout(); plt.show()

# Call spread residual: VEV_K1 - VEV_K2 vs theoretical spread (delta * (K2-K1))
K1, K2 = 5000, 5200
if f"VEV_{K1}" in wide.columns and f"VEV_{K2}" in wide.columns:
    spread_mkt  = wide[f"VEV_{K1}"] - wide[f"VEV_{K2}"]
    spread_theo = np.maximum(vef - K1, 0) - np.maximum(vef - K2, 0)
    residual    = spread_mkt - spread_theo

    fig2, ax2 = plt.subplots(figsize=(16, 4))
    ax2.plot(wide["global_ts"], residual, lw=0.6, color="#4C72B0")
    ax2.axhline(0, color="black", lw=0.5)
    ax2.set_title(f"Call Spread Residual: (VEV_{K1}-VEV_{K2}) − Intrinsic Spread")
    ax2.set_xlabel("Global timestamp"); ax2.set_ylabel("Residual (time-value spread)")
    ax2.grid(True, alpha=0.3)
    plt.tight_layout(); plt.show()
    print(f"Residual stats: mean={residual.mean():.3f}  std={residual.std():.3f}")
"""

CORR_RETURN_CORR = """\
ret_cols = [c for c in ALL_PRODUCTS if c in wide.columns]
rets = wide[ret_cols].diff()

# Heatmap
fig, ax = plt.subplots(figsize=(13, 10))
sns.heatmap(rets.corr(), ax=ax, annot=True, fmt=".2f", cmap="RdYlGn",
            vmin=-1, vmax=1, annot_kws={"size":7}, linewidths=0.3)
ax.set_title("Returns Correlation Heatmap", fontsize=13)
plt.xticks(rotation=45, ha="right"); plt.yticks(rotation=0)
plt.tight_layout(); plt.show()

# Lead-lag between VEF and VEV_5200 (ATM option)
if "VEV_5200" in wide.columns:
    vef_r = wide["VELVETFRUIT_EXTRACT"].diff().dropna()
    vev_r = wide["VEV_5200"].diff().dropna()
    lags  = range(-10, 11)
    idx   = vef_r.index.intersection(vev_r.index)
    ll    = [vef_r[idx].corr(vev_r[idx].shift(l)) for l in lags]
    fig2, ax2 = plt.subplots(figsize=(10, 4))
    ax2.bar(list(lags), ll, color="#4C72B0", alpha=0.8)
    ax2.axhline(0, color="black", lw=0.5)
    ax2.set_title("Lead-Lag Correlation: VELVETFRUIT_EXTRACT Returns vs VEV_5200 Returns")
    ax2.set_xlabel("Lag (ticks, positive = VEV lags VEF)")
    ax2.set_ylabel("Correlation"); ax2.grid(True, alpha=0.3)
    plt.tight_layout(); plt.show()
"""

corr_cells = [
    md("# Cross-Product Correlation — Round 3\n\n"
       "All 12 products: 2 base commodities + 10 VEV option strikes."),
    code(CORR_SETUP),
    md("## 1 — Full Correlation Matrix"),
    code(CORR_MATRIX),
    md("## 2 — VELVETFRUIT_EXTRACT vs HYDROGEL_PACK"),
    code(CORR_VEF_HYD),
    md("## 3 — VELVETFRUIT_EXTRACT vs VEV Option Strikes"),
    code(CORR_VEF_VEV),
    md("## 4 — HYDROGEL_PACK vs VEV Options"),
    code(CORR_HYD_VEV),
    md("## 5 — Cointegration Analysis (Engle-Granger)"),
    code(CORR_COINT),
    md("## 6 — Spread Trading Signal (Time Value & Call Spread Residual)"),
    code(CORR_SPREAD_SIGNAL),
    md("## 7 — Cross-Product Returns Correlation & Lead-Lag"),
    code(CORR_RETURN_CORR),
]
save(corr_cells, "CROSS_PRODUCT_CORRELATION.ipynb")

print("\nAll notebooks generated successfully.")
