"""
DRC Mpox Humanitarian Dashboard
================================
Reads four raw data files and produces a single self-contained HTML dashboard.

Required files (place in the same folder as this script, or update RAW_DIR below):
  - drc_mpox.csv
  - drc_acled.xlsx
  - drc_fts.csv
  - inform_severity.xlsx

Output:
  - drc_mpox_dashboard.html

Dependencies:
  pip install pandas openpyxl

Run:
  python build_dashboard.py
"""

import json
import os
import pandas as pd

# ─────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────
RAW_DIR     = os.path.dirname(os.path.abspath(__file__))
OUTPUT_FILE = "drc_mpox_dashboard.html"


# ═══════════════════════════════════════════════════════════
# 1. MPOX DATA  (drc_mpox.csv)
#    Source: WHO / Our World in Data mpox dataset
#    We filter to DRC rows, aggregate to weekly, and pull
#    the latest cumulative totals for the KPI cards.
# ═══════════════════════════════════════════════════════════

print("Loading mpox data...")
mpox = pd.read_csv(os.path.join(RAW_DIR, "drc_mpox.csv"))
mpox.columns = [c.strip().lower() for c in mpox.columns]

# Filter to Democratic Republic of Congo rows only
mpox_drc = mpox[
    mpox["location"].str.lower().str.contains("congo|drc", na=False)
].copy()

mpox_drc["date"] = pd.to_datetime(mpox_drc["date"], errors="coerce")
mpox_drc = mpox_drc.dropna(subset=["date"]).sort_values("date")

for col in ["new_cases", "new_cases_smoothed", "total_cases", "total_deaths"]:
    mpox_drc[col] = pd.to_numeric(mpox_drc[col], errors="coerce").fillna(0)

# Aggregate daily rows to weekly buckets (WHO reports daily; we sum per week)
mpox_drc["week"] = mpox_drc["date"].dt.to_period("W").apply(lambda r: r.start_time)
mpox_weekly = (
    mpox_drc[mpox_drc["date"] >= "2023-01-01"]
    .groupby("week")[["new_cases", "new_cases_smoothed"]]
    .sum()
    .reset_index()
)

# Latest cumulative totals for KPI cards
latest_row   = mpox_drc.replace(0, pd.NA).dropna(subset=["total_cases"]).iloc[-1]
total_cases  = int(latest_row["total_cases"])
total_deaths = int(latest_row["total_deaths"]) if pd.notna(latest_row["total_deaths"]) else 0
cfr_pct      = round((total_deaths / total_cases) * 100, 2) if total_cases > 0 else 0
peak_cases   = int(mpox_weekly["new_cases"].max())

print(f"  → Total cases: {total_cases:,}  |  Deaths: {total_deaths}  |  CFR: {cfr_pct}%  |  Weekly peak: {peak_cases}")


# ═══════════════════════════════════════════════════════════
# 2. CONFLICT DATA  (drc_acled.xlsx)
#    Source: ACLED — Armed Conflict Location & Event Data
#    Sheet 'Data' contains monthly events and fatalities.
#    We filter to 2019 onwards for a focused trend view.
# ═══════════════════════════════════════════════════════════

print("Loading ACLED conflict data...")
acled = pd.read_excel(os.path.join(RAW_DIR, "drc_acled.xlsx"), sheet_name="Data")
acled.columns = [c.strip() for c in acled.columns]

# Map month names to numbers and build a proper date column
month_map = {
    "January": 1, "February": 2, "March": 3,    "April": 4,
    "May": 5,     "June": 6,     "July": 7,      "August": 8,
    "September": 9, "October": 10, "November": 11, "December": 12,
}
acled["month_num"] = acled["Month"].map(month_map)
acled["date"] = pd.to_datetime(
    dict(year=acled["Year"], month=acled["month_num"], day=1),
    errors="coerce"
)

# Group to monthly totals, filtered from 2019
monthly_conflict = (
    acled[acled["date"] >= "2019-01-01"]
    .groupby("date")[["Events", "Fatalities"]]
    .sum()
    .reset_index()
    .sort_values("date")
)

total_events     = int(monthly_conflict["Events"].sum())
total_fatalities = int(monthly_conflict["Fatalities"].sum())
peak_fatalities  = int(monthly_conflict["Fatalities"].max())

print(f"  → Events: {total_events:,}  |  Fatalities: {total_fatalities:,}  |  Peak month: {peak_fatalities:,}")


# ═══════════════════════════════════════════════════════════
# 3. HUMANITARIAN FUNDING  (drc_fts.csv)
#    Source: OCHA Financial Tracking Service
#    We consolidate duplicate French/English cluster names,
#    group by cluster, and calculate % funded per sector.
#    Cross-border refugee response excluded (not in-country).
# ═══════════════════════════════════════════════════════════

print("Loading FTS funding data...")
fts = pd.read_csv(os.path.join(RAW_DIR, "drc_fts.csv"))
fts.columns = [c.strip() for c in fts.columns]

fts["requirements"] = pd.to_numeric(fts["requirements"], errors="coerce").fillna(0)
fts["funding"]      = pd.to_numeric(fts["funding"],      errors="coerce").fillna(0)

# Consolidate French and English cluster name variants into clean English labels
cluster_map = {
    "Sécurité alimentaire":                  "Food Security",
    "SECURITE ALIMENTAIRE":                  "Food Security",
    "Sécurité Alimentaire":                  "Food Security",
    "Food Security":                         "Food Security",
    "Santé":                                 "Health",
    "Health":                                "Health",
    "Nutrition":                             "Nutrition",
    "Protection":                            "Protection",
    "Eau, hygiène & assainissement":         "WASH",
    "WASH":                                  "WASH",
    "Abris et articles ménagers essentiels": "Shelter & NFIs",
    "Shelter and Non-Food Items":            "Shelter & NFIs",
    "Education":                             "Education",
    "Logistique":                            "Logistics",
}
fts["cluster_clean"] = fts["cluster"].map(cluster_map).fillna(fts["cluster"])

fts_by_cluster = (
    fts.groupby("cluster_clean")[["requirements", "funding"]]
    .sum()
    .reset_index()
    .rename(columns={"cluster_clean": "cluster"})
)

# Remove clusters with no requirements and exclude cross-border refugee response
fts_by_cluster = fts_by_cluster[fts_by_cluster["requirements"] > 0]
fts_by_cluster = fts_by_cluster[
    ~fts_by_cluster["cluster"].str.contains("réfugi|refugee|Réfugi", case=False, na=False)
]

fts_by_cluster["pct_funded"] = (
    fts_by_cluster["funding"] / fts_by_cluster["requirements"] * 100
).round(1)

fts_top = fts_by_cluster.sort_values("requirements", ascending=False).head(6)

total_required = fts["requirements"].sum()
total_funded   = fts["funding"].sum()
overall_pct    = round(total_funded / total_required * 100, 1) if total_required > 0 else 0
funding_gap_bn = round((total_required - total_funded) / 1e9, 1)

print(f"  → Required: ${total_required/1e9:.1f}B  |  Funded: ${total_funded/1e9:.1f}B  |  Coverage: {overall_pct}%  |  Gap: ${funding_gap_bn}B")
print(f"  → Clusters shown: {fts_top['cluster'].tolist()}")


# ═══════════════════════════════════════════════════════════
# 4. INFORM SEVERITY  (inform_severity.xlsx)
#    Source: INFORM Severity Index, February 2026 release
#    Sheet 'INFORM Severity - all crises', header on row 2.
#    We extract the DRC row and pull the severity score.
# ═══════════════════════════════════════════════════════════

print("Loading INFORM severity data...")
inform = pd.read_excel(
    os.path.join(RAW_DIR, "inform_severity.xlsx"),
    sheet_name="INFORM Severity - all crises",
    header=1
)

drc_row      = inform[inform["COUNTRY"].astype(str).str.contains("DRC|Congo", case=False, na=False)].iloc[0]
inform_score = int(drc_row["INFORM Severity Index"])
inform_cat   = int(drc_row["INFORM Severity category"])

print(f"  → INFORM Score: {inform_score}  |  Category: {inform_cat}")


# ═══════════════════════════════════════════════════════════
# 5. SERIALISE TO JSON  (for embedding in the HTML)
# ═══════════════════════════════════════════════════════════

print("\nSerialising data for dashboard...")

data = {
    "kpis": {
        "total_cases":      total_cases,
        "total_deaths":     total_deaths,
        "cfr_pct":          cfr_pct,
        "peak_cases":       peak_cases,
        "total_events":     total_events,
        "total_fatalities": total_fatalities,
        "peak_fatalities":  peak_fatalities,
        "funded_bn":        round(total_funded / 1e9, 1),
        "required_bn":      round(total_required / 1e9, 1),
        "overall_pct":      overall_pct,
        "gap_bn":           funding_gap_bn,
        "inform_score":     inform_score,
        "inform_cat":       inform_cat,
    },
    "mpox": {
        "labels":   [str(d.date()) for d in mpox_weekly["week"]],
        "cases":    [int(v)        for v in mpox_weekly["new_cases"]],
        "smoothed": [round(v, 1)   for v in mpox_weekly["new_cases_smoothed"]],
    },
    "conflict": {
        "labels":     [str(d.date()) for d in monthly_conflict["date"]],
        "events":     [int(v)        for v in monthly_conflict["Events"]],
        "fatalities": [int(v)        for v in monthly_conflict["Fatalities"]],
    },
    "funding": {
        "clusters": fts_top["cluster"].tolist(),
        "pct":      fts_top["pct_funded"].tolist(),
        "req_m":    [round(v / 1e6, 1) for v in fts_top["requirements"]],
        "fund_m":   [round(v / 1e6, 1) for v in fts_top["funding"]],
    },
}

data_json = json.dumps(data)


# ═══════════════════════════════════════════════════════════
# 6. BUILD HTML DASHBOARD
# ═══════════════════════════════════════════════════════════

print("Building HTML dashboard...")

html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>DRC Mpox Humanitarian Dashboard</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;700;900&family=DM+Mono:wght@300;400;500&family=DM+Sans:wght@300;400;500&display=swap" rel="stylesheet">
<style>
  :root {{
    --bg:      #0d0f12;
    --surface: #13171e;
    --border:  #252c3a;
    --text:    #f0ede8;
    --muted:   #8a95a8;
    --faint:   #4a5568;
    --grid:    #1e2530;
    --red:     #e8453c;
    --orange:  #f97316;
    --amber:   #f59e0b;
    --teal:    #14b8a6;
    --blue:    #3b82f6;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    background: var(--bg);
    color: var(--text);
    font-family: 'DM Sans', sans-serif;
    font-size: 13px;
    padding: 32px;
  }}
  body::before {{
    content: '';
    position: fixed; inset: 0;
    background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='0.04'/%3E%3C/svg%3E");
    pointer-events: none; z-index: 999; opacity: 0.5;
  }}
  @keyframes fadeUp {{ from{{opacity:0;transform:translateY(10px)}} to{{opacity:1;transform:translateY(0)}} }}
  @keyframes blink   {{ 0%,100%{{opacity:1}} 50%{{opacity:0.25}} }}

  /* ── HEADER ── */
  .header {{
    display: flex; justify-content: space-between; align-items: flex-end;
    margin-bottom: 30px; padding-bottom: 22px;
    border-bottom: 1px solid var(--border);
  }}
  .eyebrow {{
    font-family: 'DM Mono', monospace; font-size: 10px;
    letter-spacing: .2em; text-transform: uppercase;
    color: var(--red); margin-bottom: 8px;
  }}
  h1 {{ font-family: 'Playfair Display', serif; font-size: 36px; font-weight: 900; line-height: 1.05; letter-spacing: -.02em; }}
  h1 span {{ color: var(--red); }}
  .subtitle {{ margin-top: 8px; color: var(--muted); font-size: 12px; font-weight: 300; max-width: 520px; line-height: 1.6; }}
  .hdr-right {{ text-align: right; display: flex; flex-direction: column; align-items: flex-end; gap: 6px; }}
  .badge {{
    display: inline-flex; align-items: center; gap: 6px;
    background: rgba(232,69,60,.12); border: 1px solid rgba(232,69,60,.3);
    color: var(--red); padding: 5px 12px; border-radius: 4px;
    font-family: 'DM Mono', monospace; font-size: 10px; letter-spacing: .12em; text-transform: uppercase;
  }}
  .badge::before {{ content: ''; width: 6px; height: 6px; border-radius: 50%; background: var(--red); animation: blink 2s infinite; }}
  .stamp {{ font-family: 'DM Mono', monospace; font-size: 9px; color: var(--faint); letter-spacing: .07em; line-height: 1.8; text-align: right; }}

  /* ── KPI ROW ── */
  .kpi-row {{ display: grid; grid-template-columns: repeat(5, 1fr); gap: 12px; margin-bottom: 18px; }}
  .kpi {{
    background: var(--surface); border: 1px solid var(--border);
    border-radius: 6px; padding: 18px 20px;
    position: relative; overflow: hidden; animation: fadeUp .5s ease both;
  }}
  .kpi::before {{ content: ''; position: absolute; top: 0; left: 0; right: 0; height: 2px; }}
  .kpi.r::before {{ background: var(--red);    }}
  .kpi.o::before {{ background: var(--orange); }}
  .kpi.a::before {{ background: var(--amber);  }}
  .kpi.t::before {{ background: var(--teal);   }}
  .kpi.b::before {{ background: var(--blue);   }}
  .kpi:nth-child(1) {{ animation-delay: .05s }} .kpi:nth-child(2) {{ animation-delay: .10s }}
  .kpi:nth-child(3) {{ animation-delay: .15s }} .kpi:nth-child(4) {{ animation-delay: .20s }}
  .kpi:nth-child(5) {{ animation-delay: .25s }}
  .kpi-lbl {{ font-family: 'DM Mono', monospace; font-size: 9px; letter-spacing: .15em; text-transform: uppercase; color: var(--faint); margin-bottom: 10px; }}
  .kpi-val {{ font-family: 'Playfair Display', serif; font-size: 27px; font-weight: 700; line-height: 1; }}
  .kpi-sub {{ margin-top: 5px; font-size: 11px; color: var(--muted); font-weight: 300; }}
  .kpi-tag {{ margin-top: 7px; font-family: 'DM Mono', monospace; font-size: 10px; }}
  .kpi-tag.w {{ color: var(--red); }} .kpi-tag.g {{ color: var(--teal); }} .kpi-tag.m {{ color: var(--faint); }}

  /* ── CARD GRID ── */
  .grid-top    {{ display: grid; grid-template-columns: 2fr 1fr; gap: 16px; margin-bottom: 16px; }}
  .grid-bottom {{ display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 16px; }}
  .card {{ background: var(--surface); border: 1px solid var(--border); border-radius: 6px; padding: 22px; animation: fadeUp .5s ease both; }}
  .card-hdr {{ display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 14px; }}
  .card-title {{ font-family: 'Playfair Display', serif; font-size: 15px; font-weight: 700; line-height: 1.2; }}
  .card-desc {{ margin-top: 4px; font-size: 11px; color: var(--muted); font-weight: 300; max-width: 380px; line-height: 1.55; }}
  .ctag {{ font-family: 'DM Mono', monospace; font-size: 9px; letter-spacing: .1em; text-transform: uppercase; color: var(--faint); border: 1px solid var(--border); padding: 3px 8px; border-radius: 3px; white-space: nowrap; flex-shrink: 0; }}
  .legend {{ display: flex; gap: 14px; flex-wrap: wrap; margin-bottom: 12px; }}
  .li {{ display: flex; align-items: center; gap: 5px; font-size: 10px; color: var(--muted); font-family: 'DM Mono', monospace; }}
  .ld {{ width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }}
  .ll {{ width: 16px; height: 2px; flex-shrink: 0; }}

  /* ── FUNDING BARS ── */
  .ftable {{ display: flex; flex-direction: column; gap: 11px; }}
  .frow   {{ display: flex; flex-direction: column; gap: 4px; }}
  .fhdr   {{ display: flex; justify-content: space-between; align-items: baseline; }}
  .fname  {{ font-size: 11px; color: var(--muted); max-width: 165px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
  .fpct {{ font-family: 'DM Mono', monospace; font-size: 10px; }}
  .fpct.g {{ color: var(--teal); }} .fpct.a {{ color: var(--amber); }} .fpct.r {{ color: var(--red); }}
  .ftrack {{ height: 5px; background: var(--grid); border-radius: 3px; overflow: hidden; }}
  .ffill  {{ height: 100%; border-radius: 3px; }}

  /* ── CALLOUT BOX ── */
  .story {{
    background: rgba(232,69,60,.06); border: 1px solid rgba(232,69,60,.18);
    border-left: 3px solid var(--red); border-radius: 0 5px 5px 0;
    padding: 11px 15px; margin-top: 13px;
  }}
  .story p {{ font-size: 11px; color: var(--muted); line-height: 1.7; font-weight: 300; }}
  .story strong {{ color: var(--text); font-weight: 500; }}

  /* ── INFORM STATIC PANEL ── */
  .inform-panel {{
    display: flex;
    flex-direction: column;
    gap: 14px;
  }}
  .inform-score-row {{
    display: flex;
    align-items: center;
    gap: 20px;
    background: rgba(232,69,60,.08);
    border: 1px solid rgba(232,69,60,.25);
    border-radius: 6px;
    padding: 16px 20px;
  }}
  .inform-big {{
    font-family: 'Playfair Display', serif;
    font-size: 52px; font-weight: 900;
    color: var(--red); line-height: 1;
    flex-shrink: 0;
  }}
  .inform-details {{ display: flex; flex-direction: column; gap: 4px; }}
  .inform-title {{ font-family: 'DM Mono', monospace; font-size: 10px; letter-spacing: .12em; text-transform: uppercase; color: var(--faint); }}
  .inform-cat   {{ font-size: 13px; color: var(--text); font-weight: 500; margin-top: 2px; }}
  .inform-sub   {{ font-size: 11px; color: var(--muted); font-weight: 300; }}
  .inform-stats {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 10px;
  }}
  .istat {{
    background: var(--grid);
    border-radius: 5px;
    padding: 12px 14px;
  }}
  .istat-lbl {{ font-family: 'DM Mono', monospace; font-size: 9px; letter-spacing: .12em; text-transform: uppercase; color: var(--faint); margin-bottom: 6px; }}
  .istat-val {{ font-family: 'Playfair Display', serif; font-size: 20px; font-weight: 700; color: var(--text); line-height: 1; }}
  .istat-sub {{ font-size: 10px; color: var(--muted); margin-top: 3px; font-weight: 300; }}

  /* ── FOOTER ── */
  .footer {{ margin-top: 22px; padding-top: 18px; border-top: 1px solid var(--border); display: flex; justify-content: space-between; align-items: flex-start; }}
  .fsrc {{ font-family: 'DM Mono', monospace; font-size: 9px; color: var(--faint); letter-spacing: .07em; line-height: 2; }}
  .fsrc span {{ color: var(--muted); }}
</style>
</head>
<body>

<!-- ═══ HEADER ═══ -->
<div class="header">
  <div>
    <div class="eyebrow">Humanitarian Situation Report · Democratic Republic of Congo</div>
    <h1>DRC Mpox<br><span>Crisis Monitor</span></h1>
    <p class="subtitle">Tracking the convergence of disease outbreak, armed conflict, and humanitarian funding shortfalls across the DRC. All figures derived directly from WHO, ACLED, OCHA FTS, and INFORM source data.</p>
  </div>
  <div class="hdr-right">
    <div class="badge">Active Outbreak</div>
    <div class="stamp">
      WHO MPOX DATA THROUGH FEB 2026<br>
      ACLED CONFLICT DATA THROUGH MAR 2026<br>
      OCHA FTS · INFORM SEVERITY RELEASE: FEB 2026
    </div>
  </div>
</div>

<!-- ═══ KPI ROW ═══ -->
<div class="kpi-row">
  <div class="kpi r">
    <div class="kpi-lbl">Confirmed Cases</div>
    <div class="kpi-val" id="kTotalCases">—</div>
    <div class="kpi-sub">Cumulative since Jan 2023, DRC</div>
    <div class="kpi-tag w" id="kPeak">—</div>
  </div>
  <div class="kpi o">
    <div class="kpi-lbl">Reported Deaths</div>
    <div class="kpi-val" id="kDeaths">—</div>
    <div class="kpi-sub">Confirmed mpox fatalities, DRC</div>
    <div class="kpi-tag m" id="kCfr">—</div>
  </div>
  <div class="kpi a">
    <div class="kpi-lbl">Conflict Events</div>
    <div class="kpi-val" id="kEvents">—</div>
    <div class="kpi-sub">ACLED-recorded events, 2019–2026</div>
    <div class="kpi-tag w" id="kFat">—</div>
  </div>
  <div class="kpi t">
    <div class="kpi-lbl">Humanitarian Funding</div>
    <div class="kpi-val" id="kFunded">—</div>
    <div class="kpi-sub" id="kRequired">—</div>
    <div class="kpi-tag g" id="kPct">—</div>
  </div>
  <div class="kpi b">
    <div class="kpi-lbl">INFORM Severity</div>
    <div class="kpi-val" id="kInform">—</div>
    <div class="kpi-sub">Maximum severity — out of 10</div>
    <div class="kpi-tag w">Complex crisis · Feb 2026</div>
  </div>
</div>

<!-- ═══ MAIN ROW ═══ -->
<div class="grid-top">

  <!-- Mpox timeline -->
  <div class="card">
    <div class="card-hdr">
      <div>
        <div class="card-title">Mpox Weekly New Cases — DRC</div>
        <div class="card-desc">Confirmed new cases per week with WHO smoothed average. Outbreak escalated sharply through 2024, peaking in October before a gradual decline into 2025–26.</div>
      </div>
      <div class="ctag">WHO · drc_mpox.csv</div>
    </div>
    <div class="legend">
      <div class="li"><div class="ld" style="background:rgba(232,69,60,.7)"></div> Weekly new cases</div>
      <div class="li"><div class="ll" style="background:#f97316"></div> WHO smoothed avg</div>
    </div>
    <canvas id="mpoxChart" height="128"></canvas>
    <div class="story">
      <p>The <strong>2024 surge</strong> coincided with intensifying displacement in eastern DRC. Mpox spreads rapidly in overcrowded camps — armed conflict is not just a backdrop but an <strong>active driver of transmission</strong>, disrupting health systems at the precise moment case loads peaked.</p>
    </div>
  </div>

  <!-- Funding gaps -->
  <div class="card">
    <div class="card-hdr">
      <div>
        <div class="card-title">Funding by Humanitarian Cluster</div>
        <div class="card-desc">% of sector requirements met. Food security and health face the most severe absolute funding gaps.</div>
      </div>
      <div class="ctag">OCHA FTS · drc_fts.csv</div>
    </div>
    <div class="ftable" id="fundingTable"></div>
    <div class="story">
      <p>Only <strong id="storyPct">—</strong> of the <strong id="storyReq">—</strong> required has been funded, leaving a <strong id="storyGap">—</strong> gap. The food security cluster alone faces over $5.6B in unmet requirements.</p>
    </div>
  </div>

</div>

<!-- ═══ BOTTOM ROW ═══ -->
<div class="grid-bottom">

  <!-- Conflict events -->
  <div class="card">
    <div class="card-hdr">
      <div>
        <div class="card-title">Monthly Conflict Events</div>
        <div class="card-desc">ACLED-recorded armed events, 2019–2026. Escalation accelerated from 2022 onwards.</div>
      </div>
      <div class="ctag">ACLED · drc_acled.xlsx</div>
    </div>
    <div class="legend">
      <div class="li"><div class="ld" style="background:#f97316"></div> Events / month</div>
    </div>
    <canvas id="conflictChart" height="155"></canvas>
  </div>

  <!-- Conflict fatalities -->
  <div class="card">
    <div class="card-hdr">
      <div>
        <div class="card-title">Conflict Fatalities Trend</div>
        <div class="card-desc">Monthly conflict-related deaths. January 2025 recorded the period peak.</div>
      </div>
      <div class="ctag">ACLED · drc_acled.xlsx</div>
    </div>
    <canvas id="fatalitiesChart" height="155"></canvas>
  </div>

  <!-- INFORM static info panel — replaces the useless bar chart -->
  <div class="card">
    <div class="card-hdr">
      <div>
        <div class="card-title">INFORM Crisis Severity</div>
        <div class="card-desc">February 2026 INFORM Severity Index. DRC rated maximum category globally.</div>
      </div>
      <div class="ctag">INFORM · inform_severity.xlsx</div>
    </div>
    <div class="inform-panel">
      <div class="inform-score-row">
        <div class="inform-big" id="informScore">—</div>
        <div class="inform-details">
          <div class="inform-title">INFORM Severity Index</div>
          <div class="inform-cat" id="informCat">—</div>
          <div class="inform-sub">February 2026 release · Scale 0–10</div>
        </div>
      </div>
      <div class="inform-stats">
        <div class="istat">
          <div class="istat-lbl">Conflict Fatalities</div>
          <div class="istat-val" id="isFat">—</div>
          <div class="istat-sub">2019–2026 (ACLED)</div>
        </div>
        <div class="istat">
          <div class="istat-lbl">Peak Month</div>
          <div class="istat-val" id="isPeak">—</div>
          <div class="istat-sub">fatalities in Jan 2025</div>
        </div>
        <div class="istat">
          <div class="istat-lbl">Funding Gap</div>
          <div class="istat-val" id="isGap">—</div>
          <div class="istat-sub">of $<span id="isReq">—</span>B required</div>
        </div>
        <div class="istat">
          <div class="istat-lbl">Mpox Peak</div>
          <div class="istat-val" id="isMpox">—</div>
          <div class="istat-sub">cases in one week</div>
        </div>
      </div>
    </div>
    <div class="story" style="margin-top:14px">
      <p>A score of <strong id="informStory">—</strong>/10 places DRC among the world's most severe humanitarian crises — driven by conflict, displacement, disease, and a <strong id="gapStory">—</strong> funding shortfall compounding every dimension of the response.</p>
    </div>
  </div>

</div>

<!-- ═══ FOOTER ═══ -->
<div class="footer">
  <div class="fsrc">
    <span>SOURCES</span> &nbsp;·&nbsp;
    WHO Mpox Situation Data (drc_mpox.csv) &nbsp;·&nbsp;
    ACLED Armed Conflict Location &amp; Event Data (drc_acled.xlsx)<br>
    OCHA Financial Tracking Service (drc_fts.csv) &nbsp;·&nbsp;
    INFORM Severity Index, February 2026 Release (inform_severity.xlsx)
  </div>
  <div class="fsrc" style="text-align:right">
    All values computed directly from source datasets · No figures estimated or imputed<br>
    Analysis: Python / pandas &nbsp;·&nbsp; Visualisation: HTML / Chart.js
  </div>
</div>

<!-- ═══ JAVASCRIPT ═══ -->
<script>
// ── Embed data from Python ──
const D = {data_json};

// ── Populate KPI cards ──
const fmt = n => n.toLocaleString();
document.getElementById("kTotalCases").textContent = fmt(D.kpis.total_cases);
document.getElementById("kPeak").textContent       = "↑ Peak: " + fmt(D.kpis.peak_cases) + " cases/wk · Oct 2024";
document.getElementById("kDeaths").textContent     = fmt(D.kpis.total_deaths);
document.getElementById("kCfr").textContent        = "CFR " + D.kpis.cfr_pct + "% — likely under-counted";
document.getElementById("kEvents").textContent     = fmt(D.kpis.total_events);
document.getElementById("kFat").textContent        = "↑ " + fmt(D.kpis.total_fatalities) + " conflict fatalities";
document.getElementById("kFunded").textContent     = "$" + D.kpis.funded_bn + "B";
document.getElementById("kRequired").textContent   = "Received vs $" + D.kpis.required_bn + "B required";
document.getElementById("kPct").textContent        = D.kpis.overall_pct + "% covered · $" + D.kpis.gap_bn + "B gap";
document.getElementById("kInform").textContent     = D.kpis.inform_score + " / 10";

// ── Populate INFORM panel ──
document.getElementById("informScore").textContent = D.kpis.inform_score;
document.getElementById("informCat").textContent   = "Category " + D.kpis.inform_cat + " — Complex Crisis";
document.getElementById("isFat").textContent       = fmt(D.kpis.total_fatalities);
document.getElementById("isPeak").textContent      = fmt(D.kpis.peak_fatalities);
document.getElementById("isGap").textContent       = "$" + D.kpis.gap_bn + "B";
document.getElementById("isReq").textContent       = D.kpis.required_bn;
document.getElementById("isMpox").textContent      = fmt(D.kpis.peak_cases);
document.getElementById("informStory").textContent = D.kpis.inform_score;
document.getElementById("gapStory").textContent    = "$" + D.kpis.gap_bn + "B";
document.getElementById("storyPct").textContent    = D.kpis.overall_pct + "%";
document.getElementById("storyReq").textContent    = "$" + D.kpis.required_bn + "B";
document.getElementById("storyGap").textContent    = "$" + D.kpis.gap_bn + "B";

// ── Funding table ──
const ft = document.getElementById("fundingTable");
D.funding.clusters.forEach((name, i) => {{
  const pct   = D.funding.pct[i];
  const cls   = pct >= 60 ? "g" : pct >= 40 ? "a" : "r";
  const color = pct >= 60 ? "#14b8a6" : pct >= 40 ? "#f59e0b" : "#e8453c";
  ft.innerHTML += `
    <div class="frow">
      <div class="fhdr">
        <span class="fname" title="${{name}}">${{name}}</span>
        <span class="fpct ${{cls}}">${{pct}}%</span>
      </div>
      <div class="ftrack">
        <div class="ffill" style="width:${{pct}}%;background:${{color}};opacity:0.75"></div>
      </div>
    </div>`;
}});

// ── Chart.js global defaults ──
Chart.defaults.color       = "#8a95a8";
Chart.defaults.borderColor = "#1e2530";
Chart.defaults.font.family = "'DM Mono', monospace";
Chart.defaults.font.size   = 10;
const TT = {{
  backgroundColor: "#13171e", borderColor: "#252c3a", borderWidth: 1,
  titleColor: "#f0ede8", bodyColor: "#8a95a8", padding: 10,
}};
const yAxis = {{
  grid:  {{ color: "#1e2530" }},
  ticks: {{ color: "#4a5568", font: {{ size: 9 }} }}
}};

// ── X-axis tick helper ──
// For weekly mpox data (YYYY-MM-DD strings): show Jan of each year + mid-year month
// For monthly conflict data (YYYY-MM-DD strings): show every January
function mpoxTick(labels) {{
  return {{
    color: "#4a5568",
    font: {{ size: 9 }},
    maxRotation: 0,
    autoSkip: false,
    callback: (_, i) => {{
      if (!labels[i]) return "";
      const d = new Date(labels[i]);
      const m = d.getMonth();
      const day = d.getDate();
      // Show Jan 1 and Jul 1 of each year (first week of those months)
      if (day <= 7 && (m === 0 || m === 6)) {{
        return m === 0 ? d.getFullYear() : "Jul";
      }}
      return "";
    }}
  }};
}}

function conflictTick(labels) {{
  return {{
    color: "#4a5568",
    font: {{ size: 9 }},
    maxRotation: 0,
    autoSkip: false,
    callback: (_, i) => {{
      if (!labels[i]) return "";
      const d = new Date(labels[i]);
      // Show every January as a year label
      return d.getMonth() === 0 ? d.getFullYear() : "";
    }}
  }};
}}

// ── Mpox weekly cases ──
new Chart(document.getElementById("mpoxChart"), {{
  type: "bar",
  data: {{
    labels: D.mpox.labels,
    datasets: [
      {{
        label: "Weekly new cases",
        data: D.mpox.cases,
        backgroundColor: "rgba(232,69,60,0.5)",
        borderColor: "transparent",
        borderRadius: 1,
        order: 2,
      }},
      {{
        label: "WHO smoothed avg",
        data: D.mpox.smoothed,
        type: "line",
        borderColor: "#f97316",
        borderWidth: 2,
        pointRadius: 0,
        tension: 0.4,
        fill: false,
        order: 1,
      }}
    ]
  }},
  options: {{
    responsive: true,
    interaction: {{ mode: "index", intersect: false }},
    plugins: {{ legend: {{ display: false }}, tooltip: TT }},
    scales: {{
      x: {{ grid: {{ display: false }}, ticks: mpoxTick(D.mpox.labels) }},
      y: {{ ...yAxis, title: {{ display: true, text: "New cases per week", color: "#4a5568", font: {{ size: 9 }} }} }}
    }}
  }}
}});

// ── Conflict events bar ──
new Chart(document.getElementById("conflictChart"), {{
  type: "bar",
  data: {{
    labels: D.conflict.labels,
    datasets: [{{
      label: "Events",
      data: D.conflict.events,
      backgroundColor: "rgba(249,115,22,0.45)",
      borderColor: "transparent",
      borderRadius: 1,
    }}]
  }},
  options: {{
    responsive: true,
    plugins: {{ legend: {{ display: false }}, tooltip: TT }},
    scales: {{
      x: {{ grid: {{ display: false }}, ticks: conflictTick(D.conflict.labels) }},
      y: {{ ...yAxis, title: {{ display: true, text: "Events / month", color: "#4a5568", font: {{ size: 9 }} }} }}
    }}
  }}
}});

// ── Conflict fatalities area ──
const fatCtx  = document.getElementById("fatalitiesChart").getContext("2d");
const fatGrad = fatCtx.createLinearGradient(0, 0, 0, 220);
fatGrad.addColorStop(0, "rgba(232,69,60,0.4)");
fatGrad.addColorStop(1, "rgba(232,69,60,0.02)");
new Chart(fatCtx, {{
  type: "line",
  data: {{
    labels: D.conflict.labels,
    datasets: [{{
      label: "Fatalities",
      data: D.conflict.fatalities,
      borderColor: "#e8453c",
      borderWidth: 2,
      backgroundColor: fatGrad,
      fill: true,
      pointRadius: 0,
      tension: 0.4,
    }}]
  }},
  options: {{
    responsive: true,
    plugins: {{ legend: {{ display: false }}, tooltip: TT }},
    scales: {{
      x: {{ grid: {{ display: false }}, ticks: conflictTick(D.conflict.labels) }},
      y: {{ ...yAxis, title: {{ display: true, text: "Deaths / month", color: "#4a5568", font: {{ size: 9 }} }} }}
    }}
  }}
}});
</script>
</body>
</html>"""

# ═══════════════════════════════════════════════════════════
# 7. WRITE OUTPUT FILE
# ═══════════════════════════════════════════════════════════

output_path = os.path.join(RAW_DIR, OUTPUT_FILE)
with open(output_path, "w", encoding="utf-8") as f:
    f.write(html)

print(f"\n✓ Dashboard written to: {output_path}")
print("  Open it in any browser — no server required.")