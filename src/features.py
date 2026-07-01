"""
特徴量エンジニアリングモジュール (Phase B-1)
路線価予測モデルのための特徴量を生成する。

生成する特徴量:
  - ジオメトリ派生: 矢線の長さ・方向角・重心座標
  - 空間ラグ: k近傍路線価の統計量（mean/std/median）
  - 属性: 地区区分(One-hot)・借地権割合・前年価格
  - 位置: 都市中心からの距離
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.strtree import STRtree
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))
from compute_change import CITY_CENTERS, add_distance_to_city
from rex_io import CHIKUKBN_LABEL


# ── ジオメトリ派生特徴量 ──────────────────────────────────────────────────

def add_geometry_features(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    矢線ジオメトリから派生する特徴量を追加する。

    追加列:
        line_length_m  : 矢線の長さ（メートル、平面直角座標系前提）
        centroid_lon   : 重心の経度（EPSG:4326 換算）
        centroid_lat   : 重心の緯度（EPSG:4326 換算）
        azimuth_deg    : 矢線の方向角（度、0=北、時計回り）
    """
    gdf = gdf.copy()

    # 平面直角座標系で長さを計算
    gdf_proj = gdf.to_crs(epsg=3857)
    gdf["line_length_m"] = gdf_proj.geometry.length.astype(np.float32)

    # 重心座標（元のCRSで）
    centroids = gdf.geometry.centroid
    if gdf.crs and gdf.crs.to_epsg() != 4326:
        centroids_4326 = gdf.set_geometry(centroids).to_crs(epsg=4326).geometry
    else:
        centroids_4326 = centroids

    gdf["centroid_lon"] = centroids_4326.x.astype(np.float32)
    gdf["centroid_lat"] = centroids_4326.y.astype(np.float32)

    # 方向角（始点→終点の角度、北=0度、時計回り）
    def _azimuth(geom):
        coords = list(geom.coords)
        if len(coords) < 2:
            return np.nan
        dx = coords[-1][0] - coords[0][0]
        dy = coords[-1][1] - coords[0][1]
        angle = np.degrees(np.arctan2(dx, dy)) % 360
        return angle

    gdf["azimuth_deg"] = gdf.geometry.apply(_azimuth).astype(np.float32)

    return gdf


# ── 空間ラグ特徴量 ────────────────────────────────────────────────────────

def add_spatial_lag(
    gdf: gpd.GeoDataFrame,
    k: int = 8,
    target_col: str = "kakaku",
    prefix: str | None = None,
) -> gpd.GeoDataFrame:
    """
    k近傍路線の価格統計を特徴量として追加する（空間ラグ）。

    Parameters
    ----------
    gdf : GeoDataFrame
        平面直角座標系（メートル単位）を推奨
    k : int
        近傍数
    target_col : str
        近傍統計を取る列名
    prefix : str | None
        列名のプレフィックス。None のとき f"lag{k}_{target_col}" を使用

    追加列:
        {prefix}_mean   : k近傍の平均
        {prefix}_std    : k近傍の標準偏差
        {prefix}_median : k近傍の中央値
        {prefix}_min    : k近傍の最小値
        {prefix}_max    : k近傍の最大値
    """
    gdf = gdf.copy()
    pfx = prefix or f"lag{k}_{target_col}"

    centroids = np.column_stack([
        gdf.geometry.centroid.x.values,
        gdf.geometry.centroid.y.values,
    ])
    values = gdf[target_col].to_numpy(dtype=float, na_value=np.nan)

    # STRtree で k近傍を高速探索
    tree = STRtree(gdf.geometry.centroid.values)
    indices = tree.query(
        gdf.geometry.centroid.values,
        predicate=None,
    )

    # k+1 近傍（自身を除く）
    from shapely.geometry import MultiPoint
    neighbor_means   = np.empty(len(gdf), dtype=np.float32)
    neighbor_stds    = np.empty(len(gdf), dtype=np.float32)
    neighbor_medians = np.empty(len(gdf), dtype=np.float32)
    neighbor_mins    = np.empty(len(gdf), dtype=np.float32)
    neighbor_maxs    = np.empty(len(gdf), dtype=np.float32)

    centroids_geom = gdf.geometry.centroid.values

    for i in range(len(gdf)):
        # 全点との距離を計算して k 近傍を特定
        dists = np.sqrt(
            (centroids[:, 0] - centroids[i, 0]) ** 2 +
            (centroids[:, 1] - centroids[i, 1]) ** 2
        )
        # 自身を除いた上位k件
        nn_idx = np.argsort(dists)[1: k + 1]
        nn_vals = values[nn_idx]

        neighbor_means[i]   = nn_vals.mean()
        neighbor_stds[i]    = nn_vals.std()
        neighbor_medians[i] = np.median(nn_vals)
        neighbor_mins[i]    = nn_vals.min()
        neighbor_maxs[i]    = nn_vals.max()

    gdf[f"{pfx}_mean"]   = neighbor_means
    gdf[f"{pfx}_std"]    = neighbor_stds
    gdf[f"{pfx}_median"] = neighbor_medians
    gdf[f"{pfx}_min"]    = neighbor_mins
    gdf[f"{pfx}_max"]    = neighbor_maxs

    return gdf


def add_spatial_lag_fast(
    gdf: gpd.GeoDataFrame,
    k: int = 8,
    target_col: str = "kakaku",
) -> gpd.GeoDataFrame:
    """
    大規模データ向けの空間ラグ計算（scipy.cKDTree 使用）。
    230万件の実データ処理時はこちらを使用。

    add_spatial_lag() と同じ列を追加するが、scipy が必要。
    """
    try:
        from scipy.spatial import cKDTree
    except ImportError:
        raise ImportError("scipy が必要です: pip install scipy")

    gdf = gdf.copy()
    pfx = f"lag{k}_{target_col}"

    centroids = np.column_stack([
        gdf.geometry.centroid.x.values,
        gdf.geometry.centroid.y.values,
    ])
    values = gdf[target_col].to_numpy(dtype=float, na_value=np.nan)

    tree = cKDTree(centroids)
    # k+1: 自身を含むため1つ多く取得
    _, nn_indices = tree.query(centroids, k=k + 1)
    nn_indices = nn_indices[:, 1:]  # 自身を除く

    nn_vals = values[nn_indices]  # shape: (n, k)

    gdf[f"{pfx}_mean"]   = nn_vals.mean(axis=1).astype(np.float32)
    gdf[f"{pfx}_std"]    = nn_vals.std(axis=1).astype(np.float32)
    gdf[f"{pfx}_median"] = np.median(nn_vals, axis=1).astype(np.float32)
    gdf[f"{pfx}_min"]    = nn_vals.min(axis=1).astype(np.float32)
    gdf[f"{pfx}_max"]    = nn_vals.max(axis=1).astype(np.float32)

    return gdf


# ── カテゴリ特徴量 ────────────────────────────────────────────────────────

def add_category_features(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    地区区分の One-hot エンコーディングと借地権割合を追加する。

    追加列:
        chiku_{1-7}   : 地区区分のOne-hot
        swari_ratio   : 借地権割合（0.2〜0.9）
        is_commercial : 商業系フラグ（chikukbn in 1,2,3,4）
    """
    gdf = gdf.copy()

    # One-hot
    for code, label in CHIKUKBN_LABEL.items():
        if code == 0:
            continue
        col = f"chiku_{code}"
        gdf[col] = (gdf["chikukbn"] == code).astype(np.int8)

    gdf["is_commercial"] = gdf["chikukbn"].isin([1, 2, 3, 4]).astype(np.int8)

    # 借地権割合（数値）
    if "swari_ratio" not in gdf.columns:
        swari_map = {0: np.nan, 1: 0.9, 2: 0.8, 3: 0.7, 4: 0.6,
                     5: 0.5, 6: 0.4, 7: 0.3, 8: 0.2}
        gdf["swari_ratio"] = gdf["swari"].map(swari_map).astype(np.float32)

    return gdf


# ── 前年価格特徴量 ─────────────────────────────────────────────────────────

def add_historical_features(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    前年・前前年の価格を特徴量として追加する。

    追加列:
        log_pre1_kakak  : log(前年価格+1)
        log_pre2_kakak  : log(前前年価格+1)
        change_y2       : 前年 vs 前前年の変化率（既存列がなければ計算）
    """
    gdf = gdf.copy()
    gdf["log_pre1_kakak"] = np.log1p(gdf["pre1_kakak"]).astype(np.float32)
    gdf["log_pre2_kakak"] = np.log1p(gdf["pre2_kakak"]).astype(np.float32)

    if "change_y2" not in gdf.columns:
        gdf["change_y2"] = (
            (gdf["pre1_kakak"] - gdf["pre2_kakak"])
            / gdf["pre2_kakak"].replace(0, np.nan) * 100
        ).astype(np.float32)

    return gdf


# ── 特徴量マトリクス構築 ──────────────────────────────────────────────────

FEATURE_COLS = [
    # 空間ラグ（最重要）
    "lag8_kakaku_mean", "lag8_kakaku_std", "lag8_kakaku_median",
    "lag8_kakaku_min",  "lag8_kakaku_max",
    # ジオメトリ
    "line_length_m", "azimuth_deg",
    "centroid_lon", "centroid_lat",
    # 属性
    "chiku_1", "chiku_2", "chiku_3", "chiku_4",
    "chiku_5", "chiku_6", "chiku_7",
    "is_commercial", "swari_ratio",
    # 前年情報
    "log_pre1_kakak", "log_pre2_kakak", "change_y2",
]


def build_feature_matrix(
    gdf: gpd.GeoDataFrame,
    use_fast: bool = True,
) -> tuple[pd.DataFrame, pd.Series, pd.Series]:
    """
    全特徴量を生成し (X, y, groups) を返す。

    Parameters
    ----------
    gdf : GeoDataFrame
        load_and_prepare() 済みのデータ
    use_fast : bool
        True のとき scipy の cKDTree を使用（大規模データ推奨）

    Returns
    -------
    X : pd.DataFrame
        特徴量マトリクス
    y : pd.Series
        目的変数 log(kakaku + 1)
    groups : pd.Series
        Spatial CV 用グループ（都道府県コード）
    """
    # 平面直角座標系へ変換（距離計算のため）
    gdf = gdf.to_crs(epsg=3857).copy()

    # 特徴量を順番に追加
    gdf = add_geometry_features(gdf)
    gdf = add_category_features(gdf)
    gdf = add_historical_features(gdf)

    if use_fast:
        gdf = add_spatial_lag_fast(gdf, k=8, target_col="kakaku")
    else:
        gdf = add_spatial_lag(gdf, k=8, target_col="kakaku")

    # 存在する特徴量のみ使用
    feat_cols = [c for c in FEATURE_COLS if c in gdf.columns]
    missing = [c for c in FEATURE_COLS if c not in gdf.columns]
    if missing:
        print(f"[警告] 以下の特徴量が存在しないためスキップ: {missing}")

    X = gdf[feat_cols].astype(np.float32)
    y = np.log1p(gdf["kakaku"]).rename("log_kakaku")
    groups = (gdf["code"] // 1000).fillna(0).astype(int).rename("pref_code")

    return X, y, groups
