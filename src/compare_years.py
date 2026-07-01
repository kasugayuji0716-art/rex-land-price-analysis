"""
5年間パネル比較モジュール（Phase E）
2020年ファイル（2018・2019年価格）と 2022年ファイル（2020〜2022年価格）を
serial_id で結合し、コロナ前後の変化率を比較する。

実データには触れない。生レコードは出力しない。
"""

from __future__ import annotations
from pathlib import Path

import numpy as np
import pandas as pd
import geopandas as gpd

import sys
sys.path.insert(0, str(Path(__file__).parent))
from rex_io import load, CHIKUKBN_LABEL

# 地区区分グループ
COMMERCIAL_CODES  = [1, 2, 3, 4]
RESIDENTIAL_CODES = [5]
INDUSTRIAL_CODES  = [6, 7]

# 分析に使う列（最小限）
LOAD_COLS = [
    "serial_id", "code", "kakaku", "chikukbn", "swari",
    "pre1_kakak", "pre2_kakak", "flgdraw", "geometry"
]


# ── データ読み込み・結合 ──────────────────────────────────────────────────

def build_panel(path_2022: str | Path, path_2020: str | Path) -> gpd.GeoDataFrame:
    """
    2022年・2020年ファイルを読み込み、serial_id で結合して
    2018〜2022年の5年分パネルを返す。

    返却列:
        serial_id, code, chikukbn, geometry（2022年のもの）
        price_2018 〜 price_2022
        chg_18_19  : 2018→2019（コロナ前ベースライン）
        chg_19_20  : 2019→2020（コロナ発生年）
        chg_20_21  : 2020→2021（コロナ禍）
        chg_21_22  : 2021→2022（回復期）
        chg_pre    : 2018→2019（コロナ前）
        chg_covid  : 2019→2022（コロナ禍累計）
        chg_total  : 2018→2022（5年累計）
        district_type : 商業系／住宅系／工業系
    """
    # 2022年ファイル → 2020・2021・2022年価格
    gdf22 = load(Path(path_2022), drop_deleted=True, cols=LOAD_COLS)
    gdf22 = gdf22[gdf22["kakaku"] > 0].copy()
    gdf22 = gdf22.rename(columns={
        "kakaku":     "price_2022",
        "pre1_kakak": "price_2021",
        "pre2_kakak": "price_2020",
    })

    # 2020年ファイル → 2018・2019年価格（kakaku=2020は参照用）
    gdf20 = load(Path(path_2020), drop_deleted=True, cols=LOAD_COLS)
    gdf20 = gdf20[gdf20["kakaku"] > 0].copy()
    gdf20 = gdf20.rename(columns={
        "kakaku":     "price_2020_ref",  # 2022ファイルのpre2_kakakと照合用
        "pre1_kakak": "price_2019",
        "pre2_kakak": "price_2018",
    })

    # serial_id で結合（両方に存在するもの）
    df20 = pd.DataFrame(gdf20[["serial_id", "price_2020_ref", "price_2019", "price_2018"]])
    gdf = gdf22.merge(df20, on="serial_id", how="inner")

    n_all  = len(gdf22)
    n_join = len(gdf)
    print(f"2022年ファイル: {n_all:,}件")
    print(f"結合後（5年分揃った路線）: {n_join:,}件 ({n_join/n_all*100:.1f}%)")

    # ── 変化率計算 ──────────────────────────────────────────────────────
    def _rate(a: pd.Series, b: pd.Series) -> pd.Series:
        return (a - b) / b.replace(0, np.nan) * 100

    gdf["chg_18_19"] = _rate(gdf["price_2019"], gdf["price_2018"])
    gdf["chg_19_20"] = _rate(gdf["price_2020"], gdf["price_2019"])
    gdf["chg_20_21"] = _rate(gdf["price_2021"], gdf["price_2020"])
    gdf["chg_21_22"] = _rate(gdf["price_2022"], gdf["price_2021"])

    gdf["chg_pre"]   = _rate(gdf["price_2019"], gdf["price_2018"])   # コロナ前
    gdf["chg_covid"] = _rate(gdf["price_2022"], gdf["price_2019"])   # コロナ禍累計
    gdf["chg_total"] = _rate(gdf["price_2022"], gdf["price_2018"])   # 5年累計

    # ── 地区グループ ────────────────────────────────────────────────────
    gdf["district_type"] = "その他"
    gdf.loc[gdf["chikukbn"].isin(COMMERCIAL_CODES),  "district_type"] = "商業系"
    gdf.loc[gdf["chikukbn"].isin(RESIDENTIAL_CODES), "district_type"] = "住宅系"
    gdf.loc[gdf["chikukbn"].isin(INDUSTRIAL_CODES),  "district_type"] = "工業系"

    gdf["chikukbn_label"] = gdf["chikukbn"].map(CHIKUKBN_LABEL)
    gdf["pref_code"] = (gdf["code"] // 1000).fillna(0).astype(int)

    return gdf


# ── 集計関数 ──────────────────────────────────────────────────────────────

def yearly_summary(panel: gpd.GeoDataFrame) -> pd.DataFrame:
    """
    年次変化率の全国サマリー（中央値・平均・標準偏差）。

    コロナ前ベースラインとの比較ができる形で返す。
    """
    chg_cols = {
        "2018→2019（コロナ前）": "chg_18_19",
        "2019→2020（コロナ発生）": "chg_19_20",
        "2020→2021（コロナ禍）":  "chg_20_21",
        "2021→2022（回復期）":    "chg_21_22",
        "2019→2022（コロナ禍累計）": "chg_covid",
        "2018→2022（5年累計）":   "chg_total",
    }
    rows = []
    for label, col in chg_cols.items():
        s = panel[col].dropna()
        rows.append({
            "期間": label,
            "件数": len(s),
            "中央値(%)": round(s.median(), 3),
            "平均(%)":   round(s.mean(), 3),
            "標準偏差":  round(s.std(), 3),
            "下落割合(%)": round((s < 0).mean() * 100, 1),
        })
    return pd.DataFrame(rows).set_index("期間")


def by_district_yearly(panel: gpd.GeoDataFrame) -> pd.DataFrame:
    """
    地区区分別 × 年次の変化率中央値テーブル。
    コロナ前後で地区ごとの影響差を比較する。
    """
    chg_cols = ["chg_18_19", "chg_19_20", "chg_20_21", "chg_21_22", "chg_covid"]
    result = (
        panel.groupby("district_type")[chg_cols]
        .median()
        .round(3)
    )
    result.columns = [
        "2018→2019\n（コロナ前）",
        "2019→2020\n（発生年）",
        "2020→2021\n（コロナ禍）",
        "2021→2022\n（回復期）",
        "2019→2022\n（累計）",
    ]
    return result


def by_prefecture_yearly(panel: gpd.GeoDataFrame) -> pd.DataFrame:
    """
    都道府県別 × 年次の変化率平均テーブル。
    """
    chg_cols = ["chg_18_19", "chg_19_20", "chg_20_21", "chg_21_22", "chg_covid"]
    result = (
        panel.groupby("pref_code")[chg_cols]
        .agg(["mean", "count"])
        .round(3)
    )
    return result


def donut_effect_panel(
    panel: gpd.GeoDataFrame,
    city: str = "東京",
    bins: list[float] | None = None,
) -> pd.DataFrame:
    """
    距離帯別 × 年次の変化率中央値テーブル（Donut Effect 検証）。
    コロナ前ベースライン（chg_18_19）との差分も出す。
    """
    if bins is None:
        bins = [0, 5, 10, 20, 30, 50, 100, 300]

    # 距離列を追加
    sys.path.insert(0, str(Path(__file__).parent))
    from compute_change import add_distance_to_city
    panel = add_distance_to_city(panel, city)

    dist_col = f"dist_{city}_km"
    labels   = [f"{bins[i]}-{bins[i+1]}km" for i in range(len(bins) - 1)]
    panel    = panel.copy()
    panel["dist_band"] = pd.cut(panel[dist_col], bins=bins, labels=labels, right=False)

    chg_cols = ["chg_18_19", "chg_19_20", "chg_20_21", "chg_21_22", "chg_covid"]
    result = (
        panel.groupby("dist_band", observed=True)[chg_cols]
        .agg(count=("chg_18_19", "count"),
             pre_median=("chg_18_19", "median"),
             p1920_median=("chg_19_20", "median"),
             p2021_median=("chg_20_21", "median"),
             p2122_median=("chg_21_22", "median"),
             covid_median=("chg_covid", "median"))
        .round(3)
    )
    # コロナ禍累計とコロナ前の差分
    result["donut_diff"] = (result["covid_median"] - result["pre_median"]).round(3)
    return result
