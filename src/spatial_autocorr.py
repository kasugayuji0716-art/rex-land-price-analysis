"""
空間的自己相関モジュール (Phase A-3)
Global / Local Moran's I を計算し、LISAクラスターラベルを付与する。

依存: libpysal, esda
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import geopandas as gpd

try:
    from libpysal.weights import KNN, DistanceBand
    from esda.moran import Moran, Moran_Local
    HAS_PYSAL = True
except ImportError:
    HAS_PYSAL = False


# ── LISA クラスターラベル ────────────────────────────────────────────────
LISA_LABELS = {
    1: "HH",   # High-High: 高値に囲まれた高値（ホットスポット）
    2: "LH",   # Low-High:  低値だが高値に囲まれている
    3: "LL",   # Low-Low:   低値に囲まれた低値（コールドスポット）
    4: "HL",   # High-Low:  高値だが低値に囲まれている
    0: "NS",   # Not Significant
}


def _require_pysal():
    if not HAS_PYSAL:
        raise ImportError(
            "libpysal と esda が必要です。\n"
            "  pip install libpysal esda"
        )


def build_weights(
    gdf: gpd.GeoDataFrame,
    method: str = "knn",
    k: int = 8,
    distance: float | None = None,
) -> "libpysal.weights.W":
    """
    空間重み行列を構築する。

    Parameters
    ----------
    gdf : GeoDataFrame
        ジオメトリは平面直角座標系（メートル単位）を推奨
    method : str
        "knn"（k近傍）または "distance"（距離閾値）
    k : int
        knn のとき使う近傍数
    distance : float | None
        distance のとき使う閾値（メートル）

    Returns
    -------
    libpysal.weights.W
        行標準化済みの空間重み行列
    """
    _require_pysal()

    centroids = gdf.copy()
    centroids["geometry"] = gdf.geometry.centroid

    if method == "knn":
        w = KNN.from_dataframe(centroids, k=k)
    elif method == "distance":
        if distance is None:
            raise ValueError("distance メソッドのとき distance 引数が必要です")
        w = DistanceBand.from_dataframe(centroids, threshold=distance, binary=True)
    else:
        raise ValueError(f"未対応の method: {method}（'knn' または 'distance'）")

    w.transform = "R"   # 行標準化
    return w


def global_moran(
    gdf: gpd.GeoDataFrame,
    col: str = "change_y1",
    w=None,
    n_permutations: int = 999,
) -> dict:
    """
    Global Moran's I を計算する。

    Parameters
    ----------
    gdf : GeoDataFrame
    col : str
        対象列名
    w : libpysal.weights.W | None
        None のとき k=8 KNN で自動構築
    n_permutations : int
        モンテカルロ検定の試行回数

    Returns
    -------
    dict
        I（Moran's I値）, EI（期待値）, p_sim（p値）, z_sim（z値）
    """
    _require_pysal()

    if gdf[col].isna().any():
        gdf = gdf[gdf[col].notna()].copy()

    y = gdf[col].values

    if w is None:
        w = build_weights(gdf)

    mi = Moran(y, w, permutations=n_permutations)
    return {
        "column":  col,
        "I":       round(mi.I, 6),
        "EI":      round(mi.EI, 6),
        "z_sim":   round(mi.z_sim, 4),
        "p_sim":   round(mi.p_sim, 4),
        "significant": mi.p_sim < 0.05,
    }


def local_moran(
    gdf: gpd.GeoDataFrame,
    col: str = "change_y1",
    w=None,
    alpha: float = 0.05,
    n_permutations: int = 999,
) -> gpd.GeoDataFrame:
    """
    Local Moran's I（LISA）を計算し、クラスターラベル列を追加して返す。

    追加列:
        lisa_Is_{col}    : 局所 Moran's I 値
        lisa_p_{col}     : 擬似p値
        lisa_q_{col}     : 象限（1=HH, 2=LH, 3=LL, 4=HL）
        lisa_label_{col} : HH/LH/LL/HL/NS のラベル

    Parameters
    ----------
    gdf : GeoDataFrame
    col : str
        対象列名
    w : libpysal.weights.W | None
    alpha : float
        有意水準（デフォルト 0.05）
    n_permutations : int

    Returns
    -------
    GeoDataFrame
        LISA 結果列を追加したもの
    """
    _require_pysal()

    valid_mask = gdf[col].notna()
    gdf_valid = gdf[valid_mask].copy()

    if w is None:
        w = build_weights(gdf_valid)

    y = gdf_valid[col].values
    lm = Moran_Local(y, w, permutations=n_permutations)

    gdf_valid[f"lisa_Is_{col}"]  = lm.Is
    gdf_valid[f"lisa_p_{col}"]   = lm.p_sim
    gdf_valid[f"lisa_q_{col}"]   = lm.q

    # 有意でない箇所は 0 (NS) にする
    sig = lm.p_sim < alpha
    q_sig = np.where(sig, lm.q, 0)
    gdf_valid[f"lisa_label_{col}"] = pd.array(q_sig).map(LISA_LABELS)

    # 元の gdf に結合（NaN 行は NS）
    result = gdf.copy()
    for c in [f"lisa_Is_{col}", f"lisa_p_{col}", f"lisa_q_{col}", f"lisa_label_{col}"]:
        result[c] = np.nan
        result.loc[valid_mask, c] = gdf_valid[c].values

    result.loc[~valid_mask, f"lisa_label_{col}"] = "NS"
    return result


def moran_sensitivity(
    gdf: gpd.GeoDataFrame,
    col: str = "change_y1",
    k_values: list[int] | None = None,
) -> pd.DataFrame:
    """
    k近傍数を変えて Global Moran's I の感度分析を行う。

    Parameters
    ----------
    k_values : list[int]
        試す k のリスト。デフォルト: [4, 6, 8, 12, 16]

    Returns
    -------
    pd.DataFrame
        k × (I, p_sim, significant)
    """
    _require_pysal()

    if k_values is None:
        k_values = [4, 6, 8, 12, 16]

    # NaN行を先に除外してから重み行列を構築（サイズ不整合を防ぐ）
    gdf = gdf[gdf[col].notna()].copy()

    rows = []
    for k in k_values:
        w = build_weights(gdf, method="knn", k=k)
        res = global_moran(gdf, col=col, w=w)
        res["k"] = k
        rows.append(res)

    return pd.DataFrame(rows).set_index("k")[["I", "p_sim", "significant"]]


def lisa_summary(gdf: gpd.GeoDataFrame, col: str = "change_y1") -> pd.DataFrame:
    """LISA クラスターラベルの件数・割合を返す。"""
    label_col = f"lisa_label_{col}"
    if label_col not in gdf.columns:
        raise ValueError(f"列 '{label_col}' がありません。先に local_moran() を実行してください。")

    counts = gdf[label_col].value_counts().rename("件数")
    pct = (counts / len(gdf) * 100).round(1).rename("割合(%)")
    return pd.concat([counts, pct], axis=1)
