"""
変化率集計モジュール (Phase A-1, A-2)
路線価の年次変化率を計算し、地区区分・都道府県・距離帯などで集計する。

実データには触れない。パスは引数で渡す。生レコードは出力しない。
"""

from __future__ import annotations
from pathlib import Path

import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point

import sys
sys.path.insert(0, str(Path(__file__).parent))
from rex_io import load_and_prepare, CHIKUKBN_LABEL


# ── 都市中心点（Donut Effect 分析用）────────────────────────────────────────
CITY_CENTERS = {
    "東京":  Point(139.7671, 35.6812),   # 東京駅
    "大阪":  Point(135.4959, 34.7024),   # 大阪駅
    "名古屋": Point(136.8817, 35.1710),  # 名古屋駅
    "札幌":  Point(141.3503, 43.0686),
    "福岡":  Point(130.4199, 33.5902),
    "仙台":  Point(140.8719, 38.2682),
    "広島":  Point(132.4596, 34.3966),
}

# ── 地区区分グループ ──────────────────────────────────────────────────────
COMMERCIAL_CODES = [1, 2, 3, 4]   # 商業系
RESIDENTIAL_CODES = [5]            # 住宅系
INDUSTRIAL_CODES = [6, 7]          # 工業系


def by_chikukbn(gdf: gpd.GeoDataFrame) -> pd.DataFrame:
    """
    地区区分別の変化率統計を返す。

    Returns
    -------
    pd.DataFrame
        index=地区区分名, columns=件数/平均/中央値/std（変化率 y1, y2, 2y）
    """
    gdf = gdf.copy()
    gdf["chikukbn_label"] = gdf["chikukbn"].map(CHIKUKBN_LABEL)

    result = (
        gdf.groupby("chikukbn_label")[["change_y1", "change_y2", "change_2y"]]
        .agg(["count", "mean", "median", "std"])
        .round(2)
    )
    return result


def by_prefecture(gdf: gpd.GeoDataFrame) -> pd.DataFrame:
    """
    都道府県（codeの上2桁）別の変化率統計を返す。

    Returns
    -------
    pd.DataFrame
        index=都道府県コード(2桁), columns=件数/平均変化率
    """
    gdf = gdf.copy()
    gdf["pref_code"] = (gdf["code"] // 1000).fillna(0).astype(int)

    result = (
        gdf.groupby("pref_code")[["change_y1", "change_y2", "change_2y", "kakaku"]]
        .agg(count=("kakaku", "count"),
             kakaku_median=("kakaku", "median"),
             change_y1_mean=("change_y1", "mean"),
             change_y1_median=("change_y1", "median"),
             change_2y_mean=("change_2y", "mean"))
        .round(2)
    )
    return result


def by_district_type(gdf: gpd.GeoDataFrame) -> pd.DataFrame:
    """
    商業系 / 住宅系 / 工業系 の3グループ別に変化率を集計する。
    """
    gdf = gdf.copy()
    gdf["district_type"] = "その他"
    gdf.loc[gdf["chikukbn"].isin(COMMERCIAL_CODES),  "district_type"] = "商業系"
    gdf.loc[gdf["chikukbn"].isin(RESIDENTIAL_CODES), "district_type"] = "住宅系"
    gdf.loc[gdf["chikukbn"].isin(INDUSTRIAL_CODES),  "district_type"] = "工業系"

    result = (
        gdf.groupby("district_type")[["change_y1", "change_y2", "change_2y"]]
        .agg(["count", "mean", "median", "std"])
        .round(2)
    )
    return result


def add_distance_to_city(
    gdf: gpd.GeoDataFrame,
    city: str = "東京",
) -> gpd.GeoDataFrame:
    """
    指定した都市中心からの距離（km）を列として追加する。

    Parameters
    ----------
    gdf : GeoDataFrame
        CRS は EPSG:4326 または平面直角座標系
    city : str
        CITY_CENTERS のキー

    Returns
    -------
    GeoDataFrame
        distance_km 列を追加したもの
    """
    if city not in CITY_CENTERS:
        raise ValueError(f"未定義の都市: {city}。定義済み: {list(CITY_CENTERS.keys())}")

    center = CITY_CENTERS[city]
    center_gdf = gpd.GeoDataFrame(geometry=[center], crs="EPSG:4326")

    # CRS未設定の場合は EPSG:4326 を仮定
    if gdf.crs is None:
        gdf = gdf.set_crs(epsg=4326)

    # 距離計算のため等距離投影（EPSG:3857）へ一時変換
    gdf_proj = gdf.to_crs(epsg=3857)
    center_proj = center_gdf.to_crs(epsg=3857).geometry[0]

    centroids = gdf_proj.geometry.centroid
    gdf = gdf.copy()
    gdf[f"dist_{city}_km"] = centroids.distance(center_proj) / 1000
    return gdf


def donut_effect_table(
    gdf: gpd.GeoDataFrame,
    city: str = "東京",
    bins: list[float] | None = None,
) -> pd.DataFrame:
    """
    都市中心からの距離帯別に変化率を集計する（Donut Effect 検証）。

    Parameters
    ----------
    gdf : GeoDataFrame
    city : str
        対象都市
    bins : list[float]
        距離帯の境界（km）。デフォルト: [0, 5, 10, 20, 30, 50, 100]

    Returns
    -------
    pd.DataFrame
        距離帯 × 変化率統計
    """
    if bins is None:
        bins = [0, 5, 10, 20, 30, 50, 100]

    dist_col = f"dist_{city}_km"
    if dist_col not in gdf.columns:
        gdf = add_distance_to_city(gdf, city)

    labels = [f"{bins[i]}-{bins[i+1]}km" for i in range(len(bins) - 1)]
    gdf = gdf.copy()
    gdf["distance_band"] = pd.cut(
        gdf[dist_col], bins=bins, labels=labels, right=False
    )

    result = (
        gdf.groupby("distance_band", observed=True)[["change_y1", "change_y2", "change_2y"]]
        .agg(count=("change_y1", "count"),
             change_y1_mean=("change_y1", "mean"),
             change_y1_median=("change_y1", "median"),
             change_2y_mean=("change_2y", "mean"),
             change_2y_median=("change_2y", "median"))
        .round(2)
    )
    return result


def price_distribution(gdf: gpd.GeoDataFrame) -> pd.DataFrame:
    """路線価（kakaku）の分布統計を返す（log変換後も含む）。"""
    s = gdf["kakaku"]
    return pd.DataFrame({
        "count":   [s.count()],
        "min":     [s.min()],
        "p25":     [s.quantile(0.25)],
        "median":  [s.median()],
        "p75":     [s.quantile(0.75)],
        "max":     [s.max()],
        "mean":    [s.mean().round(1)],
        "std":     [s.std().round(1)],
        "log_mean": [np.log1p(s).mean().round(4)],
        "log_std":  [np.log1p(s).std().round(4)],
    })
