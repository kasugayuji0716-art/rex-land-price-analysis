# AGENTS.md — REX Land Price Analysis Project

This file provides guidance for AI coding agents (OpenAI Codex, GitHub Copilot Workspace, etc.) working on this repository.

---

## Critical Constraints — Read First

**The actual REX dataset is NOT in this repository.** It is a licensed dataset (NII IDR) and must not be read, displayed, or sent to any external service.

- Real data lives outside the repo at `/path/to/REX_data/` (user-configured path)
- **Never open, cat, or read real `.shp` files**
- **Never print raw records** (`gdf.head()`, row dumps, feature exports are prohibited)
- Only aggregated statistics (counts, means, medians, distributions) may be output
- All development and testing uses `data_synthetic/` only
- Real data execution is the **user's responsibility** — agents write scripts, users run them

---

## Repository Structure

```
data_analysis/
├── CLAUDE.md              # Project instructions (authoritative)
├── AGENTS.md              # This file
├── README.md
├── requirements.txt
├── data_synthetic/        # Synthetic data for dev/test (safe to read)
├── src/
│   ├── rex_io.py          # Data loading & preprocessing
│   ├── make_synthetic.py  # Synthetic data generator
│   ├── compute_change.py  # Change rate computation, Donut Effect
│   ├── spatial_autocorr.py# Global/Local Moran's I
│   ├── compare_years.py   # 5-year panel builder (2018-2022)
│   ├── features.py        # Feature engineering for ML
│   ├── train.py           # LightGBM training + SHAP
│   └── residual_check.py  # Residual diagnostics
├── notebooks/
│   ├── A1_descriptive.ipynb   # Phase A: descriptive stats + autocorr
│   ├── B1_model.ipynb         # Phase B: price prediction model
│   ├── F1_slide_figures.ipynb # Road type classification maps
│   ├── G1_covid_shock_model.ipynb # COVID resilience model
│   └── D1_visualization.ipynb # Phase D: interactive maps
└── outputs/               # Generated figures, CSVs, PPTX (git-tracked)
    ├── make_pbl.js        # Node.js script to generate PPTX slides
    ├── PBL発表_v2.pptx    # Output presentation
    ├── corona_map_road_*.png  # 4-period road classification maps
    └── shap_covid_shock.png   # SHAP beeswarm plot
```

---

## Data Schema

### Input files: `nouhin_line_YYYY.shp`

| Column | Type | Description |
|--------|------|-------------|
| `serial_id` | bigint | Primary key = code(5) + linkcode(7) |
| `kakaku` | int | Current year price (thousand yen/m²) |
| `pre1_kakak` | int | Previous year price |
| `pre2_kakak` | int | Two years prior price |
| `chikukbn` | int | District type (1-7) |
| `swari` | int | Leasehold ratio code (1-8) |
| `flgdraw` | bool | True = deleted road segment |
| `code` | int | Municipal code (5 digits) |
| `geometry` | LineString | Road segment, EPSG:4326 |

Each file contains **3 years of prices** (current + 2 prior years). No cross-file join needed for 3-year analysis.

### `build_panel()` output (compare_years.py)

Joins 2022 file + 2020 file on `serial_id` to produce 5-year panel:

| Column | Source |
|--------|--------|
| `price_2022` | 2022 file: `kakaku` |
| `price_2021` | 2022 file: `pre1_kakak` |
| `price_2020` | 2022 file: `pre2_kakak` |
| `price_2019` | 2020 file: `pre1_kakak` |
| `price_2018` | 2020 file: `pre2_kakak` |
| `chg_18_19` | (price_2019 - price_2018) / price_2018 * 100 |
| `chg_19_20` | (price_2020 - price_2019) / price_2019 * 100 |
| `chg_20_21` | (price_2021 - price_2020) / price_2020 * 100 |
| `chg_21_22` | (price_2022 - price_2021) / price_2021 * 100 |
| `chg_covid` | (price_2022 - price_2019) / price_2019 * 100 |
| `district_type` | 商業系 / 住宅系 / 工業系 / その他 |

**Common mistake**: After `build_panel()`, the column is `price_2022`, NOT `kakaku`. Always check column names after calling this function.

---

## Analysis Phases

### Phase A: Spatial Analysis (`A1_descriptive.ipynb`)
- Descriptive stats by district type and prefecture
- Global Moran's I: confirms spatial clustering of land prices
- Local Moran's I (LISA): identifies hot/cold spot clusters
- Donut Effect: change rate by distance band from city centers

### Phase B: Price Prediction (`B1_model.ipynb`)
- Target: `log(kakaku + 1)`
- Features: spatial lag (k=8 neighbors), geometry, prior prices, district type
- Model: LightGBM + Spatial CV (GroupKFold by prefecture, 5-fold)
- Results: R²=0.9985, MAE≈3.4 thousand yen/m²
- SHAP: prior price (#1) > neighbor mean price (#2) > prior-prior price (#3)

### Phase F: Road Type Classification (`F1_slide_figures.ipynb`)
5-type classification using `classify_road()`:

```python
def classify_road(row):
    pre, covid, rec = row["chg_18_19"], row["chg_20_21"], row["chg_21_22"]
    if pd.isna(pre) or pd.isna(covid) or pd.isna(rec): return "不明"
    if pre < 0: return "構造的下落"
    if pre > 0 and covid > 0 and rec > 0: return "構造的上昇"
    if covid < 0: return "回復型" if rec > 0 else "コロナ型下落"
    return "安定"
```

Types: 構造的上昇 / 安定 / 回復型 / コロナ型下落 / 構造的下落

### Phase G: COVID Resilience Model (`G1_covid_shock_model.ipynb`)
- Target: `chg_20_21` (COVID-year change rate)
- Purpose: identify conditions for COVID resilience using SHAP
- Features: pre-COVID trend, spatial lag of prices, district type, distance to major cities
- Expected R²≈0.18 (change rate prediction is inherently noisy)
- Output: `shap_covid_shock.png` (beeswarm), `shap_importance_bar.png`

---

## Development Workflow

1. **Always develop against `data_synthetic/`** — never real data
2. Scripts accept data paths as arguments; notebooks have a `DATA_PATH` variable at the top
3. Run tests: `python src/make_synthetic.py` to regenerate synthetic data
4. Notebook outputs are cleared before commit (nbstripout)
5. Generated figures go to `outputs/` and are git-tracked

### Running with real data (user's responsibility)
```python
# In notebooks, change:
DATA_PATH = "data_synthetic/synthetic_2022.shp"
# to:
DATA_PATH = "/path/to/REX_data/2022/nouhin_line_2022.shp"
```

---

## Presentation Generation

`outputs/make_pbl.js` generates `PBL発表_v2.pptx` using pptxgenjs:

```bash
cd outputs
node make_pbl.js
```

Slide images must exist in `outputs/` before running. The script references:
- `corona_map_road_01.png` through `corona_map_road_04.png` (F1 notebook output)
- `shap_covid_shock.png` (G1 notebook output)

---

## Key Dependencies

```
geopandas >= 0.14    # Spatial data handling
pyogrio              # Fast shapefile I/O (required for large files)
lightgbm             # Gradient boosting model
shap                 # SHAP feature importance
scipy                # cKDTree for spatial lag computation
contextily           # Basemap tiles for static maps
folium               # Interactive maps
pydeck               # WebGL maps for 2.3M records
```

Install: `pip install -r requirements.txt`

For PPTX generation: `npm install -g pptxgenjs` (or use local install in `outputs/`)
