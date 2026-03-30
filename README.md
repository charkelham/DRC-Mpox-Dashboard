# 🇨🇩 DRC Mpox Humanitarian Dashboard

A self-contained, data-driven dashboard tracking the intersection of the **Mpox outbreak**, **armed conflict**, and **humanitarian funding gaps** in the Democratic Republic of Congo.

Built in Python, rendered as a single HTML file with interactive Chart.js visualisations — no server required.

## Overview

The DRC faces one of the world's most severe humanitarian crises. This dashboard brings together four authoritative datasets to visualise the converging pressures:

| Dimension | Source | File |
|-----------|--------|------|
| **Mpox outbreak** | WHO / Our World in Data | `drc_mpox.csv` |
| **Armed conflict** | ACLED (Armed Conflict Location & Event Data) | `drc_acled.xlsx` |
| **Humanitarian funding** | OCHA Financial Tracking Service | `drc_fts.csv` |
| **Crisis severity** | INFORM Severity Index (Feb 2026) | `inform_severity.xlsx` |

## Dashboard Features

- **KPI cards** — Cumulative cases, deaths, case fatality rate, conflict events, funding coverage, and INFORM severity score
- **Mpox weekly trend** — Bar chart of weekly new cases with WHO smoothed average overlay
- **Funding gap analysis** — Horizontal bar breakdown by humanitarian cluster (Food Security, Health, WASH, etc.) with % funded
- **Conflict timeline** — Monthly armed events and fatalities from 2019–2026
- **INFORM severity panel** — Score, category, and contextual summary statistics
- **Narrative callouts** — Contextual analysis linking conflict displacement to disease transmission

## Tech Stack

| Component | Technology |
|-----------|------------|
| Data processing | Python 3, pandas, openpyxl |
| Visualisation | Chart.js 4.4 (CDN) |
| Output | Single self-contained HTML file |
| Styling | Custom CSS (dark theme, responsive grid layout) |

## How to Run

```bash
# Install dependencies
pip install pandas openpyxl

# Build the dashboard
python build_dashboard.py

# Open the output in any browser
open drc_mpox_dashboard.html
```

The script reads the four raw data files, processes and aggregates them, serialises the results to JSON, and generates `drc_mpox_dashboard.html` — a fully self-contained file you can open directly in a browser.

## Project Structure

```
���── build_dashboard.py          # Main build script — data processing + HTML generation
├── drc_mpox_dashboard.html     # Generated dashboard (open in browser)
├── drc_mpox.csv                # WHO mpox case/death data
├── drc_acled.xlsx              # ACLED monthly conflict events & fatalities
├── drc_fts.csv                 # OCHA FTS humanitarian funding by cluster
├── inform_severity.xlsx        # INFORM Severity Index scores
└── README.md
```

## Data Processing Highlights

- **Mpox data**: Filtered to DRC, aggregated from daily to weekly, cumulative totals extracted for KPIs
- **Conflict data**: Month names mapped to dates, grouped to monthly totals from 2019 onward
- **Funding data**: French/English cluster name variants consolidated (e.g. *Sécurité alimentaire* → *Food Security*), cross-border refugee response excluded, % funded calculated per sector
- **INFORM data**: DRC row extracted from multi-crisis spreadsheet, severity score and category parsed

## Sources & Attribution

- [WHO Mpox Situation Data](https://ourworldindata.org/mpox) — Our World in Data
- [ACLED](https://acleddata.com/) — Armed Conflict Location & Event Data Project
- [OCHA Financial Tracking Service](https://fts.unocha.org/) — UN Office for the Coordination of Humanitarian Affairs
- [INFORM Severity Index](https://drmkc.jrc.ec.europa.eu/inform-index/INFORM-Severity) — INFORM / JRC