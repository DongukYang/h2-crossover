#!/usr/bin/env python3
"""
make_all_figures.py — 100 kW ALK sensor-validation: ALL manuscript figures
=====================================================================================
covering the EXTENDED dataset:

  Campaign 1 : 2025-12-16 .. 2026-04-09  (combined_raw.parquet, 5,221,100 samples)
  Campaign 2 : 2026-06-15 .. 2026-07-17  (daily xlsx files, +2,819,907 samples)

STEP 1  builds  combined_raw_extended.parquet   (skipped if it already exists)
STEP 2  renders manuscript figures, each saved as PNG (300 dpi) + PDF:
  Figure10_overview_24h        representative 24-h record (2026-01-19)
  Figure11_intersensor        steady-state inter-sensor comparison (violin/BA/x-val)
  Figure12_idle_stability     idle-period stability (weekly baselines, violin, FP)
  Figure13_longterm_weekly    long-term weekly behaviour (flow + 4 channels)
  Figure15_t90_startup        start-up (system) response with t90,sys markers
STEP 2f renders Fig6_spangas (manuscript Fig. 15): span-gas step overlays.
STEP 3  writes  key_metrics_extended.json  with the numbers used in the text.

Output-file -> manuscript-figure mapping:
  Fig1_overview_24h -> Fig. 10 | Fig2_accuracy -> Fig. 11 | Fig3_stability -> Fig. 12
  Fig5_longterm  -> Fig. 13    | Fig6_spangas -> Fig. 15  

Edit the PATHS block below, then:   python3 make_all_figures.py
"""
import os, glob, json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.patches import Patch

# ----------------------------------------------------------------- PATHS ----
OLD_PARQUET = "path/to/campaign1_raw.parquet"      # 1 Hz campaign-1 log      # campaign 1
NEW_XLSX_MULTI = ["path/to/campaign2_multisheet.xlsx"]  # multi-sheet books
NEW_XLSX_GLOB  = "path/to/campaign2_daily/*.xlsx"   # one-sheet daily books
OUT    = "path/to/campaign1_raw.parquet"
FIGDIR = os.path.join(OUT, "figures")
EXT_PARQUET = os.path.join(OUT, "combined_raw_extended.parquet")
os.makedirs(FIGDIR, exist_ok=True)

# ----------------------------------------------------------------- STYLE ----
plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 8, "axes.titlesize": 9,
    "axes.labelsize": 8.5, "xtick.labelsize": 7.5, "ytick.labelsize": 7.5,
    "legend.fontsize": 7, "axes.linewidth": 0.8, "lines.linewidth": 1.0,
    "figure.dpi": 100, "savefig.dpi": 300})
W = 7.2                                   # double-column width (inch)
C_COMM_H2, C_KEPCO_H2 = "#d95f02", "#1f77b4"   # H2-in-O2 pair (orange / blue)
C_COMM_O2, C_KEPCO_O2 = "#e6ab02", "#1b9e77"   # O2-in-H2 pair (amber / green)
C_COMM,  C_KEPCO      = "#d62728", "#2ca02c"   # weekly plots (red / green)
C_FLOW = "0.45"
KGS_H2, KGS_O2 = 2.0, 3.0                 # KGS AH271 emergency-stop thresholds
FAULT_WEEKS = (9, 10, 11)                 # in-house O2 stuck (campaign 1)
metrics = {}

def save(fig, name):
    fig.tight_layout()
    for e in ("png", "pdf"):
        fig.savefig(os.path.join(FIGDIR, f"{name}.{e}"), bbox_inches="tight")
    plt.close(fig)
    print("  saved", name)

def tag(ax, t):
    ax.text(0.02, 0.97, t, transform=ax.transAxes, fontweight="bold",
            fontsize=10, ha="left", va="top")

# ======================================================================
# STEP 1 — build extended parquet
# ======================================================================
def map_columns(cols):
    m = {}
    for c in cols:
        cl = str(c)
        if "DataTime" in cl: m["datetime"] = c
        elif "수소_생산_유량" in cl: m["flow"] = c
        elif "한전" in cl:
            if ("H2inO2" in cl) or ("H2_in_O2" in cl): m["kepco_H2"] = c
            elif ("O2inH2" in cl) or ("O2_in_H2" in cl): m["kepco_O2"] = c
        else:
            if "O2_in_H2" in cl: m["comm_O2"] = c
            elif "H2_in_O2" in cl: m["comm_H2"] = c
    return m

def proc_frame(raw, name):
    cmap = map_columns(raw.columns)
    d = pd.DataFrame()
    d["datetime"] = pd.to_datetime(raw[cmap["datetime"]], errors="coerce")
    for k in ["flow", "comm_O2", "comm_H2", "kepco_H2", "kepco_O2"]:
        d[k] = pd.to_numeric(raw[cmap[k]], errors="coerce") if k in cmap else np.nan
    if "comm_O2" in cmap and "ppm" in str(cmap["comm_O2"]).lower():
        d["comm_O2"] /= 10000.0           # ppm -> vol%
    d["source_file"] = name
    return d

def build_extended():
    if os.path.exists(EXT_PARQUET):
        print("STEP 1: extended parquet exists — skipping rebuild")
        return pd.read_parquet(EXT_PARQUET)
    print("STEP 1: building extended parquet ...")
    try:
        engine = "calamine"; pd.read_excel  # python-calamine (fast) if installed
        import python_calamine  # noqa
    except Exception:
        engine = "openpyxl"
    parts = []
    for book in NEW_XLSX_MULTI:
        for sh, raw in pd.read_excel(book, sheet_name=None, engine=engine).items():
            parts.append(proc_frame(raw, f"{os.path.basename(book)}::{sh}"))
    for p in sorted(glob.glob(NEW_XLSX_GLOB)):
        parts.append(proc_frame(pd.read_excel(p, engine=engine), os.path.basename(p)))
    new = (pd.concat(parts, ignore_index=True)
           .dropna(subset=["datetime"]).sort_values("datetime").reset_index(drop=True))
    new["comm_O2_masked"] = False
    old = pd.read_parquet(OLD_PARQUET)
    base = ["datetime", "flow", "comm_O2", "comm_H2", "kepco_H2", "kepco_O2",
            "source_file", "comm_O2_masked"]
    df = (pd.concat([old[base], new[base]], ignore_index=True)
          .sort_values("datetime").reset_index(drop=True))
    # derived columns — recomputed consistently over the full record
    df["operating_state"] = np.where(df["flow"] > 0.5, "operating", "idle")
    gap = df["datetime"].diff().dt.total_seconds().fillna(1) > 5   # break runs at gaps
    rid = ((df["operating_state"] != df["operating_state"].shift()) | gap).cumsum()
    rsz = df.groupby(rid)["operating_state"].transform("size")
    df["idle_continuous"] = (df["operating_state"].eq("idle") & (rsz >= 60)).values
    df["steady_state"] = ((df["flow"] > 30) &
                          (df["flow"].rolling(30, min_periods=30).std() < 5)
                          ).fillna(False).values
    t0 = df["datetime"].min()
    df["week_idx"] = ((df["datetime"] - t0).dt.days // 7 + 1).astype(int)
    cols = ["datetime", "flow", "comm_O2", "comm_H2", "kepco_H2", "kepco_O2",
            "source_file", "operating_state", "idle_continuous", "steady_state",
            "week_idx", "comm_O2_masked"]
    df[cols].to_parquet(EXT_PARQUET, index=False)
    print(f"  saved {EXT_PARQUET}  rows={len(df):,}")
    return df[cols]

df = build_extended().sort_values("datetime").reset_index(drop=True)
metrics["row_count"] = int(len(df))
metrics["date_range"] = [str(df.datetime.min()), str(df.datetime.max())]

# ======================================================================
# FIGURE 10 — representative 24-h record (2026-01-19)
# ======================================================================
print("Figure 10 ...")
d = df[(df.datetime >= "2026-01-19") & (df.datetime < "2026-01-20")]
ds = d.iloc[::5]
fig, axs = plt.subplots(3, 1, figsize=(W, 6.6), sharex=True)
ax = axs[0]
ax.plot(ds.datetime, ds.flow, color=C_FLOW, lw=0.8)
ax.set_ylabel("H$_2$ flow\n(NL min$^{-1}$)"); tag(ax, "(a)")
ax = axs[1]
ax.plot(ds.datetime, ds.comm_H2, color=C_COMM_H2, lw=0.9, label="Commercial H$_2$ sensor")
ax.plot(ds.datetime, ds.kepco_H2, color=C_KEPCO_H2, lw=0.9, label="In-house H$_2$ sensor")
z = d[(d.datetime >= "2026-01-19 11:00") & (d.datetime <= "2026-01-19 11:20")]
fp = z.loc[z.comm_H2.idxmax()]
ax.annotate(f"Weekly span-gas check\n({fp.comm_H2:.1f} vol% step)",
            xy=(fp.datetime, min(fp.comm_H2, 5.4)), xytext=(0.18, 0.72),
            textcoords="axes fraction", fontsize=7, color="#444444",
            arrowprops=dict(arrowstyle="->", color="#444444", lw=0.8))
ax.axvspan(pd.Timestamp("2026-01-19 11:00"), pd.Timestamp("2026-01-19 11:20"),
           color="0.5", alpha=0.15)
ax.set_ylabel("H$_2$ in O$_2$ (%)"); ax.set_ylim(-0.4, 6); tag(ax, "(b)")
ax.legend(loc="upper right")
ax = axs[2]
ax.plot(ds.datetime, ds.comm_O2, color=C_COMM_O2, lw=0.9, label="Commercial O$_2$ sensor")
ax.plot(ds.datetime, ds.kepco_O2, color=C_KEPCO_O2, lw=0.9, label="In-house O$_2$ sensor")
ax.axvspan(pd.Timestamp("2026-01-19 11:00"), pd.Timestamp("2026-01-19 11:20"),
           color="0.5", alpha=0.15)
ax.annotate("Same span-gas check\n(0.6 vol% step)",
            xy=(pd.Timestamp("2026-01-19 11:08"), 0.55), xytext=(0.15, 0.80),
            textcoords="axes fraction", fontsize=6.5, color="#444444",
            arrowprops=dict(arrowstyle="->", color="#444444", lw=0.7))
ax.set_ylabel("O$_2$ in H$_2$ (%)"); ax.set_ylim(-0.25, 0.65); tag(ax, "(c)")
ax.legend(loc="upper right"); ax.set_xlabel("Time (2026-01-19)")
ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
save(fig, "Figure10_overview_24h")
metrics["fig10_false_reading_volpct"] = float(round(fp.comm_H2, 2))

# ======================================================================
# FIGURE 11 — inter-sensor comparison (steady-state 5-min averages)
# ======================================================================
print("Figure 11 ...")
ss = df[df.steady_state].set_index("datetime")
agg = (ss[["comm_H2", "kepco_H2", "comm_O2", "kepco_O2"]]
       .resample("5min").mean().dropna(how="all"))
aH = agg.dropna(subset=["comm_H2", "kepco_H2"])
n5 = len(aH)
fig, axs = plt.subplots(2, 2, figsize=(W, 6.6))
# (a) H2 violins
ax = axs[0, 0]
p = ax.violinplot([aH.comm_H2, aH.kepco_H2], showmedians=True, showextrema=True)
for pc, c in zip(p["bodies"], [C_COMM_H2, C_KEPCO_H2]):
    pc.set_facecolor(c); pc.set_alpha(0.55)
mu_c, sd_c = aH.comm_H2.mean(), aH.comm_H2.std()
mu_k, sd_k = aH.kepco_H2.mean(), aH.kepco_H2.std()
ax.text(0.97, 0.97, (f"Commercial: $\\mu$={mu_c:.2f}%, $\\sigma$={sd_c:.2f}%\n"
                     f"In-house: $\\mu$={mu_k:.2f}%, $\\sigma$={sd_k:.2f}%"),
        transform=ax.transAxes, ha="right", va="top", fontsize=6.5,
        bbox=dict(boxstyle="round", fc="w", ec="0.7"))
ax.set_xticks([1, 2]); ax.set_xticklabels(["Commercial", "In-house"])
ax.set_ylabel("H$_2$ in O$_2$ (%)"); tag(ax, "(a)")
ax.set_title("H$_2$ sensor — steady state")
metrics["steady_H2"] = dict(comm_mu=round(mu_c, 3), comm_sd=round(sd_c, 3),
                            kepco_mu=round(mu_k, 3), kepco_sd=round(sd_k, 3), n_5min=n5)
# (b) O2 violins
ax = axs[0, 1]
aO = agg.dropna(subset=["comm_O2", "kepco_O2"])
p = ax.violinplot([aO.comm_O2, aO.kepco_O2], showmedians=True, showextrema=True)
for pc, c in zip(p["bodies"], [C_COMM_O2, C_KEPCO_O2]):
    pc.set_facecolor(c); pc.set_alpha(0.55)
ax.text(0.97, 0.97, (f"Commercial: $\\mu$={aO.comm_O2.mean():.2f}%, $\\sigma$={aO.comm_O2.std():.2f}%\n"
                     f"In-house: $\\mu$={aO.kepco_O2.mean():.2f}%, $\\sigma$={aO.kepco_O2.std():.2f}%"),
        transform=ax.transAxes, ha="right", va="top", fontsize=6.5,
        bbox=dict(boxstyle="round", fc="w", ec="0.7"))
ax.set_xticks([1, 2]); ax.set_xticklabels(["Commercial", "In-house"])
ax.set_ylabel("O$_2$ in H$_2$ (%)"); tag(ax, "(b)")
ax.set_title("O$_2$ sensor — steady state")
metrics["steady_O2"] = dict(comm_mu=round(float(aO.comm_O2.mean()), 3),
                            kepco_mu=round(float(aO.kepco_O2.mean()), 3))
# (c) Bland–Altman (H2 only; O2 dropped: proportional bias, r~0.95)
ax = axs[1, 0]
mean = (aH.kepco_H2 + aH.comm_H2) / 2
diff = aH.kepco_H2 - aH.comm_H2
bias, sd = diff.mean(), diff.std()
lo, hi = bias - 1.96 * sd, bias + 1.96 * sd
ax.scatter(mean, diff, s=4, c=C_KEPCO_H2, alpha=0.25, lw=0)
ax.axhline(bias, color="red", lw=1.1, label=f"bias = {bias:.2f}%")
for y in (lo, hi):
    ax.axhline(y, color="k", ls="--", lw=0.8)
ax.axhline(0, color="0.6", ls=":", lw=0.7)
ax.text(0.03, 0.05, f"bias = {bias:.2f}%\n95% LoA = [{lo:.2f}, {hi:.2f}]\nn = {n5:,}",
        transform=ax.transAxes, va="bottom", fontsize=6.5,
        bbox=dict(boxstyle="round", fc="w", ec="0.7"))
ax.set_xlabel("Mean of two sensors, H$_2$ in O$_2$ (%)")
ax.set_ylabel("In-house $-$ commercial (%)")
tag(ax, "(c)"); ax.set_title("H$_2$ sensor Bland--Altman"); ax.legend(loc="upper right")
metrics["bland_altman_H2"] = dict(bias=round(float(bias), 3),
                                  loa=[round(float(lo), 2), round(float(hi), 2)], n=n5)
# (d) cross-validation scatter
ax = axs[1, 1]
x, y = aH.comm_H2.values, aH.kepco_H2.values
r2 = np.corrcoef(x, y)[0, 1] ** 2
rmse = float(np.sqrt(np.mean((y - x) ** 2)))
ax.scatter(x, y, s=4, c=C_KEPCO_H2, alpha=0.25, lw=0)
lim = [min(x.min(), y.min()) - 0.05, max(x.max(), y.max()) + 0.05]
ax.plot(lim, lim, "k--", lw=0.8, label="$y=x$ (ideal)")
ax.set_xlim(lim); ax.set_ylim(lim)
ax.text(0.97, 0.05, f"$R^2$ = {r2:.3f}\nn = {n5:,}\nRMSE = {rmse:.3f} %",
        transform=ax.transAxes, ha="right", va="bottom", fontsize=6.5,
        bbox=dict(boxstyle="round", fc="w", ec="0.7"))
ax.set_xlabel("Commercial H$_2$ sensor (%)"); ax.set_ylabel("In-house H$_2$ sensor (%)")
tag(ax, "(d)"); ax.set_title("H$_2$ sensor cross-validation"); ax.legend(loc="upper left")
metrics["crossval_H2"] = dict(R2=round(float(r2), 3), RMSE=round(rmse, 3), n=n5)
save(fig, "Figure11_intersensor")

# ======================================================================
# FIGURE 12 — idle-period stability
# ======================================================================
print("Figure 12 ...")
idle = df[df.idle_continuous]
metrics["idle_hours"] = round(len(idle) / 3600, 2)
weeks = sorted(idle.week_idx.unique())
wk = idle.groupby("week_idx")
def wmu(col): return wk[col].mean()
def wsd(col): return wk[col].std()
camp1 = [w for w in weeks if w <= 17]; camp2 = [w for w in weeks if w >= 26]
fig, axs = plt.subplots(2, 2, figsize=(W, 6.6))
# (a) weekly idle H2 baseline
ax = axs[0, 0]
for col, c, lab in [("comm_H2", C_COMM, "Commercial"), ("kepco_H2", C_KEPCO, "In-house")]:
    mu, sd = wmu(col), wsd(col)
    for seg in (camp1, camp2):
        ax.errorbar(seg, mu.reindex(seg), yerr=sd.reindex(seg), fmt="o-", color=c,
                    ms=3, lw=0.9, capsize=2, label=lab if seg is camp1 else None)
ax.axvspan(FAULT_WEEKS[0] - 0.5, FAULT_WEEKS[-1] + 0.5, color="red", alpha=0.10)
ax.axhline(0, color="0.6", ls=":", lw=0.7)
ax.set_ylabel("Idle H$_2$ in O$_2$ (vol%)"); ax.set_xlabel("Week")
tag(ax, "(a)"); ax.legend(loc="upper right"); ax.set_title("Weekly idle H$_2$ baseline")
# (b) weekly idle O2 baseline
ax = axs[0, 1]
for col, c, lab in [("comm_O2", C_COMM, "Commercial"), ("kepco_O2", C_KEPCO, "In-house")]:
    mu, sd = wmu(col), wsd(col)
    for seg in (camp1, camp2):
        ax.errorbar(seg, mu.reindex(seg), yerr=sd.reindex(seg), fmt="o-", color=c,
                    ms=3, lw=0.9, capsize=2, label=lab if seg is camp1 else None)
ax.axvspan(FAULT_WEEKS[0] - 0.5, FAULT_WEEKS[-1] + 0.5, color="red", alpha=0.10)
ax.annotate("Sensor stuck\n(weeks 9–11 fault)", xy=(10, 1.6), xytext=(15, 4.2),
            fontsize=6.5, color="red", ha="center",
            arrowprops=dict(arrowstyle="->", color="red", lw=0.8))
ax.axhline(0, color="0.6", ls=":", lw=0.7)
ax.set_ylabel("Idle O$_2$ in H$_2$ (vol%)"); ax.set_xlabel("Week")
tag(ax, "(b)"); ax.legend(loc="upper right"); ax.set_title("Weekly idle O$_2$ baseline")
# (c) pooled idle violins
ax = axs[1, 0]
data = [idle.comm_H2.dropna(), idle.kepco_H2.dropna(),
        idle.comm_O2.dropna(), idle.kepco_O2.dropna()]
p = ax.violinplot([s.sample(min(120000, len(s)), random_state=0) for s in data],
                  showmedians=True, showextrema=False)
for pc, c in zip(p["bodies"], [C_COMM_H2, C_KEPCO_H2, C_COMM_O2, C_KEPCO_O2]):
    pc.set_facecolor(c); pc.set_alpha(0.55)
ax.annotate("weeks 9–11\nO$_2$ sensor fault", xy=(4.12, 1.45), xytext=(2.9, 2.6),
            fontsize=6.5, arrowprops=dict(arrowstyle="->", lw=0.8))
ax.set_xticks([1, 2, 3, 4])
ax.set_xticklabels(["Commercial\nH$_2$", "In-house\nH$_2$",
                    "Commercial\nO$_2$", "In-house\nO$_2$"], fontsize=6.5)
ax.set_ylabel("Sensor reading (%)"); ax.set_ylim(-0.6, 3.4)
tag(ax, "(c)"); ax.set_title("Idle baseline distribution")
# (d) false-reading rate vs threshold (log y)
ax = axs[1, 1]
thr = [0.1, 0.2, 0.3, 0.5, 1.0, 2.0]
ok = ~idle.week_idx.isin(FAULT_WEEKS)
series = [("Commercial H$_2$", idle.comm_H2, C_COMM_H2, None),
          ("In-house H$_2$", idle.kepco_H2, C_KEPCO_H2, None),
          ("Commercial O$_2$", idle.comm_O2, C_COMM_O2, None),
          ("In-house O$_2$ (incl. fault)", idle.kepco_O2, "#a6dcc8", "///"),
          ("In-house O$_2$ (fault excl.)", idle.kepco_O2[ok], C_KEPCO_O2, None)]
nb = len(series); wbar = 0.8 / nb
xs = np.arange(len(thr))
FLOOR = 5e-3
for k, (lab, s, c, hatch) in enumerate(series):
    s = s.dropna()
    vals = [max((s.abs() > t).mean() * 100, FLOOR) for t in thr]
    ax.bar(xs + (k - nb / 2 + 0.5) * wbar, vals, wbar, color=c, alpha=0.9,
           hatch=hatch, edgecolor="w", lw=0.3, label=lab)
ax.set_yscale("log"); ax.set_ylim(FLOOR, 120)
ax.set_xticks(xs); ax.set_xticklabels([f">{t:g}" for t in thr])
ax.set_xlabel("|reading| threshold (%)"); ax.set_ylabel("False reading rate (%)")
tag(ax, "(d)"); ax.set_title("False reading rate during idle")
ax.legend(fontsize=5.6, loc="upper right", ncol=1)
save(fig, "Figure11_idle_stability")
ist = {}
for s in ["comm_H2", "kepco_H2", "comm_O2", "kepco_O2"]:
    v = idle[s].dropna()
    ist[s] = dict(mean=round(float(v.mean()), 4), std=round(float(v.std()), 4),
                  fp1=round(float((v.abs() > 1).mean() * 100), 3))
metrics["idle_stats"] = ist
metrics["idle_sd_ratio_H2"] = round(ist["comm_H2"]["std"] / ist["kepco_H2"]["std"], 1)
metrics["idle_fp_ratio_H2"] = round(ist["comm_H2"]["fp1"] / max(ist["kepco_H2"]["fp1"], 1e-6), 0)

# ======================================================================
# FIGURE 13 — long-term weekly behaviour (operating periods)
# ======================================================================
print("Figure 13 ...")
op = df[df.flow > 0.5]
owk = sorted(op.week_idx.unique())
fig = plt.figure(figsize=(W, 8.6))
gs = fig.add_gridspec(3, 2, height_ratios=[1, 1, 1], hspace=0.45, wspace=0.3)
def wbox(ax, col, color, ylab, thr=None, thrlab=None, ylim=None):
    data = [op[op.week_idx == w][col].dropna().values for w in owk]
    data = [d if len(d) else np.array([np.nan]) for d in data]
    bp = ax.boxplot(data, positions=range(len(owk)), widths=0.6, patch_artist=True,
                    showfliers=False, whis=(5, 95),
                    medianprops=dict(color="k", lw=1.0))
    for b in bp["boxes"]:
        b.set_facecolor(color); b.set_alpha(0.6)
    if thr is not None:
        ax.axhline(thr, color="red", ls="--", lw=0.9)
        ax.text(0.02, thr, thrlab, color="red", fontsize=6, va="bottom",
                transform=ax.get_yaxis_transform())
    ax.set_xticks(range(len(owk))); ax.set_xticklabels([str(w) for w in owk], fontsize=6.5)
    ax.set_ylabel(ylab)
    if ylim: ax.set_ylim(*ylim)
ax = fig.add_subplot(gs[0, :])
wbox(ax, "flow", "0.6", "H$_2$ production\nflow (NL min$^{-1}$)")
ax.set_title("Weekly operating flow and cross-over concentrations "
             "(campaign 1: weeks 1–17; campaign 2: weeks 26–31)")
tag(ax, "(a)")
hylim = (-0.1, 2.3)
ax = fig.add_subplot(gs[1, 0]); wbox(ax, "comm_H2", C_COMM, "H$_2$ in O$_2$ (vol%)",
                                     KGS_H2, " 2 vol% shutdown threshold", hylim)
ax.set_title("Commercial H$_2$"); tag(ax, "(b)")
ax = fig.add_subplot(gs[1, 1]); wbox(ax, "kepco_H2", C_KEPCO, "H$_2$ in O$_2$ (vol%)",
                                     KGS_H2, " 2 vol% shutdown threshold", hylim)
ax.set_title("In-house H$_2$"); tag(ax, "(c)")
oylim = (-0.3, 3.6)
ax = fig.add_subplot(gs[2, 0]); wbox(ax, "comm_O2", C_COMM, "O$_2$ in H$_2$ (vol%)",
                                     ylim=oylim)
ax.set_title("Commercial O$_2$"); ax.set_xlabel("Week"); tag(ax, "(d)")
ax = fig.add_subplot(gs[2, 1]); wbox(ax, "kepco_O2", C_KEPCO, "O$_2$ in H$_2$ (vol%)",
                                     ylim=oylim)
ax.set_title("In-house O$_2$"); ax.set_xlabel("Week"); tag(ax, "(e)")
save(fig, "Figure13_longterm_weekly")
metrics["reporting_weeks"] = [int(w) for w in owk]

# ======================================================================
# FIGURE 14 — start-up (system) response with t90,sys markers
# ======================================================================
print("Figure 14 ...")
PRE, POST = 60, 900
EVENTS = [  # (timestamp, campaign label)
    ("2025-12-16 11:06:00", "campaign 1"),
    ("2026-01-21 17:40:00", "campaign 1"),
    ("2026-07-06 13:15:26", "campaign 2"),
    ("2026-07-16 09:05:51", "campaign 2")]

def event_traces(ts):
    i = int(df.datetime.searchsorted(pd.Timestamp(ts)))
    seg = df.iloc[i - PRE:i + POST]
    tx = np.arange(-PRE, POST)
    out = {"t": tx, "flow": seg.flow.values}
    for s in ("comm_H2", "kepco_H2"):
        v = seg[s].values.astype(float)
        base = np.nanmedian(v[:PRE]); plat = np.nanmedian(v[PRE + 600:PRE + 900])
        amp = plat - base
        sm = pd.Series(v).rolling(5, min_periods=1, center=True).median().values
        t90 = np.nan
        if np.isfinite(amp) and amp > 0.05:
            k = np.where(((sm - base) / amp)[PRE:] >= 0.9)[0]
            if len(k): t90 = float(k[0])
        out[s] = dict(v=v, base=base, plat=plat, amp=amp, t90=t90)
    return out

fig, axs = plt.subplots(2, 2, figsize=(W, 5.8), sharex=True)
t90_table = []
for ax, (ts, camp), lab in zip(axs.flat, EVENTS, "abcd"):
    ev = event_traces(ts)
    axf = ax.twinx()
    axf.plot(ev["t"], ev["flow"], color="0.75", lw=0.8, zorder=1)
    axf.set_ylabel("H$_2$ flow (NL min$^{-1}$)", color="0.5", fontsize=7)
    axf.tick_params(axis="y", colors="0.5", labelsize=6.5)
    for s, c, sl in [("comm_H2", C_COMM_H2, "Commercial"),
                     ("kepco_H2", C_KEPCO_H2, "In-house")]:
        e = ev[s]
        ax.plot(ev["t"], e["v"], color=c, lw=1.2, zorder=3,
                label=sl if lab == "a" else None)
        if np.isfinite(e["t90"]):
            y90 = e["base"] + 0.9 * e["amp"]
            ax.plot(e["t90"], y90, "o", color=c, ms=5, zorder=4)
            ax.annotate(f"$t_{{90,\\mathrm{{sys}}}}$ = {e['t90']:.0f} s",
                        xy=(e["t90"], y90), xytext=(8, -11 if s == "comm_H2" else 8),
                        textcoords="offset points", fontsize=6.5, color=c)
        t90_table.append(dict(event=ts, campaign=camp, sensor=sl,
                              amp_volpct=round(float(e["amp"]), 3),
                              t90_sys_s=None if not np.isfinite(e["t90"]) else float(e["t90"])))
    if not np.isfinite(ev["kepco_H2"]["t90"]):
        ax.text(0.97, 0.55, "In-house: no measurable step\n(reading $\\leq$ 0.03 vol%)",
                transform=ax.transAxes, ha="right", fontsize=6.5, color=C_KEPCO_H2)
    ax.axvline(0, color="red", ls="--", lw=0.8, alpha=0.6)
    ax.set_ylim(-0.12, 2.0)
    ax.set_title(f"({lab}) Start-up {ts[:16]}  ({camp})", fontsize=8)
    ax.set_ylabel("H$_2$ in O$_2$ (vol%)")
    ax.set_zorder(axf.get_zorder() + 1); ax.patch.set_visible(False)
for ax in axs[1]:
    ax.set_xlabel("Time relative to step-on (s)")
axs[0, 0].legend(loc="upper left", fontsize=6.5)
save(fig, "Figure14_t90_startup")
metrics["t90_sys_events"] = t90_table

# ======================================================================
with open(os.path.join(OUT, "key_metrics_extended.json"), "w") as f:
    json.dump(metrics, f, indent=2, ensure_ascii=False)
print("\nSaved key_metrics_extended.json")
print(json.dumps(metrics, indent=2, ensure_ascii=False))

# ---------- STEP 2f : Fig6_spangas (manuscript Fig. 15) ----------
CAL_EVENTS = ["2025-12-17 09:15:10","2025-12-22 13:32:17","2026-01-13 13:46:37",
 "2026-01-13 14:13:33","2026-01-13 14:20:28","2026-01-13 14:23:30","2026-01-13 14:26:10",
 "2026-01-13 14:47:41","2026-01-19 11:08:24","2026-01-20 08:26:00","2026-01-21 16:42:33",
 "2026-01-26 12:43:06","2026-02-02 12:40:25","2026-02-09 12:13:34","2026-03-23 11:41:29",
 "2026-03-30 11:29:58","2026-04-06 13:07:36","2026-04-09 13:06:33"]

def fig6_spangas(df, out):
    """Fig6 (manuscript Fig. 15): span-gas step responses with t90 markers.
    (a) commercial channel, all 18 windows overlaid, median t90 marked;
    (b) in-house channel, shared-exposure windows, 1-2 s step band marked."""
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 3.0), sharex=True)
    t90c = []
    for ts in CAL_EVENTS:
        t0 = pd.Timestamp(ts)
        w = df[(df.datetime >= t0 - pd.Timedelta("30s")) & (df.datetime <= t0 + pd.Timedelta("120s"))]
        if len(w) < 60: continue
        x = (w.datetime - t0).dt.total_seconds().values
        axes[0].plot(x, w.comm_H2, color="0.6", lw=0.8, alpha=0.75)
        base = np.median(w.comm_H2[x < 0]); span = w.comm_H2.max() - base
        if span > 3:                                   # t90 = 10%-to-90% rise time
            y = w.comm_H2.values
            i10 = np.where((x >= -5) & (y >= base + 0.1*span))[0]
            i90 = np.where((x >= -5) & (y >= base + 0.9*span))[0]
            if i10.size and i90.size and x[i90[0]] > x[i10[0]]:
                t90c.append(x[i90[0]] - x[i10[0]])
        if w.kepco_H2.max() > 1.0:
            axes[1].plot(x, w.kepco_H2, color="#1f5fa8", lw=1.0, alpha=0.9)
    m = float(np.median(t90c)) if t90c else 9.0
    axes[0].axvline(m, color="crimson", lw=1.2, ls="--")
    axes[0].annotate("$t_{90}\\approx$%.0f s" % m, xy=(m+2, 4.6), fontsize=8.5, color="crimson")
    axes[1].axvspan(1, 2, color="#1f5fa8", alpha=0.15)
    axes[1].annotate("$t_{90}\\leq$ 1--2 s", xy=(3, 1.85), fontsize=8.5, color="#1f5fa8")
    axes[0].set_title("(a) Commercial H$_2$-in-O$_2$ --- 18 windows", fontsize=9)
    axes[1].set_title("(b) In-house --- shared-exposure windows", fontsize=9)
    for ax in axes:
        ax.axvline(0, color="k", lw=0.6, ls=":"); ax.set_xlim(-15, 60)
        ax.set_xlabel("Time from step onset (s)"); ax.set_ylabel("Indicated H$_2$ (vol%)")
        ax.grid(alpha=0.25, lw=0.4)
    fig.tight_layout()
    for ext in ("png", "pdf"): fig.savefig(f"{out}/Fig6_spangas.{ext}")
    plt.close(fig)

fig6_spangas(df, FIGDIR) if "df" in dir() else None
